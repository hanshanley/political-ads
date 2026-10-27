import hashlib
from datetime import datetime, timezone
from urllib.error import HTTPError
from urllib.parse import urlencode

import pytest

from political_ads.campaign_native import collect_campaign_native
from political_ads.cli import read_json, write_json


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


def test_native_denial_is_not_retried_on_later_runs(tmp_path, native_review, monkeypatch):
    requests = []

    def denied(self, url, **kwargs):
        requests.append(url)
        raise HTTPError(url, 403, "Forbidden", {}, None)

    monkeypatch.setattr("political_ads.campaign_native.Client.get", denied)
    first = collect_campaign_native(tmp_path, "2026-10-27")
    second = collect_campaign_native(tmp_path, "2026-10-27")
    assert len(requests) == 1
    assert first["ads"] == second["ads"] == []
    assert "403" in second["sources"][0]["error"]


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
