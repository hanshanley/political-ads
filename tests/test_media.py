from political_ads.cli import read_json
from political_ads.media import caption_segments, collect_media, discover, youtube_id
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
