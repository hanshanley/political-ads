import hashlib
import io
import struct
import zipfile
from contextlib import contextmanager

import pytest

from political_ads.http import Client


@pytest.mark.parametrize("failure", [None, "status", "range", "oversize"])
def test_http_range_is_bounded_and_cannot_replace_full_response(tmp_path, monkeypatch, failure):
    requests = []
    reads = []

    class Response:
        status = 200 if failure == "status" else 206
        headers = {"Content-Range": "bytes 10-12/100", "Content-Length": "3"}

        def read(self, size=-1):
            reads.append(size)
            return b"abcd" if failure == "oversize" else b"abc"

    if failure == "range":
        Response.headers = {"Content-Range": "bytes 11-13/100"}

    @contextmanager
    def open_response(request, **kwargs):
        requests.append(request)
        yield Response()

    monkeypatch.setattr("political_ads.http.urlopen", open_response)
    client = Client(tmp_path)
    if failure:
        with pytest.raises(ValueError):
            client.get("https://campaign.example/kit.zip", byte_range=(10, 12))
        assert not list(tmp_path.glob("*.body"))
        if failure == "status":
            assert reads == []
    else:
        body, headers = client.get("https://campaign.example/kit.zip", byte_range=(10, 12))
        assert body == b"abc" and reads == [4]
        assert requests[0].get_header("Range") == "bytes=10-12"
        assert Client(tmp_path, offline=True).get(
            "https://campaign.example/kit.zip", byte_range=(10, 12)
        ) == (body, headers)
        with pytest.raises(FileNotFoundError):
            Client(tmp_path, offline=True).get("https://campaign.example/kit.zip")


@pytest.mark.parametrize("byte_range", [(-1, 2), (3, 2), (0, 64 * 1024 * 1024), (True, 2)])
def test_http_range_rejects_invalid_or_excessive_requests(tmp_path, byte_range):
    with pytest.raises(ValueError):
        Client(tmp_path, offline=True).get(
            "https://campaign.example/kit.zip", byte_range=byte_range
        )


@pytest.fixture
def archive():
    member = "Press Kit/General Mail/Ad.pdf"
    content = b"Actual original creative bytes"
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w", zipfile.ZIP_DEFLATED) as z:
        info = zipfile.ZipInfo(member, (2026, 10, 7, 12, 0, 0))
        info.compress_type = zipfile.ZIP_DEFLATED
        z.writestr(info, content)
        z.writestr("Press Kit/B-roll/not-an-ad.mp4", b"Ordinary footage")
    body = stream.getvalue()
    with zipfile.ZipFile(io.BytesIO(body)) as z:
        info = z.getinfo(member)
    descriptor = {
        "url": "https://campaign.example/kit.zip",
        "archive_bytes": len(body),
        "etag": '"reviewed-original"',
        "last_modified": "Mon, 12 Oct 2026 18:21:26 GMT",
        "tail_bytes": len(body),
        "directory_sha256": hashlib.sha256(body).hexdigest(),
        "member": member,
        "member_modified": "2026-10-07T12:00:00",
        "local_header_offset": info.header_offset,
        "compressed_bytes": info.compress_size,
        "uncompressed_bytes": info.file_size,
        "crc32": info.CRC,
    }
    return body, content, descriptor


def test_archive_recovers_only_reviewed_original_without_extraction(tmp_path, archive):
    from political_ads.archives import archive_member

    body, content, descriptor = archive
    calls = []

    class CachedClient:
        offline = True

        def get(self, url, **kwargs):
            start, end = kwargs["byte_range"]
            calls.append((url, start, end))
            return body[start : end + 1], {
                "Content-Range": f"bytes {start}-{end}/{len(body)}",
                "ETag": descriptor["etag"],
                "Last-Modified": descriptor["last_modified"],
            }

    assert archive_member(CachedClient(), descriptor) == content
    assert len(calls) == 3
    assert not list(tmp_path.iterdir())


@pytest.mark.parametrize(
    "change", ["directory", "member", "mtime", "size", "crc", "etag", "header"]
)
def test_archive_changed_or_unbound_evidence_fails_closed(archive, change):
    from political_ads.archives import archive_member

    body, _, descriptor = archive
    if change == "directory":
        descriptor["directory_sha256"] = "0" * 64
    elif change == "member":
        descriptor["member"] = "../unreviewed.pdf"
    elif change == "mtime":
        descriptor["member_modified"] = "2025-10-07T12:00:00"
    elif change == "size":
        descriptor["uncompressed_bytes"] += 1
    elif change == "crc":
        descriptor["crc32"] += 1
    elif change == "header":
        mutable = bytearray(body)
        struct.pack_into("<H", mutable, descriptor["local_header_offset"] + 8, 0)
        body = bytes(mutable)
        descriptor["directory_sha256"] = hashlib.sha256(body).hexdigest()

    class CachedClient:
        offline = True

        def get(self, url, **kwargs):
            start, end = kwargs["byte_range"]
            return body[start : end + 1], {
                "Content-Range": f"bytes {start}-{end}/{len(body)}",
                "ETag": '"changed"' if change == "etag" else descriptor["etag"],
                "Last-Modified": descriptor["last_modified"],
            }

    with pytest.raises(ValueError):
        archive_member(CachedClient(), descriptor)
