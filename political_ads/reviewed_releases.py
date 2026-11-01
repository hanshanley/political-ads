from __future__ import annotations

import json
import re
from datetime import datetime
from hashlib import sha256
from io import BytesIO
from urllib.parse import parse_qs, urljoin, urlsplit

from bs4 import BeautifulSoup
from pypdf import PdfReader

from political_ads.images import image_segments, recognize_image
from political_ads.registry import candidate_mentions, enrich
from political_ads.schema import Ad, digest
from political_ads.sources import Source, language_of, media_links, plain_html, transcript_blocks


def linked_ad_text(client, content: str, review: dict, identities: list[dict]) -> str:
    evidence = review["linked_ad_text"]
    url = evidence["url"]
    target = urlsplit(url)
    public_player = (
        target.netloc == "bigal.media"
        and target.path == "/mediaplayer.php"
        and url in media_links(content)
    )
    public_report = (
        target.netloc == "www.washingtonexaminer.com"
        and target.path.startswith("/news/campaigns/congressional/")
        and not target.query
        and not target.fragment
    )
    public_campaign_pdf = (
        target.netloc == "www.brooksforcongress.com"
        and target.path.startswith("/wp-content/uploads/2026/")
        and target.path.endswith(".pdf")
        and not target.query
        and not target.fragment
    )
    links = {a.get("href") for a in BeautifulSoup(content, "html.parser").select("a[href]")}
    if (
        target.scheme != "https"
        or not (public_player or public_report or public_campaign_pdf)
        or url not in links
    ):
        raise ValueError("Ad text must come from an explicitly linked supported public page")
    if review["completeness"] != "partial_quotation":
        raise ValueError("Linked ad words require explicitly unverified completeness")
    body, _ = client.get(url, refresh=True, retry=False)
    if public_campaign_pdf:
        if evidence.get("format") != "pdf" or sha256(body).hexdigest() != evidence["file_sha256"]:
            raise ValueError("Linked PDF bytes changed; literal ad evidence requires a new review")
        reader = PdfReader(BytesIO(body))
        pages = evidence["pages"]
        if (
            not pages
            or any(type(page) is not int or not 1 <= page <= len(reader.pages) for page in pages)
            or pages != sorted(set(pages))
        ):
            raise ValueError("Linked PDF needs distinct, ordered, in-range reviewed pages")
        selected_pages = [reader.pages[page - 1] for page in pages]
        originals = {
            (annotation.get_object().get("/A") or {}).get("/URI")
            for page in selected_pages
            for annotation in page.get("/Annots", [])
            if annotation.get_object().get("/Subtype") == "/Link"
        }
        if review["media_url"] not in originals:
            raise ValueError("Linked PDF's exact original ad link is missing")
        linked = "\n".join(page.extract_text() or "" for page in selected_pages)
    else:
        linked = body.decode("utf-8")
    if digest(linked) != evidence["content_sha256"]:
        raise ValueError("Linked source changed; literal ad evidence requires a new review")
    visible = re.sub(r"\s+", " ", plain_html(linked)).strip()
    if not evidence["required_context"] or not all(
        context in visible for context in evidence["required_context"]
    ):
        raise ValueError("Linked source's explicit ad context is missing")
    if not candidate_mentions(visible, identities):
        raise ValueError("Linked source does not identify the reviewed federal candidate")
    if public_campaign_pdf:
        return visible
    selected = BeautifulSoup(linked, "html.parser").select(evidence["selector"])
    if len(selected) != 1:
        raise ValueError("Linked ad text must match exactly one reviewed element")
    return re.sub(r"\s+", " ", plain_html(str(selected[0]))).strip()


def publisher_caption_text(
    client, content: str, source: Source, review: dict, identities: list[dict]
):
    evidence = review["publisher_captions"]
    candidate_id, release_url, caption_name, link_label = {
        "aba-wagner-captions": (
            "H2MO02102",
            "https://www.aba.com/about-us/press-room/press-releases/"
            "missouri-voter-education-ad-rep-ann-wagner",
            "expanding-opportunities-for-missourians--rep-ann-wagner-rmo02",
            "new ad",
        ),
        "aba-delacruz-captions": (
            "H0TX15124",
            "https://www.aba.com/about-us/press-room/press-releases/"
            "texas-voter-education-ad-rep-monica-de-la-cruz",
            "supporting-texas-small-businesses--rep-monica-de-la-cruz-rtx15",
            "new ad",
        ),
        "aba-huizenga-captions": (
            "H0MI02094",
            "https://www.aba.com/about-us/press-room/press-releases/"
            "michigan-rep-bill-huizenga-voter-education-ad",
            "delivering-for-michigan-families--rep-bill-huizenga-rmi04",
            "new ad",
        ),
        "aba-nunn-captions": (
            "H2IA03119",
            "https://bankingjournal.aba.com/2026/08/"
            "aba-iba-release-ads-urging-hinson-nunn-to-keep-fighting-for-iowa-families/",
            "fighting-for-a-more-affordable-iowa--rep-zach-nunn-ria03",
            "released new ads",
        ),
        "aba-ciscomani-captions": (
            "H2AZ02360",
            "https://www.aba.com/about-us/press-room/press-releases/"
            "arizona-voter-ad-rep-juan-ciscomani",
            "supporting-families-and-small-businesses--rep-juan-ciscomani-raz06",
            "Click here to see the ad.",
        ),
    }.get(source.id, ("", "", "", ""))
    index_url = (
        "https://www.aba.com/advocacy/political-engagement/voter-education/voter-education-ads"
    )
    caption_url = urlsplit(evidence["url"])
    if (
        not candidate_id
        or source.sponsor_type != "outside_group"
        or source.alignment != "R"
        or review["candidate_id"] != candidate_id
        or identities[0]["party"] != "REP"
        or review["source_url"] != release_url
        or review["retrieval_url"] != review["source_url"]
        or review["format"] != "html"
        or review["completeness"] != "partial_quotation"
        or any(
            review.get(key)
            for key in (
                "broadcast_evidence",
                "printed_ad_text",
                "reported_ad_text",
                "linked_ad_text",
            )
        )
        or evidence["index_url"] != index_url
        or caption_url.scheme != "https"
        or caption_url.netloc != "www.aba.com"
        or caption_url.path != "/-/media/aba/video-transcripts/" + caption_name + ".vtt"
        or caption_url.fragment
        or not re.fullmatch(r"rev=[a-f0-9]{32}", caption_url.query)
    ):
        raise ValueError("Unsupported publisher caption evidence")
    release_soup = BeautifulSoup(content, "html.parser")
    links = [
        a["href"]
        for a in release_soup.select("a[href]")
        if a.get_text(" ", strip=True) == link_label
    ]
    if len(links) != 1 or digest(links[0]) != evidence["release_link_sha256"]:
        raise ValueError("Publisher's reviewed new-ad link is missing or changed")
    if source.id == "aba-nunn-captions":
        originals = [
            node
            for node in release_soup.select("iframe[src]")
            if node.get("title") == evidence["ad_title"]
        ]
        video_id = parse_qs(urlsplit(review["media_url"]).query).get("v", [""])[0]
        if (
            len(originals) != 1
            or originals[0]["src"] != f"https://www.youtube.com/embed/{video_id}?feature=oembed"
        ):
            raise ValueError("Publisher's embedded original must identify the reviewed Nunn ad")
    if links[0] != index_url:
        # Inspect the public wrapper locally; never request its tracking URL.
        wrapper = urlsplit(links[0])
        protected = urlsplit(parse_qs(wrapper.query).get("url", [""])[0])
        if (
            wrapper.scheme != "https"
            or wrapper.netloc != "nam12.safelinks.protection.outlook.com"
            or protected.scheme != "https"
            or protected.netloc != "urldefense.proofpoint.com"
            or protected.path != "/v2/url"
            or parse_qs(protected.query).get("u")
            != [
                "https-3A__www.aba.com_advocacy_political-2Dengagement_"
                "voter-2Deducation_voter-2Deducation-2Dads"
            ]
        ):
            raise ValueError("Publisher's protected link must identify the exact public ad index")
    body, _ = client.get(index_url, refresh=True, retry=False)
    if sha256(body).hexdigest() != evidence["index_sha256"]:
        raise ValueError("Publisher ad index changed; captions require a new review")
    soup = BeautifulSoup(body, "html.parser")
    cards = soup.select(evidence["card_selector"])
    headings = cards[0].select("h3") if len(cards) == 1 else []
    if len(headings) != 1 or headings[0].get_text(" ", strip=True) != evidence["ad_title"]:
        raise ValueError("Publisher caption card must identify exactly one reviewed ad")
    modal_key = cards[0].get("data-vid-modal-trigger")
    modals = soup.select(f'div.video-modal[data-vid-modal="{modal_key}"]')
    players = modals[0].select("video") if len(modals) == 1 else []
    if (
        len(players) != 1
        or not re.fullmatch(r"[A-Za-z0-9_-]{11}", players[0].get("data-youtube-id", ""))
        or review["media_url"] != "https://www.youtube.com/watch?v=" + players[0]["data-youtube-id"]
        or {
            urljoin(index_url, track["src"])
            for track in players[0].select('track[src][srclang="en"]')
            if track.get("kind") in {"captions", "subtitles"}
        }
        != {evidence["url"]}
    ):
        raise ValueError(
            "Exact ad modal, original video, or publisher caption association is missing"
        )
    body, _ = client.get(evidence["url"], refresh=True, retry=False)
    if sha256(body).hexdigest() != evidence["file_sha256"]:
        raise ValueError("Publisher captions changed; literal words require a new review")
    vtt = body.decode("utf-8-sig").replace("\r\n", "\n").replace("\r", "\n")
    timestamp = r"\d{2}:[0-5]\d:[0-5]\d\.\d{3}"
    matches = list(re.finditer(rf"(?m)^(\d+)\n({timestamp}) --> ({timestamp})\n", vtt))
    if not matches or vtt[: matches[0].start()].strip() != "WEBVTT":
        raise ValueError("Publisher captions require numbered WebVTT cues")
    cues = []
    previous_end = 0
    for index, match in enumerate(matches):
        stop = matches[index + 1].start() if index + 1 < len(matches) else len(vtt)
        payload = vtt[match.end() : stop].strip()
        for marker in ("<v ->", "<v Narrator>"):
            if payload.startswith(marker):
                payload = payload.removeprefix(marker).removesuffix("</v>")
                break
        start, end = match[2], match[3]
        seconds = [
            int(time[:2]) * 3600 + int(time[3:5]) * 60 + float(time[6:]) for time in (start, end)
        ]
        if (
            int(match[1]) != index + 1
            or not payload
            or any(marker in payload for marker in ("<", ">", "\n\n"))
            or not previous_end <= seconds[0] < seconds[1]
        ):
            raise ValueError("Publisher caption cue identity, literal text, or timing is invalid")
        previous_end = seconds[1]
        cues.append(
            {
                "cue_id": index + 1,
                "start": start,
                "end": end,
                "text": re.sub(r"\s+", " ", payload),
            }
        )
    selected_ids = evidence["cue_ids"]
    if (
        not selected_ids
        or any(type(index) is not int or not 1 <= index <= len(cues) for index in selected_ids)
        or selected_ids != sorted(set(selected_ids))
    ):
        raise ValueError("Publisher captions need distinct ordered reviewed cue IDs")
    selected = [cues[index - 1] for index in selected_ids]
    text = "\n".join(cue["text"] for cue in selected)
    if (
        review["passages"] != [cue["text"] for cue in selected]
        or len(text.split()) > 25
        or not candidate_mentions(text, identities)
    ):
        raise ValueError(
            "Caption excerpt must equal reviewed cues, identify the candidate, and stay bounded"
        )
    return text, selected


def broadcast_ad_text(content: str, source: Source, review: dict) -> str:
    url = urlsplit(review["source_url"])
    audio = urlsplit(review["media_url"])
    if (
        source.id != "ngb-mtpr"
        or source.url != "https://www.mtpr.org"
        or review["retrieval_url"] != review["source_url"]
        or url.netloc != "www.mtpr.org"
        or not re.fullmatch(r"/podcast/campaign-beat/\d{4}-\d{2}-\d{2}/[^/]+", url.path)
        or url.path.split("/")[3] != review["published"]
        or url.query
        or url.fragment
        or review["format"] != "html"
        or review["candidate_id"] != "H6MT01152"
        or review["completeness"] != "partial_quotation"
        or review.get("linked_ad_text")
        or audio.scheme != "https"
        or audio.netloc != "traffic.omny.fm"
        or not audio.path.startswith("/d/clips/")
        or not audio.path.endswith("/audio.mp3")
        or audio.query
        or audio.fragment
    ):
        raise ValueError("Broadcast evidence requires the reviewed MTPR episode and public audio")
    evidence = review["broadcast_evidence"]
    soup = BeautifulSoup(content, "html.parser")
    players = [
        node
        for node in soup.select(".PCEP-audioPlayer ps-stream")
        if node.get("data-stream-id") == evidence["stream_id"]
    ]
    if len(players) != 1 or players[0].get("data-stream-program-name") != review["release_title"]:
        raise ValueError("Reviewed broadcast stream identity or episode title is missing")
    streams = players[0].select("ps-stream-url")
    if (
        len(streams) != 1
        or streams[0].get("data-stream-format") != "audio/mpeg"
        or streams[0].get("data-stream-url") != review["media_url"]
    ):
        raise ValueError("Reviewed broadcast's exact episode audio association is missing")
    paragraphs = soup.select(evidence["paragraph_selector"])
    if (
        len(paragraphs) != 1
        or paragraphs[0].name != "p"
        or paragraphs[0].find_parent(class_="PCEP-articleBody") is None
    ):
        raise ValueError("Broadcast ad must match one paragraph inside the episode transcript")
    text = re.sub(r"\s+", " ", plain_html(str(paragraphs[0]))).strip()
    disclaimer = "No Going Back PAC Inc is responsible for the content of this advertisement."
    if not text.startswith("Flint Ad ") or not text.rstrip('"”').endswith(disclaimer):
        raise ValueError(
            "Broadcast paragraph's explicit ad label and payer attribution are missing"
        )
    return text


def printed_ad_text(client, content: str, source: Source, review: dict, identities: list[dict]):
    evidence = review["printed_ad_text"]
    publisher = urlsplit(review["source_url"])
    original = urlsplit(evidence["url"])
    page = re.fullmatch(r"/places/view/(\d+)/[a-z0-9_]+\.html", publisher.path)
    soup = BeautifulSoup(content, "html.parser")
    advertiser = soup.select("h1.ad_name")
    images = soup.select(".galim > img[src]")
    county_party = (
        source.id == "barron-gop-apg-print"
        and source.sponsor_type == "party"
        and source.fixed_race == "WI-07"
        and identities[0]["candidate_id"] == "H6WI07223"
        and publisher.path == "/places/view/105270/barron_county_republican_party.html"
        and len(advertiser) == 1
        and advertiser[0].get_text(" ", strip=True)
        == "Ads for Barron County Republican Party in Rice Lake, WI"
    )
    if (
        source.url != "https://marketplace.apg-wi.com"
        or (source.sponsor_type != "candidate" and not county_party)
        or source.alignment != {"DEM": "D", "REP": "R"}.get(identities[0]["party"], "other")
        or publisher.netloc != "marketplace.apg-wi.com"
        or publisher.query
        or publisher.fragment
        or page is None
        or review["retrieval_url"] != review["source_url"]
        or review["format"] != "html"
        or review["completeness"] != "partial_quotation"
        or review.get("publication_selector") != "h2.ad_date"
        or review.get("linked_ad_text")
        or review.get("broadcast_evidence")
        or original.scheme != "https"
        or original.netloc != "static.wehaacdn.com"
        or original.query
        or original.fragment
        or not re.fullmatch(
            rf"/marketplace-apg--wi-com/imgs/media-images/\d+/images/{page[1]}\.jpg",
            original.path,
        )
        or review["media_url"] != evidence["url"]
        or len(images) != 1
        or images[0]["src"] != evidence["url"]
        or len(advertiser) != 1
        or (
            not county_party
            and not candidate_mentions(advertiser[0].get_text(" ", strip=True), identities)
        )
    ):
        raise ValueError("Print ad requires its exact individual publisher, advertiser and image")
    media, _ = client.get(evidence["url"], retry=False)
    if sha256(media).hexdigest() != evidence["media_sha256"]:
        raise ValueError("Original print image changed; literal text requires a new review")
    image_hash, ocr = recognize_image(client.cache / "printed-ad-images", media)
    lines = image_segments(ocr, image_hash, evidence["url"])
    text = re.sub(r"\s+", " ", "\n".join(line["text"] for line in lines)).strip()
    if image_hash != evidence["media_sha256"] or digest(text) != evidence["ocr_text_sha256"]:
        raise ValueError("Pinned original OCR changed; literal text requires a new review")
    if county_party:
        labels = ["U.S. CONGRESS", "Michael Alfonso (R)", "7th Congressional District"]
        authorization = "PAID FOR AND AUTHORIZED BY THE BARRON COUNTY REPUBLICAN PARTY"
        scope_lines = [[line for line in lines if line["text"] == label] for label in labels]
        if (
            any(len(matches) != 1 for matches in scope_lines)
            or not all(label in review["passages"] for label in labels + [authorization])
            or authorization not in text
        ):
            raise ValueError(
                "County-party print excerpt requires original federal endorsement and authorization"
            )
        bounds = [matches[0]["image_bounds"] for matches in scope_lines]
        if not (
            all(0.4 <= x and x + width <= 0.7 for x, _, width, _ in bounds)
            and bounds[0][1] > bounds[1][1] > bounds[2][1]
        ):
            raise ValueError("Reviewed House identity must remain in the original Congress column")
    offset = 0
    line_ranges = []
    for line in lines:
        value = re.sub(r"\s+", " ", line["text"]).strip()
        line_ranges.append((offset, offset + len(value), line["image_bounds"]))
        offset += len(value) + 1
    position = 0
    passage_bounds = []
    for passage in review["passages"]:
        start = text.find(passage, position)
        if start < 0:
            raise ValueError("Print fragments must be literal original OCR in source order")
        position = start + len(passage)
        passage_bounds.append(
            [bounds for left, right, bounds in line_ranges if left < position and right > start]
        )
    return text, {
        "image_hash": image_hash,
        "image_url": evidence["url"],
        "extraction_engine": ocr["engine"],
        "coordinate_system": ocr["coordinate_system"],
        "ocr_text_sha256": digest(text),
        "passage_bounds": passage_bounds,
    }


def reported_ad_text(content: str, source: Source, review: dict) -> str:
    if (
        source.id
        not in {
            "knott-wunc",
            "finstad-kstp",
            "deboer-washingtonreporter",
            "merrin-washingtonreporter",
            "kiggans-washingtonreporter",
            "begich-nrcc-cnbc",
            "lisonbee-sltrib",
            "gray-csd",
            "friess-primary-tax",
            "alamo-toth-cruz-mediaite",
            "lawler-tell-her-no",
            "pps-house-washingtonreporter",
        }
        or review["format"] != "html"
        or review["media_url"] is not None
        or review["completeness"] != "partial_quotation"
        or any(
            review.get(key) for key in ("broadcast_evidence", "printed_ad_text", "linked_ad_text")
        )
    ):
        raise ValueError("Unsupported unlinked publisher quotation evidence")
    if source.id == "finstad-kstp" and review["candidate_id"] != "H2MN01223":
        raise ValueError("KSTP quotation requires the reviewed Finstad candidate identity")
    if source.id == "deboer-washingtonreporter" and review["candidate_id"] != "H6MI03198":
        raise ValueError("Reporter quotation requires the reviewed DeBoer candidate identity")
    if source.id == "merrin-washingtonreporter" and review["candidate_id"] != "H4OH09169":
        raise ValueError("Reporter quotation requires the reviewed Merrin candidate identity")
    if source.id == "kiggans-washingtonreporter" and review["candidate_id"] != "H2VA02064":
        raise ValueError("Reporter quotation requires the reviewed Kiggans candidate identity")
    if source.id == "lawler-tell-her-no" and review["candidate_id"] != "H2NY17162":
        raise ValueError("Campaign quotation requires the reviewed Lawler candidate identity")
    if source.id == "begich-nrcc-cnbc" and review["candidate_id"] != "H2AK01083":
        raise ValueError("CNBC quotation requires the reviewed Begich candidate identity")
    if source.id == "lisonbee-sltrib":
        if review["candidate_id"] != "H6UT02523":
            raise ValueError("Tribune quotation requires the reviewed Lisonbee candidate identity")
        publications = BeautifulSoup(content, "html.parser").select(
            'meta[itemprop="datePublished"]'
        )
        if len(publications) != 1 or publications[0].get("content", "")[:10] != review["published"]:
            raise ValueError("Tribune visible and metadata publication dates must agree")
    if source.id == "gray-csd":
        if review["candidate_id"] != "H6WY00217":
            raise ValueError("CSD quotation requires the reviewed Gray candidate identity")
        publications = []
        for node in BeautifulSoup(content, "html.parser").select(
            'script[type="application/ld+json"]'
        ):
            article = json.loads(node.get_text())
            if isinstance(article, dict) and article.get("@type") == "NewsArticle":
                publications.append(article)
        if (
            len(publications) != 1
            or publications[0].get("datePublished", "")[:10] != review["published"]
            or " ".join(publications[0].get("headline", "").split()) != review["release_title"]
        ):
            raise ValueError("CSD visible and article metadata publication evidence must agree")
    if source.id == "friess-primary-tax":
        if review["candidate_id"] != "H6WY01165":
            raise ValueError("Campaign quotation requires the reviewed Friess candidate identity")
        publications = BeautifulSoup(content, "html.parser").select(".elementor-element-55bb28c")
        if (
            len(publications) != 1
            or datetime.strptime(
                publications[0].get_text(" ", strip=True), "For Immediate Release: %B %d, %Y"
            )
            .date()
            .isoformat()
            != review["published"]
        ):
            raise ValueError("Campaign visible and immediate-release publication dates must agree")
    if source.id == "alamo-toth-cruz-mediaite":
        if review["candidate_id"] != "H6TX08175":
            raise ValueError("Alamo endorsement requires the reviewed Toth House beneficiary")
        publications = BeautifulSoup(content, "html.parser").select(
            'meta[property="article:published_time"]'
        )
        if len(publications) != 1 or publications[0].get("content", "")[:10] != review["published"]:
            raise ValueError("Alamo report requires a unique matching publication date")
    if source.id == "pps-house-washingtonreporter" and review["candidate_id"] != "H2FL04211":
        raise ValueError("Reporter quotation requires the reviewed Bean speaker identity")
    evidence = review["reported_ad_text"]
    paragraphs = BeautifulSoup(content, "html.parser").select(evidence["paragraph_selector"])
    if len(paragraphs) != 1 or paragraphs[0].name != "p":
        raise ValueError("Reviewed ad quotation must match exactly one paragraph")
    paragraph = paragraphs[0].get_text(" ", strip=True)
    if digest(paragraph) != evidence["paragraph_sha256"]:
        raise ValueError("Reviewed ad quotation paragraph changed")
    pattern = (
        r'"([^"]+)" Knott says in the ad\. "([^"]+)"'
        if source.id == "knott-wunc"
        else r"“([^”]+)” the ad says\. “([^”]+)”"
    )
    if source.id == "deboer-washingtonreporter":
        pattern = r"“([^”]+)” the narrator says in the ad\. “([^”]+)”"
    elif source.id == "merrin-washingtonreporter":
        pattern = r"Merrin [^“”]+\. “([^”]+)” he adds in the ad\. “([^”]+)”"
    elif source.id == "kiggans-washingtonreporter":
        pattern = r"“([^”]+)” a local news anchor says during the ad\. [^“”]+“[^”]+”"
    elif source.id == "lawler-tell-her-no":
        pattern = (
            r"Pearl River, NY — October 12, 2026 — Today, the Lawler for Congress campaign "
            r"launched “Tell Her No,” which will be running on digital, text, and streaming "
            r"platforms\. “([^”]+)” Conley told an interviewer last November, and the ad "
            r"lets that sit for a second before it plays what she’s been telling Democratic "
            r"audiences ever since\."
        )
    elif source.id == "begich-nrcc-cnbc":
        pattern = (
            r'"[^"]+\. (But Nick Begich changed that\. [^"]+)" says the voiceover '
            r"in the ad for Begich, who is seeking a second term as Alaska's "
            r"at-large representative\."
        )
    elif source.id == "pps-house-washingtonreporter":
        pattern = (
            r"The ad also includes footage of Rep\. Lloyd Smucker [^“”]+“([^”]+)” "
            r"The Washington Reporter previously covered that hearing\."
        )
    elif source.id == "lisonbee-sltrib":
        pattern = r"“([^”]+)” she says in the ad\. “([^”]+)”"
    elif source.id == "gray-csd":
        pattern = r"“([^”]+)” says the ad\."
    elif source.id == "friess-primary-tax":
        pattern = r"“([^”]+)” Friess says in the ad\. “([^”]+)”"
    elif source.id == "alamo-toth-cruz-mediaite":
        pattern = (
            r"“([^”]+? Congress\.) [^”]+” said Cruz in the spot, "
            r"which was put on by the Alamo Freedom Fighters PAC\."
        )
    match = re.fullmatch(pattern, paragraph)
    if not match:
        raise ValueError("Publisher must explicitly attribute the selected quotations to the ad")
    text = (
        match[1]
        if source.id == "friess-primary-tax"
        else match[2]
        if source.id in {"deboer-washingtonreporter", "merrin-washingtonreporter"}
        else "\n".join(match.groups())
    )
    if len(text.split()) > 25:
        raise ValueError("Unlinked publisher quotations must remain within the 25-word limit")
    return text


def reviewed_release(client, source: Source, review: dict, candidates: list[dict], observed: str):
    for key in ("source_url", "retrieval_url"):
        url = urlsplit(review[key])
        if url.scheme != "https" or url.hostname != urlsplit(source.url).hostname:
            raise ValueError("Reviewed release must remain on its registered public publisher")
    scope_ids = [review["candidate_id"]]
    multi_race = source.id == "pps-house-washingtonreporter"
    if multi_race:
        expected_scope = {
            "H2FL04211": "FL-04",
            "H4MO08162": "MO-08",
            "H6PA16320": "PA-11",
            "H8OK01157": "OK-01",
        }
        if (
            review.get("candidate_ids") != sorted(expected_scope)
            or review["candidate_id"] != "H2FL04211"
            or source.fixed_race != "Multi-race"
            or source.sponsor_type != "outside_group"
            or source.alignment != "R"
            or review.get("scope_role") != "current_house_office_not_election_candidacy"
        ):
            raise ValueError("Unsupported multi-race House issue-ad scope")
        scope_ids = review["candidate_ids"]
    elif review.get("candidate_ids"):
        raise ValueError("Multiple federal identities require a supported multi-race source")
    identities = [c for c in candidates if c["candidate_id"] in scope_ids]
    candidate = next((c for c in identities if c["candidate_id"] == review["candidate_id"]), None)
    if not candidate or candidate["office"] != "H" or candidate["election_year"] != "2026":
        raise ValueError("Reviewed release requires an exact 2026 federal House candidate")
    if multi_race and (
        {c["candidate_id"]: f"{c['state']}-{int(c['district']):02}" for c in identities}
        != expected_scope
        or any(
            c["office"] != "H" or c["election_year"] != "2026" or c["party"] != "REP"
            for c in identities
        )
    ):
        raise ValueError("Multi-race issue ad requires all reviewed Republican House offices")
    race = "Multi-race" if multi_race else f"{candidate['state']}-{int(candidate['district']):02}"
    if race != source.fixed_race:
        raise ValueError("Reviewed federal candidate does not match the registered race")
    body, _ = client.get(review["retrieval_url"], refresh=True, retry=False)
    if review["format"] == "wordpress":
        post = json.loads(body)
        if str(post["id"]) != review["record_id"] or post["link"] != review["source_url"]:
            raise ValueError("Reviewed WordPress post identity changed")
        content = post["content"]["rendered"]
        published = post["date"][:10]
        title = plain_html(post["title"]["rendered"])
    elif review["format"] == "html":
        content = body.decode("utf-8")
        soup = BeautifulSoup(content, "html.parser")
        publication = soup.find("meta", property="article:published_time")
        heading = soup.find("h1")
        if review.get("heading_selector"):
            headings = soup.select(review["heading_selector"])
            if len(headings) != 1 or headings[0].name not in {"h1", "h2"}:
                raise ValueError("Reviewed article heading must match exactly one h1 or h2")
            heading = headings[0]
        if heading is None:
            raise ValueError("Reviewed article publication metadata or heading is missing")
        if review.get("publication_selector"):
            dates = soup.select(review["publication_selector"])
            if len(dates) != 1:
                raise ValueError("Reviewed visible publication date must match exactly one element")
            published = (
                datetime.strptime(
                    dates[0].get_text(" ", strip=True),
                    review.get("publication_date_format", "%B %d, %Y"),
                )
                .date()
                .isoformat()
            )
            if publication is not None and publication["content"][:10] != published:
                raise ValueError("Reviewed visible and metadata publication dates disagree")
            if dates[0].has_attr("datetime") and dates[0]["datetime"][:10] != published:
                raise ValueError("Reviewed visible and datetime publication dates disagree")
        elif publication is not None:
            published = publication["content"][:10]
        else:
            raise ValueError("Reviewed article publication metadata or heading is missing")
        title = heading.get_text(" ", strip=True)
    else:
        raise ValueError("Unsupported reviewed release format")
    if digest(content) != review["content_sha256"]:
        raise ValueError("Source content changed; literal ad evidence requires a new review")
    if published != review["published"] or title != review["release_title"]:
        raise ValueError("Reviewed publication date or release title changed")
    visible = re.sub(r"\s+", " ", plain_html(content)).strip()
    if not all(context in visible for context in review["required_context"]):
        raise ValueError("Explicit advertiser/ad quotation context is missing")
    if source.id == "friess-primary-tax":
        if (
            candidate["candidate_id"] != "H6WY01165"
            or candidate["name"] != "FRIESS, STEPHEN"
            or candidate["principal_committee"] != "C00945980"
            or review.get("candidate_public_name", {}).get("full_name") != "Steve Friess"
        ):
            raise ValueError(
                "Friess public name requires the exact reviewed candidate and committee"
            )
        identities = [candidate | {"reviewed_alias": review["candidate_public_name"]}]
    if candidate["candidate_id"] not in {
        row["candidate_id"] for row in candidate_mentions(visible, identities)
    } and not (source.id == "barron-gop-apg-print" and review.get("printed_ad_text")):
        raise ValueError("Reviewed candidate is not identified in the publisher's evidence")
    if multi_race and set(scope_ids) != {
        row["candidate_id"] for row in candidate_mentions(visible, identities)
    }:
        raise ValueError("Multi-race issue ad must explicitly identify all reviewed House members")
    if multi_race:
        original = "https://x.com/Policy_Solution/status/2059962673865920660?s=20"
        links = {a.get("href") for a in BeautifulSoup(content, "html.parser").select("a[href]")}
        if review.get("discovered_original_url") != original or original not in links:
            raise ValueError("Reviewed issue-ad report must retain its actual original-post link")
    broadcast = review.get("broadcast_evidence")
    printed = review.get("printed_ad_text")
    reported = review.get("reported_ad_text")
    captions = review.get("publisher_captions")
    if (
        not broadcast
        and not printed
        and not reported
        and not captions
        and review["media_url"] not in media_links(content)
    ):
        raise ValueError("Reviewed original ad link is missing")
    if captions:
        passage_source, caption_cues = publisher_caption_text(
            client, content, source, review, identities
        )
    elif reported:
        passage_source = reported_ad_text(content, source, review)
    elif printed:
        passage_source, print_evidence = printed_ad_text(
            client, content, source, review, identities
        )
    elif broadcast:
        passage_source = broadcast_ad_text(content, source, review)
    elif review.get("linked_ad_text"):
        passage_source = linked_ad_text(client, content, review, identities)
    else:
        passage_source = visible
    passages = review["passages"]
    if not passages or len(" ".join(passages).split()) < 15:
        raise ValueError("Reviewed ad needs substantive literal text")
    position = 0
    for passage in passages:
        match = passage_source.find(passage, position)
        if match < 0:
            raise ValueError("Reviewed ad passages must be literal and retain source order")
        position = match + len(passage)
    full_script = review["completeness"] == "marked_script"
    text = "\n".join(passages)
    language_review = review.get("reviewed_language")
    if multi_race:
        if (
            not language_review
            or language_review.get("language") != "en"
            or language_review.get("text_sha256") != digest(text)
            or not language_review.get("basis")
        ):
            raise ValueError("Reviewed issue-ad language must bind the exact English quotation")
    elif language_review:
        raise ValueError("Unsupported reviewed release language override")
    if review.get("script_selector") and not full_script:
        raise ValueError("Reviewed script boundary requires an explicitly marked full script")
    if full_script:
        script_content = content
        if review.get("script_selector"):
            scripts = BeautifulSoup(content, "html.parser").select(review["script_selector"])
            if len(scripts) != 1:
                raise ValueError("Reviewed script boundary must match exactly one element")
            script_content = str(scripts[0])
        if text not in transcript_blocks(script_content):
            raise ValueError("Complete script must equal an explicitly marked transcript block")
    elif review["completeness"] != "partial_quotation":
        raise ValueError("Unknown reviewed ad completeness")
    flags = [
        "individually_reviewed_public_ad_text",
        "publisher_date_not_verified_first_release_or_paid_delivery",
        (
            "news_publisher_reports_marked_ad_script"
            if review.get("script_selector")
            else "campaign_release_reproduced_by_news_publisher"
        )
        if full_script
        else (
            "newspaper_display_ad_partial_image_text"
            if printed
            else "publisher_caption_partial_ad_copy"
            if captions
            else "publisher_linked_source_quotes_partial_ad_copy"
            if review.get("linked_ad_text")
            else "campaign_release_quotes_partial_ad_copy"
            if source.id == "lawler-tell-her-no"
            else "news_report_quotes_partial_ad_copy"
        ),
    ]
    if not full_script:
        flags.append("publisher_ad_copy_completeness_unverified")
    if broadcast:
        flags.append("publisher_audio_episode_not_individual_ad_original")
    if reported:
        flags.extend(["original_ad_media_unverified", "ad_legal_payer_unverified"])
    if source.id == "lawler-tell-her-no":
        flags.append("opponent_interview_clip_used_in_ad")
    if source.id == "begich-nrcc-cnbc":
        flags.append("selected_ending_of_longer_ad_quotation")
    if multi_race:
        flags.extend(
            [
                "multi_race_house_issue_ad",
                "current_house_office_not_election_candidacy",
                "one_creative_not_one_record_per_highlighted_member",
            ]
        )
    if captions:
        flags.extend(
            [
                "publisher_captions_not_independently_verified_against_audio",
                "original_ad_media_unverified",
                "ad_legal_payer_unverified",
            ]
        )
    if printed:
        flags.extend(
            [
                "selected_image_words_visually_reviewed",
                "image_ocr_not_verified_complete_transcription",
                "ad_legal_payer_unverified",
            ]
        )
        if source.id == "barron-gop-apg-print":
            flags.extend(
                [
                    "mixed_federal_nonfederal_print_ad",
                    "nonfederal_slate_and_ballot_text_excluded",
                    "printed_party_authorization_visually_reviewed",
                ]
            )
    segments = [
        {"text": passage, "kind": "publisher_transcript" if full_script else "publisher_ad_copy"}
        for passage in passages
    ]
    segments[0]["release_evidence"] = review
    segments[0]["federal_scope_candidate_ids"] = scope_ids
    if captions:
        for segment, cue in zip(segments, caption_cues, strict=True):
            segment["caption_cue"] = {
                "url": captions["url"],
                "file_sha256": captions["file_sha256"],
                "cue_id": cue["cue_id"],
                "start": cue["start"],
                "end": cue["end"],
            }
    if printed:
        for segment, bounds in zip(segments, print_evidence.pop("passage_bounds"), strict=True):
            segment.update(print_evidence | {"kind": "image_ocr", "image_line_bounds": bounds})
    return enrich(
        Ad(
            id=f"{source.id}-{review['record_id']}-0",
            source=source.id,
            source_url=review["source_url"],
            source_record_id=review["record_id"],
            title=review["release_title"],
            sponsor=source.sponsor,
            sponsor_type=source.sponsor_type,
            alignment=source.alignment,
            published=published,
            observed=observed,
            placement=(
                "publisher_print_ad_listing"
                if printed
                else "publisher_linked_caption_excerpt"
                if captions
                else "publisher_reported_ad_copy"
                if reported
                else "campaign_release"
            ),
            text=text,
            segments=segments,
            source_hash=(
                digest(
                    content
                    + "\n"
                    + print_evidence["image_hash"]
                    + "\n"
                    + print_evidence["ocr_text_sha256"]
                )
                if printed
                else digest(
                    content + "\n" + captions["index_sha256"] + "\n" + captions["file_sha256"]
                )
                if captions
                else digest(content)
            ),
            date_basis="publisher_ad_listing_date" if printed else "publisher_report_date",
            phase=review["phase"],
            race=race,
            state="" if multi_race else candidate["state"],
            chamber="House",
            language="en" if multi_race else language_of(text),
            language_basis=(
                language_review["basis"]
                if multi_race
                else "langdetect seeded model; >=0.90 probability, otherwise unknown"
            ),
            media_urls=[] if reported else [review["media_url"]],
            attribution_basis=review["attribution_basis"],
            quality_flags=flags,
        ).to_dict(),
        candidates,
    )
