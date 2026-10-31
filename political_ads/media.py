from __future__ import annotations

import json
import re
import subprocess
import sys
import time
from dataclasses import asdict
from datetime import date, datetime
from pathlib import Path
from urllib.parse import urlencode

from bs4 import BeautifulSoup

from political_ads.cli import read_json, write_json
from political_ads.discovery import public_posts, rss_posts
from political_ads.http import Client
from political_ads.schema import END, START, Ad, Segment, digest
from political_ads.sources import (
    SOURCES,
    is_ad_release,
    language_of,
    media_links,
    plain_html,
    youtube_id,
)


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
    posts, complete = rss_posts(client, source, until, "ad")
    return sorted(posts, key=lambda post: post["date"], reverse=True), complete


def discover(client: Client, source, until: str) -> tuple[list[dict], bool]:
    if source.discovery == "reviewed_releases":
        return [], False
    if source.discovery not in {"wordpress", "rss"}:
        posts, complete = public_posts(client, source, until)
        return sorted(posts, key=lambda post: post["date"], reverse=True), complete
    if source.discovery == "rss":
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
        batch, headers = client.json(
            source.url + f"/wp-json/wp/v2/{source.rest_base}?" + query, refresh=True
        )
        if not isinstance(batch, list):
            raise ValueError("Media discovery did not return posts")
        if any(post["id"] in ids for post in batch):
            complete = False
            break
        for post in batch:
            if source.rest_base == "article" and "content" not in post:
                layouts = post.get("acf", {}).get("page_layout", [])
                post["content"] = {
                    "rendered": "\n".join(
                        layout.get("component_wysiwyg", {}).get("content", "") for layout in layouts
                    )
                }
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


def is_media_ad_release(title: str, source_id: str, content: str = "") -> bool:
    return (
        is_ad_release(title)
        or (
            source_id == "slf"
            and bool(
                re.match(r"^ICYMI:\s*(?:SLF|Senate Leadership Fund) Releases New Ads\b", title)
            )
        )
        or (
            source_id == "rjc-vf"
            and bool(re.search(r"\bcampaign\b", title, re.I))
            and bool(
                re.search(
                    r"\b(?:released|launched)\b[^.!?\n]{0,80}\b(?:ads?|advertising)\b",
                    plain_html(content),
                    re.I,
                )
            )
        )
    )


def inventory_media(root: Path, until: str, source_ids: list[str], offline: bool = False) -> dict:
    if not START <= until <= min(date.today().isoformat(), END):
        raise ValueError("Media inventory requires an in-scope cutoff")
    destination = root / "outputs/media-backlog.json"
    previous = read_json(destination, {"leads": [], "sources": []})
    leads = {row["id"]: row for row in previous["leads"]}
    statuses = {row["source"]: row for row in previous["sources"]}
    media = read_json(root / "data/site/media.json", {"ads": [], "attempts": {}})
    written = read_json(root / "data/site/corpus.json", {"ads": []})["ads"]
    client = Client(root / "data/raw/http", offline)
    by_id = {source.id: source for source in SOURCES}
    for key in dict.fromkeys(source_ids or [*by_id, "cfg-action", "protect-freedom"]):
        found = {}
        status = {"source": key, "checked": date.today().isoformat(), "state": "error"}
        try:
            if key == "cfg-action":
                url = "https://www.clubforgrowth.org/elections/watch/"
                body, _ = client.get(url, refresh=True)
                soup = BeautifulSoup(body, "html.parser")
                galleries = [
                    gallery
                    for gallery in soup.select(".robo-gallery-wrap")
                    if (
                        heading := gallery.find_previous(
                            string=re.compile(r"\b20\d{2}\s+General Election Ad Gallery\b")
                        )
                    )
                    and re.search(r"\b2026\b", str(heading))
                ]
                if not galleries:
                    raise ValueError("Public ad gallery omitted its 2026 heading")
                for gallery in galleries:
                    for node in gallery.select("[data-popup]"):
                        video = youtube_id(node["data-popup"])
                        title = node.get("title", "")
                        if video is None or not re.search(
                            r"\b[A-Z]{2}[-–](?:\d{1,2}|SEN|AL)\b", title, re.I
                        ):
                            continue
                        identity = key + "-" + video
                        found[identity] = {
                            "id": identity,
                            "source": key,
                            "alignment": "R",
                            "video_id": video,
                            "video_url": node["data-popup"],
                            "releases": [{"url": url, "title": title, "published": None}],
                            "date_basis": "2026_gallery_label_only_not_verified_release_date",
                            "state": "needs_date_and_text",
                        }
                complete = True
            elif key == "protect-freedom":
                url = "https://www.protectfreedompac.com/media"
                body, _ = client.get(url, refresh=True)
                soup = BeautifulSoup(body, "html.parser")
                for frame in soup.select("iframe[src]"):
                    card = frame.find_parent(class_="dmRespCol")
                    video = youtube_id(frame["src"])
                    if card is None or video is None:
                        continue
                    title = card.get_text(" ", strip=True).replace("\ufeff", "").strip()
                    day = re.search(r"\b[A-Z][a-z]+ \d{1,2}, 20\d{2}\b", title)
                    if (
                        not day
                        or not day[0].endswith("2026")
                        or not re.search(r"\bfor\s+(?:U\.?S\.?\s+Senate|Congress)\b", title, re.I)
                    ):
                        continue
                    published = datetime.strptime(day[0], "%B %d, %Y").date().isoformat()
                    if not START <= published <= until:
                        continue
                    identity = key + "-" + video
                    found[identity] = {
                        "id": identity,
                        "source": key,
                        "alignment": "R",
                        "video_id": video,
                        "video_url": f"https://www.youtube.com/watch?v={video}",
                        "releases": [
                            {
                                "url": url,
                                "title": title,
                                "published": published,
                                "source_hash": digest(str(card)),
                            }
                        ],
                        "date_basis": "publisher_dated_ad_gallery_not_delivery",
                        "state": "pending",
                    }
                complete = True
            else:
                source = by_id[key]
                posts, complete = discover(client, source, until)
                status["posts_scanned"] = len(posts)
                for post in posts:
                    title = plain_html(post["title"]["rendered"])
                    has_written = any(
                        ad["source"] == key and ad["source_record_id"] == str(post["id"])
                        for ad in written
                    )
                    if not has_written and not is_media_ad_release(
                        title, source.id, post["content"]["rendered"]
                    ):
                        continue
                    for url in media_links(post["content"]["rendered"]):
                        video = youtube_id(url)
                        if video is None:
                            continue
                        identity = key + "-" + video
                        row = found.setdefault(
                            identity,
                            {
                                "id": identity,
                                "source": key,
                                "alignment": source.alignment,
                                "video_id": video,
                                "video_url": f"https://www.youtube.com/watch?v={video}",
                                "releases": [],
                                "date_basis": "publisher_release_date",
                                "state": "pending",
                            },
                        )
                        release = {
                            "url": post["link"],
                            "title": title,
                            "published": post["date"][:10],
                            "source_record_id": str(post["id"]),
                            "source_hash": digest(post["content"]["rendered"]),
                        }
                        if release not in row["releases"]:
                            row["releases"].append(release)
            for row in found.values():
                video = row["video_id"]
                caption_ids = [
                    ad["id"]
                    for ad in media["ads"]
                    if ad["source"] == key + "-media"
                    and any(youtube_id(url) == video for url in ad["media_urls"])
                ]
                written_ids = [
                    ad["id"]
                    for ad in written
                    if ad["source"] == key
                    and {youtube_id(url) for url in ad["media_urls"] if youtube_id(url)} == {video}
                ]
                attempts = [
                    attempt
                    for identity, attempt in media["attempts"].items()
                    if identity.startswith(key + "-media-")
                    and youtube_id(attempt.get("video", "")) == video
                ]
                row["caption_ad_ids"] = sorted(caption_ids)
                row["written_ad_ids"] = sorted(written_ids)
                row["attempt_errors"] = sorted(
                    {attempt["error"] for attempt in attempts if attempt.get("error")}
                )
                if caption_ids:
                    row["state"] = "caption_text_available"
                elif written_ids:
                    row["state"] = "written_text_available"
                elif errors := "\n".join(row["attempt_errors"]):
                    if "429" in errors:
                        row["state"] = "rate_limited"
                    elif re.search(r"sign.in|not a bot|login|private video", errors, re.I):
                        row["state"] = "access_blocked"
                    elif "No public English captions" in errors:
                        row["state"] = "no_public_english_captions"
                    elif "short-ad review boundary" in errors:
                        row["state"] = "excluded_duration"
                    else:
                        row["state"] = "acquisition_error"
            if complete:
                leads = {identity: row for identity, row in leads.items() if row["source"] != key}
            leads.update(found)
            status.update(
                state="ok" if complete else "partial",
                discovery_complete=complete,
                unique_video_leads=len(found),
            )
        except (OSError, ValueError, KeyError, TypeError) as error:
            status["error"] = f"{type(error).__name__}: {error}"
            status["retained_leads"] = sum(row["source"] == key for row in leads.values())
        statuses[key] = status
        result = {
            "until": until,
            "checked": date.today().isoformat(),
            "scope": "Discovery backlog, not analyzed ads or verified paid placements",
            "leads": sorted(leads.values(), key=lambda row: row["id"]),
            "sources": sorted(statuses.values(), key=lambda row: row["source"]),
        }
        write_json(destination, result)
        print(json.dumps(status), flush=True)
    return result


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
    by_id = {source.id: source for source in SOURCES}
    for source in [by_id[key] for key in dict.fromkeys(source_ids) if key in by_id]:
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
                if not is_media_ad_release(title, source.id, post["content"]["rendered"]):
                    continue
                for url in media_links(post["content"]["rendered"]):
                    video_id = youtube_id(url)
                    if video_id is None:
                        continue
                    identity = f"{source_id}-{post['id']}-{video_id}"
                    existing = ads.get(identity)
                    if existing or any(
                        ad["source"] == source_id
                        and any(youtube_id(media) == video_id for media in ad["media_urls"])
                        for ad in ads.values()
                    ):
                        continue
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
                            else source.fixed_race or "Unresolved",
                            state=race_match[1] if race_match else source.fixed_race[:2],
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
