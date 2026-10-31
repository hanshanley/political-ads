from __future__ import annotations

import json
import re
from urllib.parse import urlsplit

from bs4 import BeautifulSoup

from political_ads.registry import candidate_mentions, enrich
from political_ads.schema import Ad, digest
from political_ads.sources import Source, language_of, media_links, plain_html, transcript_blocks


def reviewed_release(client, source: Source, review: dict, candidates: list[dict], observed: str):
    for key in ("source_url", "retrieval_url"):
        url = urlsplit(review[key])
        if url.scheme != "https" or url.hostname != urlsplit(source.url).hostname:
            raise ValueError("Reviewed release must remain on its registered public publisher")
    candidate = next((c for c in candidates if c["candidate_id"] == review["candidate_id"]), None)
    if not candidate or candidate["office"] != "H" or candidate["election_year"] != "2026":
        raise ValueError("Reviewed release requires an exact 2026 federal House candidate")
    race = f"{candidate['state']}-{int(candidate['district']):02}"
    if race != source.fixed_race:
        raise ValueError("Reviewed federal candidate does not match the registered race")
    body, _ = client.get(review["retrieval_url"], refresh=True, retry=False)
    if review["format"] == "wordpress":
        post = json.loads(body)
        if str(post["id"]) != review["record_id"] or post["link"] != review["source_url"]:
            raise ValueError("Reviewed WordPress post identity changed")
        content = post["content"]["rendered"]
        published = post["date"][:10]
        title = plain_html(post["title"]["rendered"])
    elif review["format"] == "html":
        content = body.decode("utf-8")
        soup = BeautifulSoup(content, "html.parser")
        publication = soup.find("meta", property="article:published_time")
        heading = soup.find("h1")
        if publication is None or heading is None:
            raise ValueError("Reviewed article publication metadata or heading is missing")
        published = publication["content"][:10]
        title = heading.get_text(" ", strip=True)
    else:
        raise ValueError("Unsupported reviewed release format")
    if digest(content) != review["content_sha256"]:
        raise ValueError("Source content changed; literal ad evidence requires a new review")
    if published != review["published"] or title != review["release_title"]:
        raise ValueError("Reviewed publication date or release title changed")
    visible = re.sub(r"\s+", " ", plain_html(content)).strip()
    if not all(context in visible for context in review["required_context"]):
        raise ValueError("Explicit advertiser/ad quotation context is missing")
    if candidate["candidate_id"] not in {
        row["candidate_id"] for row in candidate_mentions(visible, [candidate])
    }:
        raise ValueError("Reviewed candidate is not identified in the publisher's evidence")
    if review["media_url"] not in media_links(content):
        raise ValueError("Reviewed original ad link is missing")
    passages = review["passages"]
    if not passages or len(" ".join(passages).split()) < 15:
        raise ValueError("Reviewed ad needs substantive literal text")
    position = 0
    for passage in passages:
        match = visible.find(passage, position)
        if match < 0:
            raise ValueError("Reviewed ad passages must be literal and retain source order")
        position = match + len(passage)
    full_script = review["completeness"] == "marked_script"
    text = "\n".join(passages)
    if full_script:
        if text not in transcript_blocks(content):
            raise ValueError("Complete script must equal an explicitly marked transcript block")
    elif review["completeness"] != "partial_quotation":
        raise ValueError("Unknown reviewed ad completeness")
    flags = [
        "individually_reviewed_public_ad_text",
        "publisher_date_not_verified_first_release_or_paid_delivery",
        "campaign_release_reproduced_by_news_publisher"
        if full_script
        else "news_report_quotes_partial_ad_copy",
    ]
    if not full_script:
        flags.append("publisher_ad_copy_completeness_unverified")
    segments = [
        {"text": passage, "kind": "publisher_transcript" if full_script else "publisher_ad_copy"}
        for passage in passages
    ]
    segments[0]["release_evidence"] = review
    segments[0]["federal_scope_candidate_ids"] = [candidate["candidate_id"]]
    return enrich(
        Ad(
            id=f"{source.id}-{review['record_id']}-0",
            source=source.id,
            source_url=review["source_url"],
            source_record_id=review["record_id"],
            title=review["release_title"],
            sponsor=source.sponsor,
            sponsor_type=source.sponsor_type,
            alignment=source.alignment,
            published=published,
            observed=observed,
            text=text,
            segments=segments,
            source_hash=digest(content),
            date_basis="publisher_report_date",
            phase=review["phase"],
            race=race,
            state=candidate["state"],
            chamber="House",
            language=language_of(text),
            language_basis="langdetect seeded model; >=0.90 probability, otherwise unknown",
            media_urls=[review["media_url"]],
            attribution_basis=review["attribution_basis"],
            quality_flags=flags,
        ).to_dict(),
        candidates,
    )
