from __future__ import annotations

import json
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
        self, url: str, refresh: bool = False, retry: bool = True, data: bytes | None = None
    ) -> tuple[bytes, dict]:
        key = digest(url if data is None else url + "\nPOST\n" + data.hex())
        payload = self.cache / f"{key}.body"
        metadata = self.cache / f"{key}.json"
        if payload.exists() and (self.offline or not refresh):
            return payload.read_bytes(), json.loads(metadata.read_text())
        if self.offline:
            raise FileNotFoundError(f"No cached response for {url}")
        attempts = 3 if retry else 1
        for attempt in range(attempts):
            try:
                request = Request(url, data=data, headers={"User-Agent": USER_AGENT})
                with urlopen(request, timeout=45) as response:
                    body = response.read()
                    headers = dict(response.headers.items())
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
