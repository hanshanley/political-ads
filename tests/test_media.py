from political_ads.cli import read_json
from political_ads.media import (
    caption_segments,
    collect_media,
    discover,
    inventory_media,
    is_media_ad_release,
    youtube_id,
)
from political_ads.sources import SOURCES


def test_caption_timestamps_do_not_duplicate_window_updates_or_repeated_slogans():
    payload = {
        "events": [
            {"tStartMs": 0, "dDurationMs": 3000, "segs": [{"utf8": "Our"}, {"utf8": " families."}]},
            {"tStartMs": 1000, "segs": [{"utf8": "\n"}]},
            {"tStartMs": 0, "dDurationMs": 3000, "segs": [{"utf8": "Our families."}]},
            {"tStartMs": 4000, "dDurationMs": 2000, "segs": [{"utf8": "Our families."}]},
        ]
    }
    result = caption_segments(payload, "youtube_auto_caption")
    assert [segment["text"] for segment in result] == ["Our families.", "Our families."]
    assert result[0]["start_seconds"] == 0
    assert result[1]["end_seconds"] == 6


def test_custom_media_endpoint_does_not_claim_full_discovery():
    class Partial:
        def json(self, *args, **kwargs):
            return [{"id": 1, "date": "2026-10-01T00:00:00"}], {}

    posts, complete = discover(Partial(), SOURCES[0], "2026-10-26")
    assert len(posts) == 1
    assert not complete


def test_video_id_is_constrained_to_a_public_youtube_link():
    assert youtube_id("https://www.youtube.com/watch?v=5NTptJ2PpMw&feature=share") == "5NTptJ2PpMw"
    assert youtube_id("https://youtu.be/5NTptJ2PpMw") == "5NTptJ2PpMw"
    assert youtube_id("https://youtube.com.evil.example/watch?v=5NTptJ2PpMw") is None
    assert youtube_id("https://youtube.com/watch?feature=share&v=5NTptJ2PpMw") == "5NTptJ2PpMw"
    assert youtube_id("https://youtu.be/5NTptJ2PpMwEXTRA") is None


def test_media_discovery_uses_custom_rest_type_and_acf_content():
    class Posts:
        def json(self, url, **kwargs):
            assert "/wp-json/wp/v2/article?" in url
            return [
                {
                    "id": 1,
                    "date": "2026-10-01",
                    "title": {"rendered": "New Ad"},
                    "link": "https://www.dscc.org/ad/",
                    "acf": {
                        "page_layout": [
                            {
                                "component_wysiwyg": {
                                    "content": '<a href="https://youtu.be/5NTptJ2PpMw">Ad</a>'
                                }
                            }
                        ]
                    },
                }
            ], {"X-WP-TotalPages": "1"}

    posts, complete = discover(Posts(), next(s for s in SOURCES if s.id == "dscc"), "2026-10-26")
    assert complete and "youtu.be" in posts[0]["content"]["rendered"]


def test_only_explicit_slf_ad_release_roundups_bypass_icymi_guard():
    assert is_media_ad_release("ICYMI: SLF Releases New Ads Across the Senate Map", "slf")
    assert not is_media_ad_release("ICYMI: Opponent Discusses Ads in Interview", "slf")
    assert not is_media_ad_release("ICYMI: SLF Releases New Ads Across the Senate Map", "hmp")


def test_rjc_campaign_releases_need_actual_ad_launch_evidence():
    title = "RJC VF Launches Campaign in Michigan Senate Race"
    assert is_media_ad_release(title, "rjc-vf", "<p>Today we released two new ads.</p>")
    assert not is_media_ad_release(title, "rjc-vf", "<p>Join our campaign fundraiser.</p>")
    assert not is_media_ad_release(title, "hmp", "<p>Today we released two new ads.</p>")


def test_cfg_gallery_year_is_not_a_verified_ad_date_or_permission_to_include_older_galleries(
    tmp_path, monkeypatch
):
    markup = (
        b"<p><strong>2026 General Election Ad Gallery</strong></p>"
        b'<div class="robo-gallery-wrap"><div data-popup="https://youtu.be/5NTptJ2PpMw" '
        b'title="Test (LA-06)"></div></div>'
        b"<p><strong>2024 General Election Ad Gallery</strong></p>"
        b'<div class="robo-gallery-wrap"><div data-popup="https://youtu.be/abcdefghijk" '
        b'title="Old (LA-06)"></div></div>'
    )
    monkeypatch.setattr("political_ads.media.Client.get", lambda *a, **k: (markup, {}))
    result = inventory_media(tmp_path, "2026-10-26", ["cfg-action"])
    assert result["sources"][0]["state"] == "ok"
    assert len(result["leads"]) == 1
    lead = result["leads"][0]
    assert lead["state"] == "needs_date_and_text"
    assert lead["releases"][0]["published"] is None


def test_dated_protect_freedom_gallery_excludes_state_and_old_cycle_ads(tmp_path, monkeypatch):
    markup = (
        b'<div class="dmRespCol">John Sununu for U.S. Senate "Liberty" October 8, 2026'
        b'<iframe src="https://youtube.com/embed/5NTptJ2PpMw"></iframe></div>'
        b'<div class="dmRespCol">Candidate for Governor October 8, 2026'
        b'<iframe src="https://youtube.com/embed/abcdefghijk"></iframe></div>'
        b'<div class="dmRespCol">Old Candidate for Congress October 8, 2024'
        b'<iframe src="https://youtube.com/embed/12345678901"></iframe></div>'
    )
    monkeypatch.setattr("political_ads.media.Client.get", lambda *a, **k: (markup, {}))
    result = inventory_media(tmp_path, "2026-10-26", ["protect-freedom"])
    assert len(result["leads"]) == 1
    lead = result["leads"][0]
    assert lead["releases"][0]["published"] == "2026-10-08"
    assert lead["state"] == "pending"


def test_media_backlog_deduplicates_roundup_links_and_preserves_leads_on_failure(
    tmp_path, monkeypatch
):
    def posts(*args):
        return [
            {
                "id": identity,
                "date": "2026-10-01",
                "link": f"https://example.org/ad-{identity}",
                "title": {"rendered": "ICYMI: SLF Releases New Ads Across the Senate Map"},
                "content": {
                    "rendered": '<a href="https://youtu.be/5NTptJ2PpMw">Ad</a>'
                    '<iframe src="https://www.youtube.com/embed/5NTptJ2PpMw"></iframe>'
                },
            }
            for identity in (1, 2)
        ], True

    monkeypatch.setattr("political_ads.media.discover", posts)
    result = inventory_media(tmp_path, "2026-10-26", ["slf"])
    assert len(result["leads"]) == 1
    assert len(result["leads"][0]["releases"]) == 2
    assert result["leads"][0]["state"] == "pending"

    def failed(*args):
        raise ValueError("Access denied")

    monkeypatch.setattr("political_ads.media.discover", failed)
    failed_result = inventory_media(tmp_path, "2026-10-26", ["slf"])
    assert failed_result["leads"] == result["leads"]
    assert failed_result["sources"][0]["state"] == "error"


def test_caption_rate_limit_checkpoints_then_stops_all_sources(tmp_path, monkeypatch):
    def posts(client, source, until):
        assert source.id == "slf", "A rate limit must stop other caption sources too"
        return [
            {
                "id": 1,
                "date": "2026-10-01T00:00:00",
                "link": "https://example.org/ad",
                "title": {"rendered": "New Ad Launch"},
                "content": {
                    "rendered": '<iframe src="https://www.youtube.com/embed/5NTptJ2PpMw"></iframe>'
                },
            }
        ], True

    def limited(*args):
        raise ValueError("HTTP Error 429: Too Many Requests")

    monkeypatch.setattr("political_ads.media.discover", posts)
    monkeypatch.setattr("political_ads.media.fetch_captions", limited)
    collect_media(tmp_path, "2026-10-26", ["slf", "hmp"], 1)
    state = read_json(tmp_path / "data/site/media.json", {})
    assert state["ads"] == []
    assert state["sources"][0]["last_success"] is None
    assert state["sources"][0]["state"] == "error"
    assert "429" in next(iter(state["attempts"].values()))["error"]


def test_saved_caption_is_not_reacquired_when_backfilling_archives(tmp_path, monkeypatch):
    from political_ads.cli import write_json

    ad = {
        "id": "slf-media-1-5NTptJ2PpMw",
        "source": "slf-media",
        "published": "2026-10-01",
        "media_urls": ["https://youtu.be/5NTptJ2PpMw"],
        "text": "Saved exact text",
    }
    write_json(tmp_path / "data/site/media.json", {"ads": [ad], "sources": []})
    monkeypatch.setattr(
        "political_ads.media.discover",
        lambda *args: (
            [
                {
                    "id": 1,
                    "date": "2026-10-01",
                    "link": "https://example.org/ad",
                    "title": {"rendered": "New Ad Launch"},
                    "content": {"rendered": '<a href="https://youtu.be/5NTptJ2PpMw">Watch</a>'},
                }
            ],
            True,
        ),
    )

    def fail(*args):
        raise AssertionError("Saved caption text must not be downloaded again")

    monkeypatch.setattr("political_ads.media.fetch_captions", fail)
    collect_media(tmp_path, "2026-10-26", ["slf"], 1)
    assert read_json(tmp_path / "data/site/media.json", {})["ads"] == [ad]


def test_media_sources_follow_requested_priority(tmp_path, monkeypatch):
    visited = []

    def empty(client, source, until):
        visited.append(source.id)
        return [], True

    monkeypatch.setattr("political_ads.media.discover", empty)
    collect_media(tmp_path, "2026-10-26", ["nunn", "hmp", "slf", "nunn"], 1)
    assert visited == ["nunn", "hmp", "slf"]
