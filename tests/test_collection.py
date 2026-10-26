import json
from urllib.error import HTTPError

import pytest

from political_ads import cli
from political_ads.http import Client
from political_ads.sources import SOURCES, collect_wordpress, parse_post


def fixture_ad():
    return parse_post(
        {
            "id": 12,
            "title": {"rendered": "New ad for PA-10"},
            "content": {
                "rendered": "<p>Transcript:</p><p>We should protect health care for "
                "our families and fight for the people who work hard every day.</p>"
            },
            "date": "2026-10-01T12:00:00",
            "link": "https://dccc.org/test-ad/",
        },
        SOURCES[1],
        "2026-10-01",
    )[0]


def test_failed_source_keeps_last_good_partition_and_freshness(tmp_path, monkeypatch):
    ad = fixture_ad()
    cli.write_json(
        tmp_path / "data/site/corpus.json",
        {
            "ads": [ad],
            "sources": [{"source": "dccc", "last_success": "2026-10-01"}],
        },
    )
    monkeypatch.setattr(
        cli,
        "collect_wordpress",
        lambda *args: (
            [],
            {
                "source": "dccc",
                "state": "error",
                "error": "timeout",
            },
        ),
    )
    snapshot = cli.collect(tmp_path, "2026-10-26", ["dccc"])
    assert snapshot["ads"] == [ad]
    assert snapshot["sources"][0]["last_success"] == "2026-10-01"
    assert snapshot["sources"][0]["retained_ads"] == 1


def test_repeated_page_is_failure_not_complete_or_empty():
    class RepeatedPages:
        def json(self, *args, **kwargs):
            return [
                {
                    "id": 1,
                    "date": "2026-10-01T00:00:00",
                    "title": {"rendered": "News"},
                    "content": {"rendered": ""},
                    "link": "https://example.org/news",
                }
            ], {"X-WP-TotalPages": "2"}

    ads, status = collect_wordpress(RepeatedPages(), SOURCES[1], "2026-10-26")
    assert not ads
    assert status["state"] == "error"
    assert "repeated" in status["error"]


def test_client_retries_rate_limit_but_not_unauthorized(tmp_path, monkeypatch):
    sleeps = []
    calls = []

    def fail(*args, **kwargs):
        calls.append(1)
        raise HTTPError("https://example.org", 429, "rate limit", {"Retry-After": "1"}, None)

    monkeypatch.setattr("political_ads.http.urlopen", fail)
    monkeypatch.setattr("political_ads.http.time.sleep", sleeps.append)
    with pytest.raises(HTTPError):
        Client(tmp_path).get("https://example.org")
    assert len(calls) == 3 and sleeps == [1, 1]

    def unauthorized(*args, **kwargs):
        calls.append(1)
        raise HTTPError("https://example.org", 401, "unauthorized", {}, None)

    monkeypatch.setattr("political_ads.http.urlopen", unauthorized)
    with pytest.raises(HTTPError):
        Client(tmp_path).get("https://example.org")
    assert len(calls) == 4
    assert not list(tmp_path.glob("*.body"))


def test_first_observation_survives_unchanged_refresh(tmp_path, monkeypatch):
    ad = fixture_ad()
    cli.write_json(tmp_path / "data/site/corpus.json", {"ads": [ad], "sources": []})
    monkeypatch.setattr(
        cli,
        "collect_wordpress",
        lambda *args: (
            [
                ad
                | {
                    "observed": "2026-10-26",
                }
            ],
            {"source": "dccc", "state": "ok"},
        ),
    )
    cli.collect(tmp_path, "2026-10-26", ["dccc"])
    stored = json.loads((tmp_path / "data/site/corpus.json").read_text())
    assert stored["ads"][0]["observed"] == "2026-10-01"
