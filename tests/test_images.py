import hashlib

import pytest

from political_ads.cli import load_corpus, write_json
from political_ads.images import collect_images, image_leads, reviewed_image_ad


def image_post():
    return {
        "id": "test",
        "link": "https://www.nrcc.org/2026/07/30/new-ad/",
        "date": "2026-07-30",
        "title": {"rendered": "New Ad Campaign in CA-45"},
        "content": {
            "rendered": "<p>Today we launched a paid digital advertising campaign.</p>"
            '<img src="https://www.nrcc.org/wp-content/uploads/2026/07/ad.png">'
        },
    }


def test_image_discovery_requires_paid_ad_release_and_rejects_linked_video_thumbnails():
    post = image_post()
    post["content"]["rendered"] += (
        '<a href="https://youtu.be/5NTptJ2PpMw">'
        '<img src="https://www.nrcc.org/wp-content/uploads/2026/07/thumb.png"></a>'
        '<img src="https://outside.example/image.png">'
    )
    leads = image_leads([post, post])
    assert len(leads) == 1 and leads[0]["image_url"].endswith("/ad.png")
    post["content"]["rendered"] = post["content"]["rendered"].replace(
        "paid digital advertising campaign", "press conference"
    )
    assert image_leads([post]) == []


def test_review_gate_binds_exact_image_and_release_and_preserves_ocr_evidence():
    lead = image_leads([image_post()])[0]
    ocr = {
        "engine": "Local OCR",
        "coordinate_system": "normalized bottom-left",
        "lines": [
            {"text": "CHINA FIRST.", "confidence": 0.9, "bounds": [0.1, 0.8, 0.5, 0.1]},
            {"text": "AMERICAN WORKERS LAST.", "confidence": 0.8, "bounds": [0.1, 0.6, 0.5, 0.1]},
        ],
    }
    review = {
        "state": "approved_image_ad",
        "source_url": lead["post"]["link"],
        "image_hash": "image-hash",
        "race": "CA-45",
    }
    ad = reviewed_image_ad(lead, ocr, review, "image-hash", "2026-10-26")
    assert ad["text"] == "CHINA FIRST.\nAMERICAN WORKERS LAST."
    assert ad["segments"][0]["image_bounds"] == [0.1, 0.8, 0.5, 0.1]
    assert ad["segments"][0]["image_hash"] == "image-hash"
    assert ad["race"] == "CA-45"
    for changed in (
        {"image_hash": "changed"},
        {"source_url": "https://www.nrcc.org/other"},
        {"state": "rejected_video_thumbnail"},
    ):
        with pytest.raises(ValueError):
            reviewed_image_ad(lead, ocr, review | changed, "image-hash", "2026-10-26")


def test_unreviewed_ocr_is_retained_for_review_but_never_counted(tmp_path, monkeypatch):
    post = image_post()
    body = b"fixture image"
    image_hash = hashlib.sha256(body).hexdigest()
    monkeypatch.setattr("political_ads.images.rss_posts", lambda *a: ([post], True))
    monkeypatch.setattr("political_ads.images.Client.get", lambda *a, **k: (body, {}))
    write_json(
        tmp_path / f"data/media/nrcc-images/{image_hash}.ocr.json",
        {"engine": "test", "lines": [{"text": "Words in image"}]},
    )
    result = collect_images(tmp_path, "2026-10-26", offline=True)
    assert not result["ads"]
    assert result["sources"][0]["unreviewed_images"] == 1
    assert (tmp_path / "data/raw/nrcc-image-review.json").exists()
    write_json(
        tmp_path / "data/site/corpus.json", {"until": "2026-10-26", "ads": [], "sources": []}
    )
    assert not load_corpus(tmp_path)["ads"]
