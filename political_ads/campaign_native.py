from __future__ import annotations

import hashlib
import html
import json
import re
from datetime import date, datetime, timezone
from pathlib import Path
from urllib.parse import urlencode, urlparse

from bs4 import BeautifulSoup

from political_ads.cli import read_json, write_json
from political_ads.http import Client
from political_ads.schema import END, START, Ad, digest
from political_ads.video import recognize_video, video_segments


def collect_campaign_native(root: Path, until: str, offline: bool = False) -> dict:
    if not START <= until <= min(date.today().isoformat(), END):
        raise ValueError("Native campaign collection requires a valid cutoff")
    reviews = read_json(root / "data/campaign-native-reviews.json", {"reviews": []})["reviews"]
    candidates = {
        row["candidate_id"]: row
        for row in read_json(root / "data/site/candidates.json", {"candidates": []})["candidates"]
    }
    destination = root / "data/site/media.json"
    previous = read_json(destination, {"ads": [], "sources": [], "attempts": {}})
    ads = {ad["id"]: ad for ad in previous["ads"]}
    statuses = {row["source"]: row for row in previous["sources"]}
    attempts = previous.get("attempts", {})
    backlog_path = root / "outputs/media-backlog.json"
    backlog = read_json(backlog_path, {"leads": [], "sources": []})
    leads = {lead["id"]: lead for lead in backlog["leads"]}
    client = Client(root / "data/raw/http", offline)
    for review in reviews:
        identity, source = review["id"], review["source"]
        if identity in ads or (identity in leads and leads[identity].get("recovered_segments")):
            continue
        if review.get("post_timestamp"):
            published = (
                datetime.fromtimestamp(review["post_timestamp"], timezone.utc).date().isoformat()
            )
            if not START <= published <= until:
                continue
        else:
            published = None
        status = statuses.get(source, {})
        if re.match(r"^HTTPError: HTTP Error (401|403|429)\b", status.get("error", "")):
            continue
        status = status | {
            "source": source,
            "url": review["publisher_url"],
            "checked": date.today().isoformat(),
            "last_success": status.get("last_success"),
            "state": "partial",
            "discovery_complete": False,
            "scope": "Individually reviewed original campaign videos, not complete discovery",
        }
        status.pop("error", None)
        try:
            candidate = candidates[review["candidate_id"]]
            if candidate["office"] not in {"H", "S"} or candidate["election_year"] != "2026":
                raise ValueError("Review requires an exact 2026 federal candidate identity")
            body, _ = client.get(review["publisher_url"], retry=False)
            soup = BeautifulSoup(body, "html.parser")
            publisher_hash = hashlib.sha256(body).hexdigest()
            if request := review.get("publisher_request"):
                ajax_url = (
                    urlparse(review["publisher_url"])
                    ._replace(path="/wp-admin/admin-ajax.php", params="", query="", fragment="")
                    .geturl()
                )
                feed = soup.select_one("#cff")
                markup = html.unescape(body.decode("utf-8")).replace("\\/", "/")
                if (
                    not review.get("post_id")
                    or feed is None
                    or feed.select_one(".cff-load-more") is None
                    or ajax_url not in markup
                    or request.get("action") != "cff_get_new_posts"
                    or request.get("location") != "content"
                    or request.get("shortcode_data") != feed.get("data-cff-shortcode")
                    or str(request.get("post_id")) != feed.get("data-postid")
                    or request.get("locator_nonce") != feed.get("data-locatornonce")
                    or int(request.get("page", 0)) < 2
                ):
                    raise ValueError("Reviewed request must match the publisher's public feed")
                data = urlencode(
                    [
                        (key, request[key])
                        for key in (
                            "action",
                            "shortcode_data",
                            "pag_url",
                            "feed_id",
                            "post_id",
                            "location",
                            "page",
                            "locator_nonce",
                        )
                    ]
                ).encode()
                body, _ = client.get(ajax_url, retry=False, data=data)
                soup = BeautifulSoup(body, "html.parser")
            if review.get("post_id"):
                card = soup.find(id="cff_" + review["post_id"])
                if card is None or card.get("data-cff-timestamp") != str(review["post_timestamp"]):
                    raise ValueError("Reviewed publisher post or exact timestamp is missing")
                video = card.select_one("[data-cff-video]")
                if video is None:
                    raise ValueError("Reviewed publisher post has no original video link")
                video_url = video["data-cff-video"]
                parsed = urlparse(video_url)
                if parsed.scheme != "https" or not (parsed.hostname or "").endswith(".fbcdn.net"):
                    raise ValueError("Publisher feed video must use its public Facebook CDN")
            else:
                video_url = review["media_url"]
                markup = html.unescape(body.decode("utf-8")).replace("\\/", "/")
                if video_url not in markup:
                    raise ValueError("Reviewed original video is not linked by the publisher")
            media, _ = client.get(video_url, retry=False)
            if hashlib.sha256(media).hexdigest() != review["media_sha256"]:
                raise ValueError("Original video bytes differ from the individually reviewed ad")
            media_hash, ocr, speech = recognize_video(root, media, offline=offline)
            segments = video_segments(ocr, speech, media_hash)
            text = "\n".join(segment["text"] for segment in segments)
            if not segments or not all(quote in text for quote in review["required_quotes"]):
                raise ValueError("Recovered text does not retain the reviewed ad evidence")
            evidence = review | {
                "publisher_html_sha256": hashlib.sha256(body).hexdigest(),
                "speech_engine": {key: value for key, value in speech.items() if key != "segments"},
            }
            if review.get("publisher_request"):
                evidence["publisher_homepage_sha256"] = publisher_hash
            quality = [
                "local_speech_and_frame_ocr_not_manually_verified",
                "automatic_speech_may_misrecognize_names_or_negation",
                "release_and_delivery_dates_unverified"
                if published is None
                else "publisher_post_date_not_verified_first_release_or_paid_delivery",
            ]
            if published is None:
                leads[identity] = {
                    "id": identity,
                    "source": source,
                    "alignment": {"DEM": "D", "REP": "R"}.get(candidate["party"], "other"),
                    "state": "needs_date",
                    "video_url": video_url,
                    "releases": [
                        {
                            "url": review["publisher_url"],
                            "title": review["title"],
                            "published": None,
                        }
                    ],
                    "date_basis": "release_and_delivery_dates_unverified",
                    "date_uncertainty": review["date_uncertainty"],
                    "recovered_text": text,
                    "recovered_segments": segments,
                    "native_evidence": evidence,
                    "quality_flags": quality,
                }
            else:
                segments[0]["native_campaign_evidence"] = evidence
                ad = Ad(
                    id=identity,
                    source=source,
                    source_url=review["post_url"],
                    source_record_id=review["post_id"],
                    title=review["title"],
                    sponsor=review["sponsor"],
                    sponsor_type=review.get("sponsor_type", "candidate"),
                    alignment={"DEM": "D", "REP": "R"}.get(candidate["party"], "other"),
                    published=published,
                    observed=date.today().isoformat(),
                    text=text,
                    segments=segments,
                    source_hash=digest(
                        json.dumps({"evidence": evidence, "segments": segments}, sort_keys=True)
                    ),
                    date_basis="publisher_post_date",
                    state=candidate["state"],
                    chamber="House" if candidate["office"] == "H" else "Senate",
                    race=f"{candidate['state']}-{int(candidate['district']):02}"
                    if candidate["office"] == "H"
                    else f"{candidate['state']}-Senate",
                    language=speech["language"]
                    if speech["language_probability"] >= 0.8
                    else "unknown",
                    language_basis="Local Whisper language detection; speech and frame OCR",
                    media_urls=[review["post_url"]],
                    attribution_basis=(
                        f"Campaign-linked original with candidate approval and payer evidence; "
                        f"FEC {candidate['candidate_id']}, {candidate['party']}, principal "
                        f"committee {candidate['principal_committee']}. "
                        f"Primary publisher: {review['publisher_url']}"
                    ),
                    quality_flags=quality,
                ).to_dict()
                ads[identity] = ad
            attempts[identity] = {"state": "text" if published else "needs_date"}
            status["last_success"] = date.today().isoformat()
        except (OSError, ValueError, KeyError) as error:
            status["state"] = "error"
            status["error"] = f"{type(error).__name__}: {error}"
            attempts[identity] = {"state": "error", "error": status["error"]}
        status["ads_with_text"] = sum(ad["source"] == source for ad in ads.values())
        status["undated_videos_with_text"] = sum(
            lead["source"] == source and bool(lead.get("recovered_segments"))
            for lead in leads.values()
        )
        statuses[source] = status
        print(json.dumps(status), flush=True)
    result = previous | {
        "ads": sorted(ads.values(), key=lambda ad: (ad["published"], ad["id"])),
        "sources": list(statuses.values()),
        "attempts": attempts,
    }
    write_json(destination, result)
    if list(leads.values()) != backlog["leads"]:
        write_json(backlog_path, backlog | {"leads": list(leads.values())})
    return result
