import hashlib
import io
import json
import zipfile
from datetime import datetime, timezone
from urllib.error import HTTPError
from urllib.parse import urlencode

import pytest
from bs4 import BeautifulSoup
from pypdf import PdfReader, PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

from political_ads.campaign_native import _attachment_metadata, collect_campaign_native
from political_ads.cli import read_json, write_json
from political_ads.http import Client


@pytest.fixture
def archived_pdf_review(tmp_path, monkeypatch, native_review):
    writer = PdfWriter()
    for text in ["I approve this message.", "We will protect families and deliver results."]:
        page = writer.add_blank_page(width=300, height=300)
        page[NameObject("/Resources")] = DictionaryObject(
            {
                NameObject("/Font"): DictionaryObject(
                    {
                        NameObject("/F1"): DictionaryObject(
                            {
                                NameObject("/Type"): NameObject("/Font"),
                                NameObject("/Subtype"): NameObject("/Type1"),
                                NameObject("/BaseFont"): NameObject("/Helvetica"),
                            }
                        )
                    }
                )
            }
        )
        stream = DecodedStreamObject()
        stream.set_data(f"BT /F1 12 Tf 10 10 Td ({text}) Tj ET".encode())
        page[NameObject("/Contents")] = stream
    writer.add_metadata({"/CreationDate": "D:20261007120000Z"})
    output = io.BytesIO()
    writer.write(output)
    pdf = output.getvalue()
    reader = PdfReader(io.BytesIO(pdf))
    name = "Press Kit/Ad.pdf"
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w") as archive:
        info = zipfile.ZipInfo(name, (2026, 10, 7, 12, 0, 0))
        info.compress_type = zipfile.ZIP_DEFLATED
        archive.writestr(info, pdf)
    body = output.getvalue()
    with zipfile.ZipFile(io.BytesIO(body)) as archive:
        info = archive.getinfo(name)
    markup = b"<title>Campaign</title><a href='/kit.zip'>Public press kit</a>"
    native_review.pop("post_id")
    native_review.pop("post_timestamp")
    native_review.update(
        post_url=native_review["publisher_url"],
        media_url="https://campaign.example/kit.zip",
        media_type="pdf",
        media_sha256=hashlib.sha256(pdf).hexdigest(),
        sponsor="NRCC",
        sponsor_type="party",
        phase="general",
        publisher_archive={
            "url": "https://campaign.example/kit.zip",
            "archive_bytes": len(body),
            "tail_bytes": len(body),
            "directory_sha256": hashlib.sha256(body).hexdigest(),
            "etag": '"original"',
            "last_modified": "Mon, 12 Oct 2026 18:21:26 GMT",
            "publisher_sha256": hashlib.sha256(markup).hexdigest(),
            "publisher_title": "Campaign",
            "member": name,
            "member_modified": "2026-10-07T12:00:00",
            "local_header_offset": info.header_offset,
            "compressed_bytes": info.compress_size,
            "uncompressed_bytes": info.file_size,
            "crc32": info.CRC,
            "creative_created": reader.metadata.creation_date.isoformat(),
            "date_uncertainty": (
                "Creation and archive modification are not first publication or delivery."
            ),
        },
        pdf={
            "page_count": 2,
            "page_text_sha256": [
                hashlib.sha256(page.extract_text().encode()).hexdigest() for page in reader.pages
            ],
        },
    )
    calls = []

    def get(self, url, **kwargs):
        calls.append((url, kwargs.get("byte_range")))
        if url == native_review["publisher_url"]:
            return markup, {}
        start, end = kwargs["byte_range"]
        return body[start : end + 1], {
            "Content-Range": f"bytes {start}-{end}/{len(body)}",
            "ETag": '"original"',
            "Last-Modified": "Mon, 12 Oct 2026 18:21:26 GMT",
        }

    monkeypatch.setattr("political_ads.campaign_native.Client.get", get)
    write_json(tmp_path / "data/campaign-native-reviews.json", {"reviews": [native_review]})
    return native_review, calls


def test_archived_pdf_retains_both_pages_as_one_ad_and_keeps_payer(tmp_path, archived_pdf_review):
    review, calls = archived_pdf_review
    result = collect_campaign_native(tmp_path, "2026-10-27", offline=True)
    assert len(result["ads"]) == 1
    ad = result["ads"][0]
    assert ad["sponsor"] == "NRCC" and ad["sponsor_type"] == "party" and ad["alignment"] == "R"
    assert ad["published"] == "2026-10-12" and ad["delivery_start"] is None
    assert ad["date_basis"] == "publisher_archive_modification_date" and ad["phase"] == "general"
    assert [segment["pdf_page"] for segment in ad["segments"]] == [1, 2]
    assert ad["text"] == "\n".join(segment["text"] for segment in ad["segments"])
    assert "pdf_text_layer_not_verified_complete_visible_transcription" in ad["quality_flags"]
    assert (
        ad["segments"][0]["native_campaign_evidence"]["publisher_archive"]
        == review["publisher_archive"]
    )
    assert collect_campaign_native(tmp_path, "2026-10-27", offline=True) == result
    assert len(calls) == 4


@pytest.mark.parametrize(
    "change", ["publisher", "creation", "pages", "quotation", "undated", "format"]
)
def test_archived_pdf_requires_bound_current_creative_evidence(
    tmp_path, archived_pdf_review, change
):
    review, _ = archived_pdf_review
    if change == "publisher":
        review["publisher_archive"]["publisher_sha256"] = "0" * 64
    elif change == "creation":
        review["publisher_archive"]["creative_created"] = "2025-10-07T12:00:00+00:00"
    elif change == "pages":
        review["pdf"]["page_text_sha256"] = review["pdf"]["page_text_sha256"][:1]
    elif change == "quotation":
        review["required_quotes"] = ["Words that are not in the creative"]
    elif change == "undated":
        review.pop("publisher_archive")
    else:
        review["media_type"] = "unreviewed_b_roll"
    write_json(tmp_path / "data/campaign-native-reviews.json", {"reviews": [review]})
    result = collect_campaign_native(tmp_path, "2026-10-27", offline=True)
    assert result["ads"] == []
    assert result["attempts"][review["id"]]["state"] == "error"


@pytest.fixture
def publisher_pdf_review(tmp_path, monkeypatch, archived_pdf_review):
    review, _ = archived_pdf_review
    archive = review.pop("publisher_archive")
    review.update(
        publisher_url="https://publisher.example/2026-guide.pdf",
        post_url="https://publisher.example/2026-guide.pdf#page=2",
        media_url="https://publisher.example/2026-guide.pdf",
        sponsor="Example for Congress",
        sponsor_type="candidate",
        phase="primary",
        completeness="partial_quotation",
        passages=["We will protect families and deliver results."],
        required_quotes=["We will protect families and deliver results."],
        publisher_pdf={
            "created": archive["creative_created"],
            "page": 2,
            "candidate_name": "EXAMPLE, CANDIDATE",
            "candidate_quote": "Candidate Example",
            "payer_quote": "Paid for by Example for Congress",
            "cover_required_quotes": ["2026 primary voters guide"],
            "date_uncertainty": "PDF creation is not publication or delivery.",
        },
    )
    text = (
        "Candidate Example. Paid for by Example for Congress. "
        "We will protect families and deliver results. "
        "We will keep our communities safe and fight for affordable health care."
    )
    review["passages"] = [text.split("Congress. ", 1)[1]]
    writer = PdfWriter()
    for layer in ["2026 primary voters guide. Editorial endorsement.", text]:
        page = writer.add_blank_page(width=300, height=300)
        page[NameObject("/Resources")] = DictionaryObject()
        stream = DecodedStreamObject()
        stream.set_data(f"BT 10 10 Td ({layer}) Tj ET".encode())
        page[NameObject("/Contents")] = stream
    writer.add_metadata({"/CreationDate": "D:20261007120000Z"})
    output = io.BytesIO()
    writer.write(output)
    body = output.getvalue()
    reader = PdfReader(io.BytesIO(body))
    review["media_sha256"] = hashlib.sha256(body).hexdigest()
    review["pdf"]["page_text_sha256"] = [
        hashlib.sha256(page.extract_text().encode()).hexdigest() for page in reader.pages
    ]
    roster = read_json(tmp_path / "data/site/candidates.json", {})
    roster["candidates"][0]["name"] = "EXAMPLE, CANDIDATE"
    write_json(tmp_path / "data/site/candidates.json", roster)
    monkeypatch.setattr(
        "political_ads.campaign_native.Client.get", lambda self, url, **kwargs: (body, {})
    )
    write_json(tmp_path / "data/campaign-native-reviews.json", {"reviews": [review]})
    return review


def test_publisher_pdf_ad_uses_only_selected_paid_page_words(tmp_path, publisher_pdf_review):
    review = publisher_pdf_review
    result = collect_campaign_native(tmp_path, "2026-10-27", offline=True)
    ad = result["ads"][0]
    assert ad["text"] == "\n".join(review["passages"])
    assert "Editorial" not in ad["text"] and "Paid for" not in ad["text"]
    assert ad["published"] == "2026-10-07" and ad["delivery_start"] is None
    assert ad["date_basis"] == "publisher_pdf_creation_date"
    assert ad["placement"] == "publisher_print_ad_pdf"
    assert ad["sponsor"] == "Example for Congress" and ad["race"] == "ZZ-01"
    assert ad["media_urls"] == [review["post_url"]]
    assert [segment["pdf_page"] for segment in ad["segments"]] == [2]
    assert ad["segments"][0]["native_campaign_evidence"]["publisher_pdf"] == review["publisher_pdf"]
    assert "partial_ad_text_not_full_script" in ad["quality_flags"]
    assert collect_campaign_native(tmp_path, "2026-10-27", offline=True) == result


@pytest.mark.parametrize(
    "change",
    [
        "page",
        "original",
        "hash",
        "creation",
        "layer",
        "payer",
        "sponsor",
        "candidate",
        "cover",
        "passage",
        "short",
    ],
)
def test_publisher_pdf_requires_bound_page_candidate_payer_and_literal_excerpt(
    tmp_path, publisher_pdf_review, change
):
    review = publisher_pdf_review
    if change == "page":
        review["publisher_pdf"]["page"] = 1
        review["post_url"] = review["publisher_url"] + "#page=1"
    elif change == "original":
        review["media_url"] = "https://unrelated.example/ad.pdf"
    elif change == "hash":
        review["media_sha256"] = "0" * 64
    elif change == "creation":
        review["publisher_pdf"]["created"] = "2026-10-08T12:00:00+00:00"
    elif change == "layer":
        review["pdf"]["page_text_sha256"][1] = "0" * 64
    elif change == "payer":
        review["publisher_pdf"]["payer_quote"] = "Paid for by another campaign"
    elif change == "sponsor":
        review["sponsor"] = "Another for Congress"
    elif change == "candidate":
        review["publisher_pdf"]["candidate_name"] = "ANOTHER, CANDIDATE"
    elif change == "cover":
        review["publisher_pdf"]["cover_required_quotes"] = ["2027 voters guide"]
    elif change == "passage":
        review["passages"] = [
            "A fabricated fifteen word quotation that does not appear anywhere "
            "in the actual paid creative."
        ]
    else:
        review["passages"] = ["We will protect families and deliver results."]
    write_json(tmp_path / "data/campaign-native-reviews.json", {"reviews": [review]})
    result = collect_campaign_native(tmp_path, "2026-10-27", offline=True)
    assert result["ads"] == []
    assert result["attempts"][review["id"]]["state"] == "error"


@pytest.mark.parametrize(
    "cover_date,page_date,date_quote",
    [
        ("October 9, 2026", "October 9, 2026", "October 9, 2026"),
        ("", "October 9, 2026", "October 9, 2026"),
        ("October 9, 2026", "", "October 9, 2026"),
        ("October 9, 2026", "October 9, 2026", "October 10, 2026"),
    ],
)
def test_publisher_pdf_issue_date_requires_cover_and_ad_page_calendar_evidence(
    tmp_path, monkeypatch, publisher_pdf_review, cover_date, page_date, date_quote
):
    review = publisher_pdf_review
    review["publisher_pdf"].update(issue_date="2026-10-09", issue_date_quote=date_quote)
    writer = PdfWriter()
    for text in (
        f"2026 primary voters guide. {cover_date}",
        "Candidate Example. Paid for by Example for Congress. "
        + " ".join(review["passages"])
        + " "
        + page_date,
    ):
        page = writer.add_blank_page(width=300, height=300)
        page[NameObject("/Resources")] = DictionaryObject()
        stream = DecodedStreamObject()
        stream.set_data(f"BT 10 10 Td ({text}) Tj ET".encode())
        page[NameObject("/Contents")] = stream
    writer.add_metadata({"/CreationDate": "D:20261007120000Z"})
    output = io.BytesIO()
    writer.write(output)
    body = output.getvalue()
    reader = PdfReader(io.BytesIO(body))
    review["media_sha256"] = hashlib.sha256(body).hexdigest()
    review["pdf"]["page_text_sha256"] = [
        hashlib.sha256(page.extract_text().encode()).hexdigest() for page in reader.pages
    ]
    monkeypatch.setattr(
        "political_ads.campaign_native.Client.get", lambda self, url, **kwargs: (body, {})
    )
    write_json(tmp_path / "data/campaign-native-reviews.json", {"reviews": [review]})
    result = collect_campaign_native(tmp_path, "2026-10-27", offline=True)
    if not cover_date or not page_date or date_quote != "October 9, 2026":
        assert result["ads"] == []
        assert result["attempts"][review["id"]]["state"] == "error"
    else:
        ad = result["ads"][0]
        assert ad["published"] == "2026-10-09"
        assert ad["date_basis"] == "publisher_pdf_issue_date"
        assert (
            "publisher_pdf_issue_date_not_verified_first_release_or_paid_delivery"
            in (ad["quality_flags"])
        )
        assert ad["delivery_start"] is None
        assert ad["text"] == "\n".join(review["passages"])


@pytest.mark.parametrize("date_field", ["created", "issue_date"])
def test_publisher_pdf_dated_after_cutoff_is_not_requested(
    tmp_path, monkeypatch, publisher_pdf_review, date_field
):
    review = publisher_pdf_review
    review["publisher_pdf"][date_field] = (
        "2026-10-28T12:00:00+00:00" if date_field == "created" else "2026-10-28"
    )
    write_json(tmp_path / "data/campaign-native-reviews.json", {"reviews": [review]})
    monkeypatch.setattr(
        "political_ads.campaign_native.Client.get",
        lambda *args, **kwargs: pytest.fail("Out-of-window PDF must not be requested"),
    )
    assert collect_campaign_native(tmp_path, "2026-10-27", offline=True)["ads"] == []


@pytest.fixture
def embedded_pdf_review(tmp_path, monkeypatch, publisher_pdf_review):
    from PIL import Image
    from pypdf.generic import EncodedStreamObject, NumberObject

    from political_ads.campaign_native import Client
    from political_ads.registry import COMMITTEE_FIELDS
    from political_ads.schema import digest

    review = publisher_pdf_review
    body, _ = Client(tmp_path / "data/raw/http", offline=True).get(review["publisher_url"])
    writer = PdfWriter(PdfReader(io.BytesIO(body)))
    stream = DecodedStreamObject()
    stream.set_data(b"")
    writer.pages[1][NameObject("/Contents")] = stream
    jpeg = io.BytesIO()
    Image.new("RGB", (32, 32), "white").save(jpeg, format="JPEG")
    image = EncodedStreamObject()
    image._data = jpeg.getvalue()
    image.update(
        {
            NameObject("/Type"): NameObject("/XObject"),
            NameObject("/Subtype"): NameObject("/Image"),
            NameObject("/Width"): NumberObject(32),
            NameObject("/Height"): NumberObject(32),
            NameObject("/ColorSpace"): NameObject("/DeviceRGB"),
            NameObject("/BitsPerComponent"): NumberObject(8),
            NameObject("/Filter"): NameObject("/DCTDecode"),
        }
    )
    writer.pages[1]["/Resources"][NameObject("/XObject")] = DictionaryObject(
        {NameObject("/Im1"): writer._add_object(image)}
    )
    output = io.BytesIO()
    writer.write(output)
    body = output.getvalue()
    reader = PdfReader(io.BytesIO(body))
    extracted = reader.pages[1].images["/Im1"]
    passages = [
        "We will protect families and deliver results.",
        "We will keep our communities safe and fight for affordable health care.",
    ]
    payer = "PAID FOR BY Example Victory Fund, A JOINT FUNDRAISING COMMITTEE"
    authorization = "AUTHORIZED BY AND COMPOSED OF EXAMPLE FOR CONGRESS AND ANOTHER PAC"
    texts = ["Candidate Example", payer, authorization] + [f"X {p}" for p in passages]
    ocr = {
        "engine": "Fixture OCR",
        "coordinate_system": "normalized x,y,width,height; origin at image bottom-left",
        "image_frame_count": 1,
        "lines": [
            {"text": text, "confidence": 1, "bounds": [0.1, 0.9 - i * 0.1, 0.8, 0.05]}
            for i, text in enumerate(texts)
        ],
    }
    candidate = read_json(tmp_path / "data/site/candidates.json", {})["candidates"][0]
    rows = [
        {
            "committee_id": "C00999999",
            "name": "EXAMPLE VICTORY FUND",
            "designation": "J",
            "type": "N",
        },
        {
            "committee_id": candidate["principal_committee"],
            "name": "EXAMPLE FOR CONGRESS",
            "designation": "P",
            "type": "H",
            "party": candidate["party"],
            "candidate_id": candidate["candidate_id"],
        },
    ]
    master = io.BytesIO()
    with zipfile.ZipFile(master, "w") as archive:
        archive.writestr(
            "cm.txt",
            "\n".join("|".join(row.get(field, "") for field in COMMITTEE_FIELDS) for row in rows),
        )
    master_body = master.getvalue()
    review.update(
        sponsor="Example Victory Fund",
        sponsor_type="outside_group",
        passages=passages,
        required_quotes=passages,
        media_sha256=hashlib.sha256(body).hexdigest(),
    )
    review["pdf"]["page_text_sha256"] = [
        hashlib.sha256((page.extract_text() or "").encode()).hexdigest() for page in reader.pages
    ]
    review["publisher_pdf"].update(
        payer_quote=payer,
        authorization_quote=authorization,
        joint_fundraising_payer={
            "committee_id": rows[0]["committee_id"],
            "fec_master_sha256": hashlib.sha256(master_body).hexdigest(),
        },
        embedded_image={
            "object_path": "/Im1",
            "name": extracted.name,
            "sha256": hashlib.sha256(extracted.data).hexdigest(),
            "stream_sha256": hashlib.sha256(image._data).hexdigest(),
            "ocr_text_sha256": digest(" ".join(texts)),
            "ocr_sha256": digest(json.dumps(ocr, sort_keys=True)),
            "whole_creative_visually_reviewed": True,
        },
    )
    monkeypatch.setattr(
        "political_ads.campaign_native.Client.get",
        lambda self, url, **kwargs: (master_body if url.endswith("/cm26.zip") else body, {}),
    )
    monkeypatch.setattr(
        "political_ads.campaign_native.recognize_image",
        lambda directory, data: (hashlib.sha256(data).hexdigest(), ocr),
    )
    write_json(tmp_path / "data/campaign-native-reviews.json", {"reviews": [review]})
    return review


def test_embedded_pdf_preserves_actual_joint_fund_payer_and_literal_line_bounds(
    tmp_path, embedded_pdf_review
):
    review = embedded_pdf_review
    result = collect_campaign_native(tmp_path, "2026-10-27", offline=True)
    ad = result["ads"][0]
    assert ad["sponsor"] == "Example Victory Fund" and ad["sponsor_type"] == "outside_group"
    assert ad["text"] == "\n".join(review["passages"])
    assert all(segment["kind"] == "image_ocr" for segment in ad["segments"])
    assert all(len(segment["image_line_bounds"]) == 1 for segment in ad["segments"])
    assert ad["segments"][0]["image_object_path"] == "/Im1"
    assert (
        ad["segments"][0]["ocr_text_sha256"]
        == review["publisher_pdf"]["embedded_image"]["ocr_text_sha256"]
    )
    assert "not payer identity" in ad["attribution_basis"]
    assert "joint_fundraising_payer_not_candidate_principal_committee" in ad["quality_flags"]
    assert "text_layer" not in ad["language_basis"]
    assert ad["published"] == "2026-10-07" and ad["delivery_start"] is None
    assert collect_campaign_native(tmp_path, "2026-10-27", offline=True) == result


@pytest.mark.parametrize(
    "change",
    [
        "page",
        "object_path",
        "name",
        "sha256",
        "stream_sha256",
        "ocr_text_sha256",
        "ocr_sha256",
        "ocr_bounds",
        "ocr_engine",
        "whole_creative_visually_reviewed",
        "committee_id",
        "fec_master_sha256",
        "authorization",
        "sponsor_type",
        "payer",
        "literal",
        "order",
        "short",
    ],
)
def test_embedded_pdf_rejects_unbound_image_ocr_and_joint_fund_authorization(
    tmp_path, embedded_pdf_review, change
):
    review = embedded_pdf_review
    printed = review["publisher_pdf"]
    if change == "page":
        printed["page"] = 1
        review["post_url"] = review["publisher_url"] + "#page=1"
    elif change in printed["embedded_image"]:
        printed["embedded_image"][change] = (
            False if change == "whole_creative_visually_reviewed" else "changed"
        )
    elif change in printed["joint_fundraising_payer"]:
        printed["joint_fundraising_payer"][change] = "changed"
    elif change in {"ocr_bounds", "ocr_engine"}:
        from political_ads.campaign_native import recognize_image

        _, ocr = recognize_image(tmp_path, b"fixture")
        if change == "ocr_bounds":
            ocr["lines"][3]["bounds"] = [0, 0, 1, 1]
        else:
            ocr["engine"] = "Changed OCR engine"
    elif change == "authorization":
        printed["authorization_quote"] = "AUTHORIZED BY ANOTHER CANDIDATE"
    elif change == "sponsor_type":
        review["sponsor_type"] = "candidate"
    elif change == "payer":
        printed["payer_quote"] = "Example Victory Fund"
    elif change == "literal":
        review["passages"][0] = review["passages"][0].replace("protect", "harm")
    elif change == "order":
        review["passages"].reverse()
    else:
        review["passages"] = [review["passages"][0]]
    write_json(tmp_path / "data/campaign-native-reviews.json", {"reviews": [review]})
    result = collect_campaign_native(tmp_path, "2026-10-27", offline=True)
    assert result["ads"] == []
    assert result["attempts"][review["id"]]["state"] == "error"


def test_print_outside_group_without_joint_fund_authorization_is_not_admitted(
    tmp_path, publisher_pdf_review
):
    review = publisher_pdf_review
    review["sponsor_type"] = "outside_group"
    write_json(tmp_path / "data/campaign-native-reviews.json", {"reviews": [review]})
    assert collect_campaign_native(tmp_path, "2026-10-27", offline=True)["ads"] == []


@pytest.fixture
def native_review(tmp_path, monkeypatch):
    review = {
        "id": "example-native-123",
        "source": "example-native",
        "publisher_url": "https://campaign.example/",
        "post_url": "https://www.facebook.com/123",
        "post_id": "123",
        "post_timestamp": 1792787350,
        "media_sha256": hashlib.sha256(b"original").hexdigest(),
        "candidate_id": "H6ZZ01001",
        "title": "Campaign post",
        "sponsor": "Example for Congress",
        "required_quotes": ["I approve this message."],
    }
    write_json(tmp_path / "data/campaign-native-reviews.json", {"reviews": [review]})
    write_json(
        tmp_path / "data/site/candidates.json",
        {
            "candidates": [
                {
                    "candidate_id": "H6ZZ01001",
                    "office": "H",
                    "election_year": "2026",
                    "party": "REP",
                    "state": "ZZ",
                    "district": "01",
                    "principal_committee": "C001",
                }
            ]
        },
    )
    markup = (
        b'<div id="cff_123" data-cff-timestamp="1792787350">'
        b'<img data-cff-video="https://video.example.fbcdn.net/original.mp4"></div>'
    )
    monkeypatch.setattr(
        "political_ads.campaign_native.Client.get",
        lambda self, url, **kwargs: (markup if url == review["publisher_url"] else b"original", {}),
    )
    monkeypatch.setattr(
        "political_ads.campaign_native.recognize_video",
        lambda *args, **kwargs: (
            review["media_sha256"],
            {},
            {"language": "en", "language_probability": 0.99},
        ),
    )
    monkeypatch.setattr(
        "political_ads.campaign_native.video_segments",
        lambda *args: [{"text": "I approve this message.", "kind": "local_speech"}],
    )
    return review


def test_native_feed_uses_exact_post_date_and_preserves_prior_text(
    tmp_path, monkeypatch, native_review
):
    prior = {"id": "retained", "published": "2026-01-01", "source": "earlier", "text": "Original"}
    write_json(tmp_path / "data/site/media.json", {"ads": [prior], "sources": []})
    result = collect_campaign_native(tmp_path, "2026-10-27")
    assert result["ads"][0] == prior
    ad = result["ads"][1]
    assert ad["published"] == "2026-10-23"
    assert ad["date_basis"] == "publisher_post_date"
    assert ad["delivery_start"] is None and ad["phase"] == "unknown"
    assert ad["alignment"] == "R" and ad["race"] == "ZZ-01"

    def no_request(*args, **kwargs):
        pytest.fail("An acquired, unchanged review must not request or transcribe again")

    monkeypatch.setattr("political_ads.campaign_native.Client.get", no_request)
    assert collect_campaign_native(tmp_path, "2026-10-27") == result


@pytest.mark.parametrize("change", ["timestamp", "media", "quote", "candidate"])
def test_native_review_rejects_changed_or_unbound_evidence(tmp_path, native_review, change):
    if change == "timestamp":
        native_review["post_timestamp"] += 1
    elif change == "media":
        native_review["media_sha256"] = "0" * 64
    elif change == "quote":
        native_review["required_quotes"] = ["Not present in the recovered text"]
    else:
        native_review["candidate_id"] = "H6ZZ01999"
    write_json(tmp_path / "data/campaign-native-reviews.json", {"reviews": [native_review]})
    result = collect_campaign_native(tmp_path, "2026-10-27")
    assert result["ads"] == []
    assert result["attempts"][native_review["id"]]["state"] == "error"


def test_native_party_payer_is_not_replaced_by_authorized_candidate(tmp_path, native_review):
    native_review.update(sponsor="NRCC", sponsor_type="party")
    write_json(tmp_path / "data/campaign-native-reviews.json", {"reviews": [native_review]})
    ad = collect_campaign_native(tmp_path, "2026-10-27")["ads"][0]
    assert ad["sponsor"] == "NRCC" and ad["sponsor_type"] == "party"
    assert ad["alignment"] == "R" and "H6ZZ01001" in ad["attribution_basis"]


def test_undated_original_is_preserved_in_backlog_not_dated_corpus(
    tmp_path, native_review, monkeypatch
):
    native_review.pop("post_id")
    native_review.pop("post_timestamp")
    native_review["media_url"] = "https://campaign.example/ad.mp4"
    native_review["date_uncertainty"] = "Filename and modification time are not release dates"
    write_json(tmp_path / "data/campaign-native-reviews.json", {"reviews": [native_review]})
    monkeypatch.setattr(
        "political_ads.campaign_native.Client.get",
        lambda self, url, **kwargs: (
            b'<script>video="https:\\/\\/campaign.example\\/ad.mp4"</script>'
            if url == native_review["publisher_url"]
            else b"original",
            {},
        ),
    )
    assert collect_campaign_native(tmp_path, "2026-10-27")["ads"] == []
    lead = read_json(tmp_path / "outputs/media-backlog.json", {})["leads"][0]
    assert lead["state"] == "needs_date"
    assert lead["releases"][0]["published"] is None
    assert lead["recovered_text"] == "I approve this message."
    assert lead["native_evidence"]["media_sha256"] == native_review["media_sha256"]


@pytest.mark.parametrize("code", [401, 402, 403, 429])
def test_native_denial_is_not_retried_on_later_runs(tmp_path, native_review, monkeypatch, code):
    requests = []

    def denied(self, url, **kwargs):
        requests.append(url)
        raise HTTPError(url, code, "Forbidden", {}, None)

    monkeypatch.setattr("political_ads.campaign_native.Client.get", denied)
    first = collect_campaign_native(tmp_path, "2026-10-27")
    second = collect_campaign_native(tmp_path, "2026-10-27")
    assert len(requests) == 1
    assert first["ads"] == second["ads"] == []
    assert str(code) in second["sources"][0]["error"]


@pytest.mark.parametrize("post_date", ["2025-12-31", "2026-10-28"])
def test_native_post_outside_collection_window_is_skipped_before_request(
    tmp_path, native_review, monkeypatch, post_date
):
    native_review["post_timestamp"] = int(
        datetime.fromisoformat(post_date).replace(tzinfo=timezone.utc).timestamp()
    )
    write_json(tmp_path / "data/campaign-native-reviews.json", {"reviews": [native_review]})

    def no_request(*args, **kwargs):
        pytest.fail("An out-of-window post must not be fetched or transcribed")

    monkeypatch.setattr("political_ads.campaign_native.Client.get", no_request)
    assert collect_campaign_native(tmp_path, "2026-10-27")["ads"] == []


@pytest.fixture
def paginated_review(tmp_path, native_review, monkeypatch):
    native_review["publisher_request"] = {
        "action": "cff_get_new_posts",
        "shortcode_data": '{"feed":"1"}',
        "pag_url": '{"123":"public-pagination-placeholder"}',
        "feed_id": "public-feed",
        "post_id": "2",
        "location": "content",
        "page": 7,
        "locator_nonce": "public-nonce",
    }
    payloads = {
        native_review["publisher_url"]: (
            b'<div id="cff" data-cff-shortcode=\'{"feed":"1"}\' '
            b'data-postid="2" data-locatornonce="public-nonce">'
            b'<button class="cff-load-more">Load more</button></div>'
            b'<script>var cffajaxurl="https://campaign.example/wp-admin/admin-ajax.php";</script>'
        ),
        "https://campaign.example/wp-admin/admin-ajax.php": (
            b'<div id="cff_123" data-cff-timestamp="1792787350">'
            b'<img data-cff-video="https://video.example.fbcdn.net/original.mp4"></div>'
        ),
        "https://video.example.fbcdn.net/original.mp4": b"original",
    }
    calls = []

    def get(self, url, **kwargs):
        calls.append((url, kwargs.get("data")))
        body = payloads[url]
        if isinstance(body, Exception):
            raise body
        return body, {}

    monkeypatch.setattr("political_ads.campaign_native.Client.get", get)
    write_json(tmp_path / "data/campaign-native-reviews.json", {"reviews": [native_review]})
    return native_review, payloads, calls


def test_native_public_pagination_replays_exact_post_and_retains_both_sources(
    tmp_path, paginated_review
):
    review, payloads, calls = paginated_review
    result = collect_campaign_native(tmp_path, "2026-10-27", offline=True)
    ad = result["ads"][0]
    evidence = ad["segments"][0]["native_campaign_evidence"]
    assert calls == [
        (review["publisher_url"], None),
        (
            "https://campaign.example/wp-admin/admin-ajax.php",
            urlencode(review["publisher_request"]).encode(),
        ),
        ("https://video.example.fbcdn.net/original.mp4", None),
    ]
    assert evidence["publisher_request"] == review["publisher_request"]
    assert (
        evidence["publisher_homepage_sha256"]
        == hashlib.sha256(payloads[review["publisher_url"]]).hexdigest()
    )
    assert (
        evidence["publisher_html_sha256"]
        == hashlib.sha256(payloads["https://campaign.example/wp-admin/admin-ajax.php"]).hexdigest()
    )
    assert ad["published"] == "2026-10-23"
    assert collect_campaign_native(tmp_path, "2026-10-27", offline=True) == result
    assert len(calls) == 3


@pytest.mark.parametrize("change", ["action", "nonce", "public_button", "post_timestamp"])
def test_native_pagination_rejects_unbound_requests_or_posts(tmp_path, paginated_review, change):
    review, payloads, calls = paginated_review
    if change == "action":
        review["publisher_request"]["action"] = "unreviewed_handler"
    elif change == "nonce":
        review["publisher_request"]["locator_nonce"] = "changed"
    elif change == "public_button":
        payloads[review["publisher_url"]] = b"<div>No exposed public feed</div>"
    else:
        review["post_timestamp"] += 1
    write_json(tmp_path / "data/campaign-native-reviews.json", {"reviews": [review]})
    result = collect_campaign_native(tmp_path, "2026-10-27")
    assert result["ads"] == []
    assert len(calls) == (2 if change == "post_timestamp" else 1)


def test_native_public_pagination_denial_pauses_future_requests(tmp_path, paginated_review):
    review, payloads, calls = paginated_review
    url = "https://campaign.example/wp-admin/admin-ajax.php"
    payloads[url] = HTTPError(url, 403, "Forbidden", {}, None)
    first = collect_campaign_native(tmp_path, "2026-10-27")
    second = collect_campaign_native(tmp_path, "2026-10-27")
    assert first["ads"] == second["ads"] == []
    assert len(calls) == 2
    assert "403" in second["sources"][0]["error"]


@pytest.fixture
def release_review(tmp_path, native_review, monkeypatch):
    native_review.pop("post_id")
    native_review.pop("post_timestamp")
    native_review.update(
        publisher_url="https://publisher.example/house-ad",
        post_url="https://publisher.example/house-ad",
        media_url="https://video.example/ad.mp4",
        sponsor="Reviewed outside organization",
        sponsor_type="outside_group",
    )
    markup = (
        b"<title>House ad release</title>"
        b'<meta property="article:published_time" content="2026-03-19T14:30:10Z">'
        b'<video src="https://video.example/ad.mp4"></video>'
    )
    native_review["publisher_release"] = {
        "published": "2026-03-19",
        "title": "House ad release",
        "sha256": hashlib.sha256(markup).hexdigest(),
    }
    payloads = {native_review["publisher_url"]: markup, native_review["media_url"]: b"original"}
    calls = []

    def get(self, url, **kwargs):
        calls.append(url)
        return payloads[url], {}

    monkeypatch.setattr("political_ads.campaign_native.Client.get", get)
    write_json(tmp_path / "data/campaign-native-reviews.json", {"reviews": [native_review]})
    return native_review, payloads, calls


def test_dated_direct_original_binds_release_and_keeps_reviewed_payer(tmp_path, release_review):
    review, _, calls = release_review
    result = collect_campaign_native(tmp_path, "2026-10-30", offline=True)
    ad = result["ads"][0]
    assert ad["published"] == "2026-03-19" and ad["date_basis"] == "publisher_release_date"
    assert ad["source_record_id"] == review["id"]
    assert ad["sponsor"] == "Reviewed outside organization"
    assert ad["sponsor_type"] == "outside_group" and ad["race"] == "ZZ-01"
    assert "candidate approval" not in ad["attribution_basis"]
    assert (
        ad["segments"][0]["native_campaign_evidence"]["publisher_release"]
        == (review["publisher_release"])
    )
    assert calls == [review["publisher_url"], review["media_url"]]
    assert collect_campaign_native(tmp_path, "2026-10-30", offline=True) == result
    assert len(calls) == 2


@pytest.mark.parametrize("change", ["date", "title", "hash", "missing_date", "unlinked_media"])
def test_dated_original_rejects_unbound_release_before_media_request(
    tmp_path, release_review, change
):
    review, payloads, calls = release_review
    if change == "date":
        review["publisher_release"]["published"] = "2026-03-20"
    elif change == "title":
        review["publisher_release"]["title"] = "A different ad release"
    elif change == "hash":
        review["publisher_release"]["sha256"] = "0" * 64
    else:
        body = payloads[review["publisher_url"]]
        body = body.replace(
            b"article:published_time"
            if change == "missing_date"
            else b"https://video.example/ad.mp4",
            b"missing",
        )
        payloads[review["publisher_url"]] = body
        review["publisher_release"]["sha256"] = hashlib.sha256(body).hexdigest()
    write_json(tmp_path / "data/campaign-native-reviews.json", {"reviews": [review]})
    result = collect_campaign_native(tmp_path, "2026-10-30", offline=True)
    assert not result["ads"]
    assert result["attempts"][review["id"]]["state"] == "error"
    assert calls == [review["publisher_url"]]


def test_direct_release_outside_cutoff_is_not_requested(tmp_path, release_review):
    _, _, calls = release_review
    assert not collect_campaign_native(tmp_path, "2026-03-18", offline=True)["ads"]
    assert calls == []


@pytest.fixture
def attachment_review(tmp_path, native_review, monkeypatch):
    native_review.pop("post_id")
    native_review.pop("post_timestamp")
    native_review.update(
        post_url=native_review["publisher_url"],
        media_url="https://campaign.example/ad.mp4",
    )
    attachment = {
        "publisher_title": "Campaign",
        "page_id": 14,
        "page_api_url": "https://campaign.example/wp-json/wp/v2/pages/14",
        "attachment_id": 38,
        "attachment_api_url": "https://campaign.example/wp-json/wp/v2/media?parent=14",
        "uploaded": "2026-05-19T00:22:22",
        "filename": "ad.mp4",
        "filesize": len(b"original"),
    }
    markup = (
        "<title>Campaign</title>"
        '<meta property="article:published_time" content="2026-05-16T11:37:12Z">'
        f'<link rel="alternate" type="application/json" href="{attachment["page_api_url"]}">'
        f'<video><source src="{native_review["media_url"]}" type="video/mp4"></video>'
    ).encode()
    page = {
        "id": 14,
        "type": "page",
        "status": "publish",
        "link": native_review["publisher_url"],
        "_links": {"wp:attachment": [{"href": attachment["attachment_api_url"]}]},
    }
    media = {
        "id": 38,
        "post": 14,
        "type": "attachment",
        "status": "inherit",
        "media_type": "file",
        "mime_type": "video/mp4",
        "source_url": native_review["media_url"],
        "date": "2026-05-18T20:22:22",
        "date_gmt": attachment["uploaded"],
        "filesize": len(b"original"),
        "media_details": {"filesize": len(b"original")},
        "_links": {"wp:attached-to": [{"href": attachment["page_api_url"], "id": 14}]},
    }
    payloads = {
        native_review["publisher_url"]: markup,
        attachment["page_api_url"]: json.dumps(page).encode(),
        attachment["attachment_api_url"]: json.dumps([media]).encode(),
        native_review["media_url"]: b"original",
    }
    for field, url in (
        ("publisher_sha256", native_review["publisher_url"]),
        ("page_sha256", attachment["page_api_url"]),
        ("attachment_sha256", attachment["attachment_api_url"]),
    ):
        attachment[field] = hashlib.sha256(payloads[url]).hexdigest()
    native_review["publisher_attachment"] = attachment
    calls = []

    def get(self, url, **kwargs):
        calls.append(url)
        return payloads[url], {"X-WP-Total": "1", "X-WP-TotalPages": "1"}

    monkeypatch.setattr("political_ads.campaign_native.Client.get", get)
    write_json(tmp_path / "data/campaign-native-reviews.json", {"reviews": [native_review]})
    return native_review, payloads, calls


def test_attachment_binds_original_and_utc_upload_not_homepage_date(tmp_path, attachment_review):
    review, _, calls = attachment_review
    result = collect_campaign_native(tmp_path, "2026-10-30", offline=True)
    ad = result["ads"][0]
    assert ad["published"] == "2026-05-19"
    assert ad["date_basis"] == "publisher_attachment_upload_date"
    assert ad["delivery_start"] is None and ad["delivery_end"] is None
    assert ad["phase"] == "unknown" and ad["text"] == "I approve this message."
    assert (
        "publisher_attachment_upload_not_verified_first_release_or_paid_delivery"
        in (ad["quality_flags"])
    )
    assert (
        ad["segments"][0]["native_campaign_evidence"]["publisher_attachment"]
        == (review["publisher_attachment"])
    )
    assert calls == [
        review["publisher_url"],
        review["publisher_attachment"]["page_api_url"],
        review["publisher_attachment"]["attachment_api_url"],
        review["media_url"],
    ]
    assert collect_campaign_native(tmp_path, "2026-10-30", offline=True) == result
    assert len(calls) == 4


def test_attachment_upload_outside_cutoff_is_not_requested(tmp_path, attachment_review):
    _, _, calls = attachment_review
    assert not collect_campaign_native(tmp_path, "2026-05-18", offline=True)["ads"]
    assert calls == []


@pytest.mark.parametrize("size", [98203315, 128 * 1024 * 1024, 128 * 1024 * 1024 + 1])
def test_attachment_size_remains_bounded_before_original(tmp_path, attachment_review, size):
    review, payloads, calls = attachment_review
    attachment = review["publisher_attachment"]
    attachment["filesize"] = size
    media = json.loads(payloads[attachment["attachment_api_url"]])[0]
    media["filesize"] = media["media_details"]["filesize"] = size
    payloads[attachment["attachment_api_url"]] = json.dumps([media]).encode()
    attachment["attachment_sha256"] = hashlib.sha256(
        payloads[attachment["attachment_api_url"]]
    ).hexdigest()
    client = Client(tmp_path / "cache", offline=True)
    soup = BeautifulSoup(payloads[review["publisher_url"]], "html.parser")
    if size <= 128 * 1024 * 1024:
        _attachment_metadata(client, soup, review, attachment["publisher_sha256"])
        assert calls == [attachment["page_api_url"], attachment["attachment_api_url"]]
    else:
        with pytest.raises(ValueError, match="exact public campaign page"):
            _attachment_metadata(client, soup, review, attachment["publisher_sha256"])
        assert calls == []
    assert review["media_url"] not in calls


@pytest.mark.parametrize(
    "change",
    [
        "homepage_hash",
        "unlinked_page",
        "page_hash",
        "page_parent",
        "unlinked_attachments",
        "attachment_hash",
        "attachment_parent",
        "upload",
        "mime",
        "source",
        "backlink",
        "unbounded_collection",
        "file_size",
    ],
)
def test_attachment_rejects_changed_or_unbound_metadata_before_original(
    tmp_path, attachment_review, change
):
    review, payloads, calls = attachment_review
    attachment = review["publisher_attachment"]
    if change in {"homepage_hash", "page_hash", "attachment_hash"}:
        field = (
            "publisher_sha256" if change == "homepage_hash" else change.replace("hash", "sha256")
        )
        attachment[field] = "0" * 64
    elif change == "unlinked_page":
        payloads[review["publisher_url"]] = payloads[review["publisher_url"]].replace(
            attachment["page_api_url"].encode(), b"https://campaign.example/unrelated"
        )
        attachment["publisher_sha256"] = hashlib.sha256(
            payloads[review["publisher_url"]]
        ).hexdigest()
    elif change in {"page_parent", "unlinked_attachments"}:
        page = json.loads(payloads[attachment["page_api_url"]])
        if change == "page_parent":
            page["link"] = "https://campaign.example/unrelated"
        else:
            page["_links"]["wp:attachment"] = []
        payloads[attachment["page_api_url"]] = json.dumps(page).encode()
        attachment["page_sha256"] = hashlib.sha256(payloads[attachment["page_api_url"]]).hexdigest()
    elif change == "file_size":
        payloads[review["media_url"]] = b"original" * 2
        review["media_sha256"] = hashlib.sha256(payloads[review["media_url"]]).hexdigest()
    else:
        media = json.loads(payloads[attachment["attachment_api_url"]])[0]
        if change == "attachment_parent":
            media["post"] = 99
        elif change == "upload":
            media["date_gmt"] = "2026-05-16T11:37:12"
        elif change == "mime":
            media["mime_type"] = "image/png"
        elif change == "source":
            media["source_url"] = "https://campaign.example/another.mp4"
        elif change == "backlink":
            media["_links"]["wp:attached-to"] = []
        payloads[attachment["attachment_api_url"]] = json.dumps(
            [media] * (11 if change == "unbounded_collection" else 1)
        ).encode()
        attachment["attachment_sha256"] = hashlib.sha256(
            payloads[attachment["attachment_api_url"]]
        ).hexdigest()
    write_json(tmp_path / "data/campaign-native-reviews.json", {"reviews": [review]})
    assert not collect_campaign_native(tmp_path, "2026-10-30", offline=True)["ads"]
    if change != "file_size":
        assert review["media_url"] not in calls


def test_public_dropbox_original_uses_only_standard_download_switch(tmp_path, release_review):
    review, payloads, calls = release_review
    original = "https://www.dropbox.com/scl/fi/public/ad.mp4?rlkey=public-share&dl=0"
    download = "https://www.dropbox.com/scl/fi/public/ad.mp4?rlkey=public-share&dl=1"
    body = payloads[review["publisher_url"]].replace(
        b"https://video.example/ad.mp4", original.replace("&", "&amp;").encode()
    )
    payloads[review["publisher_url"]] = body
    payloads[download] = payloads.pop(review["media_url"])
    review["media_url"] = original
    review["publisher_release"]["sha256"] = hashlib.sha256(body).hexdigest()
    write_json(tmp_path / "data/campaign-native-reviews.json", {"reviews": [review]})
    ad = collect_campaign_native(tmp_path, "2026-10-30", offline=True)["ads"][0]
    assert calls == [review["publisher_url"], download]
    assert ad["segments"][0]["native_campaign_evidence"]["media_url"] == original


@pytest.fixture
def gallery_review(tmp_path, monkeypatch, native_review):
    native_review.pop("post_id")
    native_review.pop("post_timestamp")
    native_review.update(
        publisher_url="https://publisher.example/materials",
        post_url="https://publisher.example/materials",
        media_url="https://static.wixstatic.com/media/original.png",
        media_type="image",
        sponsor="Reviewed outside organization",
        sponsor_type="outside_group",
        required_quotes=["Do not trust the Democratic candidate."],
    )
    item = {
        "itemId": "reviewed-image",
        "createdDate": "2026-10-23T14:19:25.000Z",
        "isSecure": False,
        "mediaUrl": "original.png",
        "metaData": {"name": "original.png"},
    }
    data = {"appsWarmupData": {"gallery-app": {"gallery-data": {"items": [item]}}}}
    markup = (
        '<title>Public campaign materials</title><script id="wix-warmup-data" '
        'type="application/json">' + json.dumps(data) + "</script>"
    ).encode()
    native_review["publisher_gallery"] = {
        "title": "Public campaign materials",
        "sha256": hashlib.sha256(markup).hexdigest(),
        "gallery_id": "gallery-data",
        "item_id": "reviewed-image",
        "created": item["createdDate"],
    }
    alignment_body = b"<p>We support a Republican majority in Congress.</p>"
    native_review["alignment_review"] = {
        "alignment": "R",
        "url": "https://publisher.example/",
        "sha256": hashlib.sha256(alignment_body).hexdigest(),
        "required_quotes": ["We support a Republican majority in Congress."],
    }
    candidates = read_json(tmp_path / "data/site/candidates.json", {})
    candidates["candidates"][0]["party"] = "DEM"
    write_json(tmp_path / "data/site/candidates.json", candidates)
    payloads = {
        native_review["publisher_url"]: markup,
        native_review["alignment_review"]["url"]: alignment_body,
        native_review["media_url"]: b"original",
    }
    calls = []

    def get(self, url, **kwargs):
        calls.append(url)
        return payloads[url], {}

    monkeypatch.setattr("political_ads.campaign_native.Client.get", get)
    monkeypatch.setattr(
        "political_ads.campaign_native.recognize_image",
        lambda *args: (
            native_review["media_sha256"],
            {
                "engine": "fixture",
                "coordinate_system": "normalized",
                "lines": [
                    {
                        "text": native_review["required_quotes"][0],
                        "confidence": 0.9,
                        "bounds": [0.1, 0.2, 0.3, 0.4],
                    }
                ],
            },
        ),
        raising=False,
    )
    write_json(tmp_path / "data/campaign-native-reviews.json", {"reviews": [native_review]})
    return native_review, payloads, calls


def test_public_gallery_image_binds_upload_and_payer_alignment_not_target_party(
    tmp_path, gallery_review
):
    review, _, calls = gallery_review
    result = collect_campaign_native(tmp_path, "2026-10-30", offline=True)
    ad = result["ads"][0]
    assert ad["alignment"] == "R" and ad["race"] == "ZZ-01"
    assert ad["sponsor"] == "Reviewed outside organization"
    assert ad["published"] == "2026-10-23" and ad["date_basis"] == "publisher_gallery_upload_date"
    assert ad["delivery_start"] is None
    assert ad["text"] == "Do not trust the Democratic candidate."
    assert ad["segments"][0]["kind"] == "image_ocr"
    assert ad["segments"][0]["image_bounds"] == [0.1, 0.2, 0.3, 0.4]
    assert calls == [
        review["publisher_url"],
        review["alignment_review"]["url"],
        review["media_url"],
    ]
    assert collect_campaign_native(tmp_path, "2026-10-30", offline=True) == result
    assert len(calls) == 3


@pytest.mark.parametrize(
    "change",
    ["date", "gallery", "item", "title", "hash", "media", "alignment_hash", "alignment_quote"],
)
def test_gallery_image_rejects_unbound_evidence_before_original_request(
    tmp_path, gallery_review, change
):
    review, _, calls = gallery_review
    if change == "date":
        review["publisher_gallery"]["created"] = "2026-10-24T14:19:25.000Z"
    elif change == "gallery":
        review["publisher_gallery"]["gallery_id"] = "different-gallery"
    elif change == "item":
        review["publisher_gallery"]["item_id"] = "different-image"
    elif change == "title":
        review["publisher_gallery"]["title"] = "Different publisher"
    elif change == "hash":
        review["publisher_gallery"]["sha256"] = "0" * 64
    elif change == "media":
        review["media_url"] = "https://static.wixstatic.com/media/unlinked.png"
    elif change == "alignment_hash":
        review["alignment_review"]["sha256"] = "0" * 64
    else:
        review["alignment_review"]["required_quotes"] = ["Not present."]
    write_json(tmp_path / "data/campaign-native-reviews.json", {"reviews": [review]})
    result = collect_campaign_native(tmp_path, "2026-10-30", offline=True)
    assert not result["ads"]
    assert result["attempts"][review["id"]]["state"] == "error"
    assert review["media_url"] not in calls


def test_gallery_upload_after_cutoff_is_not_requested(tmp_path, gallery_review):
    _, _, calls = gallery_review
    assert not collect_campaign_native(tmp_path, "2026-10-22", offline=True)["ads"]
    assert calls == []


@pytest.mark.parametrize("change", ["secure", "video"])
def test_gallery_image_rejects_nonpublic_or_video_items(tmp_path, gallery_review, change):
    review, payloads, calls = gallery_review
    before = b'"isSecure": false' if change == "secure" else b'"name": "original.png"'
    after = b'"isSecure": true' if change == "secure" else b'"type": "video"'
    body = payloads[review["publisher_url"]].replace(before, after)
    payloads[review["publisher_url"]] = body
    review["publisher_gallery"]["sha256"] = hashlib.sha256(body).hexdigest()
    write_json(tmp_path / "data/campaign-native-reviews.json", {"reviews": [review]})
    result = collect_campaign_native(tmp_path, "2026-10-30", offline=True)
    assert not result["ads"]
    assert result["attempts"][review["id"]]["state"] == "error"
    assert calls == [review["publisher_url"]]
