from __future__ import annotations

import hashlib
import re
from dataclasses import asdict, dataclass, field
from datetime import date

START = "2026-01-01"
END = "2026-11-04"
VERSION = "1"


def digest(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def message_key(text: str) -> str:
    return digest(re.sub(r"\s+", " ", text).strip().casefold())


def in_window(start: str, end: str | None, until: str) -> bool:
    date.fromisoformat(start)
    if end is not None:
        date.fromisoformat(end)
        if end < start:
            raise ValueError("Delivery end precedes start")
    return start <= min(until, END) and (end is None or end >= START)


def observation_date(ad: dict) -> str:
    return max(START, ad["delivery_start"]) if ad.get("delivery_start") else ad["published"]


@dataclass
class Segment:
    text: str
    kind: str = "publisher_transcript"
    start_seconds: float | None = None
    end_seconds: float | None = None
    voice: str = "unreviewed"


@dataclass
class Ad:
    id: str
    source: str
    source_url: str
    source_record_id: str
    title: str
    sponsor: str
    sponsor_type: str
    alignment: str
    published: str
    observed: str
    text: str
    segments: list[dict]
    source_hash: str
    date_basis: str = "release_date"
    delivery_start: str | None = None
    delivery_end: str | None = None
    placement: str = "campaign_release"
    phase: str = "unknown"
    race: str = "Unresolved"
    state: str = ""
    chamber: str = ""
    language: str = "en"
    language_basis: str = "source_english"
    media_urls: list[str] = field(default_factory=list)
    attribution_basis: str = ""
    quality_flags: list[str] = field(default_factory=list)
    release_title: str = ""
    message_id: str = ""
    schema_version: str = VERSION

    def validate(self) -> None:
        if not self.source_url.startswith("https://"):
            raise ValueError("Ads require an HTTPS source")
        if not self.text.strip() or not self.segments:
            raise ValueError("Metadata-only records are not analyzed ads")
        if self.alignment not in {"D", "R", "other", "unknown"}:
            raise ValueError("Invalid alignment")
        if self.phase not in {"primary", "general", "unknown"}:
            raise ValueError("Invalid election phase")
        date.fromisoformat(self.published)
        date.fromisoformat(self.observed)
        if not self.attribution_basis:
            raise ValueError("Sponsor alignment requires evidence")
        if self.delivery_start:
            in_window(self.delivery_start, self.delivery_end, END)
        elif self.delivery_end:
            raise ValueError("Delivery end requires start")
        if self.date_basis == "delivery" and not self.delivery_start:
            raise ValueError("Delivery-based inclusion requires delivery start")
        if self.text != "\n".join(s["text"] for s in self.segments):
            raise ValueError("Canonical text must reconcile to original segments")
        self.message_id = message_key(self.text)

    def to_dict(self) -> dict:
        self.validate()
        return asdict(self)


def eligible(ad: dict, until: str) -> bool:
    if ad.get("language") != "en":
        return False
    if ad.get("delivery_start"):
        return in_window(ad["delivery_start"], ad.get("delivery_end"), until)
    return START <= ad["published"] <= min(until, END)
