import json
from datetime import date
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


@pytest.mark.parametrize(
    ("as_of", "until", "accepted"),
    [
        ("2026-10-27", "2026-11-04", False),
        ("2026-11-05", "2026-11-04", True),
        ("2026-11-05", "2026-11-05", False),
    ],
)
def test_final_cutoff_never_advances_collection_into_the_future(
    tmp_path, monkeypatch, as_of, until, accepted
):
    class Today(date):
        @classmethod
        def today(cls):
            return date.fromisoformat(as_of)

    monkeypatch.setattr(cli, "date", Today)
    monkeypatch.setattr(
        cli,
        "collect_wordpress",
        lambda *args: ([fixture_ad()], {"source": "dccc", "state": "ok"}),
    )
    if accepted:
        assert cli.collect(tmp_path, until, ["dccc"])["until"] == until
    else:
        with pytest.raises(ValueError, match="final collection cutoff"):
            cli.collect(tmp_path, until, ["dccc"])


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


def test_union_custom_news_body_is_recovered_from_public_acf():
    source = next(s for s in SOURCES if s.id == "ua-vote-pac")

    class UnionArchive:
        def json(self, *args, **kwargs):
            return [
                {
                    "id": 3853,
                    "date": "2026-10-07T08:00:00",
                    "title": {"rendered": "UA Launches Independent Expenditure in PA-1"},
                    "link": source.url + "/news/pa-1/",
                    "acf": {
                        "page_layout": [
                            {
                                "component_wysiwyg": {
                                    "content": "<p>TRANSCRIPT:</p><p>Brian Fitzpatrick "
                                    "will work across party lines to lower costs for "
                                    "working families and protect Pennsylvania jobs.</p>"
                                }
                            }
                        ]
                    },
                }
            ], {}

    candidates = [
        dict(
            candidate_id="H6PA08277",
            name="FITZPATRICK, BRIAN",
            party="REP",
            state="PA",
            office="H",
            district="01",
        )
    ]
    ads, status = collect_wordpress(UnionArchive(), source, "2026-10-26", candidates=candidates)
    assert status["state"] == "ok" and len(ads) == 1
    assert ads[0]["text"].startswith("Brian Fitzpatrick")


def test_empty_veterans_api_body_uses_the_separate_public_script_container():
    source = next(s for s in SOURCES if s.id == "votevets")
    link = source.url + "/press-releases/new-ad/"

    class VeteransArchive:
        def json(self, *args, **kwargs):
            return [
                {
                    "id": 5569,
                    "date": "2026-07-14T08:00:00",
                    "title": {"rendered": "New Ad Holding Ashley Hinson Accountable"},
                    "content": {"rendered": ""},
                    "link": link,
                }
            ], {}

        def get(self, url, **kwargs):
            assert url == link and kwargs["retry"] is False
            return (
                b'<div class="body-content"><div class="wysiwyg-text">'
                b"<p>A separate press statement.</p><p>AD TRANSCRIPT:</p>"
                b"<p>Ashley Hinson should work for Iowa farmers instead of voting "
                b"for higher costs and expensive foreign wars.</p></div></div>"
                b"<nav>Next Post: another campaign's message.</nav>",
                {},
            )

    candidates = [
        dict(
            candidate_id="S6IA00314",
            name="HINSON, ASHLEY",
            party="REP",
            state="IA",
            office="S",
            district="00",
        )
    ]
    ads, status = collect_wordpress(VeteransArchive(), source, "2026-10-26", candidates=candidates)
    assert status["public_html_bodies_recovered"] == 1 and len(ads) == 1
    assert "Next Post" not in ads[0]["text"]
    assert "press statement" not in ads[0]["text"]
    assert ads[0]["segments"][0]["federal_scope_candidate_ids"] == ["S6IA00314"]


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


def test_partial_discovery_merges_new_text_without_erasing_saved_ads(tmp_path, monkeypatch):
    old = fixture_ad()
    new = old | {"id": "dccc-new"}
    cli.write_json(tmp_path / "data/site/corpus.json", {"ads": [old], "sources": []})
    monkeypatch.setattr(
        cli,
        "collect_wordpress",
        lambda *args: ([new], {"source": "dccc", "state": "partial"}),
    )
    result = cli.collect(tmp_path, "2026-10-26", ["dccc"])
    assert {ad["id"] for ad in result["ads"]} == {old["id"], new["id"]}
    assert result["sources"][0]["state"] == "partial"
