from __future__ import annotations

import html
import re
from dataclasses import asdict, dataclass
from datetime import date
from urllib.parse import urlencode

from bs4 import BeautifulSoup

from political_ads.http import Client
from political_ads.schema import Ad, Segment, digest


@dataclass(frozen=True)
class Source:
    id: str
    url: str
    sponsor: str
    alignment: str
    sponsor_type: str
    chamber: str


SOURCES = [
    Source("nrsc", "https://www.nrsc.org", "NRSC", "R", "party", "Senate"),
    Source("dccc", "https://dccc.org", "DCCC", "D", "party", "House"),
    Source("dscc", "https://www.dscc.org", "DSCC", "D", "party", "Senate"),
    Source("nrcc", "https://www.nrcc.org", "NRCC", "R", "party", "House"),
    Source(
        "slf",
        "https://senateleadershipfund.org",
        "Senate Leadership Fund",
        "R",
        "outside_group",
        "Senate",
    ),
    Source(
        "clf",
        "https://congressionalleadershipfund.org",
        "Congressional Leadership Fund",
        "R",
        "outside_group",
        "House",
    ),
    Source(
        "hmp",
        "https://www.thehousemajoritypac.com",
        "House Majority PAC",
        "D",
        "outside_group",
        "House",
    ),
    Source(
        "smp",
        "https://www.senatemajority.com",
        "Senate Majority PAC",
        "D",
        "outside_group",
        "Senate",
    ),
]


def plain_html(value: str) -> str:
    soup = BeautifulSoup(value, "html.parser")
    for node in soup(["script", "style", "iframe"]):
        node.decompose()
    # Preserve paragraph breaks without splitting nested inline speaker markup.
    for node in soup.find_all(["p", "div", "br", "h1", "h2", "h3", "li"]):
        node.append("\n")
    text = html.unescape(soup.get_text(" "))
    return "\n".join(
        line for raw in text.splitlines() if (line := re.sub(r"[ \t\xa0]+", " ", raw).strip())
    )


def transcript_blocks(content: str) -> list[str]:
    text = plain_html(content)
    markers = list(re.finditer(r"(?im)(?:^|[^\w])transcript\s*(?::|\n|$)", text))
    blocks = []
    for i, marker in enumerate(markers):
        end = markers[i + 1].start() if i + 1 < len(markers) else len(text)
        chunk = text[marker.end() : end]
        chunk = re.split(r"(?m)^\s*(?:###|Paid for by the .* Committee\.?$)", chunk)[0]
        chunk = re.split(
            r"(?im)^\s*(?:Read (?:more|the)|Watch (?:the|this)|Share (?:this|on)|"
            r"Background:|About the |For (?:more information|Immediate Release))",
            chunk,
        )[0]
        lines = [line.strip() for line in chunk.splitlines() if line.strip()]
        if lines and len(" ".join(lines).split()) >= 15:
            blocks.append("\n".join(lines))
    return blocks


def media_links(content: str) -> list[str]:
    soup = BeautifulSoup(content, "html.parser")
    urls = []
    for tag in soup.find_all(["iframe", "a", "video", "source"]):
        value = tag.get("src", tag.get("href", ""))
        if value.startswith("https://") and (
            any(host in value for host in ("youtube.com/", "youtu.be/", "vimeo.com/"))
            or re.search(r"\.(?:mp4|webm|mp3|wav)(?:\?|$)", value)
        ):
            urls.append(value)
    return sorted(set(urls))


def is_ad_release(title: str) -> bool:
    return bool(re.search(r"\b(?:ads?|advertising|spots?)\b", title, re.I)) and not bool(
        re.search(
            r"\b(?:debate|interview|fact.check|ICYMI|takeaways|roundup|anniversary)\b",
            title,
            re.I,
        )
    )


def parse_post(post: dict, source: Source, observed: str) -> list[dict]:
    title = html.unescape(BeautifulSoup(post["title"]["rendered"], "html.parser").get_text())
    if not is_ad_release(title):
        return []
    content = post["content"]["rendered"]
    blocks = transcript_blocks(content)
    race_match = re.search(r"\b([A-Z]{2})[-–](\d{1,2})\b", title)
    phase = "primary" if re.search(r"\bprimary\b", title, re.I) else "unknown"
    full_text = plain_html(content)
    if phase == "unknown" and re.search(r"\bgeneral election\b", full_text, re.I):
        phase = "general"
    ads = []
    for index, text in enumerate(blocks):
        ad = Ad(
            id=f"{source.id}-{post['id']}-{index}",
            source=source.id,
            source_url=post["link"],
            source_record_id=str(post["id"]),
            title=title if len(blocks) == 1 else f"{title} / transcript {index + 1}",
            sponsor=source.sponsor,
            sponsor_type=source.sponsor_type,
            alignment=source.alignment,
            published=post["date"][:10],
            observed=observed,
            text=text,
            segments=[asdict(Segment(text=line)) for line in text.splitlines()],
            source_hash=digest(content),
            phase=phase,
            chamber=source.chamber,
            race=f"{race_match[1]}-{int(race_match[2]):02}" if race_match else "Unresolved",
            state=race_match[1] if race_match else "",
            media_urls=media_links(content),
            attribution_basis=(
                f"Official {source.sponsor} release at {post['link']}; alignment is the "
                "publisher's electoral alignment, not inferred from hostile vocabulary. "
                "Joint or candidate-paid creative requires separate payer review."
            ),
        )
        ads.append(ad.to_dict())
    return ads


def collect_wordpress(
    client: Client,
    source: Source,
    until: str,
    observed: str | None = None,
) -> tuple[list[dict], dict]:
    observed = observed or date.today().isoformat()
    ads = []
    seen = set()
    status = {
        "source": source.id,
        "url": source.url,
        "state": "ok",
        "checked": observed,
        "posts_scanned": 0,
        "ads_with_text": 0,
        "excluded_posts": 0,
        "scope": "Official ad-release transcripts; not all paid placements",
    }
    try:
        page = 1
        while True:
            query = urlencode(
                {
                    "search": "transcript",
                    "after": "2025-12-31T23:59:59",
                    "before": f"{until}T23:59:59",
                    "per_page": 100,
                    "page": page,
                    "orderby": "date",
                    "order": "asc",
                }
            )
            posts, headers = client.json(
                f"{source.url}/wp-json/wp/v2/posts?{query}",
                refresh=True,
            )
            if not isinstance(posts, list):
                raise ValueError("Endpoint is not a WordPress posts array")
            if any(p.get("id") in seen for p in posts):
                raise ValueError("Endpoint repeated IDs across pages; pagination is not supported")
            for post in posts:
                if not all(field in post for field in ("id", "date", "content", "title", "link")):
                    raise ValueError("Endpoint does not expose the expected WordPress schema")
                if not "2026-01-01" <= post["date"][:10] <= until:
                    raise ValueError("Endpoint ignored delivery/release date filters")
                seen.add(post["id"])
                status["posts_scanned"] += 1
                parsed = parse_post(post, source, observed)
                ads.extend(parsed)
                status["excluded_posts"] += not bool(parsed)
            total_pages = int(
                next(
                    (v for k, v in headers.items() if k.lower() == "x-wp-totalpages"),
                    "1",
                )
            )
            if page >= total_pages:
                break
            page += 1
        status["ads_with_text"] = len(ads)
    except (OSError, ValueError, KeyError, TypeError) as error:
        status.update(state="error", error=f"{type(error).__name__}: {error}")
        # A partial failed fetch must never replace the previous complete partition.
        ads = []
    return ads, status
