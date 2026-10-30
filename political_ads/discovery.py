from __future__ import annotations

import json
import re
import xml.etree.ElementTree as ET
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from time import sleep
from urllib.error import HTTPError
from urllib.parse import urlencode, urljoin, urlparse
from zoneinfo import ZoneInfo

from bs4 import BeautifulSoup

from political_ads.http import Client
from political_ads.schema import START, digest
from political_ads.sources import Source, is_ad_release


def rss_posts(
    client: Client, source: Source, until: str, search: str, max_pages: int = 100
) -> tuple[list[dict], bool]:
    posts = []
    seen = set()
    for page in range(1, max_pages + 1):
        query = urlencode({"s": search, "feed": "rss2", "year": "2026", "paged": page})
        try:
            body, _ = client.get(source.url + "/?" + query, refresh=True)
        except HTTPError as error:
            if error.code == 404 and page > 1:
                return posts, True
            raise
        try:
            root = ET.fromstring(body)
        except ET.ParseError as error:
            raise ValueError("The public feed did not return valid RSS") from error
        if root.tag != "rss" or root.find("channel") is None:
            raise ValueError("The public feed did not return an RSS channel")
        items = root.findall("./channel/item")
        if not items:
            return posts, True
        for item in items:
            link = item.findtext("link")
            if not link or link in seen:
                raise ValueError("Public feed repeated or omitted a release URL")
            if urlparse(link).hostname != urlparse(source.url).hostname:
                raise ValueError("Public feed linked to a different publisher")
            seen.add(link)
            published = parsedate_to_datetime(item.findtext("pubDate", "")).date().isoformat()
            if START <= published <= until:
                posts.append(
                    {
                        "id": digest(link)[:16],
                        "link": link,
                        "date": published,
                        "title": {"rendered": item.findtext("title", "")},
                        "content": {
                            "rendered": item.findtext(
                                "{http://purl.org/rss/1.0/modules/content/}encoded",
                                item.findtext("description", ""),
                            )
                        },
                    }
                )
    return posts, False


def archive_posts(
    client: Client, source: Source, until: str, max_pages: int = 100
) -> tuple[list[dict], bool]:
    posts = []
    seen = set()
    hmp = source.id in {"hmp", "hmf"}
    for page in range(1, max_pages + 1):
        path = f"/news?pg={page}" if hmp else ("/press/" if page == 1 else f"/press/page/{page}/")
        body, _ = client.get(source.url + path, refresh=True)
        soup = BeautifulSoup(body, "html.parser")
        cards = soup.select("h2.heading") if hmp else soup.select("article.feed-card")
        if not cards:
            raise ValueError("Public archive did not expose the expected release cards")
        older = False
        for card in cards:
            container = card.parent if hmp else card
            anchor = card.find("a") if hmp else card.select_one("a.post-link")
            time = container.find("time")
            if not anchor or not time:
                raise ValueError("Public archive release has no link or date")
            published = datetime.strptime(time.get_text(strip=True), "%B %d, %Y").date().isoformat()
            older |= published < START
            link = urljoin(source.url, anchor["href"])
            if urlparse(link).hostname != urlparse(source.url).hostname:
                raise ValueError("Public archive linked to a different publisher")
            if link in seen:
                raise ValueError("Public archive repeated release URLs across pages")
            seen.add(link)
            heading = card if hmp else card.select_one(".entry-title")
            if heading is None:
                raise ValueError("Public archive release has no title")
            title = heading.get_text(" ", strip=True)
            if not START <= published <= until or not is_ad_release(title):
                continue
            release, _ = client.get(link, refresh=True)
            article = BeautifulSoup(release, "html.parser")
            content = article.select_one("#gutenberg" if hmp else ".entry-content")
            if content is None:
                raise ValueError("Public ad release has no expected article body")
            raw_id = anchor.get("aria-describedby", "") if hmp else card.get("id", "")
            identity = re.search(r"(?:readmore|post)-(\d+)$", raw_id)
            if not identity:
                raise ValueError("Public archive has no stable publisher record ID")
            posts.append(
                {
                    "id": int(identity[1]),
                    "link": link,
                    "date": published,
                    "title": {"rendered": title},
                    "content": {"rendered": str(content)},
                }
            )
        if older:
            return posts, True
        next_page = (
            any(f"pg={page + 1}" in a.get("href", "") for a in soup.find_all("a"))
            if hmp
            else any(
                urljoin(source.url, a.get("href", "")).rstrip("/")
                == f"{source.url.rstrip('/')}/press/page/{page + 1}"
                for a in soup.find_all("a", href=True)
            )
        )
        if not next_page:
            return posts, True
    return posts, False


def public_posts(client: Client, source: Source, until: str) -> tuple[list[dict], bool]:
    if source.discovery == "smp_news":
        return smp_news_posts(client, source, until)
    if source.discovery == "lcv_sitemap":
        return lcv_sitemap_posts(client, source, until)
    if source.discovery == "nationbuilder":
        return nationbuilder_posts(client, source, until)
    if source.discovery == "rss":
        return rss_posts(client, source, until, source.search)
    if source.discovery == "archive":
        return archive_posts(client, source, until)
    if source.discovery == "squarespace":
        return squarespace_posts(client, source, until)
    if source.discovery == "news_index":
        return news_index_posts(client, source, until)
    if source.discovery == "dated_news":
        return dated_news_posts(client, source, until)
    if source.discovery == "wix_blog":
        return wix_blog_posts(client, source, until)
    if source.discovery == "grothman_release":
        return grothman_release(client, source, until)
    raise ValueError(f"Unknown public discovery strategy: {source.discovery}")


def wix_blog_posts(client: Client, source: Source, until: str) -> tuple[list[dict], bool]:
    body, _ = client.get(source.url + "/blog-posts-sitemap.xml", refresh=True, retry=False)
    try:
        root = ET.fromstring(body)
    except ET.ParseError as error:
        raise ValueError("Public blog sitemap did not return valid XML") from error
    if root.tag.rsplit("}", 1)[-1] != "urlset":
        raise ValueError("Public blog sitemap did not return a URL set")
    posts = []
    seen = set()
    for location in root.findall("./{*}url/{*}loc"):
        link = location.text or ""
        if urlparse(link).hostname != urlparse(source.url).hostname or link in seen:
            raise ValueError("Public blog sitemap repeated a URL or changed publisher")
        seen.add(link)
        release, _ = client.get(link, refresh=True, retry=False)
        soup = BeautifulSoup(release, "html.parser")
        metadata = [
            item
            for node in soup.select('script[type="application/ld+json"]')
            if isinstance(item := json.loads(node.get_text()), dict)
            and item.get("@type") == "BlogPosting"
            and item.get("url") == link
        ]
        if len(metadata) != 1:
            raise ValueError("Public blog release lacks matching publication metadata")
        published = datetime.fromisoformat(metadata[0]["datePublished"]).date().isoformat()
        title = re.sub(r"\s+", " ", metadata[0]["headline"]).strip()
        if not START <= published <= until or not is_ad_release(title):
            continue
        content = soup.select_one('article[data-hook="post"] [data-hook="post-description"]')
        heading = soup.select_one('article[data-hook="post"] h1[data-hook="post-title"]')
        if content is None or heading is None or plain_title(heading) != title:
            raise ValueError("Public blog release lacks its exact title or article body")
        posts.append(
            {
                "id": digest(link)[:16],
                "link": link,
                "date": published,
                "title": {"rendered": title},
                "content": {"rendered": str(content)},
            }
        )
    return posts, True


def grothman_release(client: Client, source: Source, until: str) -> tuple[list[dict], bool]:
    link = source.url + source.index_path
    body, _ = client.get(link, refresh=True, retry=False)
    soup = BeautifulSoup(body, "html.parser")
    canonical = soup.select_one('meta[property="og:url"]')
    published = soup.select_one('meta[property="article:published_time"]')
    heading = soup.select_one(".elementor-widget-theme-post-title h1")
    content = soup.select_one(".elementor-widget-theme-post-content .post-content")
    if (
        canonical is None
        or canonical.get("content") != link
        or published is None
        or heading is None
        or content is None
        or not plain_title(heading).startswith("U.S. Rep. Grothman:")
    ):
        raise ValueError("Reviewed campaign-release mirror lacks its original article metadata")
    day = (
        datetime.fromisoformat(published["content"])
        .astimezone(ZoneInfo("America/Chicago"))
        .date()
        .isoformat()
    )
    posts = []
    if START <= day <= until and is_ad_release(plain_title(heading)):
        posts.append(
            {
                "id": digest(link)[:16],
                "link": link,
                "date": day,
                "title": {"rendered": plain_title(heading)},
                "content": {"rendered": str(content)},
            }
        )
    # This reviewed public original is not an exhaustive search of the mirror.
    return posts, False


def smp_news_posts(
    client: Client, source: Source, until: str, max_pages: int = 100
) -> tuple[list[dict], bool]:
    posts = []
    seen = set()
    for page in range(1, max_pages + 1):
        if page == 1:
            body, _ = client.get(source.url + "/news/", refresh=True, retry=False)
        else:
            body, _ = client.get(
                source.url + "/wp-admin/admin-ajax.php",
                refresh=True,
                retry=False,
                data=urlencode({"pageNumber": page, "ppp": 5, "action": "more_post_ajax"}).encode(),
            )
        soup = BeautifulSoup(body, "html.parser")
        cards = soup.select("article.news_cards--element")
        if not cards:
            if page > 1 and not body.strip():
                return posts, True
            raise ValueError("SMP archive did not expose expected news cards")
        older = False
        for card in cards:
            anchor = card.select_one("a.news_cards--title-wrapper")
            label = card.select_one(".news_cards--metadata")
            if (
                label is None
                and anchor is not None
                and not is_ad_release(anchor.get_text(" ", strip=True))
            ):
                continue
            if anchor is None or label is None or not anchor.get("id", "").isdigit():
                raise ValueError("SMP card lacks a stable ID or date")
            published = (
                datetime.strptime(
                    label.get_text(" ", strip=True).split("|", 1)[0].strip(), "%B %d, %Y"
                )
                .date()
                .isoformat()
            )
            older |= published < START
            link = urljoin(source.url, anchor["href"])
            if urlparse(link).hostname != urlparse(source.url).hostname or link in seen:
                raise ValueError("SMP archive repeated a URL or linked outside its publisher")
            seen.add(link)
            title = anchor.get_text(" ", strip=True)
            if not START <= published <= until or not is_ad_release(title):
                continue
            release, _ = client.get(link, refresh=True, retry=False)
            article = BeautifulSoup(release, "html.parser").find("article")
            if article is None:
                raise ValueError("SMP release has no article body")
            posts.append(
                {
                    "id": int(anchor["id"]),
                    "link": link,
                    "date": published,
                    "title": {"rendered": title},
                    "content": {"rendered": str(article)},
                }
            )
        if older:
            return posts, True
        if page == 1 and soup.select_one("#more_posts") is None:
            return posts, True
    return posts, False


def lcv_sitemap_posts(client: Client, source: Source, until: str) -> tuple[list[dict], bool]:
    body, _ = client.get(source.url + "/news-sitemap.xml", refresh=True)
    root = ET.fromstring(body)
    namespace = {"s": "http://www.sitemaps.org/schemas/sitemap/0.9"}
    if root.tag != "{http://www.sitemaps.org/schemas/sitemap/0.9}urlset":
        raise ValueError("Public news sitemap did not return a URL set")
    posts = []
    seen = set()
    for entry in root.findall("s:url", namespace):
        link = entry.findtext("s:loc", namespaces=namespace)
        modified = entry.findtext("s:lastmod", namespaces=namespace)
        if not link or link in seen:
            raise ValueError("Public news sitemap repeated or omitted a URL")
        seen.add(link)
        if urlparse(link).hostname != urlparse(source.url).hostname:
            raise ValueError("Public news sitemap linked to a different publisher")
        if modified and modified[:10] < START:
            continue
        if urlparse(link).path.rstrip("/") == "/news":
            continue
        if not getattr(client, "offline", False):
            sleep(10)  # Publisher's robots.txt requests a ten-second crawl delay.
        release, _ = client.get(link, refresh=True)
        soup = BeautifulSoup(release, "html.parser")
        article = soup.select_one('article[id^="post-"]')
        heading = soup.select_one("article .news-title")
        label = soup.select_one(".news-title-date")
        content = soup.select_one(".news-content")
        published = (
            re.search(r"\b[A-Z][a-z]+ \d{1,2}, \d{4}\b", label.get_text(" ", strip=True))
            if label
            else None
        )
        if article is None or heading is None or content is None or published is None:
            raise ValueError(
                f"Public news release omitted its article, title, date, or body: {link}"
            )
        published = datetime.strptime(published[0], "%B %d, %Y").date().isoformat()
        identity = re.fullmatch(r"post-(\d+)", article["id"])
        if identity is None:
            raise ValueError("Public news release has no stable publisher record ID")
        if START <= published <= until:
            posts.append(
                {
                    "id": int(identity[1]),
                    "link": link,
                    "date": published,
                    "title": {"rendered": heading.get_text(" ", strip=True)},
                    "content": {"rendered": str(content)},
                    "publisher_classes": article.get("class", []),
                }
            )
    return posts, True


def nationbuilder_posts(
    client: Client, source: Source, until: str, max_pages: int = 100
) -> tuple[list[dict], bool]:
    posts = []
    seen = set()
    for page in range(1, max_pages + 1):
        path = source.index_path + (f"?page={page}" if page > 1 else "")
        body, _ = client.get(source.url + path, refresh=True)
        soup = BeautifulSoup(body, "html.parser")
        cards = soup.select('.page-excerpt[id^="blog-post-page-"]')
        if not cards:
            raise ValueError("Public news archive did not expose dated release cards")
        older = False
        for card in cards:
            anchor = card.select_one("h3 a[href]")
            label = card.select_one(".byline")
            if anchor is None or label is None:
                raise ValueError("Public news release omitted its title or date")
            published = datetime.strptime(label.get_text(" ", strip=True), "%B %d, %Y")
            published = published.date().isoformat()
            older |= published < START
            link = urljoin(source.url, anchor["href"])
            if urlparse(link).hostname != urlparse(source.url).hostname:
                raise ValueError("Public news archive linked to a different publisher")
            if link in seen:
                raise ValueError("Public news archive repeated a release URL")
            seen.add(link)
            title = anchor.get_text(" ", strip=True)
            campaign = re.search(r"\bcampaign\b", title, re.I) and re.search(
                r"\b(?:ads?|advertising)\b", card.get_text(" ", strip=True), re.I
            )
            if not START <= published <= until or not (is_ad_release(title) or campaign):
                continue
            release, _ = client.get(link, refresh=True)
            content = BeautifulSoup(release, "html.parser").select_one("#intro .content")
            if content is None:
                raise ValueError("Public ad release omitted its expected article body")
            posts.append(
                {
                    "id": card["id"].removeprefix("blog-post-page-"),
                    "link": link,
                    "date": published,
                    "title": {"rendered": title},
                    "content": {"rendered": str(content)},
                }
            )
        if older or not any(f"?page={page + 1}" in a.get("href", "") for a in soup.find_all("a")):
            return posts, True
    return posts, False


def squarespace_posts(
    client: Client, source: Source, until: str, max_pages: int = 100
) -> tuple[list[dict], bool]:
    posts = []
    seen = set()
    url = source.url + source.index_path + "?format=json"
    for _ in range(max_pages):
        payload, _ = client.json(url, refresh=True)
        pagination = payload.get("pagination", {})
        if not isinstance(payload.get("items"), list) or not (
            "nextPage" in pagination or pagination.get("prevPage")
        ):
            raise ValueError("Public news JSON did not expose items and pagination")
        zone = ZoneInfo(payload.get("website", {}).get("timeZone", "UTC"))
        older = False
        for item in payload["items"]:
            if item["id"] in seen:
                raise ValueError("Public news JSON repeated IDs across pages")
            seen.add(item["id"])
            published = (
                datetime.fromtimestamp(item["publishOn"] / 1000, UTC)
                .astimezone(zone)
                .date()
                .isoformat()
            )
            older |= published < START
            if not START <= published <= until:
                continue
            link = urljoin(source.url, item["fullUrl"])
            if urlparse(link).hostname != urlparse(source.url).hostname:
                raise ValueError("Public news JSON linked to a different publisher")
            posts.append(
                {
                    "id": item["id"],
                    "link": link,
                    "date": published,
                    "title": {"rendered": item["title"]},
                    "content": {"rendered": item["body"]},
                }
            )
        if older or not pagination.get("nextPage", False):
            return posts, True
        next_url = urljoin(source.url, pagination["nextPageUrl"])
        if urlparse(next_url).hostname != urlparse(source.url).hostname:
            raise ValueError("Public news JSON linked to a different pagination host")
        url = next_url + ("&" if "?" in next_url else "?") + "format=json"
    return posts, False


def news_index_posts(client: Client, source: Source, until: str) -> tuple[list[dict], bool]:
    body, _ = client.get(source.url + "/news/", refresh=True)
    soup = BeautifulSoup(body, "html.parser")
    posts = []
    seen = set()
    older = False
    cards = [a for a in soup.find_all("a", href=True) if a.find("h1")]
    if not cards:
        raise ValueError("Public news index did not expose dated release cards")
    for card in cards:
        link = urljoin(source.url, card["href"])
        if urlparse(link).hostname != urlparse(source.url).hostname:
            continue  # The index also links to third-party coverage, not campaign releases.
        if link in seen:
            continue  # Featured releases also appear in the same page's chronological list.
        seen.add(link)
        date_label = next(
            (
                p
                for p in card.find_all("p")
                if re.fullmatch(r"[A-Z][a-z]{2} \d{1,2}, \d{4}", p.get_text(" ", strip=True))
            ),
            None,
        )
        if date_label is None:
            raise ValueError("Public news index release has no date")
        published = (
            datetime.strptime(date_label.get_text(" ", strip=True), "%b %d, %Y").date().isoformat()
        )
        older |= published < START
        title = card.find("h1").get_text(" ", strip=True)
        if not START <= published <= until or not is_ad_release(title):
            continue
        release, _ = client.get(link, refresh=True)
        content = BeautifulSoup(release, "html.parser").find("main")
        if content is None:
            raise ValueError("Public news release has no main article")
        posts.append(
            {
                "id": digest(link)[:16],
                "link": link,
                "date": published,
                "title": {"rendered": title},
                "content": {"rendered": str(content)},
            }
        )
    # This rendered index includes prior-year releases; no API page-size assumption.
    return posts, older


def dated_news_posts(
    client: Client, source: Source, until: str, max_pages: int = 100
) -> tuple[list[dict], bool]:
    posts = []
    seen = set()
    url = source.url + source.index_path + "/"
    for _ in range(max_pages):
        body, _ = client.get(url, refresh=True)
        soup = BeautifulSoup(body, "html.parser")
        dates = soup.select("time[datetime], .press__date")
        if not dates:
            raise ValueError("Public news archive did not expose dated release cards")
        older = False
        for time in dates:
            published = (
                time["datetime"][:10]
                if time.has_attr("datetime")
                else datetime.strptime(time.get_text(strip=True), "%B %d, %Y").date().isoformat()
            )
            datetime.strptime(published, "%Y-%m-%d")
            older |= published < START
            card = time.parent
            while card and not card.find(["h2", "h3", "h4"]):
                card = card.parent
            if card is None or len(card.find_all(["h2", "h3", "h4"])) != 1:
                raise ValueError("Public news archive has no unambiguous release card")
            heading = card.find(["h2", "h3", "h4"])
            anchor = (
                card
                if card.name == "a"
                else card.select_one("a.read-more") or heading.find("a", href=True)
            )
            if anchor is None:
                anchor = card.find("a", href=True)
            if anchor is None:
                raise ValueError("Public news archive release has no link")
            link = urljoin(source.url, anchor["href"])
            if urlparse(link).hostname != urlparse(source.url).hostname:
                raise ValueError("Public news archive linked to a different publisher")
            if link in seen:
                raise ValueError("Public news archive repeated release URLs across pages")
            seen.add(link)
            title = plain_title(heading)
            if not START <= published <= until or not is_ad_release(title):
                continue
            release, _ = client.get(link, refresh=True)
            article = BeautifulSoup(release, "html.parser")
            if article.find("h1") is None or plain_title(article.find("h1")) != title:
                raise ValueError(f"Public release returned a different article or fallback: {link}")
            content = article.find("main")
            if content is None:
                raise ValueError("Public news release has no main article")
            posts.append(
                {
                    "id": digest(link)[:16],
                    "link": link,
                    "date": published,
                    "title": {"rendered": title},
                    "content": {"rendered": str(content)},
                }
            )
        next_page = soup.select_one("a.next, a[rel=next]")
        if older or next_page is None:
            return posts, older
        url = urljoin(source.url, next_page["href"])
        if urlparse(url).hostname != urlparse(source.url).hostname:
            raise ValueError("Public news archive linked to a different pagination host")
    return posts, False


def plain_title(node) -> str:
    return re.sub(r"\s+", " ", node.get_text(" ", strip=True)).strip()
