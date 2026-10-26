from __future__ import annotations

import html
import re
from dataclasses import asdict, dataclass
from datetime import date
from urllib.parse import urlencode

from bs4 import BeautifulSoup
from langdetect import DetectorFactory, LangDetectException
from langdetect.detector_factory import PROFILES_DIRECTORY

from political_ads.http import Client
from political_ads.schema import Ad, Segment, digest

LANGUAGE_FACTORY = DetectorFactory()
LANGUAGE_FACTORY.load_profile(PROFILES_DIRECTORY)
LANGUAGE_FACTORY.seed = 0


def language_of(text: str) -> str:
    try:
        detector = LANGUAGE_FACTORY.create()
        detector.append(text)
        prediction = detector.get_probabilities()[0]
        return prediction.lang if prediction.prob >= 0.90 else "unknown"
    except LangDetectException:
        return "unknown"


def cooper_transcripts(content: str) -> list[str]:
    soup = BeautifulSoup(content, "html.parser")
    lines = []
    started = False
    for paragraph in soup.find_all("p"):
        text = paragraph.get_text(" ", strip=True)
        if re.search(r"read a transcript", text, re.I):
            started = True
            continue
        if not started or not text:
            continue
        if not paragraph.find("em") or text == "###":
            break
        lines.append(plain_html(str(paragraph)))
    return ["\n".join(lines)] if lines else []


@dataclass(frozen=True)
class Source:
    id: str
    url: str
    sponsor: str
    alignment: str
    sponsor_type: str
    chamber: str
    rest_base: str = "posts"
    search: str = "transcript"
    fixed_race: str = ""
    discovery: str = "wordpress"
    index_path: str = "/news"


SOURCES = [
    Source("nrsc", "https://www.nrsc.org", "NRSC", "R", "party", "Senate"),
    Source("dccc", "https://dccc.org", "DCCC", "D", "party", "House"),
    Source("dscc", "https://www.dscc.org", "DSCC", "D", "party", "Senate", "article", "ad"),
    Source("nrcc", "https://www.nrcc.org", "NRCC", "R", "party", "House", discovery="rss"),
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
        discovery="archive",
    ),
    Source(
        "hmp",
        "https://www.thehousemajoritypac.com",
        "House Majority PAC",
        "D",
        "outside_group",
        "House",
        discovery="archive",
    ),
    Source(
        "smp",
        "https://www.senatemajority.com",
        "Senate Majority PAC",
        "D",
        "outside_group",
        "Senate",
    ),
    Source(
        "cooper",
        "https://roycooper.com",
        "Cooper for North Carolina",
        "D",
        "candidate",
        "Senate",
        fixed_race="NC-Senate",
    ),
    Source(
        "hinson",
        "https://ashleyhinson.com",
        "Ashley Hinson for Senate",
        "R",
        "candidate",
        "Senate",
        search="ad",
        fixed_race="IA-Senate",
    ),
    Source(
        "sullivan",
        "https://dansullivanforalaska.com",
        "Dan Sullivan for Alaska",
        "R",
        "candidate",
        "Senate",
        search="ad",
        fixed_race="AK-Senate",
    ),
    Source(
        "hickenlooper",
        "https://hickenlooper.com",
        "Hickenlooper for Colorado",
        "D",
        "candidate",
        "Senate",
        search="ad",
        fixed_race="CO-Senate",
    ),
    Source(
        "ossoff",
        "https://electjon.com",
        "Jon Ossoff for Senate",
        "D",
        "candidate",
        "Senate",
        search="ad",
        fixed_race="GA-Senate",
    ),
    Source(
        "trone-garriott",
        "https://sarahforiowa.com",
        "Sarah Trone Garriott for Congress",
        "D",
        "candidate",
        "House",
        search="ad",
        fixed_race="IA-03",
    ),
    Source(
        "mccann",
        "https://seanmccannforcongress.com",
        "Sean McCann for Congress",
        "D",
        "candidate",
        "House",
        search="ad",
        fixed_race="MI-04",
    ),
    Source(
        "nunn",
        "https://zachnunn.com",
        "Zach Nunn for Congress",
        "R",
        "candidate",
        "House",
        search="ad",
        fixed_race="IA-03",
    ),
    Source(
        "rogers",
        "https://rogersforsenate.com",
        "Rogers for Senate",
        "R",
        "candidate",
        "Senate",
        fixed_race="MI-Senate",
        discovery="squarespace",
    ),
    Source(
        "turek",
        "https://turek4iowa.com",
        "Josh Turek for Iowa",
        "D",
        "candidate",
        "Senate",
        fixed_race="IA-Senate",
        discovery="news_index",
    ),
    Source(
        "hmf",
        "https://www.housemajorityforward.org",
        "House Majority Forward",
        "D",
        "outside_group",
        "House",
        discovery="archive",
    ),
    Source(
        "unrig",
        "https://unrigoureconomy.com",
        "Unrig Our Economy",
        "D",
        "outside_group",
        "House",
        rest_base="news",
    ),
    Source(
        "dembo",
        "https://zachdembo.com",
        "Zach Dembo for Congress",
        "D",
        "candidate",
        "House",
        search="ad",
        fixed_race="KY-06",
    ),
    Source(
        "collins",
        "https://mikecollinsga.com",
        "Mike Collins for Senate",
        "R",
        "candidate",
        "Senate",
        rest_base="press_release",
        search="ad",
        fixed_race="GA-Senate",
    ),
    Source(
        "fletcher",
        "https://www.lizziefletcher.com",
        "Lizzie Fletcher for Congress",
        "D",
        "candidate",
        "House",
        search="ad",
        fixed_race="TX-07",
    ),
    Source(
        "lacore",
        "https://www.nancylacore.com",
        "Nancy Lacore for Congress",
        "D",
        "candidate",
        "House",
        fixed_race="SC-01",
        discovery="squarespace",
        index_path="/media",
    ),
    Source(
        "jackson",
        "https://www.jacksonformaine.com",
        "Troy Jackson for Maine",
        "D",
        "candidate",
        "Senate",
        fixed_race="ME-Senate",
        discovery="dated_news",
    ),
    Source(
        "el-sayed",
        "https://abdulforsenate.com",
        "Abdul for U.S. Senate",
        "D",
        "candidate",
        "Senate",
        fixed_race="MI-Senate",
        discovery="dated_news",
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
    soup = BeautifulSoup(content, "html.parser")
    # Linked, standalone video titles belong to the next creative, not the transcript.
    for node in soup.find_all(["p", "div"]):
        anchor = node.find("a")
        if anchor and not node.find(["p", "div"]):
            title = re.sub(r'[\s"“”]+', "", node.get_text())
            linked = re.sub(r'[\s"“”]+', "", anchor.get_text())
            if title and title == linked and media_links(str(node)):
                node.decompose()
    content = str(soup)
    text = plain_html(content)
    markers = list(
        re.finditer(
            r"(?im)^([^\n]{0,50}\b)?(?:transcript|(?:radio|tv|ad) script)"
            r"(?:\s*\(\s*:?\d{1,3}(?:\s*(?:seconds?|secs?|s))?\s*\))?"
            r"(?:\s+(?:of|for)\s+[^\n:]{0,120}|\s+below\.?)?\s*(?::|\n|$)",
            text,
        )
    )
    blocks = []
    for i, marker in enumerate(markers):
        if re.search(r"\b(?:phone tree|hotline|interview|debate)\s+transcript\b", marker[0], re.I):
            continue
        end = markers[i + 1].start() if i + 1 < len(markers) else len(text)
        chunk = text[marker.end() : end]
        chunk = re.split(r"(?m)^\s*(?:###|Paid for by the .* Committee\.?$)", chunk)[0]
        chunk = re.split(
            r"(?im)^\s*(?:Read (?:more|the)|Watch (?:the|this)|Share (?:this|on)|"
            r"Watch\s+[‘“\"']|"
            r"You can watch\b|"
            r"(?:On )?Background:|See also:|About the |About [^\n:]{1,80}:|"
            r"The post .+ appeared first on |Roy Cooper has launched |"
            r"Learn more about Mike Rogers and his plans? to |"
            r"DCCC (?:National |Spokesperson|Chair|Senior )|"
            r"For (?:more information|Immediate Release)|"
            r"To learn more about the campaign, |"
            r"Nancy Lacore served our nation for 35 years)",
            chunk,
        )[0]
        lines = [line.strip() for line in chunk.splitlines() if line.strip()]
        if lines and len(" ".join(lines).split()) >= 15:
            blocks.append("\n".join(lines))
    return blocks


def candidate_ad_copy(content: str, source_id: str) -> list[str]:
    soup = BeautifulSoup(content, "html.parser")
    if source_id == "hinson":
        # The campaign separates quoted ad copy from its unitalicized background.
        watch = next(
            (
                p
                for p in soup.find_all("p")
                if re.fullmatch(r"\[\s*Watch Here\s*\]", p.get_text(" ", strip=True), re.I)
            ),
            None,
        )
        paragraph = watch.find_next_sibling("p") if watch else None
        if paragraph is None:
            introduction = soup.find("p")
            image = soup.find("figure")
            if (
                introduction
                and re.search(r"\blaunched the first ad\b", introduction.get_text(), re.I)
                and image
            ):
                paragraph = image.find_next_sibling("p")
        if paragraph is None:
            return []
        quoted = paragraph.find("em") or paragraph
        match = re.match(r"^(“[^”]+”)", quoted.get_text(" ", strip=True))
        return [match[1]] if match and len(match[1].split()) >= 15 else []
    if source_id == "ossoff":
        text = plain_html(content)
        match = re.search(r"(?m)^\[[^\]\n]{1,60}\]\s", text)
        if match and re.search(r"(?m)^###\s*$", text[match.start() :]):
            block = re.split(r"(?m)^###\s*$", text[match.start() :])[0].strip()
            if len(block.split()) >= 15 and all(
                re.match(r"^\[[^\]]{1,60}\]\s", line) for line in block.splitlines()
            ):
                return [block]
    if source_id == "mccann":
        text = plain_html(content)
        match = re.search(r"(?im)^WATCH THE AD HERE\s*$", text)
        if match and re.search(r"(?m)^###\s*$", text[match.end() :]):
            return [re.split(r"(?m)^###\s*$", text[match.end() :])[0].strip()]
    if source_id == "el-sayed":
        text = plain_html(content)
        watch = re.search(r"(?im)^WATCH [^\n]{0,120}\bHERE[.!]?\s*$", text)
        if watch and re.search(r"(?m)^###\s*$", text[watch.end() :]):
            block = re.split(r"(?m)^###\s*$", text[watch.end() :])[0].strip()
            if re.match(r"(?i)^(?:Radio|Narrator|VO|Abdul(?: El[- ]Sayed)?)\s*:", block):
                return [block] if len(block.split()) >= 15 else []
    return []


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
    if re.match(r"new(?: (?:tv|digital|radio))? ads?:", title, re.I):
        title = re.sub(r"\bdebates?\b", "", title, flags=re.I)
    return bool(re.search(r"\b(?:ads?|advertising|spots?)\b", title, re.I)) and not bool(
        re.search(
            r"\b(?:debate|interview|fact.check|ICYMI|takeaways|roundup|anniversary|"
            r"ads?\s+(?:called|debunked))\b",
            title,
            re.I,
        )
    )


def parse_post(post: dict, source: Source, observed: str) -> list[dict]:
    title = html.unescape(BeautifulSoup(post["title"]["rendered"], "html.parser").get_text())
    if not is_ad_release(title):
        return []
    content = post["content"]["rendered"]
    # Rogers's release has a stray letter inside its heading, not the spoken script.
    body = (
        re.sub(r"(transcript below:)r(?=</)", r"\1", content) if source.id == "rogers" else content
    )
    blocks = cooper_transcripts(body) if source.id == "cooper" else transcript_blocks(body)
    quoted_copy = False
    if not blocks:
        blocks = candidate_ad_copy(content, source.id)
        quoted_copy = bool(blocks)
    title_races = set(re.findall(r"\b([A-Z]{2})[-–](\d{1,2})\b", title))
    race_match = next(iter(title_races)) if len(title_races) == 1 else None
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
            segments=[
                asdict(
                    Segment(
                        text=line,
                        kind="publisher_ad_copy" if quoted_copy else "publisher_transcript",
                    )
                )
                for line in text.splitlines()
            ],
            source_hash=digest(content),
            phase=phase,
            chamber=source.chamber,
            race=(
                f"{race_match[0]}-{int(race_match[1]):02}"
                if race_match
                else source.fixed_race or "Unresolved"
            ),
            state=race_match[0] if race_match else source.fixed_race[:2],
            media_urls=media_links(content),
            language=language_of(text),
            language_basis="langdetect seeded model; >=0.90 probability, otherwise unknown",
            quality_flags=["publisher_ad_copy_completeness_unverified"] if quoted_copy else [],
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
        "scope": "Official ad-release text; not all paid placements",
    }
    try:
        if source.discovery != "wordpress":
            from political_ads.discovery import public_posts

            posts, complete = public_posts(client, source, until)
            for post in posts:
                status["posts_scanned"] += 1
                parsed = parse_post(post, source, observed)
                ads.extend(parsed)
                status["excluded_posts"] += not bool(parsed)
            status.update(
                state="ok" if complete else "partial",
                discovery_complete=complete,
                ads_with_text=len(ads),
            )
            return ads, status
        page = 1
        while True:
            query = urlencode(
                {
                    "search": source.search,
                    "after": "2025-12-31T23:59:59",
                    "before": f"{until}T23:59:59",
                    "per_page": 100,
                    "page": page,
                    "orderby": "date",
                    "order": "asc",
                }
            )
            posts, headers = client.json(
                f"{source.url}/wp-json/wp/v2/{source.rest_base}?{query}",
                refresh=True,
            )
            if not isinstance(posts, list):
                raise ValueError("Endpoint is not a WordPress posts array")
            if any(p.get("id") in seen for p in posts):
                raise ValueError("Endpoint repeated IDs across pages; pagination is not supported")
            for post in posts:
                if source.rest_base == "article" and "content" not in post:
                    layouts = post.get("acf", {}).get("page_layout", [])
                    content = "\n".join(
                        layout.get("component_wysiwyg", {}).get("content", "") for layout in layouts
                    )
                    post["content"] = {"rendered": content}
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
