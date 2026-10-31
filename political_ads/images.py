from __future__ import annotations

import hashlib
import json
import re
import subprocess
from datetime import date
from pathlib import Path
from time import sleep
from urllib.parse import urlsplit

from bs4 import BeautifulSoup

from political_ads.cli import read_json, write_json
from political_ads.discovery import rss_posts
from political_ads.http import Client
from political_ads.schema import END, START, Ad, digest
from political_ads.sources import SOURCES, is_ad_release, language_of, plain_html, youtube_id


def recognize_image(directory: Path, body: bytes) -> tuple[str, dict]:
    image_hash = hashlib.sha256(body).hexdigest()
    directory.mkdir(parents=True, exist_ok=True)
    image = directory / (image_hash + ".img")
    image.write_bytes(body)
    cached = directory / (image_hash + ".ocr.json")
    if not cached.exists():
        try:
            source = Path(__file__).with_name("ocr.swift")
            executable = directory.parent / ("vision-ocr-" + digest(source.read_text())[:16])
            if not executable.exists():
                subprocess.run(
                    ["swiftc", str(source), "-o", str(executable)],
                    capture_output=True,
                    text=True,
                    check=True,
                    timeout=120,
                )
            process = subprocess.run(
                [str(executable), str(image)],
                capture_output=True,
                text=True,
                check=True,
                timeout=120,
            )
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as error:
            raise ValueError(f"Local OCR failed for {image_hash}: {error}") from error
        ocr = json.loads(process.stdout)
        ocr.pop("path", None)
        write_json(cached, ocr)
    return image_hash, read_json(cached, {})


def image_leads(posts: list[dict]) -> list[dict]:
    leads = {}
    for post in posts:
        content = post["content"]["rendered"]
        if not is_ad_release(plain_html(post["title"]["rendered"])) or not re.search(
            r"\bpaid digital advertising campaign\b", plain_html(content), re.I
        ):
            continue
        for image in BeautifulSoup(content, "html.parser").find_all("img"):
            url = image.get("src", "")
            parsed = urlsplit(url)
            parent = image.find_parent("a")
            if (
                parsed.scheme != "https"
                or parsed.hostname not in {"nrcc.org", "www.nrcc.org"}
                or not parsed.path.startswith("/wp-content/uploads/2026/")
                or not parsed.path.lower().endswith((".png", ".jpg", ".jpeg"))
                or (parent and youtube_id(parent.get("href", "")))
            ):
                continue
            identity = "nrcc-images-" + digest(post["link"] + "\n" + url)[:24]
            leads[identity] = {"id": identity, "image_url": url, "post": post}
    return list(leads.values())


def image_segments(ocr: dict, image_hash: str, image_url: str) -> list[dict]:
    return [
        {
            "text": line["text"],
            "kind": "image_ocr",
            "voice": "unreviewed",
            "start_seconds": None,
            "end_seconds": None,
            "confidence": line["confidence"],
            "image_bounds": line["bounds"],
            "image_hash": image_hash,
            "image_url": image_url,
            "coordinate_system": ocr["coordinate_system"],
            "extraction_engine": ocr["engine"],
        }
        for line in ocr["lines"]
        if line["text"].strip()
    ]


def reviewed_image_ad(lead: dict, ocr: dict, review: dict, image_hash: str, observed: str) -> dict:
    if review.get("image_hash") != image_hash:
        raise ValueError(f"Image changed since eligibility review: {lead['id']}")
    if review.get("source_url") != lead["post"]["link"]:
        raise ValueError(f"Image review belongs to a different release: {lead['id']}")
    if review.get("state") != "approved_image_ad":
        raise ValueError("An image must be reviewed as a standalone ad, not a video thumbnail")
    segments = image_segments(ocr, image_hash, lead["image_url"])
    post = lead["post"]
    text = "\n".join(line["text"] for line in segments)
    if not text or re.match(r"paid for by\b", text, re.I):
        raise ValueError("No substantive image-ad text recovered")
    race = review.get("race", "Unresolved")
    if race != "Unresolved" and not re.fullmatch(r"[A-Z]{2}-\d{2}", race):
        raise ValueError("Image review requires an explicit federal House race or Unresolved")
    return Ad(
        id=lead["id"],
        source="nrcc-images",
        source_url=post["link"],
        source_record_id=str(post["id"]),
        title=plain_html(post["title"]["rendered"]),
        sponsor="NRCC",
        sponsor_type="party",
        alignment="R",
        published=post["date"][:10],
        observed=observed,
        text=text,
        segments=segments,
        source_hash=digest(
            post["content"]["rendered"] + "\n" + image_hash + "\n" + json.dumps(ocr, sort_keys=True)
        ),
        race=race,
        chamber="House",
        state="" if race == "Unresolved" else race[:2],
        language=language_of(text),
        language_basis="Local English OCR plus seeded language detection",
        media_urls=[lead["image_url"]],
        quality_flags=[
            "image_ad_eligibility_reviewed",
            "image_ocr_may_misrecognize_words",
            "image_reading_order_unverified",
        ],
        attribution_basis=(
            f"Official NRCC release explicitly announces a paid digital advertising campaign: "
            f"{post['link']}. Image eligibility visually reviewed; OCR is not a certified "
            "transcription. Release date is not verified delivery. "
            + review.get("race_evidence", "Race unresolved.")
        ),
    ).to_dict()


def collect_images(root: Path, until: str, offline: bool = False) -> dict:
    if not START <= until <= min(date.today().isoformat(), END):
        raise ValueError("Image collection requires an in-scope cutoff")
    source = next(source for source in SOURCES if source.id == "nrcc")
    client = Client(root / "data/raw/http", offline)
    discovery_path = root / "data/raw/nrcc-image-discovery.json"
    if offline and discovery_path.exists():
        discovery = read_json(discovery_path, {})
        posts = [post for post in discovery["posts"] if START <= post["date"][:10] <= until]
        complete = discovery["complete"] and discovery["until"] >= until
    else:
        posts, complete = rss_posts(client, source, until, '"paid digital advertising campaign"')
        write_json(discovery_path, {"posts": posts, "complete": complete, "until": until})
    reviews = read_json(root / "data/image-reviews.json", {})
    previous = read_json(root / "data/site/images.json", {"ads": []})
    old_ads = {ad["id"]: ad for ad in previous["ads"]}
    leads = image_leads(posts)
    ads = []
    for lead in leads:
        body, _ = client.get(lead["image_url"])
        image_hash, ocr = recognize_image(root / "data/media/nrcc-images", body)
        lead.update(image_hash=image_hash, ocr=ocr)
        review = reviews.get(lead["id"], {})
        if review.get("state") == "approved_image_ad":
            ad = reviewed_image_ad(lead, ocr, review, image_hash, date.today().isoformat())
            prior = old_ads.get(ad["id"])
            if prior and prior["source_hash"] == ad["source_hash"]:
                ad["observed"] = prior["observed"]
            ads.append(ad)
        if not offline:
            sleep(2)
    write_json(root / "data/raw/nrcc-image-review.json", leads)
    if not complete:
        old_ads.update({ad["id"]: ad for ad in ads})
        ads = [
            ad
            for ad in old_ads.values()
            if not reviews.get(ad["id"], {}).get("state", "").startswith("rejected_")
        ]
    snapshot = {
        "ads": sorted(ads, key=lambda ad: (ad["published"], ad["id"])),
        "sources": [
            {
                "source": "nrcc-images",
                "url": source.url,
                "state": "partial",
                "checked": date.today().isoformat(),
                "last_success": until,
                "discovery_complete": complete,
                "posts_scanned": len(posts),
                "images_found": len(leads),
                "ads_with_text": len(ads),
                "unreviewed_images": sum(lead["id"] not in reviews for lead in leads),
                "scope": "Reviewed standalone images in explicit paid-digital campaign releases; "
                "not a census; excludes video thumbnails and unreviewed graphics",
            }
        ],
    }
    write_json(root / "data/site/images.json", snapshot)
    print(json.dumps(snapshot["sources"][0]), flush=True)
    return snapshot
