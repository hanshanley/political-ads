import json
from datetime import UTC, datetime
from urllib.error import HTTPError

import pytest

from political_ads.discovery import (
    archive_posts,
    dated_news_posts,
    grothman_release,
    lcv_sitemap_posts,
    nationbuilder_posts,
    news_index_posts,
    rss_posts,
    smp_news_posts,
    squarespace_posts,
    wix_blog_posts,
)
from political_ads.sources import SOURCES


def source(identity):
    return next(s for s in SOURCES if s.id == identity)


@pytest.mark.parametrize("mismatched", [False, True])
def test_reviewed_release_mirror_excludes_calendar_and_uses_publisher_timezone(mismatched):
    class News:
        def get(self, url, **kwargs):
            return (
                f'<meta property="og:url" content="{url if not mismatched else "other"}">'
                '<meta property="article:published_time" content="2026-10-16T00:09:14+00:00">'
                '<div class="elementor-widget-theme-post-title">'
                "<h1>U.S. Rep. Grothman: Releases first campaign ad of 2026 cycle</h1></div>"
                '<div class="elementor-widget-theme-post-content"><div class="post-content">'
                "<p>TRANSCRIPT:</p><p>Only the actual campaign ad script.</p></div></div>"
                '<aside><time datetime="2026-11-03">Next event</time>'
                "Calendar and navigation are not part of this script.</aside>"
            ).encode(), {}

    if mismatched:
        with pytest.raises(ValueError, match="original article metadata"):
            grothman_release(News(), source("grothman"), "2026-10-26")
    else:
        posts, complete = grothman_release(News(), source("grothman"), "2026-10-26")
        assert not complete and len(posts) == 1
        assert posts[0]["date"] == "2026-10-15"
        assert "Calendar" not in posts[0]["content"]["rendered"]


@pytest.mark.parametrize("invalid", [None, "whitespace", "title", "identity", "body"])
def test_wix_blog_uses_original_publication_and_exact_article_body(invalid):
    class News:
        def get(self, url, **kwargs):
            if url.endswith(".xml"):
                return (
                    b'<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
                    b"<url><loc>https://www.julialetlow.com/post/current</loc>"
                    b"<lastmod>2026-10-26</lastmod>"
                    b'<image:image xmlns:image="http://www.google.com/schemas/sitemap-image/1.1">'
                    b"<image:loc>https://images.example.test/photo.png</image:loc></image:image>"
                    b"</url><url><loc>https://www.julialetlow.com/post/old</loc></url></urlset>"
                ), {}
            metadata = {
                "@type": "BlogPosting",
                "url": url if invalid != "identity" else "https://other.example.test/",
                "headline": " \nNew   Ad: Test " if invalid == "whitespace" else "New Ad: Test",
                "datePublished": "2025-12-01T05:00:00Z"
                if url.endswith("/old")
                else "2026-06-09T05:00:00Z",
                "dateModified": "2026-10-26T05:00:00Z",
            }
            heading = "Wrong article" if invalid == "title" else metadata["headline"]
            return (
                f'<script type="application/ld+json">{json.dumps(metadata)}</script>'
                '<article data-hook="post">'
                f'<h1 data-hook="post-title">{heading}</h1>'
                f'<section data-hook="{"other" if invalid == "body" else "post-description"}">'
                "<p>TRANSCRIPT:</p><p>Only actual ad text belongs here.</p></section></article>"
                "<aside>Recent posts and navigation must not become ad text.</aside>"
            ).encode(), {}

    if invalid not in {None, "whitespace"}:
        with pytest.raises(ValueError, match="matching publication metadata|exact title"):
            wix_blog_posts(News(), source("letlow"), "2026-10-26")
    else:
        posts, complete = wix_blog_posts(News(), source("letlow"), "2026-10-26")
        assert complete and len(posts) == 1
        assert posts[0]["title"]["rendered"] == "New Ad: Test"
        assert posts[0]["date"] == "2026-06-09"
        assert "Only actual ad text" in posts[0]["content"]["rendered"]
        assert "navigation" not in posts[0]["content"]["rendered"]


def test_smp_news_uses_published_form_pagination_and_stops_at_prior_year():
    calls = []

    class News:
        def get(self, url, **kwargs):
            calls.append((url, kwargs.get("data")))
            if "/news/new-ad" in url:
                return b"<main><article><p>Ad copy here.</p></article></main>", {}
            older = "admin-ajax" in url
            date = "December 20, 2025" if older else "October 20, 2026"
            identity = "1" if older else "2"
            return (
                f'<article class="news_cards--element">'
                f'<div class="news_cards--metadata">{date} | Release subtitle</div>'
                f'<a class="news_cards--title-wrapper" id="{identity}" '
                f'href="/news/new-ad-{identity}/">New Ad: Test</a></article>'
                '<article class="news_cards--element">'
                '<a class="news_cards--title-wrapper" id="3" '
                'href="/news/poll/">Our latest polling results</a></article>'
                '<button id="more_posts">View more</button>'
            ).encode(), {}

    posts, complete = smp_news_posts(News(), source("smp"), "2026-10-26")
    assert complete and len(posts) == 1
    assert posts[0]["id"] == 2 and posts[0]["date"] == "2026-10-20"
    assert calls[-1][1] == b"pageNumber=2&ppp=5&action=more_post_ajax"


def test_form_post_cache_does_not_collide_with_get_or_other_pages(tmp_path, monkeypatch):
    from political_ads.http import Client

    requests = []

    class Response:
        headers = {}

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def read(self):
            return requests[-1] or b"GET"

    def open_request(request, **kwargs):
        requests.append(request.data)
        return Response()

    monkeypatch.setattr("political_ads.http.urlopen", open_request)
    client = Client(tmp_path)
    for data in (None, b"page=2", b"page=3"):
        assert client.get("https://example.test/", data=data)[0] == (data or b"GET")
    offline = Client(tmp_path, offline=True)
    assert offline.get("https://example.test/", data=b"page=2")[0] == b"page=2"
    assert requests == [None, b"page=2", b"page=3"]


def test_lcv_sitemap_uses_actual_article_title_and_publication_not_modified_date(monkeypatch):
    waits = []
    monkeypatch.setattr("political_ads.discovery.sleep", waits.append)

    class News:
        def get(self, url, **kwargs):
            if url.endswith(".xml"):
                return (
                    b'<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
                    b"<url><loc>https://www.lcvvictoryfund.org/news/current/</loc>"
                    b"<lastmod>2026-10-26</lastmod></url>"
                    b"<url><loc>https://www.lcvvictoryfund.org/news/updated-old/</loc>"
                    b"<lastmod>2026-10-26</lastmod></url></urlset>"
                ), {}
            day = "October 25, 2024" if "updated-old" in url else "October 20, 2026"
            return (
                '<main><h1>Latest News</h1><article id="post-42" class="race-nc-11">'
                '<h1 class="news-title">Actual release title</h1>'
                f'<div class="news-title-date"><span>{day}</span>'
                "<h2>Actual release title</h2></div>"
                '<div class="news-content"><p>Script below</p></div></article></main>'
            ).encode(), {}

    posts, complete = lcv_sitemap_posts(News(), source("lcv-vf"), "2026-10-26")
    assert complete and len(posts) == 1
    assert posts[0]["date"] == "2026-10-20"
    assert posts[0]["title"]["rendered"] == "Actual release title"
    assert posts[0]["publisher_classes"] == ["race-nc-11"]
    assert waits == [10, 10]


def test_nationbuilder_archive_follows_dates_and_does_not_confuse_ceo_quotes_with_scripts():
    from political_ads.sources import parse_post

    class News:
        def get(self, url, **kwargs):
            if "/news" not in url:
                return (
                    b'<div id="intro"><div class="content"><p>Our CEO said:</p>'
                    b"<blockquote><p>This is commentary about our new advertisement and "
                    b"not the actual words spoken by its narrator.</p></blockquote></div></div>",
                    {},
                )
            second = "?page=2" in url
            day = "December 20, 2025" if second else "October 20, 2026"
            next_link = "" if second else '<a href="/news?page=2">Next</a>'
            return (
                f'<div class="page-excerpt" id="blog-post-page-{2 if second else 1}">'
                f'<h3><a href="/actual-ad-{int(second)}">'
                "New Ad Campaign in PA-01</a></h3>"
                f'<div class="byline">{day}</div></div>{next_link}'
            ).encode(), {}

    posts, complete = nationbuilder_posts(News(), source("rjc-vf"), "2026-10-26")
    assert complete and len(posts) == 1
    assert posts[0]["id"] == "1"
    assert parse_post(posts[0], source("rjc-vf"), "2026-10-26") == []


def test_nationbuilder_campaign_headline_requires_ad_evidence_in_its_excerpt():
    class News:
        def get(self, url, **kwargs):
            if "/news" not in url:
                return b'<div id="intro"><div class="content">Released two new ads.</div></div>', {}
            return (
                b'<div class="page-excerpt" id="blog-post-page-1">'
                b'<h3><a href="/campaign">Launches Campaign in Michigan Senate Race</a></h3>'
                b'<div class="byline">October 7, 2026</div><p>Released two new ads.</p></div>'
                b'<div class="page-excerpt" id="blog-post-page-2">'
                b'<h3><a href="/fundraiser">Campaign Fundraiser in Michigan</a></h3>'
                b'<div class="byline">October 7, 2026</div><p>Join our event.</p></div>'
            ), {}

    posts, _ = nationbuilder_posts(News(), source("rjc-vf"), "2026-10-26")
    assert len(posts) == 1 and posts[0]["id"] == "1"


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


def test_clf_archive_follows_actual_next_url_without_next_css_class():
    class Archive:
        def get(self, url, **kwargs):
            if url.endswith("/new-ad/"):
                return b'<div class="entry-content"><p>Transcript: Actual ad copy.</p></div>', {}
            second = "/page/2/" in url
            third = "/page/3/" in url
            title = "New ad" if second else "Primary results"
            day = "December 20, 2025" if third else "October 20, 2026"
            identity = 3 if third else 2 if second else 1
            return (
                f'<article class="feed-card" id="post-{identity}">'
                f'<a class="post-link" href="/{"new-ad" if second else f"results-{identity}"}/">'
                f'<h2 class="entry-title">{title}</h2></a><time>{day}</time></article>'
                f'<a class="page-link" href="/press/page/{identity + 1}/">next</a>'
                '<a class="page-link" href="https://other.example/press/page/2/">Other</a>'
            ).encode(), {}

    posts, complete = archive_posts(Archive(), source("clf"), "2026-10-26")
    assert complete and [post["id"] for post in posts] == [2]
    assert "Actual ad copy" in posts[0]["content"]["rendered"]
    assert archive_posts(Archive(), source("clf"), "2026-10-26", max_pages=1) == ([], False)


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


def test_rendered_press_dates_are_read_without_claiming_full_historical_coverage():
    class Press:
        def get(self, url, **kwargs):
            if url.endswith("/news/ad"):
                return b"<main><h1>New ad</h1><p>Transcript:</p></main>", {}
            return (
                b'<a class="press__row" href="/news/ad">'
                b'<div class="press__date">October 21, 2026</div>'
                b"<h2>New ad</h2></a>",
                {},
            )

    posts, complete = dated_news_posts(Press(), source("marshall"), "2026-10-26")
    assert not complete
    assert len(posts) == 1 and posts[0]["date"] == "2026-10-21"
    assert dated_news_posts(Press(), source("marshall"), "2026-10-20") == ([], False)


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
