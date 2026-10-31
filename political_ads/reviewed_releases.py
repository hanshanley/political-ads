from __future__ import annotations

import json
import re
from datetime import datetime
from hashlib import sha256
from io import BytesIO
from urllib.parse import urlsplit

from bs4 import BeautifulSoup
from pypdf import PdfReader

from political_ads.images import image_segments, recognize_image
from political_ads.registry import candidate_mentions, enrich
from political_ads.schema import Ad, digest
from political_ads.sources import Source, language_of, media_links, plain_html, transcript_blocks


def linked_ad_text(client, content: str, review: dict, identities: list[dict]) -> str:
    evidence = review["linked_ad_text"]
    url = evidence["url"]
    target = urlsplit(url)
    public_player = (
        target.netloc == "bigal.media"
        and target.path == "/mediaplayer.php"
        and url in media_links(content)
    )
    public_report = (
        target.netloc == "www.washingtonexaminer.com"
        and target.path.startswith("/news/campaigns/congressional/")
        and not target.query
        and not target.fragment
    )
    public_campaign_pdf = (
        target.netloc == "www.brooksforcongress.com"
        and target.path.startswith("/wp-content/uploads/2026/")
        and target.path.endswith(".pdf")
        and not target.query
        and not target.fragment
    )
    links = {a.get("href") for a in BeautifulSoup(content, "html.parser").select("a[href]")}
    if (
        target.scheme != "https"
        or not (public_player or public_report or public_campaign_pdf)
        or url not in links
    ):
        raise ValueError("Ad text must come from an explicitly linked supported public page")
    if review["completeness"] != "partial_quotation":
        raise ValueError("Linked ad words require explicitly unverified completeness")
    body, _ = client.get(url, refresh=True, retry=False)
    if public_campaign_pdf:
        if evidence.get("format") != "pdf" or sha256(body).hexdigest() != evidence["file_sha256"]:
            raise ValueError("Linked PDF bytes changed; literal ad evidence requires a new review")
        reader = PdfReader(BytesIO(body))
        pages = evidence["pages"]
        if (
            not pages
            or any(type(page) is not int or not 1 <= page <= len(reader.pages) for page in pages)
            or pages != sorted(set(pages))
        ):
            raise ValueError("Linked PDF needs distinct, ordered, in-range reviewed pages")
        selected_pages = [reader.pages[page - 1] for page in pages]
        originals = {
            (annotation.get_object().get("/A") or {}).get("/URI")
            for page in selected_pages
            for annotation in page.get("/Annots", [])
            if annotation.get_object().get("/Subtype") == "/Link"
        }
        if review["media_url"] not in originals:
            raise ValueError("Linked PDF's exact original ad link is missing")
        linked = "\n".join(page.extract_text() or "" for page in selected_pages)
    else:
        linked = body.decode("utf-8")
    if digest(linked) != evidence["content_sha256"]:
        raise ValueError("Linked source changed; literal ad evidence requires a new review")
    visible = re.sub(r"\s+", " ", plain_html(linked)).strip()
    if not evidence["required_context"] or not all(
        context in visible for context in evidence["required_context"]
    ):
        raise ValueError("Linked source's explicit ad context is missing")
    if not candidate_mentions(visible, identities):
        raise ValueError("Linked source does not identify the reviewed federal candidate")
    if public_campaign_pdf:
        return visible
    selected = BeautifulSoup(linked, "html.parser").select(evidence["selector"])
    if len(selected) != 1:
        raise ValueError("Linked ad text must match exactly one reviewed element")
    return re.sub(r"\s+", " ", plain_html(str(selected[0]))).strip()


def broadcast_ad_text(content: str, source: Source, review: dict) -> str:
    url = urlsplit(review["source_url"])
    audio = urlsplit(review["media_url"])
    if (
        source.id != "ngb-mtpr"
        or source.url != "https://www.mtpr.org"
        or review["retrieval_url"] != review["source_url"]
        or url.netloc != "www.mtpr.org"
        or not re.fullmatch(r"/podcast/campaign-beat/\d{4}-\d{2}-\d{2}/[^/]+", url.path)
        or url.path.split("/")[3] != review["published"]
        or url.query
        or url.fragment
        or review["format"] != "html"
        or review["candidate_id"] != "H6MT01152"
        or review["completeness"] != "partial_quotation"
        or review.get("linked_ad_text")
        or audio.scheme != "https"
        or audio.netloc != "traffic.omny.fm"
        or not audio.path.startswith("/d/clips/")
        or not audio.path.endswith("/audio.mp3")
        or audio.query
        or audio.fragment
    ):
        raise ValueError("Broadcast evidence requires the reviewed MTPR episode and public audio")
    evidence = review["broadcast_evidence"]
    soup = BeautifulSoup(content, "html.parser")
    players = [
        node
        for node in soup.select(".PCEP-audioPlayer ps-stream")
        if node.get("data-stream-id") == evidence["stream_id"]
    ]
    if len(players) != 1 or players[0].get("data-stream-program-name") != review["release_title"]:
        raise ValueError("Reviewed broadcast stream identity or episode title is missing")
    streams = players[0].select("ps-stream-url")
    if (
        len(streams) != 1
        or streams[0].get("data-stream-format") != "audio/mpeg"
        or streams[0].get("data-stream-url") != review["media_url"]
    ):
        raise ValueError("Reviewed broadcast's exact episode audio association is missing")
    paragraphs = soup.select(evidence["paragraph_selector"])
    if (
        len(paragraphs) != 1
        or paragraphs[0].name != "p"
        or paragraphs[0].find_parent(class_="PCEP-articleBody") is None
    ):
        raise ValueError("Broadcast ad must match one paragraph inside the episode transcript")
    text = re.sub(r"\s+", " ", plain_html(str(paragraphs[0]))).strip()
    disclaimer = "No Going Back PAC Inc is responsible for the content of this advertisement."
    if not text.startswith("Flint Ad ") or not text.rstrip('"”').endswith(disclaimer):
        raise ValueError(
            "Broadcast paragraph's explicit ad label and payer attribution are missing"
        )
    return text


def printed_ad_text(client, content: str, source: Source, review: dict, identities: list[dict]):
    evidence = review["printed_ad_text"]
    publisher = urlsplit(review["source_url"])
    original = urlsplit(evidence["url"])
    page = re.fullmatch(r"/places/view/(\d+)/[a-z0-9_]+\.html", publisher.path)
    soup = BeautifulSoup(content, "html.parser")
    advertiser = soup.select("h1.ad_name")
    images = soup.select(".galim > img[src]")
    if (
        source.url != "https://marketplace.apg-wi.com"
        or source.sponsor_type != "candidate"
        or source.alignment != {"DEM": "D", "REP": "R"}.get(identities[0]["party"], "other")
        or publisher.netloc != "marketplace.apg-wi.com"
        or publisher.query
        or publisher.fragment
        or page is None
        or review["retrieval_url"] != review["source_url"]
        or review["format"] != "html"
        or review["completeness"] != "partial_quotation"
        or review.get("publication_selector") != "h2.ad_date"
        or review.get("linked_ad_text")
        or review.get("broadcast_evidence")
        or original.scheme != "https"
        or original.netloc != "static.wehaacdn.com"
        or original.query
        or original.fragment
        or not re.fullmatch(
            rf"/marketplace-apg--wi-com/imgs/media-images/\d+/images/{page[1]}\.jpg",
            original.path,
        )
        or review["media_url"] != evidence["url"]
        or len(images) != 1
        or images[0]["src"] != evidence["url"]
        or len(advertiser) != 1
        or not candidate_mentions(advertiser[0].get_text(" ", strip=True), identities)
    ):
        raise ValueError("Print ad requires its exact individual publisher, advertiser and image")
    media, _ = client.get(evidence["url"], retry=False)
    if sha256(media).hexdigest() != evidence["media_sha256"]:
        raise ValueError("Original print image changed; literal text requires a new review")
    image_hash, ocr = recognize_image(client.cache / "printed-ad-images", media)
    lines = image_segments(ocr, image_hash, evidence["url"])
    text = re.sub(r"\s+", " ", "\n".join(line["text"] for line in lines)).strip()
    if image_hash != evidence["media_sha256"] or digest(text) != evidence["ocr_text_sha256"]:
        raise ValueError("Pinned original OCR changed; literal text requires a new review")
    offset = 0
    line_ranges = []
    for line in lines:
        value = re.sub(r"\s+", " ", line["text"]).strip()
        line_ranges.append((offset, offset + len(value), line["image_bounds"]))
        offset += len(value) + 1
    position = 0
    passage_bounds = []
    for passage in review["passages"]:
        start = text.find(passage, position)
        if start < 0:
            raise ValueError("Print fragments must be literal original OCR in source order")
        position = start + len(passage)
        passage_bounds.append(
            [bounds for left, right, bounds in line_ranges if left < position and right > start]
        )
    return text, {
        "image_hash": image_hash,
        "image_url": evidence["url"],
        "extraction_engine": ocr["engine"],
        "coordinate_system": ocr["coordinate_system"],
        "ocr_text_sha256": digest(text),
        "passage_bounds": passage_bounds,
    }


def reviewed_release(client, source: Source, review: dict, candidates: list[dict], observed: str):
    for key in ("source_url", "retrieval_url"):
        url = urlsplit(review[key])
        if url.scheme != "https" or url.hostname != urlsplit(source.url).hostname:
            raise ValueError("Reviewed release must remain on its registered public publisher")
    identities = [c for c in candidates if c["candidate_id"] == review["candidate_id"]]
    candidate = next(iter(identities), None)
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
        if review.get("heading_selector"):
            headings = soup.select(review["heading_selector"])
            if len(headings) != 1 or headings[0].name not in {"h1", "h2"}:
                raise ValueError("Reviewed article heading must match exactly one h1 or h2")
            heading = headings[0]
        if heading is None:
            raise ValueError("Reviewed article publication metadata or heading is missing")
        if review.get("publication_selector"):
            dates = soup.select(review["publication_selector"])
            if len(dates) != 1:
                raise ValueError("Reviewed visible publication date must match exactly one element")
            published = (
                datetime.strptime(
                    dates[0].get_text(" ", strip=True),
                    review.get("publication_date_format", "%B %d, %Y"),
                )
                .date()
                .isoformat()
            )
            if publication is not None and publication["content"][:10] != published:
                raise ValueError("Reviewed visible and metadata publication dates disagree")
            if dates[0].has_attr("datetime") and dates[0]["datetime"][:10] != published:
                raise ValueError("Reviewed visible and datetime publication dates disagree")
        elif publication is not None:
            published = publication["content"][:10]
        else:
            raise ValueError("Reviewed article publication metadata or heading is missing")
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
        row["candidate_id"] for row in candidate_mentions(visible, identities)
    }:
        raise ValueError("Reviewed candidate is not identified in the publisher's evidence")
    broadcast = review.get("broadcast_evidence")
    printed = review.get("printed_ad_text")
    if not broadcast and not printed and review["media_url"] not in media_links(content):
        raise ValueError("Reviewed original ad link is missing")
    if printed:
        passage_source, print_evidence = printed_ad_text(
            client, content, source, review, identities
        )
    elif broadcast:
        passage_source = broadcast_ad_text(content, source, review)
    elif review.get("linked_ad_text"):
        passage_source = linked_ad_text(client, content, review, identities)
    else:
        passage_source = visible
    passages = review["passages"]
    if not passages or len(" ".join(passages).split()) < 15:
        raise ValueError("Reviewed ad needs substantive literal text")
    position = 0
    for passage in passages:
        match = passage_source.find(passage, position)
        if match < 0:
            raise ValueError("Reviewed ad passages must be literal and retain source order")
        position = match + len(passage)
    full_script = review["completeness"] == "marked_script"
    text = "\n".join(passages)
    if review.get("script_selector") and not full_script:
        raise ValueError("Reviewed script boundary requires an explicitly marked full script")
    if full_script:
        script_content = content
        if review.get("script_selector"):
            scripts = BeautifulSoup(content, "html.parser").select(review["script_selector"])
            if len(scripts) != 1:
                raise ValueError("Reviewed script boundary must match exactly one element")
            script_content = str(scripts[0])
        if text not in transcript_blocks(script_content):
            raise ValueError("Complete script must equal an explicitly marked transcript block")
    elif review["completeness"] != "partial_quotation":
        raise ValueError("Unknown reviewed ad completeness")
    flags = [
        "individually_reviewed_public_ad_text",
        "publisher_date_not_verified_first_release_or_paid_delivery",
        (
            "news_publisher_reports_marked_ad_script"
            if review.get("script_selector")
            else "campaign_release_reproduced_by_news_publisher"
        )
        if full_script
        else (
            "newspaper_display_ad_partial_image_text"
            if printed
            else "publisher_linked_source_quotes_partial_ad_copy"
            if review.get("linked_ad_text")
            else "news_report_quotes_partial_ad_copy"
        ),
    ]
    if not full_script:
        flags.append("publisher_ad_copy_completeness_unverified")
    if broadcast:
        flags.append("publisher_audio_episode_not_individual_ad_original")
    if printed:
        flags.extend(
            [
                "selected_image_words_visually_reviewed",
                "image_ocr_not_verified_complete_transcription",
                "ad_legal_payer_unverified",
            ]
        )
    segments = [
        {"text": passage, "kind": "publisher_transcript" if full_script else "publisher_ad_copy"}
        for passage in passages
    ]
    segments[0]["release_evidence"] = review
    segments[0]["federal_scope_candidate_ids"] = [candidate["candidate_id"]]
    if printed:
        for segment, bounds in zip(segments, print_evidence.pop("passage_bounds"), strict=True):
            segment.update(print_evidence | {"kind": "image_ocr", "image_line_bounds": bounds})
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
            placement="publisher_print_ad_listing" if printed else "campaign_release",
            text=text,
            segments=segments,
            source_hash=(
                digest(
                    content
                    + "\n"
                    + print_evidence["image_hash"]
                    + "\n"
                    + print_evidence["ocr_text_sha256"]
                )
                if printed
                else digest(content)
            ),
            date_basis="publisher_ad_listing_date" if printed else "publisher_report_date",
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
