from datetime import UTC, datetime
from urllib.error import HTTPError

import pytest

from political_ads.discovery import (
    archive_posts,
    dated_news_posts,
    news_index_posts,
    rss_posts,
    squarespace_posts,
)
from political_ads.sources import SOURCES


def source(identity):
    return next(s for s in SOURCES if s.id == identity)


def rss(link="https://www.nrcc.org/ad", published="Mon, 26 Oct 2026 12:00:00 +0000"):
    return (
        '<rss xmlns:content="http://purl.org/rss/1.0/modules/content/"><channel>'
        f"<item><link>{link}</link><pubDate>{published}</pubDate>"
        "<title>New campaign ad</title><content:encoded><![CDATA["
        "<p>Transcript:</p><p>Exact publisher script.</p>"
        "]]></content:encoded></item></channel></rss>"
    ).encode()


def test_rss_full_body_date_scope_and_normal_pagination_end():
    class Feed:
        def get(self, url, **kwargs):
            if "paged=2" in url:
                raise HTTPError(url, 404, "end", {}, None)
            return rss(), {}

    posts, complete = rss_posts(Feed(), source("nrcc"), "2026-10-26", "transcript")
    assert complete and len(posts) == 1
    assert posts[0]["date"] == "2026-10-26"
    assert "Exact publisher script" in posts[0]["content"]["rendered"]
    assert rss_posts(Feed(), source("nrcc"), "2026-10-25", "transcript") == ([], True)


def test_rss_repeated_pages_or_access_errors_are_not_empty_successes():
    class Repeated:
        def get(self, *args, **kwargs):
            return rss(), {}

    with pytest.raises(ValueError, match="repeated"):
        rss_posts(Repeated(), source("nrcc"), "2026-10-26", "ad")

    class Denied:
        def get(self, url, **kwargs):
            raise HTTPError(url, 403, "denied", {}, None)

    with pytest.raises(HTTPError):
        rss_posts(Denied(), source("nrcc"), "2026-10-26", "ad")
    with pytest.raises(ValueError, match="different publisher"):
        rss_posts(
            type("Other", (), {"get": lambda *a, **k: (rss("https://other.org/ad"), {})})(),
            source("nrcc"),
            "2026-10-26",
            "ad",
        )


def test_hmp_archive_backfills_beyond_recent_index_with_stable_ids():
    class Archive:
        def get(self, url, **kwargs):
            if "/news/first" in url or "/news/second" in url:
                return (
                    b'<div id="gutenberg"><a href="https://youtu.be/5NTptJ2PpMw">Ad</a></div>',
                    {},
                )
            second = "pg=2" in url
            name = "second" if second else "first"
            identity = "12" if second else "11"
            next_link = (
                ""
                if second
                else '<a href="https:///www.thehousemajoritypac.com/news?pg=2">Load more</a>'
            )
            return (
                f'<main><div><h2 class="heading"><a aria-describedby="readmore-{identity}" '
                f'href="https://www.thehousemajoritypac.com/news/{name}">New ads</a></h2>'
                f"<time>October 20, 2026</time></div>{next_link}</main>"
            ).encode(), {}

    posts, complete = archive_posts(Archive(), source("hmp"), "2026-10-26")
    assert complete and [p["id"] for p in posts] == [11, 12]
    assert "youtu.be" in posts[1]["content"]["rendered"]
    partial, complete = archive_posts(Archive(), source("hmp"), "2026-10-26", max_pages=1)
    assert not complete and len(partial) == 1


def test_archive_schema_failure_does_not_silently_claim_completion():
    class Empty:
        def get(self, *args, **kwargs):
            return b"<html><h1>Try again later</h1></html>", {}

    with pytest.raises(ValueError, match="expected release cards"):
        archive_posts(Empty(), source("hmp"), "2026-10-26")


def test_public_squarespace_json_follows_offset_and_publisher_timezone():
    class News:
        def json(self, url, **kwargs):
            second = "offset=next" in url
            assert url.endswith("format=json")
            timestamp = (
                datetime(2026, 1, 1, 2, tzinfo=UTC)
                if second
                else datetime(2026, 10, 2, 12, tzinfo=UTC)
            )
            return {
                "website": {"timeZone": "America/New_York"},
                "items": [
                    {
                        "id": "old" if second else "new",
                        "publishOn": timestamp.timestamp() * 1000,
                        "fullUrl": "/news/new-ad",
                        "title": "New campaign ad",
                        "body": "<p>Exact script.</p>",
                    }
                ],
                "pagination": {"nextPage": True, "nextPageUrl": "/news?offset=next"},
            }, {}

    posts, complete = squarespace_posts(News(), source("rogers"), "2026-10-26")
    assert complete and len(posts) == 1
    assert posts[0]["date"] == "2026-10-02"
    assert posts[0]["link"] == "https://rogersforsenate.com/news/new-ad"


def test_public_squarespace_repeated_ids_do_not_claim_complete():
    class Repeated:
        def json(self, *args, **kwargs):
            return {
                "items": [
                    {
                        "id": "same",
                        "publishOn": datetime(2026, 10, 2, tzinfo=UTC).timestamp() * 1000,
                        "fullUrl": "/news/ad",
                        "title": "New ad",
                        "body": "<p>Script.</p>",
                    }
                ],
                "pagination": {"nextPage": True, "nextPageUrl": "/news?offset=ignored"},
            }, {}

    with pytest.raises(ValueError, match="repeated IDs"):
        squarespace_posts(Repeated(), source("rogers"), "2026-10-26")


def test_squarespace_media_collection_accepts_explicit_previous_page_only_at_end():
    class Media:
        def json(self, url, **kwargs):
            assert url == source("lacore").url + "/media?format=json"
            return {
                "items": [],
                "pagination": {"prevPage": True, "pageSize": 20},
            }, {}

    assert squarespace_posts(Media(), source("lacore"), "2026-10-26") == ([], True)


def test_dated_news_cards_follow_pagination_and_ignore_embedded_external_links():
    class News:
        def get(self, url, **kwargs):
            if url.endswith("/news/ad"):
                return b"<main><h1>New ad</h1><p>Exact publisher script.</p></main>", {}
            if url.endswith("/news/page/2/"):
                return (
                    b'<a href="/news/old"><h2>Old ad</h2>'
                    b'<time datetime="2025-12-01">December 1, 2025</time></a>',
                    {},
                )
            return (
                b'<div><h4>New ad</h4><a href="https://outside.org">Quoted coverage</a>'
                b'<a class="read-more" href="/news/ad">Read more</a>'
                b'<time datetime="2026-10-02">October 2, 2026</time></div>'
                b'<a class="next" href="/news/page/2/">Next</a>',
                {},
            )

    posts, complete = dated_news_posts(News(), source("jackson"), "2026-10-26")
    assert complete and len(posts) == 1
    assert posts[0]["link"] == source("jackson").url + "/news/ad"
    assert posts[0]["date"] == "2026-10-02"
    assert dated_news_posts(News(), source("jackson"), "2026-10-26", max_pages=1)[1] is False


def test_dated_news_rejects_homepage_fallback_instead_of_manufacturing_ad_text():
    class Fallback:
        def get(self, url, **kwargs):
            if url.endswith("/news/ad"):
                return b"<main><h1>Welcome to the campaign</h1></main>", {}
            return (
                b'<a href="/news/ad"><h2>New ad</h2>'
                b'<time datetime="2026-10-02">October 2, 2026</time></a>',
                {},
            )

    with pytest.raises(ValueError, match="fallback"):
        dated_news_posts(Fallback(), source("el-sayed"), "2026-10-26")


def test_rendered_campaign_index_keeps_only_in_scope_first_party_releases():
    class Index:
        def get(self, url, **kwargs):
            if url.endswith("/news/new"):
                return b"<main><p>Exact ad text.</p></main>", {}
            assert url.endswith("/news/")
            return (
                b'<a href="/news/new"><p>Breaking News</p><p>Oct 2, 2026</p><h1>New ad</h1></a>'
                b'<a href="/news/new"><p>Oct 2, 2026</p><h1>New ad</h1></a>'
                b'<a href="/news/old"><p>Dec 2, 2025</p><h1>Old ad</h1></a>'
                b'<a href="https://other.org/story"><h1>Outside coverage</h1></a>'
            ), {}

    posts, complete = news_index_posts(Index(), source("turek"), "2026-10-26")
    assert complete and len(posts) == 1
    assert posts[0]["date"] == "2026-10-02"
    assert posts[0]["content"]["rendered"] == "<main><p>Exact ad text.</p></main>"
