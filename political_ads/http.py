from __future__ import annotations

import json
import re
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from political_ads.schema import digest

USER_AGENT = "PoliticalAdsResearch/0.1"


class Client:
    def __init__(self, cache: Path, offline: bool = False):
        self.cache = cache
        self.offline = offline
        cache.mkdir(parents=True, exist_ok=True)

    def get(
        self,
        url: str,
        refresh: bool = False,
        retry: bool = True,
        data: bytes | None = None,
        byte_range: tuple[int, int] | None = None,
    ) -> tuple[bytes, dict]:
        key = digest(url if data is None else url + "\nPOST\n" + data.hex())
        if byte_range is not None:
            start, end = byte_range
            if (
                data is not None
                or type(start) is not int
                or type(end) is not int
                or not 0 <= start <= end
                or end - start + 1 > 64 * 1024 * 1024
            ):
                raise ValueError("HTTP ranges require bounded, nonnegative GET coordinates")
            key = digest(url + f"\nRANGE\n{start}-{end}")

        def validate_range(body: bytes, headers: dict) -> None:
            if byte_range is not None:
                content_range = {k.lower(): v for k, v in headers.items()}.get("content-range", "")
                match = re.fullmatch(rf"bytes {start}-{end}/(\d+)", content_range)
                if match is None or int(match[1]) <= end or len(body) != end - start + 1:
                    raise ValueError("HTTP response does not match the exact requested byte range")

        payload = self.cache / f"{key}.body"
        metadata = self.cache / f"{key}.json"
        if payload.exists() and (self.offline or not refresh):
            if byte_range is not None and payload.stat().st_size != end - start + 1:
                raise ValueError("Cached HTTP range has an unexpected size")
            body, headers = payload.read_bytes(), json.loads(metadata.read_text())
            validate_range(body, headers)
            return body, headers
        if self.offline:
            raise FileNotFoundError(f"No cached response for {url}")
        attempts = 3 if retry else 1
        for attempt in range(attempts):
            try:
                request_headers = {"User-Agent": USER_AGENT}
                if byte_range is not None:
                    request_headers["Range"] = f"bytes={start}-{end}"
                request = Request(url, data=data, headers=request_headers)
                with urlopen(request, timeout=45) as response:
                    if byte_range is not None and response.status != 206:
                        raise ValueError("HTTP range requires a partial-content response")
                    body = (
                        response.read(end - start + 2)
                        if byte_range is not None
                        else response.read()
                    )
                    headers = dict(response.headers.items())
                    validate_range(body, headers)
                payload.write_bytes(body)
                metadata.write_text(json.dumps(headers, sort_keys=True))
                return body, headers
            except HTTPError as error:
                if error.code not in {429, 500, 502, 503, 504} or attempt == attempts - 1:
                    raise
                retry = error.headers.get("Retry-After", "")
                time.sleep(min(float(retry), 60) if retry.isdigit() else 2 ** (attempt + 1))
            except (URLError, TimeoutError):
                if attempt == attempts - 1:
                    raise
                time.sleep(2 ** (attempt + 1))
        raise RuntimeError("Request retries exhausted")

    def json(self, url: str, refresh: bool = False) -> tuple[object, dict]:
        body, headers = self.get(url, refresh)
        return json.loads(body), headers
