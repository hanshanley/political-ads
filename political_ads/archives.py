from __future__ import annotations

import hashlib
import io
import struct
import time
import zipfile
import zlib
from datetime import datetime
from pathlib import PurePosixPath

from political_ads.http import Client


def archive_member(client: Client, review: dict) -> bytes:
    size, tail_size = review["archive_bytes"], review["tail_bytes"]
    if not 22 <= tail_size <= min(size, 65557):
        raise ValueError("Reviewed archive requires a bounded ZIP directory tail")

    def get(start: int, end: int) -> bytes:
        if not 0 <= start <= end < size:
            raise ValueError("Archive member range is outside the reviewed original")
        if not client.offline:
            delay = review.get("crawl_delay_seconds", 0)
            time.sleep(
                max(0, delay - (time.monotonic() - getattr(client, "_archive_request_at", 0)))
            )
        body, headers = client.get(review["url"], retry=False, byte_range=(start, end))
        client._archive_request_at = time.monotonic()
        headers = {key.lower(): value for key, value in headers.items()}
        if (
            headers.get("content-range") != f"bytes {start}-{end}/{size}"
            or headers.get("etag") != review["etag"]
            or headers.get("last-modified") != review["last_modified"]
            or len(body) != end - start + 1
        ):
            raise ValueError("Archive range does not retain the reviewed version and coordinates")
        return body

    tail_start = size - tail_size
    tail = get(tail_start, size - 1)
    if hashlib.sha256(tail).hexdigest() != review["directory_sha256"]:
        raise ValueError("Archive directory differs from the individually reviewed inventory")
    name = review["member"]
    if name.startswith("/") or "\\" in name or ".." in PurePosixPath(name).parts:
        raise ValueError("Archive requires an exact safe reviewed member name")
    try:
        with zipfile.ZipFile(io.BytesIO(tail)) as directory:
            matches = [entry for entry in directory.infolist() if entry.filename == name]
            if len(matches) != 1:
                raise ValueError("Archive requires exactly one reviewed member")
            member = matches[0]
    except zipfile.BadZipFile as error:
        raise ValueError("Reviewed archive tail has no complete ZIP directory") from error
    if (
        member.is_dir()
        or member.flag_bits & 1
        or member.compress_type != zipfile.ZIP_DEFLATED
        or member.header_offset + tail_start != review["local_header_offset"]
        or member.compress_size != review["compressed_bytes"]
        or member.file_size != review["uncompressed_bytes"]
        or member.CRC != review["crc32"]
        or datetime(*member.date_time).isoformat() != review["member_modified"]
        or not 0 < member.file_size <= 32 * 1024 * 1024
        or not 0 < member.compress_size <= 32 * 1024 * 1024
    ):
        raise ValueError("Archive member metadata differs from the reviewed creative")
    start = review["local_header_offset"]
    header = get(start, start + 29)
    signature, _, flags, compression, _, _, _, _, _, name_size, extra_size = struct.unpack(
        "<4s5H3I2H", header
    )
    if (
        signature != b"PK\x03\x04"
        or flags != member.flag_bits
        or compression != member.compress_type
    ):
        raise ValueError("Archive local header does not match its directory")
    content = get(start + 30, start + 29 + name_size + extra_size + member.compress_size)
    if content[:name_size].decode("utf-8" if flags & 0x800 else "cp437") != name:
        raise ValueError("Archive local header names a different member")
    compressed = content[name_size + extra_size :]
    decoder = zlib.decompressobj(-15)
    try:
        original = decoder.decompress(compressed, member.file_size + 1)
    except zlib.error as error:
        raise ValueError("Archive creative has invalid compressed bytes") from error
    if (
        len(original) != member.file_size
        or not decoder.eof
        or decoder.unused_data
        or decoder.unconsumed_tail
        or zlib.crc32(original) != member.CRC
    ):
        raise ValueError("Archive creative failed bounded size or CRC verification")
    return original
