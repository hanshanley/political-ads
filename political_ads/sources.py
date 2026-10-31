from __future__ import annotations

import html
import re
from dataclasses import asdict, dataclass
from datetime import date, datetime
from urllib.parse import parse_qs, urlencode, urlsplit, urlunsplit

from bs4 import BeautifulSoup
from langdetect import DetectorFactory, LangDetectException
from langdetect.detector_factory import PROFILES_DIRECTORY

from political_ads.http import Client
from political_ads.registry import candidate_mentions, enrich
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
    requires_federal_candidate: bool = False


SOURCES = [
    Source("nrsc", "https://www.nrsc.org", "NRSC", "R", "party", "Senate", search="ad"),
    Source("dccc", "https://dccc.org", "DCCC", "D", "party", "House"),
    Source("dscc", "https://www.dscc.org", "DSCC", "D", "party", "Senate", "article", "ad"),
    Source(
        "nrcc",
        "https://www.nrcc.org",
        "NRCC",
        "R",
        "party",
        "House",
        search="script",
        discovery="rss",
    ),
    Source(
        "nrcc-iowa-standard",
        "https://theiowastandard.com",
        "NRCC",
        "R",
        "party",
        "House",
        fixed_race="IA-03",
        discovery="reviewed_releases",
    ),
    Source(
        "marques-yellowhammer",
        "https://yellowhammernews.com",
        "Rhett Marques for Congress",
        "R",
        "candidate",
        "House",
        fixed_race="AL-02",
        discovery="reviewed_releases",
    ),
    Source(
        "odonnell-nevada-independent",
        "https://thenevadaindependent.com",
        "Marty for Congress",
        "R",
        "candidate",
        "House",
        fixed_race="NV-03",
        discovery="reviewed_releases",
    ),
    Source(
        "ngb-aptv",
        "https://aptv.org",
        "No Going Back",
        "R",
        "outside_group",
        "House",
        fixed_race="AL-02",
        discovery="reviewed_releases",
    ),
    Source(
        "acc-aptv",
        "https://aptv.org",
        "Alabama Christian Conservatives",
        "R",
        "outside_group",
        "House",
        fixed_race="AL-02",
        discovery="reviewed_releases",
    ),
    Source(
        "hurd-coloradopols",
        "https://www.coloradopols.com",
        "Jeff Hurd campaign (reported advertiser; payer unverified)",
        "R",
        "candidate",
        "House",
        fixed_race="CO-03",
        discovery="reviewed_releases",
    ),
    Source(
        "evans-coloradotimes",
        "https://coloradotimesrecorder.com",
        "Gabe Evans campaign (reported advertiser; payer unverified)",
        "R",
        "candidate",
        "House",
        fixed_race="CO-08",
        discovery="reviewed_releases",
    ),
    Source(
        "saf-factcheck",
        "https://www.factcheck.org",
        "Safety and Affordability PAC (reported ad sponsor)",
        "R",
        "outside_group",
        "House",
        fixed_race="PA-07",
        discovery="reviewed_releases",
    ),
    Source(
        "clf-factcheck",
        "https://www.factcheck.org",
        "Congressional Leadership Fund (reported ad sponsor)",
        "R",
        "outside_group",
        "House",
        fixed_race="PA-10",
        discovery="reviewed_releases",
    ),
    Source(
        "nrcc-townhall",
        "https://townhall.com",
        "NRCC (reported ad sponsor)",
        "R",
        "party",
        "House",
        fixed_race="AZ-01",
        discovery="reviewed_releases",
    ),
    Source(
        "holdtheline-metroweekly",
        "https://www.metroweekly.com",
        "Restore Freedom PAC (Hold the Line PAC project, reported ad sponsor)",
        "R",
        "outside_group",
        "House",
        fixed_race="KY-04",
        discovery="reviewed_releases",
    ),
    Source(
        "rjc-vf-jewishinsider",
        "https://jewishinsider.com",
        "RJC Victory Fund (reported ad sponsor)",
        "R",
        "outside_group",
        "House",
        fixed_race="PA-01",
        discovery="reviewed_releases",
    ),
    Source(
        "rjc-jewishinsider",
        "https://jewishinsider.com",
        "RJC (reported ad sponsor)",
        "R",
        "outside_group",
        "House",
        fixed_race="KY-04",
        discovery="reviewed_releases",
    ),
    Source(
        "nrcc-ncnewsline",
        "https://ncnewsline.com",
        "NRCC (reported payer of Balkcom Mom ad)",
        "R",
        "party",
        "House",
        fixed_race="NC-11",
        discovery="reviewed_releases",
    ),
    Source(
        "nrcc-cardinalpine",
        "https://cardinalpine.com",
        "NRCC (reported payer of Balkcom attack ad)",
        "R",
        "party",
        "House",
        fixed_race="NC-11",
        discovery="reviewed_releases",
    ),
    Source(
        "safety-affordability-americanjournal",
        "https://americanjournalnews.com",
        "Safety and Affordability PAC",
        "R",
        "outside_group",
        "House",
        fixed_race="AZ-01",
        discovery="reviewed_releases",
    ),
    Source(
        "clf-americanjournal",
        "https://americanjournalnews.com",
        "Congressional Leadership Fund",
        "R",
        "outside_group",
        "House",
        fixed_race="AZ-06",
        discovery="reviewed_releases",
    ),
    Source(
        "ciscomani-americanjournal",
        "https://americanjournalnews.com",
        "Juan Ciscomani campaign",
        "R",
        "candidate",
        "House",
        fixed_race="AZ-06",
        discovery="reviewed_releases",
    ),
    Source(
        "miller-americanjournal",
        "https://americanjournalnews.com",
        "Max Miller and NRCC (reported coordinated ad)",
        "R",
        "party",
        "House",
        fixed_race="OH-07",
        discovery="reviewed_releases",
    ),
    Source(
        "cunningham-americanjournal",
        "https://americanjournalnews.com",
        "Greg Cunningham and NRCC (reported joint ad)",
        "R",
        "party",
        "House",
        fixed_race="NM-02",
        discovery="reviewed_releases",
    ),
    Source(
        "lepage-mediaite",
        "https://www.mediaite.com",
        "Paul LePage campaign",
        "R",
        "candidate",
        "House",
        fixed_race="ME-02",
        discovery="reviewed_releases",
    ),
    Source(
        "ciscomani-townhall",
        "https://townhall.com",
        "Juan Ciscomani campaign",
        "R",
        "candidate",
        "House",
        fixed_race="AZ-06",
        discovery="reviewed_releases",
    ),
    Source(
        "flippo-americanjournal",
        "https://americanjournalnews.com",
        "David Flippo campaign",
        "R",
        "candidate",
        "House",
        fixed_race="NV-02",
        discovery="reviewed_releases",
    ),
    Source(
        "buckhout-nsj",
        "https://nsjonline.com",
        "Laurie Buckhout campaign",
        "R",
        "candidate",
        "House",
        fixed_race="NC-01",
        discovery="reviewed_releases",
    ),
    Source(
        "buckhout-centersquare",
        "https://www.thecentersquare.com",
        "Laurie Buckhout campaign",
        "R",
        "candidate",
        "House",
        fixed_race="NC-01",
        discovery="reviewed_releases",
    ),
    Source(
        "kean-globe",
        "https://newjerseyglobe.com",
        "Tom Kean Jr. campaign",
        "R",
        "candidate",
        "House",
        fixed_race="NJ-07",
        discovery="reviewed_releases",
    ),
    Source(
        "nj-gop-globe",
        "https://newjerseyglobe.com",
        "New Jersey Republican State Committee",
        "R",
        "party",
        "House",
        fixed_race="NJ-07",
        discovery="reviewed_releases",
    ),
    Source(
        "aan-globe",
        "https://newjerseyglobe.com",
        "American Action Network",
        "R",
        "outside_group",
        "House",
        fixed_race="NJ-07",
        discovery="reviewed_releases",
    ),
    Source(
        "hathaway-globe",
        "https://newjerseyglobe.com",
        "Joe Hathaway campaign",
        "R",
        "candidate",
        "House",
        fixed_race="NJ-11",
        discovery="reviewed_releases",
    ),
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
        "https://senatemajority.com",
        "Senate Majority PAC",
        "D",
        "outside_group",
        "Senate",
        search="ad",
        discovery="smp_news",
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
        "one-nation",
        "https://onenationamerica.org",
        "One Nation",
        "R",
        "outside_group",
        "",
        search="ad",
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
        "cassidy",
        "https://www.billcassidy.com",
        "Bill Cassidy for US Senate",
        "R",
        "candidate",
        "Senate",
        fixed_race="LA-Senate",
        discovery="wix_blog",
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
        "lawler",
        "https://www.lawlerforcongress.com",
        "Lawler for Congress",
        "R",
        "candidate",
        "House",
        search="ad",
        fixed_race="NY-17",
    ),
    Source(
        "salazar",
        "https://mariaelvirasalazar.com",
        "Salazar for Congress",
        "R",
        "candidate",
        "House",
        search="ad",
        fixed_race="FL-27",
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
    Source(
        "susan-collins",
        "https://susancollins.com",
        "Susan Collins for Senator",
        "R",
        "candidate",
        "Senate",
        search="ad",
        fixed_race="ME-Senate",
    ),
    Source(
        "barr",
        "https://barrforsenate.com",
        "Andy Barr for Senate",
        "R",
        "candidate",
        "Senate",
        search="ad",
        fixed_race="KY-Senate",
    ),
    Source(
        "whatley",
        "https://michaelwhatley.com",
        "Michael Whatley for Senate",
        "R",
        "candidate",
        "Senate",
        search="ad",
        fixed_race="NC-Senate",
    ),
    Source(
        "ricketts",
        "https://www.petericketts.com",
        "Pete Ricketts for Senate",
        "R",
        "candidate",
        "Senate",
        search="ad",
        fixed_race="NE-Senate",
    ),
    Source(
        "young-kim",
        "https://youngkimforcongress.com",
        "Young Kim for Congress",
        "R",
        "candidate",
        "House",
        search="ad",
        fixed_race="CA-40",
    ),
    Source(
        "ciscomani",
        "https://juanciscomani.com",
        "Ciscomani for Congress",
        "R",
        "candidate",
        "House",
        fixed_race="AZ-06",
        discovery="squarespace",
    ),
    Source(
        "marshall",
        "https://www.kansansformarshall.com",
        "Kansans for Marshall",
        "R",
        "candidate",
        "Senate",
        fixed_race="KS-Senate",
        discovery="dated_news",
    ),
    Source(
        "lcv-vf",
        "https://www.lcvvictoryfund.org",
        "LCV Victory Fund",
        "D",
        "outside_group",
        "",
        discovery="lcv_sitemap",
    ),
    Source(
        "rjc-vf",
        "https://www.rjchq.org",
        "Republican Jewish Coalition Victory Fund",
        "R",
        "outside_group",
        "",
        discovery="nationbuilder",
    ),
    Source(
        "ua-vote-pac",
        "https://www.uagetinvolved.org",
        "UA Vote! PAC",
        "unknown",
        "outside_group",
        "",
        rest_base="news",
        search="independent expenditure",
        requires_federal_candidate=True,
    ),
    Source(
        "votevets",
        "https://votevets.org",
        "VoteVets",
        "D",
        "outside_group",
        "",
        search="ad",
        requires_federal_candidate=True,
    ),
    Source(
        "letlow",
        "https://www.julialetlow.com",
        "Julia Letlow for Louisiana",
        "R",
        "candidate",
        "Senate",
        fixed_race="LA-Senate",
        discovery="wix_blog",
    ),
    Source(
        "grothman",
        "https://www.wispolitics.com",
        "Glenn Grothman campaign",
        "R",
        "candidate",
        "House",
        fixed_race="WI-06",
        discovery="grothman_release",
        index_path="/2026/u-s-rep-grothman-releases-first-campaign-ad-of-2026-cycle/",
        requires_federal_candidate=True,
    ),
    Source(
        "flint",
        "https://flintformontana.com",
        "Aaron Flint for Montana",
        "R",
        "candidate",
        "House",
        search="ad",
        fixed_race="MT-01",
    ),
    Source(
        "stover",
        "https://www.brianstoverforcongress.com",
        "Brian Stover for Congress",
        "R",
        "candidate",
        "House",
        search="ad",
        fixed_race="GA-14",
    ),
    Source(
        "conroy",
        "https://ericconroy.com",
        "Conroy for Congress",
        "R",
        "candidate",
        "House",
        search="ad",
        fixed_race="OH-01",
    ),
    Source(
        "wfw",
        "https://winningforwomen.com",
        "Winning For Women",
        "R",
        "outside_group",
        "House",
        search="ad",
        requires_federal_candidate=True,
    ),
    Source(
        "wfw-af",
        "https://www.wfwactionfund.com",
        "WFW Action Fund",
        "R",
        "outside_group",
        "House",
        search="ad",
        requires_federal_candidate=True,
    ),
    Source(
        "cfg",
        "https://www.clubforgrowth.org",
        "Club for Growth Action",
        "R",
        "outside_group",
        "",
        search="ad",
        requires_federal_candidate=True,
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
    for separator in soup.find_all("hr"):
        separator.replace_with("\n###\n")
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
            r"(?im)(?:\bThe full text of the ad is below:\s*|"
            r"^([^\n]{0,50}\b)?(?:transcript|(?:(?:radio|tv|ad) )?script)"
            r"(?:\s*\(\s*:?\d{1,3}(?:\s*(?:seconds?|secs?|s))?\s*\))?"
            r"(?:\s+(?:of|for)\s+[^\n:]{0,120}|\s+below\.?)?\s*"
            r"(?::|[-–—][ \t]*(?=\n|$)|\n|$))",
            text,
        )
    )
    blocks = []
    for i, marker in enumerate(markers):
        if re.search(
            r"\b(?:phone tree|hotline|interview|debate)\s+(?:transcript|script)\b",
            marker[0],
            re.I,
        ):
            continue
        end = markers[i + 1].start() if i + 1 < len(markers) else len(text)
        chunk = text[marker.end() : end]
        chunk = re.split(r"(?m)^\s*(?:###|Paid for by the .* Committee\.?$)", chunk)[0]
        chunk = re.split(
            r"(?im)^\s*(?:Read (?:more|the)|Watch (?:the|this)|Share (?:this|on)|"
            r"Watch\s+[‘“\"']|"
            r"You can watch\b|"
            r"Below is a list of [^\n]{0,120}\bad campaign:|"
            r"(?:On )?Background[ \t]*(?::|$)|See also:|About the |About [^\n:]{1,80}:|"
            r"(?:ARTICLE|STORY) EXCERPTS[ \t]*:|"
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
    if source_id == "lawler":
        blocks = []
        for paragraph in soup.find_all("p"):
            text = paragraph.get_text(" ", strip=True)
            titled = re.match(
                r"^(?:In “[^”]+,”|“[^”]+” opens|"
                r"The first ad of the campaign is a 30-second spot)",
                text,
            )
            if not titled and not text.startswith(
                ("Lawler opens with images", "The ad opens with Conley’s own words:")
            ):
                continue
            quotes = re.findall(r"“([^”]+)”", text)[1 if titled else 0 :]
            if len(" ".join(quotes).split()) >= 15:
                blocks.append("\n".join(quotes))
        if blocks or len(media_links(content)) != 1:
            return blocks
        passages = []
        for paragraph in soup.find_all("p"):
            for match in re.finditer(
                r"“([^”]+)”\s+Lawler\s+says\s+in\s+the\s+ad\s*\."
                r"(?:\s+“([^”]+)”(?!\s+(?:says?|said)\b))?",
                paragraph.get_text(" ", strip=True),
                re.I,
            ):
                passages.extend(quote for quote in match.groups() if quote)
        return ["\n".join(passages)] if len(" ".join(passages).split()) >= 15 else []
    if source_id == "salazar":
        blocks = []
        for paragraph in soup.find_all("p"):
            for match in re.finditer(
                r"“([^”]+)”\s+Salazar\s+says\s+in\s+the\s+(?:new\s+)?ad\b\.?"
                r"(?:[\s\ufeff]*“([^”]+)”(?!\s+Salazar\s+(?:says?|said)\b))?",
                paragraph.get_text(" ", strip=True),
                re.I,
            ):
                quotes = [quote for quote in match.groups() if quote]
                if len(" ".join(quotes).split()) >= 15:
                    blocks.append("\n".join(quotes))
        return blocks
    if source_id in {"smp", "one-nation"}:
        blocks = []
        for paragraph in soup.find_all("p"):
            text = paragraph.get_text(" ", strip=True)
            if re.search(r"\b(?:says?|said)\s+in\s+(?:the|an)\s+(?:new\s+)?ad\b", text, re.I):
                quotes = re.findall(r"“([^”]+)”", text)
                if len(" ".join(quotes).split()) >= 15:
                    blocks.append("\n".join(quotes))
        return blocks
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
            if re.match(r"^[A-Z][^:\n]{0,100}\s*:", block):
                return [block] if len(block.split()) >= 15 else []
    return []


def media_links(content: str) -> list[str]:
    soup = BeautifulSoup(content, "html.parser")
    urls = []
    for tag in soup.find_all(["iframe", "a", "video", "source", "div"]):
        value = tag.get("src") or tag.get("href") or tag.get("data-popup", "")
        parsed = urlsplit(value)
        video_host = parsed.hostname in {
            "youtube.com",
            "www.youtube.com",
            "youtu.be",
            "vimeo.com",
            "www.vimeo.com",
            "player.vimeo.com",
            "www.youtube-nocookie.com",
        }
        if parsed.scheme in {"http", "https"} and video_host:
            urls.append(urlunsplit(parsed._replace(scheme="https")))
        elif parsed.scheme == "https" and re.search(r"\.(?:mp4|webm|mp3|wav)(?:\?|$)", value):
            urls.append(value)
        elif (
            parsed.scheme == "https"
            and parsed.hostname in {"x.com", "www.x.com", "twitter.com", "www.twitter.com"}
            and re.fullmatch(r"/[A-Za-z0-9_]{1,15}/status/[0-9]{15,20}", parsed.path)
        ):
            urls.append(value)
        elif (
            parsed.scheme == "https"
            and parsed.netloc == "bigal.media"
            and parsed.path == "/mediaplayer.php"
            and not parsed.fragment
            and set(parse_qs(parsed.query, keep_blank_values=True)) == {"q"}
            and len(parse_qs(parsed.query).get("q", [])) == 1
        ):
            urls.append(value)
        elif (
            parsed.scheme == "https"
            and parsed.netloc == "host2.adimpact.com"
            and not parsed.query
            and not parsed.fragment
            and re.fullmatch(
                r"/admo/viewer/[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}/?", parsed.path
            )
        ):
            urls.append(value)
        elif (
            parsed.scheme == "https"
            and parsed.hostname == "platform.adimpact.com"
            and not parsed.query
            and not parsed.fragment
            and re.fullmatch(r"/viewer/[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}", parsed.path)
        ):
            urls.append(value)
    return sorted(set(urls))


def youtube_id(url: str) -> str | None:
    parsed = urlsplit(url)
    if parsed.scheme != "https":
        return None
    if parsed.hostname == "youtu.be":
        candidate = parsed.path.removeprefix("/")
    elif parsed.hostname in {"youtube.com", "www.youtube.com", "www.youtube-nocookie.com"}:
        if parsed.path == "/watch":
            candidate = parse_qs(parsed.query).get("v", [""])[0]
        elif parsed.path.startswith("/embed/"):
            candidate = parsed.path.removeprefix("/embed/")
        else:
            return None
    else:
        return None
    return candidate if re.fullmatch(r"[A-Za-z0-9_-]{11}", candidate) else None


def lcv_creatives(post: dict) -> list[dict]:
    soup = BeautifulSoup(post["content"]["rendered"], "html.parser")
    classes = post.get("publisher_classes", [])
    races = {
        f"{match[1].upper()}-{int(match[2]):02}"
        for label in classes
        if (match := re.fullmatch(r"race-([a-z]{2})-(\d{2})", label))
    }
    races.update(
        f"{match[0]}-{int(match[1]):02}"
        for match in re.findall(
            r"\b([A-Z]{2})[-–](\d{1,2})\b", plain_html(post["title"]["rendered"])
        )
    )
    senate_states = {
        "iowa": "IA",
        "maine": "ME",
        "michigan": "MI",
        "new-hampshire": "NH",
        "north-carolina": "NC",
        "ohio": "OH",
        "texas": "TX",
    }
    if "position-senate" in classes:
        races.update(
            state + "-Senate" for name, state in senate_states.items() if f"race-{name}" in classes
        )
    creatives = []
    starts = set()
    explicit = bool(re.search(r"\bscript\s+below\b", soup.get_text(" "), re.I))
    for heading in soup.find_all(["p", "h2", "h3"]):
        label = heading.get_text(" ", strip=True)
        marker = bool(re.fullmatch(r"script\s+below", label, re.I))
        heading_marker = bool(re.search(r"\bscript\s+below\b", label, re.I))
        if not marker and not (
            (heading_marker or any(youtube_id(url) for url in media_links(str(heading))))
            and re.match(r"(?:WATCH\b|[A-Z]{2}(?:[-–]|\s+)(?:\d{1,2}|Sen(?:ate)?):)", label, re.I)
        ):
            continue
        context = heading.find_previous_sibling() if marker else heading
        if context is None:
            continue
        urls = [url for url in media_links(str(context)) if youtube_id(url)]
        if not urls and not (marker or heading_marker):
            continue
        lines = []
        start = None
        for paragraph in heading.find_next_siblings():
            text = paragraph.get_text(" ", strip=True)
            if not text or re.fullmatch(r"script\s+below", text, re.I):
                continue
            if paragraph.name != "p" or any(
                node.strip() and node.find_parent(["i", "em"]) is None
                for node in paragraph.find_all(string=True)
            ):
                break
            start = start or id(paragraph)
            lines.append(plain_html(str(paragraph)))
        text = "\n".join(lines)
        if (
            start is None
            or start in starts
            or len(text.split()) < 15
            or re.match(r"paid for by\b", text, re.I)
        ):
            continue
        starts.add(start)
        label = re.sub(r"\s*script\s+below\s*$", "", context.get_text(" ", strip=True), flags=re.I)
        match = re.search(r"\b([A-Z]{2})(?:[-–]|\s+)(\d{1,2}|Sen(?:ate)?)\b", label, re.I)
        race = (
            f"{match[1].upper()}-"
            + ("Senate" if match[2].lower().startswith("sen") else f"{int(match[2]):02}")
            if match
            else next(iter(races))
            if len(races) == 1
            else "Unresolved"
            if races
            else None
        )
        if race is None:
            continue  # Do not silently include state/local ads or guess a multi-race target.
        creatives.append(
            {
                "text": text,
                "title": label,
                "race": race,
                "chamber": (
                    "Senate"
                    if race.endswith("-Senate")
                    else "House"
                    if race != "Unresolved" or all(not hint.endswith("-Senate") for hint in races)
                    else ""
                ),
                "media_urls": urls,
                "quoted_copy": not explicit,
            }
        )
    return creatives


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


def cfg_creatives(content: str, candidates: list[dict]) -> list[dict]:
    scripts = transcript_blocks(content)
    if scripts:
        return [{"text": script} for script in scripts]
    soup = BeautifulSoup(content, "html.parser")
    excerpts = []
    linked_candidates = {}
    for paragraph in soup.find_all("p"):
        text = paragraph.get_text(" ", strip=True)
        urls = media_links(str(paragraph))
        if len(urls) == 1 and re.search(r"\b(?:watch|view)\b", text, re.I):
            ids = {c["candidate_id"] for c in candidate_mentions(text, candidates)}
            linked_candidates.setdefault(urls[0], set()).update(ids)
        if re.search(r"\b(?:the\s+ad\s+(?:says|states|asked)|a\s+narrator\s+says)\b", text, re.I):
            quotes = re.findall(r'“([^”]+)”|"([^"]+)"', text)
            lines = [curly or straight for curly, straight in quotes]
            if len(" ".join(lines).split()) >= 15:
                excerpts.append("\n".join(lines))
    urls = media_links(content)
    if len(urls) == 1 and excerpts:
        return [{"text": "\n".join(excerpts), "media_urls": urls, "quoted_copy": True}]
    creatives = {}
    for excerpt in excerpts:
        ids = {c["candidate_id"] for c in candidate_mentions(excerpt, candidates)}
        matches = [url for url, linked_ids in linked_candidates.items() if ids & linked_ids]
        if len(matches) == 1:
            creatives.setdefault(matches[0], []).append(excerpt)
    return [
        {"text": "\n".join(excerpts), "media_urls": [url], "quoted_copy": True}
        for url, excerpts in creatives.items()
    ]


def parse_post(
    post: dict, source: Source, observed: str, candidates: list[dict] | None = None
) -> list[dict]:
    title = html.unescape(BeautifulSoup(post["title"]["rendered"], "html.parser").get_text())
    content = post["content"]["rendered"]
    reviewed_copy = candidate_ad_copy(content, source.id) if source.id == "lawler" else []
    reviewed_expenditure = source.id == "ua-vote-pac" and re.match(
        r"^UA Launches Independent Expenditure\b", title
    )
    announcement_names = {
        "nrsc": r"(?:National Republican Senatorial Committee(?:\s*\(NRSC\))?|NRSC)",
        "rogers": r"Mike Rogers",
        "sullivan": r"Dan Sullivan",
        "flint": r"Aaron Flint",
    }
    announcement_name = announcement_names.get(source.id)
    introduction = plain_html(content)[:1500]
    cfg_producer = None
    if source.id == "cfg":
        if re.search(r"\b[A-Z]{2}[-–](?:GOV|AG)\b", title) or not re.search(
            r"\b(?:[A-Z]{2}[-–](?:SEN|AL|\d{1,2})|"
            r"\d{1,2}\s*(?:st|nd|rd|th)?\s+Congressional District|U\.S\.\s+Senate)\b",
            title + "\n" + introduction,
        ):
            return []
        announcement = re.search(
            r"\b(Club for Growth Action|Win It Back PAC|Alabama Freedom Fund)\s+"
            r"(?:launched|released|announced)[^.\n]{0,180}\b(?:ads?|investment|buy)\b",
            introduction,
        )
        if not announcement:
            return []
        cfg_producer = announcement[1]
    reviewed_announcement = announcement_name and re.search(
        rf"\b{announcement_name}[^.\n]{{0,50}}"
        r"\b(?:released|launched|unveiled|is releasing|is out with|"
        r"announced the launch of)\s+(?:a|an|his|its)"
        r"(?:\s+(?:new|newest|digital|television|TV|radio|six-figure|seven-figure))*"
        r"\s+ad\b",
        introduction,
        re.I,
    )
    if source.id == "nrsc" and not reviewed_announcement:
        reviewed_announcement = re.search(
            r"\bNRSC\) is celebrating [^.\n]{0,220}"
            r"\bwith a new voter outreach effort highlighting a digital ad\b",
            introduction,
            re.I,
        )
    if source.id == "wfw":
        reviewed_announcement = re.match(
            r"^Winning For Women Launches\b.*\bAdvocacy Campaign\b", title, re.I
        ) and re.search(r"\bThe ads will run in\b", introduction, re.I)
    if cfg_producer:
        reviewed_announcement = True
    if (
        not is_ad_release(title)
        and source.id != "lcv-vf"
        and not reviewed_copy
        and not reviewed_expenditure
        and not reviewed_announcement
    ):
        return []
    # Rogers's release has a stray letter inside its heading, not the spoken script.
    body = (
        re.sub(r"(transcript below:)r(?=</)", r"\1", content) if source.id == "rogers" else content
    )
    blocks = cooper_transcripts(body) if source.id == "cooper" else transcript_blocks(body)
    if source.id == "wfw-af":
        blocks = [
            re.split(
                r"(?m)^[^\n]{1,160}[ \t][–—-][ \t][A-Z]{2}-\d{2}\nWatch Here(?:\n|$)",
                block,
            )[0].strip()
            for block in blocks
        ]
    if source.id == "stover":
        blocks = [
            re.split(
                r"(?m)^(?:Stover is committed to representing|To learn more about Stover)",
                block,
            )[0].strip()
            for block in blocks
        ]
    if source.id == "marshall":
        soup = BeautifulSoup(body, "html.parser")
        blocks = []
        for heading in soup.select("h2.release__heading"):
            paragraph = heading.find_next_sibling()
            if (
                re.fullmatch(r"Transcript:", heading.get_text(strip=True), re.I)
                and paragraph
                and "release__lines" in paragraph.get("class", [])
            ):
                blocks.extend(transcript_blocks(str(heading) + str(paragraph)))
    if source.id == "barr":
        # Barr's scripts label every speaker; unlabeled paragraphs resume the release.
        speaker_blocks = []
        for block in blocks:
            lines = []
            for line in block.splitlines():
                if not re.match(r"^[A-Z][^:\n]{0,100}\s*:", line):
                    break
                lines.append(line)
            if len(" ".join(lines).split()) >= 15:
                speaker_blocks.append("\n".join(lines))
        blocks = speaker_blocks
    quoted_copy = False
    if not blocks:
        blocks = reviewed_copy or candidate_ad_copy(content, source.id)
        quoted_copy = bool(blocks)
    title_races = set(re.findall(r"\b([A-Z]{2})[-–](\d{1,2})\b", title))
    race_match = next(iter(title_races)) if len(title_races) == 1 else None
    phase = "primary" if re.search(r"\bprimary\b", title, re.I) else "unknown"
    full_text = plain_html(content)
    visible_release_date = None
    if source.id == "salazar" and (
        release_date := re.search(
            r"FOR IMMEDIATE RELEASE\s+([A-Za-z]+)\s+(\d{1,2})(?:st|nd|rd|th)?,\s+(2026)\b",
            full_text,
            re.I,
        )
    ):
        visible_release_date = (
            datetime.strptime(
                f"{release_date[1]} {release_date[2]}, {release_date[3]}", "%B %d, %Y"
            )
            .date()
            .isoformat()
        )
    if phase == "unknown" and re.search(r"\bgeneral election\b", full_text, re.I):
        phase = "general"
    if source.id == "young-kim" and re.search(
        r"\bad buy that runs through the [^.\n]{0,60}\bprimary\b", full_text, re.I
    ):
        phase = "primary"
    if source.id == "wfw-af" and re.search(
        r"\bahead of [^.\n]{0,80}\bprimary\b", introduction, re.I
    ):
        phase = "primary"
    if source.id == "cfg" and re.search(
        r"\b(?:Republican|GOP) (?:Senate )?(?:primary|runoff)\b|\bprimary elections\b",
        full_text,
        re.I,
    ):
        phase = "primary"
    creatives = (
        cfg_creatives(body, candidates or [])
        if source.id == "cfg"
        else lcv_creatives(post)
        if source.id == "lcv-vf"
        else [{"text": text} for text in blocks]
    )
    ads = []
    for index, creative in enumerate(creatives):
        text = creative["text"]
        federal_mentions = []
        if source.requires_federal_candidate:
            if not candidates:
                raise ValueError("This source requires the actual federal candidate registry")
            federal_mentions = candidate_mentions(title + "\n" + text, candidates)
            if not federal_mentions:
                continue
        copy = creative.get("quoted_copy", quoted_copy)
        ad = Ad(
            id=f"{source.id}-{post['id']}-{index}",
            source=source.id,
            source_url=post["link"],
            source_record_id=str(post["id"]),
            title=creative.get("title")
            or (title if len(blocks) == 1 else f"{title} / transcript {index + 1}"),
            release_title=title if source.id == "lcv-vf" else "",
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
                        kind="publisher_ad_copy" if copy else "publisher_transcript",
                    )
                )
                for line in text.splitlines()
            ],
            source_hash=digest(content),
            phase=phase,
            chamber=creative.get(
                "chamber", "House" if source.id == "cfg" and race_match else source.chamber
            ),
            race=creative.get("race")
            or (
                f"{race_match[0]}-{int(race_match[1]):02}"
                if race_match
                else source.fixed_race or "Unresolved"
            ),
            state=("" if creative["race"] == "Unresolved" else creative["race"][:2])
            if "race" in creative
            else race_match[0]
            if race_match
            else source.fixed_race[:2],
            media_urls=creative.get("media_urls", media_links(content)),
            language=language_of(text),
            language_basis="langdetect seeded model; >=0.90 probability, otherwise unknown",
            quality_flags=["publisher_ad_copy_completeness_unverified"] if copy else [],
            attribution_basis=(
                f"Official {source.sponsor} release at {post['link']}; alignment is the "
                "publisher's electoral alignment, not inferred from hostile vocabulary. "
                "Joint or candidate-paid creative requires separate payer review."
            ),
        )
        if (
            source.id == "cassidy"
            and title.startswith("NRSC Releases New Ad")
            and "NRSC-produced video" in full_text
        ):
            ad.sponsor = "NRSC"
            ad.sponsor_type = "party"
            ad.quality_flags.append("party_ad_republished_by_candidate_campaign")
            ad.attribution_basis = (
                f"Official Cassidy release at {post['link']} explicitly identifies the "
                "NRSC as the ad's producer and releasing organization. The campaign "
                "hosts the script; sole legal payer is not independently verified."
            )
        if cfg_producer:
            ad.sponsor = cfg_producer
            ad.quality_flags.append("affiliated_group_ad_published_by_club_for_growth")
            ad.attribution_basis = (
                f"The Club for Growth public release at {post['link']} explicitly names "
                f"{cfg_producer} as the organization releasing this ad. These affiliated "
                "organizations are not interchangeable payers; the sole legal payer is "
                "not independently verified. Republican alignment describes the named "
                "organization's electoral program."
            )
        if visible_release_date and visible_release_date != ad.published:
            ad.quality_flags.append("publisher_visible_release_date_differs_from_cms")
            ad.segments[0].update(
                publisher_visible_release_date=visible_release_date,
                cms_publication_date=ad.published,
            )
        if federal_mentions:
            ad.segments[0]["federal_scope_candidate_ids"] = sorted(
                {candidate["candidate_id"] for candidate in federal_mentions}
            )
        if source.id == "grothman":
            ad.attribution_basis = (
                f"Campaign-issued release reproduced by WisPolitics at {post['link']}; "
                "Republican alignment describes the Grothman campaign, not the mirror's "
                "editorial alignment. Creative payer not independently verified."
            )
            ad.quality_flags.append("campaign_release_reproduced_by_wispolitics")
        record = ad.to_dict()
        ads.append(enrich(record, candidates) if source.requires_federal_candidate else record)
    return ads


def collect_wordpress(
    client: Client,
    source: Source,
    until: str,
    observed: str | None = None,
    candidates: list[dict] | None = None,
    reviews: list[dict] | None = None,
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
        if source.discovery == "reviewed_releases":
            from political_ads.reviewed_releases import reviewed_release

            selected = [review for review in reviews or [] if review["source"] == source.id]
            if not selected:
                raise ValueError("Reviewed release source requires its explicit evidence ledger")
            for review in selected:
                if "2026-01-01" <= review["published"] <= until:
                    ads.append(reviewed_release(client, source, review, candidates or [], observed))
                    status["posts_scanned"] += 1
            status.update(
                state="partial",
                discovery_complete=False,
                ads_with_text=len(ads),
                scope="Individually reviewed public ad scripts/quotations; not complete discovery",
            )
            return ads, status
        if source.discovery != "wordpress":
            from political_ads.discovery import public_posts

            posts, complete = public_posts(client, source, until)
            for post in posts:
                status["posts_scanned"] += 1
                parsed = parse_post(post, source, observed, candidates)
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
                if (
                    source.rest_base == "article" or source.id == "ua-vote-pac"
                ) and "content" not in post:
                    layouts = post.get("acf", {}).get("page_layout", [])
                    content = "\n".join(
                        layout.get("component_wysiwyg", {}).get("content", "") for layout in layouts
                    )
                    post["content"] = {"rendered": content}
                if not all(field in post for field in ("id", "date", "content", "title", "link")):
                    raise ValueError("Endpoint does not expose the expected WordPress schema")
                if not "2026-01-01" <= post["date"][:10] <= until:
                    raise ValueError("Endpoint ignored delivery/release date filters")
                if (
                    source.id == "votevets"
                    and not post["content"]["rendered"].strip()
                    and is_ad_release(plain_html(post["title"]["rendered"]))
                ):
                    if urlsplit(post["link"]).hostname != urlsplit(source.url).hostname:
                        raise ValueError("Public release linked to a different publisher")
                    release, _ = client.get(post["link"], refresh=True, retry=False)
                    article = BeautifulSoup(release, "html.parser")
                    content = article.select_one(".body-content .wysiwyg-text")
                    if content is not None:
                        post["content"] = {"rendered": str(content)}
                        status["public_html_bodies_recovered"] = (
                            status.get("public_html_bodies_recovered", 0) + 1
                        )
                    else:
                        status["public_html_without_script_container"] = (
                            status.get("public_html_without_script_container", 0) + 1
                        )
                seen.add(post["id"])
                status["posts_scanned"] += 1
                parsed = parse_post(post, source, observed, candidates)
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
