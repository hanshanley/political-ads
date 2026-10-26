from __future__ import annotations

import json
import re
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
from dataclasses import asdict
from datetime import date
from email.utils import parsedate_to_datetime
from pathlib import Path
from urllib.parse import urlencode

from political_ads.cli import read_json, write_json
from political_ads.http import Client
from political_ads.schema import END, START, Ad, Segment, digest
from political_ads.sources import SOURCES, is_ad_release, language_of, media_links, plain_html


def caption_segments(payload: dict, kind: str) -> list[dict]:
    segments = []
    for event in payload.get("events", []):
        text = "".join(part.get("utf8", "") for part in event.get("segs", [])).strip()
        if not text:
            continue
        start = event["tStartMs"] / 1000
        segment = asdict(
            Segment(
                text=text,
                kind=kind,
                start_seconds=start,
                end_seconds=start + event.get("dDurationMs", 0) / 1000,
            )
        )
        # Suppress only an exact repeated cue at the same timestamp, not repeated slogans.
        if not segments or (segments[-1]["text"], segments[-1]["start_seconds"]) != (text, start):
            segments.append(segment)
    return segments


def discover_rss(client: Client, source, until: str) -> tuple[list[dict], bool]:
    posts = []
    seen = set()
    for page in range(1, 11):
        query = urlencode({"s": "ad", "feed": "rss2", "year": "2026", "paged": page})
        body, _ = client.get(source.url + "/?" + query, refresh=True)
        try:
            items = ET.fromstring(body).findall("./channel/item")
        except ET.ParseError as error:
            raise ValueError("The public feed did not return valid RSS") from error
        if not items:
            break
        for item in items:
            link = item.findtext("link")
            if not link or link in seen:
                return posts, False
            seen.add(link)
            published = parsedate_to_datetime(item.findtext("pubDate")).date().isoformat()
            if START <= published <= until:
                posts.append(
                    {
                        "id": digest(link)[:16],
                        "link": link,
                        "date": published,
                        "title": {"rendered": item.findtext("title", "")},
                        "content": {
                            "rendered": item.findtext(
                                "{http://purl.org/rss/1.0/modules/content/}encoded",
                                item.findtext("description", ""),
                            )
                        },
                    }
                )
    return sorted(posts, key=lambda post: post["date"], reverse=True), False


def discover(client: Client, source, until: str) -> tuple[list[dict], bool]:
    if source.id in {"nrcc", "clf"}:
        return discover_rss(client, source, until)
    posts = []
    ids = set()
    complete = True
    for page in range(1, 31):
        query = urlencode(
            {
                "search": "ad",
                "after": "2025-12-31T23:59:59",
                "before": until + "T23:59:59",
                "per_page": 100,
                "page": page,
                "orderby": "date",
                "order": "asc",
            }
        )
        batch, headers = client.json(source.url + "/wp-json/wp/v2/posts?" + query, refresh=True)
        if not isinstance(batch, list):
            raise ValueError("Media discovery did not return posts")
        if any(post["id"] in ids for post in batch):
            complete = False
            break
        for post in batch:
            ids.add(post["id"])
            if START <= post["date"][:10] <= until:
                posts.append(post)
        total = next((int(v) for k, v in headers.items() if k.lower() == "x-wp-totalpages"), None)
        if total is not None and page >= total:
            break
        if not batch:
            break
        if total is None and len(batch) < 100:
            # A short custom endpoint may ignore page, date, and search parameters.
            complete = False
            break
    else:
        complete = False
    return sorted(posts, key=lambda post: post["date"], reverse=True), complete


def youtube_id(url: str) -> str | None:
    match = re.match(
        r"https://(?:www\.)?(?:youtube\.com/(?:watch\?v=|embed/)|youtu\.be/)([A-Za-z0-9_-]{11})",
        url,
    )
    return match[1] if match else None


def fetch_captions(root: Path, video_id: str) -> tuple[list[dict], str, dict]:
    path = root / "data/media" / video_id
    path.mkdir(parents=True, exist_ok=True)
    metadata_path = path / "video.info.json"
    files = sorted(path.glob("video.en*.json3"))
    if not metadata_path.exists() or not files:
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "yt_dlp",
                "--skip-download",
                "--write-info-json",
                "--write-subs",
                "--write-auto-subs",
                "--sub-langs",
                "en,en-US,en-GB",
                "--sub-format",
                "json3",
                "--no-playlist",
                "--js-runtimes",
                "node",
                "--no-progress",
                "--sleep-requests",
                "2",
                "-o",
                str(path / "video.%(ext)s"),
                f"https://www.youtube.com/watch?v={video_id}",
            ],
            capture_output=True,
            text=True,
            timeout=100,
        )
        if result.returncode:
            raise ValueError(result.stderr[-400:])
        files = sorted(path.glob("video.en*.json3"))
    if not files or not metadata_path.exists():
        raise ValueError("No public English captions; local ASR/review is still required")
    metadata = read_json(metadata_path, {})
    lang = files[0].name.removeprefix("video.").removesuffix(".json3")
    manual = lang in metadata.get("subtitles", {})
    kind = "youtube_caption" if manual else "youtube_auto_caption"
    raw = files[0].read_text()
    segments = caption_segments(json.loads(raw), kind)
    if not segments:
        raise ValueError("Empty caption cues")
    duration = metadata.get("duration") or 0
    if duration > 180 or duration < 5:
        raise ValueError("Video duration is not within the short-ad review boundary (5–180s)")
    if max(segment["end_seconds"] for segment in segments) < duration * 0.75:
        raise ValueError("Captions do not cover the final quarter of this video")
    return segments, raw, metadata


def collect_media(
    root: Path, until: str, source_ids: list[str], limit: int, retry_failed: bool = False
) -> None:
    if not START <= until <= min(date.today().isoformat(), END) or limit < 1:
        raise ValueError("Media collection requires a valid cutoff and a positive limit")
    destination = root / "data/site/media.json"
    previous = read_json(destination, {"ads": [], "sources": [], "attempts": {}})
    ads = {ad["id"]: ad for ad in previous["ads"]}
    for ad in ads.values():
        video_id = youtube_id(ad["media_urls"][0]) if ad["media_urls"] else None
        metadata_path = root / "data/media" / (video_id or "") / "video.info.json"
        if video_id and metadata_path.exists():
            metadata = read_json(metadata_path, {})
            ad["release_title"] = ad.get("release_title") or ad["title"].split(" / ", 1)[0]
            ad["title"] = metadata["title"]
            race_match = re.search(r"\b([A-Z]{2})[-–](\d{1,2})\b", ad["title"])
            if race_match:
                ad["race"] = f"{race_match[1]}-{int(race_match[2]):02}"
                ad["state"] = race_match[1]
    statuses = {row["source"]: row for row in previous["sources"]}
    attempts = previous.get("attempts", {})
    client = Client(root / "data/raw/http")
    for source in [source for source in SOURCES if source.id in source_ids]:
        source_id = source.id + "-media"
        status = {
            "source": source_id,
            "url": source.url,
            "checked": date.today().isoformat(),
            "last_success": statuses.get(source_id, {}).get("last_success"),
            "state": "partial",
            "posts_scanned": 0,
            "ads_with_text": 0,
            "scope": "Public English captions linked in official ad releases; bounded discovery",
        }
        acquired = 0
        try:
            posts, complete = discover(client, source, until)
            status["posts_scanned"] = len(posts)
            status["discovery_complete"] = complete
            for post in posts:
                title = plain_html(post["title"]["rendered"])
                if not is_ad_release(title):
                    continue
                for url in media_links(post["content"]["rendered"]):
                    video_id = youtube_id(url)
                    if video_id is None:
                        continue
                    identity = f"{source_id}-{post['id']}-{video_id}"
                    existing = ads.get(identity)
                    failed = attempts.get(identity, {})
                    retryable = "429" in failed.get("error", "")
                    if not existing and failed and not retry_failed and not retryable:
                        continue
                    if not existing and acquired >= limit:
                        break
                    acquired += not bool(existing)
                    try:
                        segments, raw, metadata = fetch_captions(root, video_id)
                        text = "\n".join(segment["text"] for segment in segments)
                        quality = [
                            "captions_not_independently_verified",
                            "on_screen_text_not_extracted",
                        ]
                        if segments[0]["kind"] == "youtube_auto_caption":
                            quality.append("automatic_captions_may_misrecognize_names")
                        race_match = re.search(r"\b([A-Z]{2})[-–](\d{1,2})\b", metadata["title"])
                        ad = Ad(
                            id=identity,
                            source=source_id,
                            source_url=post["link"],
                            source_record_id=str(post["id"]),
                            title=metadata["title"],
                            release_title=title,
                            sponsor=source.sponsor,
                            sponsor_type=source.sponsor_type,
                            alignment=source.alignment,
                            published=post["date"][:10],
                            observed=existing["observed"] if existing else date.today().isoformat(),
                            text=text,
                            segments=segments,
                            source_hash=digest(post["content"]["rendered"] + "\n" + raw),
                            chamber=source.chamber,
                            race=f"{race_match[1]}-{int(race_match[2]):02}"
                            if race_match
                            else "Unresolved",
                            state=race_match[1] if race_match else "",
                            media_urls=[url],
                            language=language_of(text),
                            language_basis="English caption track plus seeded language detection",
                            quality_flags=quality,
                            attribution_basis=f"Video linked in an official {source.sponsor} ad "
                            f"release: {post['link']}. Alignment is publisher alignment, not "
                            "a separately verified payer identity.",
                        ).to_dict()
                        ads[identity] = ad
                        attempts[identity] = {"state": "ok", "video": url}
                        print(f"Captioned {identity}", flush=True)
                    except (OSError, ValueError, KeyError, subprocess.TimeoutExpired) as error:
                        attempts[identity] = {
                            "state": "error",
                            "error": f"{type(error).__name__}: {error}",
                            "video": url,
                        }
                        print(f"Caption unavailable for {identity}: {error}", flush=True)
                        if "429" in str(error):
                            raise ValueError(
                                "Caption service rate-limited (429); retaining prior text"
                            ) from error
                    if not existing:
                        time.sleep(2)
                if acquired >= limit:
                    break
            status["last_success"] = until
        except (OSError, ValueError, KeyError, TypeError) as error:
            status.update(state="error", error=f"{type(error).__name__}: {error}")
        status["ads_with_text"] = sum(ad["source"] == source_id for ad in ads.values())
        status["attempted_this_run"] = acquired
        statuses[source_id] = status
        write_json(
            destination,
            {
                "ads": sorted(ads.values(), key=lambda ad: (ad["published"], ad["id"])),
                "sources": list(statuses.values()),
                "attempts": attempts,
            },
        )
        print(json.dumps(status), flush=True)
        if "429" in status.get("error", ""):
            break
