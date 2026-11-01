from __future__ import annotations

import hashlib
import html
import json
import re
import time
from datetime import date, datetime, timezone
from email.utils import parsedate_to_datetime
from io import BytesIO
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urljoin, urlparse

from bs4 import BeautifulSoup
from pypdf import PdfReader
from pypdf import __version__ as pdf_version

from political_ads.archives import archive_member
from political_ads.cli import read_json, write_json
from political_ads.http import Client
from political_ads.images import image_segments, recognize_image
from political_ads.registry import fec_table
from political_ads.schema import END, START, Ad, digest
from political_ads.sources import language_of
from political_ads.video import recognize_video, video_segments


def _attachment_metadata(
    client: Client, soup: BeautifulSoup, review: dict, publisher_hash: str
) -> None:
    attachment = review["publisher_attachment"]
    origin = urlparse(review["publisher_url"])
    page_url = urlparse(attachment["page_api_url"])
    collection_url = urlparse(attachment["attachment_api_url"])
    media_url = urlparse(review["media_url"])
    datetime.strptime(attachment["uploaded"], "%Y-%m-%dT%H:%M:%S")
    if (
        any(
            review.get(key)
            for key in (
                "post_id",
                "post_timestamp",
                "publisher_request",
                "publisher_release",
                "publisher_gallery",
                "publisher_archive",
                "publisher_pdf",
            )
        )
        or review.get("media_type", "video") != "video"
        or review["post_url"] != review["publisher_url"]
        or publisher_hash != attachment["publisher_sha256"]
        or soup.title is None
        or soup.title.get_text(" ", strip=True) != attachment["publisher_title"]
        or origin.scheme != "https"
        or origin.username
        or origin.password
        or any(
            url.scheme != "https" or url.netloc != origin.netloc or url.fragment
            for url in (page_url, collection_url, media_url)
        )
        or type(attachment["page_id"]) is not int
        or type(attachment["attachment_id"]) is not int
        or attachment["page_id"] <= 0
        or attachment["attachment_id"] <= 0
        or page_url.path != f"/wp-json/wp/v2/pages/{attachment['page_id']}"
        or page_url.query
        or collection_url.path != "/wp-json/wp/v2/media"
        or collection_url.query != f"parent={attachment['page_id']}"
        or media_url.path.rsplit("/", 1)[-1] != attachment["filename"]
        or not attachment["filename"].endswith(".mp4")
        or type(attachment["filesize"]) is not int
        or not 0 < attachment["filesize"] <= 128 * 1024 * 1024
        or len(
            soup.find_all(
                "link",
                attrs={
                    "rel": "alternate",
                    "type": "application/json",
                    "href": attachment["page_api_url"],
                },
            )
        )
        != 1
        or not any(
            tag.get("src") == review["media_url"] and tag.get("type") in (None, "video/mp4")
            for tag in soup.select("video[src], video source[src]")
        )
    ):
        raise ValueError("Attachment requires exact public campaign page and original links")
    body, _ = client.get(attachment["page_api_url"], retry=False)
    if hashlib.sha256(body).hexdigest() != attachment["page_sha256"]:
        raise ValueError("Reviewed campaign page metadata changed")
    page = json.loads(body)
    if (
        type(page["id"]) is not int
        or page["id"] != attachment["page_id"]
        or page["type"] != "page"
        or page["status"] != "publish"
        or page["link"] != review["publisher_url"]
        or [link["href"] for link in page["_links"]["wp:attachment"]]
        != [attachment["attachment_api_url"]]
    ):
        raise ValueError("Campaign page must link its exact public attachment collection")
    body, headers = client.get(attachment["attachment_api_url"], retry=False)
    if hashlib.sha256(body).hexdigest() != attachment["attachment_sha256"]:
        raise ValueError("Reviewed campaign attachment metadata changed")
    items = json.loads(body)
    headers = {key.lower(): value for key, value in headers.items()}
    if (
        not isinstance(items, list)
        or not 1 <= len(items) <= 10
        or not all(isinstance(item, dict) for item in items)
        or headers.get("x-wp-totalpages") != "1"
        or headers.get("x-wp-total") != str(len(items))
    ):
        raise ValueError("Attachment metadata requires one bounded complete public page")
    matches = [item for item in items if item.get("id") == attachment["attachment_id"]]
    if len(matches) != 1:
        raise ValueError("Attachment metadata must identify exactly one reviewed original")
    item = matches[0]
    if (
        type(item["id"]) is not int
        or item["post"] != attachment["page_id"]
        or item["type"] != "attachment"
        or item["status"] != "inherit"
        or item["media_type"] != "file"
        or item["mime_type"] != "video/mp4"
        or item["source_url"] != review["media_url"]
        or item["date_gmt"] != attachment["uploaded"]
        or item["filesize"] != attachment["filesize"]
        or item["media_details"]["filesize"] != attachment["filesize"]
        or [(link["href"], link["id"]) for link in item["_links"]["wp:attached-to"]]
        != [(attachment["page_api_url"], attachment["page_id"])]
    ):
        raise ValueError("Original must retain exact parent, upload time, MIME, size and backlink")


def _print_payer(client: Client, candidate: dict, review: dict) -> None:
    printed = review["publisher_pdf"]
    joint = printed.get("joint_fundraising_payer")
    if not joint:
        if review.get("sponsor_type", "candidate") != "candidate":
            raise ValueError("Non-candidate print payers require exact authorization evidence")
        return
    master = Client(client.cache, offline=True)
    body, _ = master.get("https://www.fec.gov/files/bulk-downloads/2026/cm26.zip", retry=False)
    if hashlib.sha256(body).hexdigest() != joint["fec_master_sha256"]:
        raise ValueError("Reviewed FEC committee master changed")
    committees = {row["committee_id"]: row for row in fec_table(master, "cm")}
    payer = committees[joint["committee_id"]]
    principal = committees[candidate["principal_committee"]]
    authorization = " ".join(printed["authorization_quote"].split()).casefold()
    if (
        review.get("sponsor_type") != "outside_group"
        or payer["designation"] != "J"
        or payer["type"] != "N"
        or payer["name"].casefold() != review["sponsor"].casefold()
        or principal["designation"] != "P"
        or principal["type"] != candidate["office"]
        or principal["candidate_id"] != candidate["candidate_id"]
        or principal["party"] != candidate["party"]
        or not "".join(printed["payer_quote"].split()).casefold().startswith("paidforby")
        or "joint fundraising committee" not in " ".join(printed["payer_quote"].split()).casefold()
        or f"authorized by and composed of {principal['name'].casefold()}" not in authorization
    ):
        raise ValueError("Joint-fund payer requires exact FEC identity and campaign authorization")


def _print_segments(
    root: Path, reader: PdfReader, pages: list[str], review: dict, media_hash: str
) -> tuple[list[dict], dict]:
    printed = review["publisher_pdf"]
    page = pages[printed["page"] - 1]
    if printed.get("issue_date"):
        issue_date = date.fromisoformat(printed["issue_date"])
        date_quote = issue_date.strftime("%B %d, %Y").replace(" 0", " ")
        if printed.get("issue_date_quote") != date_quote or not all(
            date_quote in " ".join(layer.split()) for layer in (pages[0], page)
        ):
            raise ValueError("Print issue date must appear on both cover and selected ad page")
    embedded = printed.get("embedded_image")
    lines, engine = [], {}
    if embedded:
        if (
            not isinstance(embedded["object_path"], str)
            or not embedded["object_path"].startswith("/")
            or embedded.get("whole_creative_visually_reviewed") is not True
        ):
            raise ValueError("Raster print requires an exact reviewed whole-creative image")
        image = reader.pages[printed["page"] - 1].images[embedded["object_path"]]
        stream = image.indirect_reference.get_object()
        if (
            image.name != embedded["name"]
            or "/SMask" in stream
            or "/Mask" in stream
            or hashlib.sha256(stream._data).hexdigest() != embedded["stream_sha256"]
            or hashlib.sha256(image.data).hexdigest() != embedded["sha256"]
        ):
            raise ValueError("Original page-local unmasked image bytes changed")
        image_hash, ocr = recognize_image(root / "data/raw/http/publisher-pdf-images", image.data)
        lines = image_segments(ocr, image_hash, review["post_url"])
        page = " ".join("\n".join(line["text"] for line in lines).split())
        if (
            ocr.get("image_frame_count") != 1
            or digest(page) != embedded["ocr_text_sha256"]
            or digest(json.dumps(ocr, sort_keys=True)) != embedded["ocr_sha256"]
        ):
            raise ValueError("Pinned whole-creative OCR changed; a new review is required")
        engine = {"pdf_image_engine": {k: v for k, v in ocr.items() if k != "lines"}}
    normalized = " ".join(page.split()).casefold()
    quotes = [printed["payer_quote"], printed["candidate_quote"]]
    if printed.get("joint_fundraising_payer"):
        quotes.append(printed["authorization_quote"])
    passages = review["passages"]
    if (
        not printed["cover_required_quotes"]
        or not all(q in pages[0] for q in printed["cover_required_quotes"])
        or not all(q and " ".join(q.split()).casefold() in normalized for q in quotes)
        or not passages
        or not all(p.strip() and p in page for p in passages)
        or not 15 <= len(" ".join(passages).split()) <= 25
    ):
        raise ValueError("Selected print words require page-local paid-ad evidence")
    ranges, offset = [], 0
    for line in lines:
        value = " ".join(line["text"].split())
        ranges.append((offset, offset + len(value), line["image_bounds"]))
        offset += len(value) + 1
    segments, position = [], 0
    for passage in passages:
        segment = {
            "text": passage,
            "kind": "publisher_pdf_text_layer",
            "pdf_page": printed["page"],
            "original_sha256": media_hash,
            "source_url": review["post_url"],
            "completeness": "partial_quotation",
        }
        if embedded:
            start = page.find(passage, position)
            if start < 0:
                raise ValueError("Raster print fragments must retain original OCR source order")
            position = start + len(passage)
            segment.update(
                kind="image_ocr",
                image_hash=embedded["sha256"],
                image_object_path=embedded["object_path"],
                ocr_text_sha256=embedded["ocr_text_sha256"],
                ocr_sha256=embedded["ocr_sha256"],
                image_line_bounds=[
                    bounds for left, right, bounds in ranges if left < position and right > start
                ],
                extraction_engine=ocr["engine"],
                coordinate_system=ocr["coordinate_system"],
                voice="unreviewed",
            )
        segments.append(segment)
    return segments, engine


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
        gallery = review.get("publisher_gallery")
        archive = review.get("publisher_archive")
        printed = review.get("publisher_pdf")
        attachment = review.get("publisher_attachment")
        is_image = review.get("media_type") == "image"
        is_pdf = review.get("media_type") == "pdf"
        if identity in ads or (identity in leads and leads[identity].get("recovered_segments")):
            continue
        if review.get("post_timestamp"):
            published = (
                datetime.fromtimestamp(review["post_timestamp"], timezone.utc).date().isoformat()
            )
            if not START <= published <= until:
                continue
        elif release := review.get("publisher_release"):
            published = release["published"]
            if not START <= published <= until:
                continue
        elif gallery:
            published = datetime.fromisoformat(gallery["created"]).date().isoformat()
            if not START <= published <= until:
                continue
        elif archive:
            published = parsedate_to_datetime(archive["last_modified"]).date().isoformat()
            if not START <= published <= until:
                continue
        elif printed:
            published = printed.get("issue_date") or printed["created"][:10]
            if not START <= published <= until:
                continue
        elif attachment:
            published = str(attachment.get("uploaded", ""))[:10]
            if not START <= published <= until:
                continue
        else:
            published = None
        status = statuses.get(source, {})
        if re.match(r"^HTTPError: HTTP Error (401|402|403|429)\b", status.get("error", "")):
            continue
        status = status | {
            "source": source,
            "url": review["publisher_url"],
            "checked": date.today().isoformat(),
            "last_success": status.get("last_success"),
            "state": "partial",
            "discovery_complete": False,
            "scope": (
                "Individually reviewed campaign PDF/video archive members, not complete discovery"
                if archive
                else "Individually reviewed original campaign PDFs, not complete discovery"
                if is_pdf
                else "Individually reviewed original campaign images, not complete discovery"
                if is_image
                else "Individually reviewed original campaign videos, not complete discovery"
            ),
        }
        status.pop("error", None)
        try:
            candidate = candidates[review["candidate_id"]]
            if candidate["office"] not in {"H", "S"} or candidate["election_year"] != "2026":
                raise ValueError("Review requires an exact 2026 federal candidate identity")
            body, _ = client.get(review["publisher_url"], retry=False)
            soup = BeautifulSoup(b"" if printed else body, "html.parser")
            publisher_hash = hashlib.sha256(body).hexdigest()
            alignment = {"DEM": "D", "REP": "R"}.get(candidate["party"], "other")
            if is_image != bool(gallery):
                raise ValueError("Reviewed images require exact public gallery upload evidence")
            if is_pdf and not (archive or printed):
                raise ValueError(
                    "Reviewed PDFs require exact archive or page-scoped print evidence"
                )
            if printed:
                page_number = printed["page"]
                surname, _, given = candidate["name"].partition(",")
                candidate_quote = f"{given.split()[0] if given.split() else ''} {surname}"
                if (
                    not is_pdf
                    or archive
                    or gallery
                    or review.get("post_id")
                    or review.get("post_timestamp")
                    or review.get("publisher_release")
                    or review.get("publisher_request")
                    or type(page_number) is not int
                    or not 1 <= page_number <= review["pdf"]["page_count"]
                    or urlparse(review["publisher_url"]).scheme != "https"
                    or not urlparse(review["publisher_url"]).path.lower().endswith(".pdf")
                    or review["media_url"] != review["publisher_url"]
                    or review["post_url"] != f"{review['publisher_url']}#page={page_number}"
                    or candidate["name"] != printed["candidate_name"]
                    or not given
                    or printed["candidate_quote"].casefold() != candidate_quote.casefold()
                    or " ".join(review["sponsor"].split()).casefold()
                    not in " ".join(printed["payer_quote"].split()).casefold()
                    or not printed["date_uncertainty"]
                    or review.get("completeness") != "partial_quotation"
                ):
                    raise ValueError("Print ad requires exact original, page, candidate and date")
                _print_payer(client, candidate, review)
            if archive:
                if (
                    gallery
                    or review.get("post_id")
                    or review.get("post_timestamp")
                    or review.get("publisher_release")
                    or review.get("publisher_request")
                    or review["post_url"] != review["publisher_url"]
                    or review.get("media_type") not in {"pdf", "video"}
                    or publisher_hash != archive["publisher_sha256"]
                    or soup.title is None
                    or soup.title.get_text(" ", strip=True) != archive["publisher_title"]
                    or archive["url"]
                    not in {
                        urljoin(review["publisher_url"], link["href"])
                        for link in soup.select("a[href]")
                    }
                    or not START <= archive["creative_created"][:10] <= published
                    or not archive["date_uncertainty"]
                    or review["media_url"] != archive["url"]
                ):
                    raise ValueError(
                        "Creative requires exact publisher-linked archive and date evidence"
                    )
                client._archive_request_at = time.monotonic()
            if gallery:
                script = soup.find("script", id="wix-warmup-data")
                if (
                    review.get("post_id")
                    or review.get("post_timestamp")
                    or review.get("publisher_request")
                    or review.get("publisher_release")
                    or review["post_url"] != review["publisher_url"]
                    or publisher_hash != gallery["sha256"]
                    or soup.title is None
                    or soup.title.get_text(" ", strip=True) != gallery["title"]
                    or script is None
                ):
                    raise ValueError("Image requires the exact reviewed public gallery")
                apps = json.loads(script.get_text())["appsWarmupData"]
                items = [
                    item
                    for app in apps.values()
                    if gallery["gallery_id"] in app
                    for item in app[gallery["gallery_id"]]["items"]
                    if item["itemId"] == gallery["item_id"]
                ]
                if (
                    len(items) != 1
                    or items[0]["createdDate"] != gallery["created"]
                    or items[0].get("isSecure") is not False
                    or items[0]["metaData"].get("type", "image") != "image"
                    or review["media_url"]
                    != "https://static.wixstatic.com/media/" + items[0]["mediaUrl"]
                ):
                    raise ValueError("Exact reviewed public image and upload timestamp are missing")
                alignment_review = review["alignment_review"]
                alignment_body, _ = client.get(alignment_review["url"], retry=False)
                alignment_text = BeautifulSoup(alignment_body, "html.parser").get_text(
                    " ", strip=True
                )
                if (
                    alignment_review["alignment"] not in {"D", "R", "other", "unknown"}
                    or hashlib.sha256(alignment_body).hexdigest() != alignment_review["sha256"]
                    or not alignment_review["required_quotes"]
                    or not all(q in alignment_text for q in alignment_review["required_quotes"])
                ):
                    raise ValueError("Publisher alignment requires exact reviewed primary evidence")
                alignment = alignment_review["alignment"]
            if release := review.get("publisher_release"):
                metadata = soup.select_one('meta[property="article:published_time"]')
                if (
                    review.get("post_id")
                    or review.get("post_timestamp")
                    or review["post_url"] != review["publisher_url"]
                    or publisher_hash != release["sha256"]
                    or soup.title is None
                    or soup.title.get_text(" ", strip=True) != release["title"]
                    or metadata is None
                    or metadata.get("content", "")[:10] != published
                ):
                    raise ValueError(
                        "Original requires the exact reviewed release title, hash and date"
                    )
            if attachment:
                _attachment_metadata(client, soup, review, publisher_hash)
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
                if not printed:
                    markup = html.unescape(body.decode("utf-8")).replace("\\/", "/")
                    if not gallery and not archive and video_url not in markup:
                        raise ValueError("Reviewed original video is not linked by the publisher")
            download_url = video_url
            parsed = urlparse(video_url)
            if parsed.scheme == "https" and parsed.hostname == "www.dropbox.com":
                query = dict(parse_qsl(parsed.query))
                query["dl"] = "1"
                download_url = parsed._replace(query=urlencode(query)).geturl()
            if archive:
                media = archive_member(client, archive)
            elif printed:
                media = body
            else:
                media, _ = client.get(download_url, retry=False)
            if hashlib.sha256(media).hexdigest() != review["media_sha256"]:
                raise ValueError("Original video bytes differ from the individually reviewed ad")
            if attachment and len(media) != attachment["filesize"]:
                raise ValueError("Original byte size differs from the reviewed attachment")
            if is_pdf:
                reader = PdfReader(BytesIO(media))
                pages = [page.extract_text() or "" for page in reader.pages]
                if (
                    reader.metadata is None
                    or reader.metadata.creation_date is None
                    or reader.metadata.creation_date.isoformat()
                    != (printed["created"] if printed else archive["creative_created"])
                    or len(pages) != review["pdf"]["page_count"]
                    or [hashlib.sha256(page.encode()).hexdigest() for page in pages]
                    != review["pdf"]["page_text_sha256"]
                ):
                    raise ValueError(
                        "PDF creation metadata or complete ordered text layers changed"
                    )
                media_hash = review["media_sha256"]
                engine = {"pdf_engine": {"name": "pypdf", "version": pdf_version}}
                if printed:
                    segments, image_engine = _print_segments(
                        root, reader, pages, review, media_hash
                    )
                    engine.update(image_engine)
                else:
                    segments = [
                        {
                            "text": page,
                            "kind": "publisher_pdf_text_layer",
                            "pdf_page": index + 1,
                            "original_sha256": media_hash,
                            "source_url": video_url,
                        }
                        for index, page in enumerate(pages)
                        if page.strip()
                    ]
                language = language_of("\n".join(segment["text"] for segment in segments))
            elif is_image:
                media_hash, ocr = recognize_image(root / "data/media/campaign-images", media)
                segments = image_segments(ocr, media_hash, video_url)
                language = language_of("\n".join(segment["text"] for segment in segments))
                engine = {
                    "image_engine": {key: value for key, value in ocr.items() if key != "lines"}
                }
            else:
                if archive:
                    import av

                    with av.open(BytesIO(media)) as container:
                        created = container.metadata.get("creation_time")
                    if created != archive["creative_created"]:
                        raise ValueError(
                            "Video creation metadata differs from reviewed archive creative"
                        )
                media_hash, ocr, speech = recognize_video(root, media, offline=offline)
                segments = video_segments(ocr, speech, media_hash)
                language = (
                    speech["language"] if speech["language_probability"] >= 0.8 else "unknown"
                )
                engine = {
                    "speech_engine": {
                        key: value for key, value in speech.items() if key != "segments"
                    }
                }
            text = "\n".join(segment["text"] for segment in segments)
            if not segments or not all(quote in text for quote in review["required_quotes"]):
                raise ValueError("Recovered text does not retain the reviewed ad evidence")
            evidence = review | {
                "publisher_pdf_sha256" if printed else "publisher_html_sha256": hashlib.sha256(
                    body
                ).hexdigest(),
                **engine,
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
            if release:
                quality[-1] = "publisher_release_date_not_verified_first_airing"
            if attachment:
                quality[-1] = (
                    "publisher_attachment_upload_not_verified_first_release_or_paid_delivery"
                )
            if is_image:
                quality = [
                    "image_ad_eligibility_reviewed",
                    "image_ocr_may_misrecognize_words",
                    "image_reading_order_unverified",
                    "publisher_gallery_upload_not_verified_first_publication_or_paid_delivery",
                ]
            if archive:
                quality[-1] = "archive_modification_date_not_verified_publication_or_paid_delivery"
            if is_pdf:
                quality = [
                    "printed_ad_eligibility_and_payer_visually_reviewed",
                    "pdf_text_layer_not_verified_complete_visible_transcription",
                    "pdf_reading_order_and_repeated_design_words_unverified",
                    "rasterized_words_may_be_missing_from_text_layer",
                    "archive_modification_date_not_verified_publication_or_paid_delivery",
                ]
                if printed:
                    print_date_quality = (
                        "publisher_pdf_issue_date_not_verified_first_release_or_paid_delivery"
                        if printed.get("issue_date")
                        else "publisher_pdf_creation_date_not_verified_publication_or_paid_delivery"
                    )
                    quality[-1] = print_date_quality
                    quality.extend(
                        ["selected_pdf_words_visually_reviewed", "partial_ad_text_not_full_script"]
                    )
                    if printed.get("embedded_image"):
                        quality = [
                            "printed_ad_eligibility_and_payer_visually_reviewed",
                            "selected_embedded_pdf_image_words_visually_reviewed",
                            "image_ocr_may_misrecognize_words",
                            "partial_ad_text_not_full_script",
                            print_date_quality,
                        ]
                    if printed.get("joint_fundraising_payer"):
                        quality.append("joint_fundraising_payer_not_candidate_principal_committee")
            quality.extend(review.get("quality_flags", []))
            if published is None:
                leads[identity] = {
                    "id": identity,
                    "source": source,
                    "alignment": alignment,
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
                    source_record_id=review.get("post_id", identity),
                    title=review["title"],
                    sponsor=review["sponsor"],
                    sponsor_type=review.get("sponsor_type", "candidate"),
                    alignment=alignment,
                    published=published,
                    phase=review.get("phase", "unknown"),
                    observed=date.today().isoformat(),
                    text=text,
                    segments=segments,
                    source_hash=digest(
                        json.dumps({"evidence": evidence, "segments": segments}, sort_keys=True)
                    ),
                    date_basis=(
                        "publisher_pdf_issue_date"
                        if printed and printed.get("issue_date")
                        else "publisher_pdf_creation_date"
                        if printed
                        else "publisher_attachment_upload_date"
                        if attachment
                        else "publisher_gallery_upload_date"
                        if gallery
                        else "publisher_archive_modification_date"
                        if archive
                        else "publisher_release_date"
                        if release
                        else "publisher_post_date"
                    ),
                    placement="publisher_print_ad_pdf" if printed else "campaign_release",
                    state=candidate["state"],
                    chamber="House" if candidate["office"] == "H" else "Senate",
                    race=f"{candidate['state']}-{int(candidate['district']):02}"
                    if candidate["office"] == "H"
                    else f"{candidate['state']}-Senate",
                    language=language,
                    language_basis=(
                        "Local embedded-image OCR plus seeded language detection"
                        if printed and printed.get("embedded_image")
                        else "Publisher PDF text layer plus seeded language detection"
                        if is_pdf
                        else "Local English OCR plus seeded language detection"
                        if is_image
                        else "Local Whisper language detection; speech and frame OCR"
                    ),
                    media_urls=[review["post_url"]],
                    attribution_basis=(
                        (
                            "Publisher-linked original with individually reviewed payer evidence; "
                            if release or gallery or archive or printed or attachment
                            else (
                                "Campaign-linked original with candidate approval "
                                "and payer evidence; "
                            )
                        )
                        + f"FEC {candidate['candidate_id']}, {candidate['party']}, principal "
                        f"committee {candidate['principal_committee']}. "
                        + (
                            f"Actual payer {printed['joint_fundraising_payer']['committee_id']}, "
                            "registered joint fundraising committee; candidate principal "
                            "committee establishes authorization, not payer identity. "
                            if printed and printed.get("joint_fundraising_payer")
                            else ""
                        )
                        + f"Primary publisher: {review['publisher_url']}"
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
