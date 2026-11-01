import json
from dataclasses import replace
from hashlib import sha256
from io import BytesIO
from urllib.parse import urlencode

import pytest
from pypdf import PdfReader, PdfWriter
from pypdf.annotations import Link
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

from political_ads import cli
from political_ads.schema import digest
from political_ads.sources import SOURCES, collect_wordpress


@pytest.mark.parametrize("sponsor", ["wagner", "delacruz", "huizenga", "nunn", "ciscomani"])
@pytest.mark.parametrize(
    ("failure", "message"),
    [
        (None, None),
        ("missing_link", "new-ad link is missing"),
        ("wrong_destination", "exact public ad index"),
        ("index_changed", "ad index changed"),
        ("missing_card", "exactly one reviewed ad"),
        ("duplicate_card", "exactly one reviewed ad"),
        ("missing_modal", "caption association is missing"),
        ("wrong_video", "caption association is missing"),
        ("wrong_track", "caption association is missing"),
        ("caption_changed", "Publisher captions changed"),
        ("invalid_timing", "timing is invalid"),
        ("duplicate_vtt_id", "cue identity"),
        ("unexpected_markup", "literal text"),
        ("duplicate_selected_id", "ordered reviewed cue IDs"),
        ("reversed_selected_ids", "ordered reviewed cue IDs"),
        ("nonliteral_passage", "must equal reviewed cues"),
        ("long_excerpt", "stay bounded"),
        ("missing_caption_candidate", "identify the candidate"),
        ("unsupported_source", "Unsupported publisher caption"),
        ("candidate_mismatch", "Unsupported publisher caption"),
        ("race_mismatch", "registered race"),
        ("party_mismatch", "Unsupported publisher caption"),
        ("complete_script", "Unsupported publisher caption"),
    ],
)
def test_publisher_caption_excerpt_requires_exact_release_card_video_and_cues(
    sponsor, failure, message
):
    from political_ads.reviewed_releases import reviewed_release

    source = next(s for s in SOURCES if s.id == f"aba-{sponsor}-captions")
    if failure == "unsupported_source":
        source = replace(source, id="unsupported-caption-publisher")
    candidate_id, formal_name, public_name, release_path, caption_name, original_id = {
        "wagner": (
            "H2MO02102",
            "WAGNER, ANN L.",
            "Ann Wagner",
            "missouri-voter-education-ad-rep-ann-wagner",
            "expanding-opportunities-for-missourians--rep-ann-wagner-rmo02",
            "HamagNqLjgM",
        ),
        "delacruz": (
            "H0TX15124",
            "DE LA CRUZ, MONICA",
            "Monica De La Cruz",
            "texas-voter-education-ad-rep-monica-de-la-cruz",
            "supporting-texas-small-businesses--rep-monica-de-la-cruz-rtx15",
            "nDfvmZ6GETI",
        ),
        "huizenga": (
            "H0MI02094",
            "HUIZENGA, WILLIAM P",
            "Bill Huizenga",
            "michigan-rep-bill-huizenga-voter-education-ad",
            "delivering-for-michigan-families--rep-bill-huizenga-rmi04",
            "8vBOgzOmwTY",
        ),
        "nunn": (
            "H2IA03119",
            "NUNN, ZACH",
            "Zach Nunn",
            "",
            "fighting-for-a-more-affordable-iowa--rep-zach-nunn-ria03",
            "lgeYp1Br2aY",
        ),
        "ciscomani": (
            "H2AZ02360",
            "CISCOMANI, JUAN",
            "Juan Ciscomani",
            "arizona-voter-ad-rep-juan-ciscomani",
            "supporting-families-and-small-businesses--rep-juan-ciscomani-raz06",
            "W3nV6yHm2VI",
        ),
    }[sponsor]
    state, district = source.fixed_race.split("-")
    candidate = {
        "candidate_id": candidate_id,
        "name": formal_name,
        "party": "REP",
        "state": state,
        "office": "H",
        "district": district,
        "election_year": "2026",
    }
    if failure == "party_mismatch":
        candidate["party"] = "DEM"
    elif failure == "candidate_mismatch":
        candidate["candidate_id"] = "H9MO02999"
    elif failure == "race_mismatch":
        candidate["district"] = "99"
    candidates = [candidate]
    if sponsor == "huizenga":
        alias = {
            "candidate_id": candidate_id,
            "name": "HUIZENGA, BILL",
            "evidence_url": "https://huizenga.house.gov/",
            "basis": "Fixture reviewed public full name.",
        }
        candidates.append(candidate | {"name": alias["name"], "reviewed_alias": alias})
    index_url = (
        "https://www.aba.com/advocacy/political-engagement/voter-education/voter-education-ads"
    )
    caption_url = (
        "https://www.aba.com/-/media/aba/video-transcripts/" + caption_name + ".vtt?rev=" + "a" * 32
    )
    destination = (
        "https-3A__www.aba.com_advocacy_political-2Dengagement_"
        "voter-2Deducation_voter-2Deducation-2Dads"
    )
    if failure == "wrong_destination":
        destination = "https-3A__www.example.test_unrelated"
    protected = "https://urldefense.proofpoint.com/v2/url?" + urlencode({"u": destination})
    link = "https://nam12.safelinks.protection.outlook.com/?" + urlencode({"url": protected})
    if sponsor != "wagner" and failure != "wrong_destination":
        link = index_url
    label = (
        "released new ads"
        if sponsor == "nunn"
        else "Click here to see the ad."
        if sponsor == "ciscomani"
        else "new ad"
    )
    anchor = "" if failure == "missing_link" else f'<a href="{link}">{label}</a>'
    content = (
        "<h1>Fixture new ad announcement</h1>"
        '<li class="byline__inline">October 23, 2026</li>'
        f"<p>{public_name} is the beneficiary of the {anchor}.</p>"
    )
    if sponsor == "nunn":
        embed_id = "OtherVid123" if failure == "wrong_primary_original" else original_id
        content += (
            f'<iframe title="Fixture {public_name} ad" '
            f'src="https://www.youtube.com/embed/{embed_id}?feature=oembed"></iframe>'
            '<iframe title="Another candidate ad" '
            'src="https://www.youtube.com/embed/Another1234?feature=oembed"></iframe>'
        )
    card = (
        '<div class="video" data-vid-modal-trigger="fixture">'
        f"<h3>Fixture {public_name} ad</h3></div>"
    )
    if failure == "missing_card":
        card = ""
    elif failure == "duplicate_card":
        card *= 2
    video_id = "OtherVid123" if failure == "wrong_video" else original_id
    track = caption_url + "wrong" if failure == "wrong_track" else caption_url
    modal = (
        '<div class="video-modal" data-vid-modal="fixture">'
        f'<video data-youtube-id="{video_id}">'
        f'<track kind="captions" srclang="en" src="{track}">'
        f'<track kind="subtitles" srclang="en" src="{track}">'
        "</video></div>"
    )
    if failure == "missing_modal":
        modal = ""
    index = (card + modal).encode()
    passages = [
        "Families deserve lower costs and better local opportunities.",
        f"That's why Representative {public_name}",
        "is supporting local investment and small businesses.",
        "An excluded fourth cue describes proposals outside this bounded excerpt.",
    ]
    if failure == "missing_caption_candidate":
        passages[1] = "That's why our local representative"
    voice = "<v ->" if sponsor == "wagner" else "<v Narrator>"
    voice_end = "</v>" if sponsor in {"nunn", "ciscomani"} else ""
    vtt = (
        "\ufeffWEBVTT\n\n"
        + "".join(
            f"{number}\n00:00:0{number - 1}.000 --> 00:00:0{number}.000\n"
            f"{voice}{passage}{voice_end}\n"
            for number, passage in enumerate(passages, 1)
        )
    ).encode()
    if failure == "invalid_timing":
        vtt = vtt.replace(b"00:00:03.000", b"00:00:00.100")
    elif failure == "duplicate_vtt_id":
        vtt = vtt.replace(b"\n3\n", b"\n2\n")
    elif failure == "unexpected_markup":
        vtt = vtt.replace(voice.encode(), b"<script>")
    cue_ids = [1, 2, 3]
    if failure == "duplicate_selected_id":
        cue_ids = [1, 2, 2]
    elif failure == "reversed_selected_ids":
        cue_ids = [3, 2, 1]
    elif failure == "long_excerpt":
        cue_ids.append(4)
    selected = [passages[number - 1] for number in cue_ids]
    if failure == "nonliteral_passage":
        selected[0] += " Invented words."
    review = {
        "source": source.id,
        "source_url": (
            source.url + "/2026/08/"
            "aba-iba-release-ads-urging-hinson-nunn-to-keep-fighting-for-iowa-families/"
            if sponsor == "nunn"
            else source.url + "/about-us/press-room/press-releases/" + release_path
        ),
        "record_id": "fixture",
        "format": "html",
        "published": "2026-10-23",
        "release_title": "Fixture new ad announcement",
        "publication_selector": "li.byline__inline",
        "candidate_id": candidate["candidate_id"],
        "media_url": "https://www.youtube.com/watch?v=" + original_id,
        "phase": "unknown",
        "completeness": "marked_script" if failure == "complete_script" else "partial_quotation",
        "required_context": [public_name],
        "passages": selected,
        "content_sha256": digest(content),
        "publisher_captions": {
            "index_url": index_url,
            "index_sha256": sha256(index).hexdigest(),
            "release_link_sha256": digest(link),
            "card_selector": 'div.video[data-vid-modal-trigger="fixture"]',
            "ad_title": f"Fixture {public_name} ad",
            "url": caption_url,
            "file_sha256": sha256(vtt).hexdigest(),
            "cue_ids": cue_ids,
        },
        "attribution_basis": "Fixture beneficiary alignment, not organization-wide partisanship.",
    }
    review["retrieval_url"] = review["source_url"]
    calls = []
    bodies = {
        review["source_url"]: content.encode(),
        index_url: index + (b" changed" if failure == "index_changed" else b""),
        caption_url: vtt + (b" changed" if failure == "caption_changed" else b""),
    }

    class Client:
        def get(self, url, **kwargs):
            calls.append(url)
            assert url in bodies, "Only the three public publisher assets may be requested"
            return bodies[url], {}

    if failure:
        with pytest.raises(ValueError, match=message):
            reviewed_release(Client(), source, review, candidates, "2026-11-01")
    else:
        ad = reviewed_release(Client(), source, review, candidates, "2026-11-01")
        assert calls == [review["source_url"], index_url, caption_url]
        assert ad["text"] == "\n".join(selected)
        assert [s["caption_cue"]["cue_id"] for s in ad["segments"]] == [1, 2, 3]
        assert ad["segments"][-1]["caption_cue"]["end"] == "00:00:03.000"
        assert ad["source_hash"] == digest(
            content + "\n" + sha256(index).hexdigest() + "\n" + sha256(vtt).hexdigest()
        )
        assert ad["phase"] == "unknown"
        assert ad["date_basis"] == "publisher_report_date"
        assert "original_ad_media_unverified" in ad["quality_flags"]
        assert "publisher_captions_not_independently_verified_against_audio" in ad["quality_flags"]


def test_nunn_publisher_captions_reject_another_embedded_original():
    test_publisher_caption_excerpt_requires_exact_release_card_video_and_cues(
        "nunn", "wrong_primary_original", "embedded original"
    )


@pytest.mark.parametrize("failure", [None, "missing_original", "date_mismatch", "missing_alias"])
def test_linked_partial_ad_with_reviewed_name_and_visible_utc_date(failure):
    from political_ads.reviewed_releases import reviewed_release

    source = next(s for s in SOURCES if s.id == "wittman-yahoo-verify")
    candidate = {
        "candidate_id": "H8VA01147",
        "name": "WITTMAN, ROBERT J. MR.",
        "party": "REP",
        "state": "VA",
        "office": "H",
        "district": "01",
        "election_year": "2026",
    }
    alias = {
        "candidate_id": candidate["candidate_id"],
        "name": "WITTMAN, ROB",
        "evidence_url": "https://wittman.house.gov/",
        "basis": "Fixture reviewed public full name and district.",
    }
    candidates = [candidate]
    if failure != "missing_alias":
        candidates.append(candidate | {"name": alias["name"], "reviewed_alias": alias})
    original = "https://media.example.test/individual-ad.mp4"
    timestamp = "2026-09-25T21:41:39Z" if failure == "date_mismatch" else "2026-09-24T21:41:39Z"
    link = "" if failure == "missing_original" else f'<a href="{original}">The original ad</a>'
    passages = [
        "I listen to working families and support local small businesses.",
        "We can lower costs and improve opportunities for everyone.",
    ]
    body = (
        "<h1>Fixture ad report</h1>"
        f'<time datetime="{timestamp}">Thu, September 24, 2026 at 9:41 PM UTC</time>'
        "<p>Congressman Rob Wittman released an ad.</p>"
        f'<p>"{passages[0]}" Wittman says in the ad. "{passages[1]}"</p>' + link
    ).encode()
    review = {
        "source": source.id,
        "record_id": "fixture",
        "source_url": source.url + "/fixture",
        "retrieval_url": source.url + "/fixture",
        "format": "html",
        "content_sha256": digest(body.decode()),
        "published": "2026-09-24",
        "release_title": "Fixture ad report",
        "heading_selector": "h1",
        "publication_selector": "time[datetime]",
        "publication_date_format": "%a, %B %d, %Y at %I:%M %p %Z",
        "candidate_id": candidate["candidate_id"],
        "media_url": original,
        "phase": "unknown",
        "completeness": "partial_quotation",
        "required_context": ["Congressman Rob Wittman", "Wittman says in the ad."],
        "passages": passages,
        "attribution_basis": "Fixture publisher attribution, not independently verified payer.",
    }

    class Client:
        def get(self, url, **kwargs):
            assert url == review["retrieval_url"]
            return body, {}

    if failure:
        message = {
            "missing_original": "original ad link is missing",
            "date_mismatch": "visible and datetime publication dates disagree",
            "missing_alias": "candidate is not identified",
        }[failure]
        with pytest.raises(ValueError, match=message):
            reviewed_release(Client(), source, review, candidates, "2026-11-01")
    else:
        ad = reviewed_release(Client(), source, review, candidates, "2026-11-01")
        assert ad["text"] == "\n".join(passages)
        assert ad["published"] == "2026-09-24"
        assert ad["date_basis"] == "publisher_report_date"
        assert ad["phase"] == "unknown"
        assert ad["media_urls"] == [original]
        assert "publisher_ad_copy_completeness_unverified" in ad["quality_flags"]


def print_fixture():
    source = next(s for s in SOURCES if s.id == "hermening-apg-print")
    candidate = {
        "candidate_id": "H6WI07249",
        "name": "HERMENING, KEVIN",
        "party": "REP",
        "state": "WI",
        "office": "H",
        "district": "07",
        "election_year": "2026",
    }
    url = source.url + "/places/view/103908/kevin_hermening_for_congress.html"
    image = (
        "https://static.wehaacdn.com/marketplace-apg--wi-com/"
        "imgs/media-images/103899/images/103908.jpg"
    )
    passages = [
        "Congress needs leaders who listen.",
        "Kevin Hermening will protect Wisconsin families and support working people.",
    ]
    body = (
        '<h1 class="ad_name">Ads for Kevin Hermening for Congress in Wisconsin</h1>'
        '<h2 itemprop="title">A campaign advertisement</h2>'
        '<h2 class="ad_date">Aug 05, 2026.\n Kevin Hermening for Congress '
        "Government Ads from Spooner Advocate</h2>"
        f'<div class="galim"><img src="{image}"></div>'
    ).encode()
    media = b"\xff\xd8\xfffixture original JPEG"
    ocr = {
        "engine": "Fixture OCR",
        "coordinate_system": "normalized image coordinates",
        "lines": [
            {"text": passages[0], "confidence": 1, "bounds": [0.1, 0.8, 0.8, 0.05]},
            {
                "text": "Kevin Hermening will protect",
                "confidence": 1,
                "bounds": [0.1, 0.6, 0.8, 0.05],
            },
            {
                "text": "Wisconsin families and support working people.",
                "confidence": 1,
                "bounds": [0.1, 0.5, 0.8, 0.05],
            },
        ],
    }
    review = {
        "source": source.id,
        "record_id": "103908",
        "source_url": url,
        "retrieval_url": url,
        "format": "html",
        "published": "2026-08-05",
        "release_title": "A campaign advertisement",
        "heading_selector": 'h2[itemprop="title"]',
        "publication_selector": "h2.ad_date",
        "publication_date_format": (
            "%b %d, %Y. Kevin Hermening for Congress Government Ads from Spooner Advocate"
        ),
        "candidate_id": candidate["candidate_id"],
        "media_url": image,
        "phase": "unknown",
        "completeness": "partial_quotation",
        "required_context": ["Kevin Hermening"],
        "passages": passages,
        "content_sha256": digest(body.decode()),
        "printed_ad_text": {
            "url": image,
            "media_sha256": sha256(media).hexdigest(),
            "ocr_text_sha256": digest(" ".join(line["text"] for line in ocr["lines"])),
        },
        "attribution_basis": "Publisher-listed candidate advertiser; legal payer unverified.",
    }
    return source, candidate, review, body, media, ocr


def test_print_ad_binds_individual_image_and_retains_only_selected_ocr(tmp_path, monkeypatch):
    from political_ads import reviewed_releases

    source, candidate, review, body, media, ocr = print_fixture()
    calls = []

    class Client:
        cache = tmp_path

        def get(self, url, **kwargs):
            calls.append(url)
            assert not kwargs["retry"]
            return (body if url == review["source_url"] else media), {}

    def recognize(directory, original):
        assert directory == tmp_path / "printed-ad-images" and original == media
        return sha256(media).hexdigest(), ocr

    monkeypatch.setattr(reviewed_releases, "recognize_image", recognize)
    ad = reviewed_releases.reviewed_release(Client(), source, review, [candidate], "2026-10-31")
    assert ad["text"] == "\n".join(review["passages"])
    assert calls == [review["source_url"], review["media_url"]]
    assert ad["date_basis"] == "publisher_ad_listing_date" and ad["phase"] == "unknown"
    assert "ad_legal_payer_unverified" in ad["quality_flags"]
    assert all(s["kind"] == "image_ocr" for s in ad["segments"])
    assert ad["segments"][1]["image_line_bounds"] == [line["bounds"] for line in ocr["lines"][1:]]
    assert ad["source_hash"] == digest(
        body.decode()
        + "\n"
        + sha256(media).hexdigest()
        + "\n"
        + review["printed_ad_text"]["ocr_text_sha256"]
    )


@pytest.mark.parametrize(
    "change",
    [
        "image",
        "duplicate",
        "advertiser",
        "bytes",
        "ocr",
        "html_only",
        "full_script",
        "date",
        "alignment",
    ],
)
def test_print_ad_rejects_unbound_or_nonliteral_evidence(tmp_path, monkeypatch, change):
    from dataclasses import replace

    from political_ads import reviewed_releases

    source, candidate, review, body, media, ocr = print_fixture()
    if change == "image":
        review["media_url"] = review["media_url"].replace("103908.jpg", "103909.jpg")
        review["printed_ad_text"]["url"] = review["media_url"]
        body = body.replace(b"103908.jpg", b"103909.jpg")
    elif change == "duplicate":
        body += f'<div class="galim"><img src="{review["media_url"]}"></div>'.encode()
    elif change == "advertiser":
        body = body.replace(b"Ads for Kevin Hermening", b"Ads for Another Candidate")
    elif change == "bytes":
        media += b"changed"
    elif change == "ocr":
        ocr["lines"][-1]["text"] = "Changed recognized words."
    elif change == "html_only":
        review["passages"] = [
            "Kevin Hermening offers additional promises here that are not actually in "
            "the original campaign image."
        ]
        body += f"<p>{review['passages'][0]}</p>".encode()
    elif change == "full_script":
        review["completeness"] = "marked_script"
    elif change == "date":
        body = body.replace(b"Aug 05", b"Aug 06")
    else:
        source = replace(source, alignment="D")
    review["content_sha256"] = digest(body.decode())

    class Client:
        cache = tmp_path

        def get(self, url, **kwargs):
            return (body if url == review["source_url"] else media), {}

    monkeypatch.setattr(
        reviewed_releases,
        "recognize_image",
        lambda *args: (review["printed_ad_text"]["media_sha256"], ocr),
    )
    with pytest.raises(ValueError):
        reviewed_releases.reviewed_release(Client(), source, review, [candidate], "2026-10-31")


def county_party_print_fixture():
    source, candidate, review, _, media, _ = print_fixture()
    source = next(s for s in SOURCES if s.id == "barron-gop-apg-print")
    candidate = candidate | {"candidate_id": "H6WI07223", "name": "ALFONSO, MICHAEL"}
    url = source.url + "/places/view/105270/barron_county_republican_party.html"
    image = (
        "https://static.wehaacdn.com/marketplace-apg--wi-com/"
        "imgs/media-images/105261/images/105270.jpg"
    )
    passages = [
        "STRONG LEADERSHIP. SAFE COMMUNITIES. COMMON SENSE SOLUTIONS.",
        "U.S. CONGRESS",
        "Michael Alfonso (R)",
        "7th Congressional District",
        "PAID FOR AND AUTHORIZED BY THE BARRON COUNTY REPUBLICAN PARTY",
    ]
    body = (
        '<h1 class="ad_name">Ads for Barron County Republican Party in Rice Lake, WI</h1>'
        '<h2 itemprop="title">A campaign advertisement</h2>'
        '<h2 class="ad_date">Oct 28, 2026. Barron County Republican Party '
        "Government Ads from Rice Lake Chronotype</h2>"
        f'<div class="galim"><img src="{image}"></div>'
    ).encode()
    ocr = {
        "engine": "Fixture OCR",
        "coordinate_system": "normalized image coordinates",
        "lines": [
            {"text": passages[0], "confidence": 1, "bounds": [0.1, 0.8, 0.8, 0.05]},
            {"text": passages[1], "confidence": 1, "bounds": [0.43, 0.57, 0.2, 0.02]},
            {"text": "STATEWIDE OFFICES", "confidence": 1, "bounds": [0.1, 0.57, 0.2, 0.02]},
            {"text": passages[2], "confidence": 1, "bounds": [0.46, 0.53, 0.2, 0.02]},
            {"text": "Tom Tiffany (R)", "confidence": 1, "bounds": [0.1, 0.53, 0.2, 0.02]},
            {"text": passages[3], "confidence": 1, "bounds": [0.46, 0.51, 0.2, 0.02]},
            {"text": passages[4], "confidence": 1, "bounds": [0.1, 0.1, 0.8, 0.02]},
        ],
    }
    review = review | {
        "source": source.id,
        "record_id": "105270",
        "source_url": url,
        "retrieval_url": url,
        "published": "2026-10-28",
        "publication_date_format": (
            "%b %d, %Y. Barron County Republican Party Government Ads from Rice Lake Chronotype"
        ),
        "candidate_id": candidate["candidate_id"],
        "media_url": image,
        "required_context": ["Barron County Republican Party"],
        "passages": passages,
        "content_sha256": digest(body.decode()),
        "printed_ad_text": {
            "url": image,
            "media_sha256": sha256(media).hexdigest(),
            "ocr_text_sha256": digest(" ".join(line["text"] for line in ocr["lines"])),
        },
    }
    return source, candidate, review, body, media, ocr


@pytest.mark.parametrize(
    "change",
    [None, "source", "candidate", "office", "column", "selected_scope", "authorization"],
)
def test_county_party_print_requires_original_selected_house_column(tmp_path, monkeypatch, change):
    from dataclasses import replace

    from political_ads import reviewed_releases

    source, candidate, review, body, media, ocr = county_party_print_fixture()
    if change == "source":
        source = replace(source, id="another-party-print")
    elif change == "candidate":
        candidate["candidate_id"] = review["candidate_id"] = "H6WI07249"
    elif change == "office":
        ocr["lines"][1]["text"] = "STATE SENATE"
    elif change == "column":
        ocr["lines"][3]["bounds"][0] = 0.1
    elif change == "selected_scope":
        review["passages"].remove("Michael Alfonso (R)")
    elif change == "authorization":
        ocr["lines"][-1]["text"] = "An unrelated organization's authorization."
    review["printed_ad_text"]["ocr_text_sha256"] = digest(
        " ".join(line["text"] for line in ocr["lines"])
    )

    class Client:
        cache = tmp_path

        def get(self, url, **kwargs):
            return (body if url == review["source_url"] else media), {}

    monkeypatch.setattr(
        reviewed_releases,
        "recognize_image",
        lambda *args: (review["printed_ad_text"]["media_sha256"], ocr),
    )
    if change:
        with pytest.raises(ValueError):
            reviewed_releases.reviewed_release(Client(), source, review, [candidate], "2026-11-01")
    else:
        ad = reviewed_releases.reviewed_release(Client(), source, review, [candidate], "2026-11-01")
        assert ad["text"] == "\n".join(review["passages"])
        assert "Tom Tiffany" not in ad["text"] and "STATEWIDE" not in ad["text"]
        assert ad["sponsor_type"] == "party"
        assert "mixed_federal_nonfederal_print_ad" in ad["quality_flags"]
        assert ad["segments"][0]["federal_scope_candidate_ids"] == ["H6WI07223"]


def broadcast_fixture():
    from political_ads.sources import Source

    source = Source(
        "ngb-mtpr",
        "https://www.mtpr.org",
        "No Going Back PAC Inc",
        "R",
        "outside_group",
        "House",
        fixed_race="MT-01",
        discovery="reviewed_releases",
    )
    candidate = {
        "candidate_id": "H6MT01152",
        "name": "FLINT, AARON",
        "party": "REP",
        "state": "MT",
        "office": "H",
        "district": "01",
        "election_year": "2026",
    }
    passage = (
        "Sam Forstag has failed Montana families and supports policies that "
        "will make everyday life more expensive."
    )
    url = "https://www.mtpr.org/podcast/campaign-beat/2026-10-02/fixture-episode"
    audio = (
        "https://traffic.omny.fm/d/clips/"
        "e09de6da-b14d-486a-8271-b19c00d572a0/"
        "e4b419f7-79b4-4815-9b27-b3ce0020c349/"
        "cd8f5757-899c-403f-8c03-b4d8001cf6ae/audio.mp3"
    )
    disclaimer = "No Going Back PAC Inc is responsible for the content of this advertisement."
    content = (
        "<h1>Fixture episode</h1>"
        '<div class="PCEP-timestamp">Published October 2, 2026 at 7:52 PM MDT</div>'
        "<p>A PAC supporting Aaron Flint has a new ad.</p>"
        '<div class="PCEP-audioPlayer">'
        '<ps-stream data-stream-id="fixture-stream" '
        'data-stream-program-name="Fixture episode">'
        f'<ps-stream-url data-stream-format="audio/mpeg" data-stream-url="{audio}">'
        "</ps-stream-url></ps-stream></div>"
        '<div class="PCEP-articleBody">'
        f'<p class="opponent">Forstag Ad "{passage}"</p>'
        f'<p class="supporter">Flint Ad "{passage} {disclaimer}"</p>'
        "</div>"
    )
    review = {
        "source": source.id,
        "record_id": "20261002",
        "source_url": url,
        "retrieval_url": url,
        "format": "html",
        "published": "2026-10-02",
        "release_title": "Fixture episode",
        "heading_selector": "h1",
        "publication_selector": ".PCEP-timestamp",
        "publication_date_format": "Published %B %d, %Y at %I:%M %p MDT",
        "candidate_id": candidate["candidate_id"],
        "media_url": audio,
        "phase": "general",
        "completeness": "partial_quotation",
        "required_context": ["A PAC supporting Aaron Flint has a new ad."],
        "passages": [passage],
        "content_sha256": digest(content),
        "broadcast_evidence": {
            "stream_id": "fixture-stream",
            "paragraph_selector": ".PCEP-articleBody p.supporter",
        },
        "attribution_basis": "Fixture explicitly labeled ad in a publisher audio episode.",
    }
    return source, candidate, review, content.encode()


def test_reviewed_broadcast_binds_the_labeled_ad_and_episode_without_media_requests():
    from political_ads.reviewed_releases import reviewed_release

    source, candidate, review, body = broadcast_fixture()
    calls = []

    class Client:
        def get(self, url, **kwargs):
            calls.append(url)
            return body, {}

    ad = reviewed_release(Client(), source, review, [candidate], "2026-10-31")
    assert ad["text"] == review["passages"][0]
    assert ad["media_urls"] == [review["media_url"]]
    assert "publisher_audio_episode_not_individual_ad_original" in ad["quality_flags"]
    assert calls == [review["retrieval_url"]]


@pytest.mark.parametrize(
    "change",
    ["opponent", "stream", "program", "disclaimer", "audio", "publisher"],
)
def test_reviewed_broadcast_rejects_unbound_ad_or_episode_evidence(change):
    from dataclasses import replace

    from political_ads.reviewed_releases import reviewed_release

    source, candidate, review, body = broadcast_fixture()
    if change == "opponent":
        review["broadcast_evidence"]["paragraph_selector"] = ".PCEP-articleBody p.opponent"
    elif change == "stream":
        review["broadcast_evidence"]["stream_id"] = "different-stream"
    elif change == "program":
        body = body.replace(
            b'data-stream-program-name="Fixture episode"',
            b'data-stream-program-name="Different episode"',
        )
    elif change == "disclaimer":
        body = body.replace(b"No Going Back PAC Inc is responsible", b"Another PAC is responsible")
    elif change == "audio":
        review["media_url"] = review["media_url"].replace("traffic.omny.fm", "example.com")
        body = body.replace(b"traffic.omny.fm", b"example.com")
    else:
        source = replace(source, url="https://example.com")
        review["source_url"] = review["source_url"].replace("www.mtpr.org", "example.com")
        review["retrieval_url"] = review["source_url"]
    review["content_sha256"] = digest(body.decode())

    class Client:
        def get(self, url, **kwargs):
            return body, {}

    with pytest.raises(ValueError):
        reviewed_release(Client(), source, review, [candidate], "2026-10-31")


def linked_pdf_fixture():
    source, candidate, review, body = release_fixture("html")
    passage = review["passages"][0]
    url = "https://www.brooksforcongress.com/wp-content/uploads/2026/10/Fixture-Letter.pdf"
    content = body.decode().replace(passage, "Rhett Marques discussed the campaign.")
    content += f'<a href="{url}">The letter quoting the advertisement</a>'
    context = "The document quotes Rhett Marques's advertisement."
    writer = PdfWriter()
    for text in (
        f"{context} {passage}",
        "The attorney disputes the advertisement and demands a retraction.",
    ):
        page = writer.add_blank_page(width=612, height=792)
        page[NameObject("/Resources")] = DictionaryObject(
            {
                NameObject("/Font"): DictionaryObject(
                    {
                        NameObject("/F1"): DictionaryObject(
                            {
                                NameObject("/Type"): NameObject("/Font"),
                                NameObject("/Subtype"): NameObject("/Type1"),
                                NameObject("/BaseFont"): NameObject("/Helvetica"),
                            }
                        )
                    }
                )
            }
        )
        stream = DecodedStreamObject()
        stream.set_data(f"BT /F1 12 Tf 20 750 Td ({text}) Tj ET".encode())
        page[NameObject("/Contents")] = writer._add_object(stream)
    writer.add_annotation(
        page_number=0,
        annotation=Link(rect=(0, 0, 20, 20), url=review["media_url"]),
    )
    output = BytesIO()
    writer.write(output)
    pdf = output.getvalue()
    extracted = PdfReader(BytesIO(pdf)).pages[0].extract_text()
    review["content_sha256"] = digest(content)
    review["linked_ad_text"] = {
        "url": url,
        "format": "pdf",
        "file_sha256": sha256(pdf).hexdigest(),
        "content_sha256": digest(extracted),
        "pages": [1],
        "required_context": [context],
    }
    return source, candidate, review, content.encode(), pdf


def test_reviewed_linked_pdf_keeps_only_ad_words_and_binds_the_original():
    source, candidate, review, body, pdf = linked_pdf_fixture()
    calls = []

    class Client:
        def get(self, url, **kwargs):
            calls.append(url)
            return (body if url == review["retrieval_url"] else pdf), {}

    ads, status = collect_wordpress(
        Client(), source, "2026-10-30", "2026-10-30", [candidate], [review]
    )
    assert status["state"] == "partial" and len(ads) == 1
    assert ads[0]["text"] == review["passages"][0]
    assert "attorney" not in ads[0]["text"]
    assert ads[0]["segments"][0]["release_evidence"]["linked_ad_text"] == review["linked_ad_text"]
    assert calls == [review["retrieval_url"], review["linked_ad_text"]["url"]]


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("file_sha256", "0" * 64),
        ("content_sha256", "0" * 64),
        ("pages", []),
        ("pages", [1, 1]),
        ("pages", [3]),
        ("required_context", ["A statement absent from the document."]),
    ],
)
def test_reviewed_linked_pdf_rejects_changed_or_unbound_evidence(field, value):
    from political_ads.reviewed_releases import reviewed_release

    source, candidate, review, body, pdf = linked_pdf_fixture()
    review["linked_ad_text"][field] = value

    class Client:
        def get(self, url, **kwargs):
            return (body if url == review["retrieval_url"] else pdf), {}

    with pytest.raises(ValueError):
        reviewed_release(Client(), source, review, [candidate], "2026-10-30")


def test_reviewed_linked_pdf_requires_its_own_exact_original_link():
    from political_ads.reviewed_releases import reviewed_release

    source, candidate, review, body, pdf = linked_pdf_fixture()
    reader = PdfReader(BytesIO(pdf))
    reader.pages[0].pop("/Annots")
    writer = PdfWriter()
    for page in reader.pages:
        writer.add_page(page)
    output = BytesIO()
    writer.write(output)
    pdf = output.getvalue()
    review["linked_ad_text"]["file_sha256"] = sha256(pdf).hexdigest()

    class Client:
        def get(self, url, **kwargs):
            return (body if url == review["retrieval_url"] else pdf), {}

    with pytest.raises(ValueError, match="original"):
        reviewed_release(Client(), source, review, [candidate], "2026-10-30")


def release_fixture(format="wordpress", completeness="partial_quotation"):
    source = next(s for s in SOURCES if s.id == "marques-yellowhammer")
    candidate = {
        "candidate_id": "H6AL01086",
        "name": "MARQUES, RHETT",
        "party": "REP",
        "state": "AL",
        "office": "H",
        "district": "02",
        "election_year": "2026",
    }
    passage = (
        "Rhett Marques will work hard for Alabama families and bring down the costs "
        "of groceries and housing."
    )
    content = (
        "<p>The Marques campaign released a new ad.</p><iframe "
        'src="https://www.youtube.com/embed/aaaaaaaaaaa"></iframe>'
        "<p>A spokesperson said the campaign was spending heavily.</p><p>SCRIPT:</p>"
        f"<p>{passage}</p>"
    )
    url = source.url + "/ad/"
    review = {
        "source": source.id,
        "record_id": "123",
        "source_url": url,
        "retrieval_url": source.url + "/wp-json/wp/v2/posts/123",
        "format": format,
        "published": "2026-07-14",
        "release_title": "A new House ad",
        "candidate_id": candidate["candidate_id"],
        "media_url": "https://www.youtube.com/embed/aaaaaaaaaaa",
        "phase": "primary",
        "completeness": completeness,
        "required_context": ["The Marques campaign released a new ad."],
        "passages": [passage],
        "attribution_basis": "Fixture campaign announcement; publisher is not the legal payer.",
    }
    if format == "wordpress":
        body = json.dumps(
            {
                "id": 123,
                "link": url,
                "date": "2026-07-14T12:00:00",
                "title": {"rendered": review["release_title"]},
                "content": {"rendered": content},
            }
        ).encode()
    else:
        content = (
            '<meta property="article:published_time" content="2026-07-14T12:00:00">'
            "<h1>A new House ad</h1>" + content
        )
        body = content.encode()
        review["retrieval_url"] = url
    review["content_sha256"] = digest(content)
    return source, candidate, review, body


def test_reviewed_release_binds_individual_facebook_library_link_without_requesting_meta():
    source, candidate, review, body = release_fixture()
    original = (
        "https://www.facebook.com/ads/library/?active_status=active&ad_type=all&country=US"
        "&id=1023109076854193&is_targeted_country=false&media_type=all&search_type=page"
        "&sort_data%5Bmode%5D=total_impressions&sort_data%5Bdirection%5D=desc"
        "&view_all_page_id=628266147047913"
    )
    post = json.loads(body)
    post["content"]["rendered"] = post["content"]["rendered"].replace(
        '<iframe src="https://www.youtube.com/embed/aaaaaaaaaaa"></iframe>',
        f'<a href="{original}">First advertisement</a>',
    )
    review["media_url"] = original
    review["content_sha256"] = digest(post["content"]["rendered"])
    calls = []

    class Client:
        def get(self, url, **kwargs):
            calls.append(url)
            assert url == review["retrieval_url"]
            return json.dumps(post).encode(), {}

    ads, status = collect_wordpress(
        Client(), source, "2026-10-30", "2026-10-30", [candidate], [review]
    )
    assert status["state"] == "partial" and len(ads) == 1
    assert ads[0]["text"] == review["passages"][0]
    assert ads[0]["media_urls"] == [original]
    assert ads[0]["segments"][0]["release_evidence"]["media_url"] == original
    assert calls == [review["retrieval_url"]]


def unlinked_knott_fixture():
    source = next(s for s in SOURCES if s.id == "knott-wunc")
    candidate = {
        "candidate_id": "H4NC13116",
        "name": "KNOTT, BRAD",
        "party": "REP",
        "state": "NC",
        "office": "H",
        "district": "13",
        "election_year": "2026",
    }
    passages = [
        "Our families deserve leaders who listen to their concerns.",
        "I will work for our community and protect its future.",
    ]
    paragraph = f'"{passages[0]}" Knott says in the ad. "{passages[1]}"'
    content = (
        '<meta property="article:published_time" content="2026-10-27T15:54:09.967">'
        '<h1>Republican House campaign advertising</h1><div class="ArtP-articleBody">'
        "<p>Brad Knott is buying television advertisements.</p>"
        f"<p>{paragraph}</p><p>A professor discusses advertising strategy.</p></div>"
    )
    url = source.url + "/politics/2026-10-27/republican-house-advertising"
    review = {
        "source": source.id,
        "record_id": "knott-20261027",
        "source_url": url,
        "retrieval_url": url,
        "format": "html",
        "published": "2026-10-27",
        "release_title": "Republican House campaign advertising",
        "candidate_id": candidate["candidate_id"],
        "media_url": None,
        "phase": "unknown",
        "completeness": "partial_quotation",
        "required_context": ["Brad Knott", "Knott says in the ad."],
        "passages": passages,
        "content_sha256": digest(content),
        "reported_ad_text": {
            "paragraph_selector": '.ArtP-articleBody > p:-soup-contains("Knott says in the ad.")',
            "paragraph_sha256": digest(paragraph),
        },
        "attribution_basis": (
            "Publisher quotes ad words; original media and legal payer unverified."
        ),
    }
    return source, candidate, review, content.encode()


def test_unlinked_publisher_quotation_keeps_only_ad_words_and_discloses_missing_original():
    source, candidate, review, body = unlinked_knott_fixture()
    calls = []

    class Client:
        def get(self, url, **kwargs):
            calls.append(url)
            assert url == review["retrieval_url"]
            return body, {}

    ads, status = collect_wordpress(
        Client(), source, "2026-10-30", "2026-11-01", [candidate], [review]
    )
    assert len(ads) == 1 and status["state"] == "partial"
    ad = ads[0]
    assert ad["text"] == "\n".join(review["passages"])
    assert ad["media_urls"] == []
    assert ad["placement"] == "publisher_reported_ad_copy"
    assert ad["segments"][0]["release_evidence"] == review
    assert {"original_ad_media_unverified", "ad_legal_payer_unverified"} <= set(ad["quality_flags"])
    assert ad["date_basis"] == "publisher_report_date" and ad["delivery_start"] is None
    assert "portrayal_review" not in ad
    assert calls == [review["retrieval_url"]]


@pytest.mark.parametrize("failure", ["missing", "ambiguous", "journalism", "statement", "too_long"])
def test_unlinked_publisher_quotation_rejects_unbound_or_non_ad_words(failure):
    source, candidate, review, body = unlinked_knott_fixture()
    if failure == "missing":
        review["reported_ad_text"]["paragraph_selector"] = ".missing"
    elif failure == "ambiguous":
        review["reported_ad_text"]["paragraph_selector"] = ".ArtP-articleBody > p"
    elif failure == "journalism":
        review["passages"].append("Knott says in the ad.")
    else:
        content = body.decode()
        if failure == "statement":
            content = content.replace("Knott says in the ad.", "Knott says in an interview.")
            review["required_context"] = ["Brad Knott"]
            review["reported_ad_text"]["paragraph_selector"] = ".ArtP-articleBody > p:nth-child(2)"
        else:
            content = content.replace(
                review["passages"][0],
                review["passages"][0] + " Another seven words make this excerpt excessive.",
            )
        from bs4 import BeautifulSoup

        paragraph = (
            BeautifulSoup(content, "html.parser")
            .select(review["reported_ad_text"]["paragraph_selector"])[0]
            .get_text(" ", strip=True)
        )
        review["reported_ad_text"]["paragraph_sha256"] = digest(paragraph)
        review["content_sha256"] = digest(content)
        body = content.encode()

    class Client:
        def get(self, url, **kwargs):
            return body, {}

    ads, status = collect_wordpress(
        Client(), source, "2026-10-30", "2026-11-01", [candidate], [review]
    )
    assert ads == [] and status["state"] == "error"


def unlinked_finstad_fixture():
    source = next(s for s in SOURCES if s.id == "finstad-kstp")
    candidate = {
        "candidate_id": "H2MN01223",
        "name": "FINSTAD, BRAD",
        "party": "REP",
        "state": "MN",
        "office": "H",
        "district": "01",
        "election_year": "2026",
    }
    passages = [
        "Our families deserve leaders who listen to their concerns.",
        "I will work for our community and protect its future.",
    ]
    paragraph = f"“{passages[0]}” the ad says. “{passages[1]}”"
    content = (
        '<meta property="article:published_time" content="2026-10-07T23:10:40+00:00">'
        '<h1>Unrelated navigation title</h1><h1 class="fuel-title-heading">House ad report</h1>'
        '<div id="storyContent"><p>Brad Finstad is a Republican House candidate.</p>'
        f'<p class="quoted">{paragraph}</p><p>A spokesman disputes the report.</p></div>'
    )
    url = source.url + "/kstp-news/top-news/house-ad-report/"
    review = {
        "source": source.id,
        "record_id": "20261007",
        "source_url": url,
        "retrieval_url": url,
        "format": "html",
        "content_sha256": digest(content),
        "published": "2026-10-07",
        "release_title": "House ad report",
        "heading_selector": "h1.fuel-title-heading",
        "candidate_id": candidate["candidate_id"],
        "media_url": None,
        "phase": "unknown",
        "completeness": "partial_quotation",
        "required_context": ["Brad Finstad"],
        "passages": passages,
        "reported_ad_text": {
            "paragraph_selector": "#storyContent > p.quoted",
            "paragraph_sha256": digest(paragraph),
        },
        "attribution_basis": (
            "Publisher quotes ad words; original media and legal payer unverified."
        ),
    }
    return source, candidate, review, content.encode()


def test_finstad_report_retains_only_bound_ad_quotations_without_inventing_an_original():
    source, candidate, review, body = unlinked_finstad_fixture()
    calls = []

    class Client:
        def get(self, url, **kwargs):
            calls.append(url)
            assert url == review["retrieval_url"]
            return body, {}

    ads, status = collect_wordpress(
        Client(), source, "2026-10-30", "2026-11-01", [candidate], [review]
    )
    assert status["state"] == "partial" and len(ads) == 1
    ad = ads[0]
    assert ad["text"] == "\n".join(review["passages"])
    assert ad["media_urls"] == [] and ad["phase"] == "unknown"
    assert ad["date_basis"] == "publisher_report_date"
    assert ad["alignment"] == "R" and ad["race"] == "MN-01"
    assert {"original_ad_media_unverified", "ad_legal_payer_unverified"} <= set(ad["quality_flags"])
    assert ad["segments"][0]["release_evidence"] == review
    assert calls == [review["retrieval_url"]]


@pytest.mark.parametrize("failure", ["candidate", "statement", "too_long", "news_video"])
def test_finstad_report_rejects_wrong_identity_non_ad_speech_and_unsupported_media(failure):
    source, candidate, review, body = unlinked_finstad_fixture()
    if failure == "candidate":
        candidate["candidate_id"] = review["candidate_id"] = "H6MN01099"
    elif failure == "news_video":
        review["media_url"] = "https://kstp.com/video/news-report"
    else:
        content = body.decode()
        if failure == "statement":
            content = content.replace("the ad says.", "his spokesman says.")
        else:
            content = content.replace(
                review["passages"][0],
                review["passages"][0]
                + " Another seven words make this selected excerpt excessive.",
            )
        from bs4 import BeautifulSoup

        paragraph = BeautifulSoup(content, "html.parser").select("#storyContent > p.quoted")[0]
        review["reported_ad_text"]["paragraph_sha256"] = digest(paragraph.get_text(" ", strip=True))
        review["content_sha256"] = digest(content)
        body = content.encode()

    class Client:
        def get(self, url, **kwargs):
            return body, {}

    ads, status = collect_wordpress(
        Client(), source, "2026-10-30", "2026-11-01", [candidate], [review]
    )
    assert ads == [] and status["state"] == "error"


def unlinked_deboer_fixture():
    source, candidate, review, body = unlinked_finstad_fixture()
    source = next(s for s in SOURCES if s.id == "deboer-washingtonreporter")
    candidate.update(candidate_id="H6MI03198", name="DEBOER, TERRI", state="MI", district="03")
    first = (
        "Neighbors have known this local broadcaster for years, and the narrator recalls "
        "her service to the community."
    )
    selected = (
        "Now she’s ready to serve our community in Congress, standing up for West Michigan "
        "values of family, hard work, and community."
    )
    paragraph = f"“{first}” the narrator says in the ad. “{selected}”"
    content = (
        '<meta property="article:published_time" content="2026-08-21T14:50:25+00:00">'
        "<h1>DeBoer outside-group ad report</h1><article>"
        "<p>West Michigan for Common Sense supports Terri DeBoer.</p>"
        f'<p class="quoted">{paragraph}</p><p>A spokesman praises the candidate.</p></article>'
    )
    url = source.url + "/deboer-outside-group-ad-report/"
    review.update(
        source=source.id,
        record_id="20260821",
        source_url=url,
        retrieval_url=url,
        content_sha256=digest(content),
        published="2026-08-21",
        release_title="DeBoer outside-group ad report",
        candidate_id=candidate["candidate_id"],
        required_context=["Terri DeBoer", "West Michigan for Common Sense"],
        passages=[selected],
        reported_ad_text={
            "paragraph_selector": "article > p.quoted",
            "paragraph_sha256": digest(paragraph),
        },
    )
    review.pop("heading_selector")
    return source, candidate, review, content.encode(), first


def test_deboer_report_retains_only_selected_narrator_sentence_and_outside_group_provenance():
    source, candidate, review, body, first = unlinked_deboer_fixture()
    calls = []

    class Client:
        def get(self, url, **kwargs):
            calls.append(url)
            assert url == review["retrieval_url"]
            return body, {}

    ads, status = collect_wordpress(
        Client(), source, "2026-10-30", "2026-11-01", [candidate], [review]
    )
    assert status["state"] == "partial" and len(ads) == 1
    ad = ads[0]
    assert ad["text"] == review["passages"][0] and first not in ad["text"]
    assert ad["sponsor_type"] == "outside_group" and ad["race"] == "MI-03"
    assert ad["alignment"] == "R" and ad["media_urls"] == [] and ad["phase"] == "unknown"
    assert ad["date_basis"] == "publisher_report_date"
    assert {"original_ad_media_unverified", "ad_legal_payer_unverified"} <= set(ad["quality_flags"])
    assert ad["segments"][0]["release_evidence"] == review
    assert "portrayal_review" not in ad and calls == [review["retrieval_url"]]


@pytest.mark.parametrize("failure", ["candidate", "statement", "too_long", "unselected"])
def test_deboer_report_rejects_wrong_candidate_non_ad_speech_and_unselected_words(failure):
    source, candidate, review, body, first = unlinked_deboer_fixture()
    if failure == "candidate":
        candidate["candidate_id"] = review["candidate_id"] = "H6MI03999"
    elif failure == "unselected":
        review["passages"] = [first]
    else:
        content = body.decode()
        if failure == "statement":
            content = content.replace("the narrator says in the ad.", "a spokesman says.")
        else:
            original = review["passages"][0]
            review["passages"][0] += (
                " Additional words push the quotation beyond its permitted limit."
            )
            content = content.replace(original, review["passages"][0])
        from bs4 import BeautifulSoup

        paragraph = BeautifulSoup(content, "html.parser").select("article > p.quoted")[0]
        review["reported_ad_text"]["paragraph_sha256"] = digest(paragraph.get_text(" ", strip=True))
        review["content_sha256"] = digest(content)
        body = content.encode()

    class Client:
        def get(self, url, **kwargs):
            return body, {}

    ads, status = collect_wordpress(
        Client(), source, "2026-10-30", "2026-11-01", [candidate], [review]
    )
    assert ads == [] and status["state"] == "error"


def unlinked_merrin_fixture():
    source, candidate, review, _, _ = unlinked_deboer_fixture()
    source = next(s for s in SOURCES if s.id == "merrin-washingtonreporter")
    candidate.update(candidate_id="H4OH09169", name="MERRIN, DEREK", state="OH", district="09")
    first = (
        "The first unselected quotation contains enough words to meet the substantive floor "
        "but must remain outside the acquired passage."
    )
    selected = (
        "This selected statement contains enough literal words to satisfy the minimum "
        "without including either neighboring quotation or reporter commentary."
    )
    introduction = (
        "Merrin discusses the purpose of the advertisement with the reporter while "
        "describing the campaign and its upcoming television schedule."
    )
    paragraph = f"{introduction} “{first}” he adds in the ad. “{selected}”"
    content = (
        '<meta property="article:published_time" content="2026-08-26T21:06:08+00:00">'
        "<h1>Merrin ad report</h1><article><p>Derek Merrin has a new campaign advertisement.</p>"
        f'<p class="quoted">{paragraph}</p></article>'
    )
    url = source.url + "/merrin-ad-report/"
    review.update(
        source=source.id,
        record_id="20260826",
        source_url=url,
        retrieval_url=url,
        content_sha256=digest(content),
        published="2026-08-26",
        release_title="Merrin ad report",
        candidate_id=candidate["candidate_id"],
        required_context=["Derek Merrin"],
        passages=[selected],
        reported_ad_text={
            "paragraph_selector": "article > p.quoted",
            "paragraph_sha256": digest(paragraph),
        },
    )
    return source, candidate, review, content.encode(), first, introduction


def test_merrin_report_excludes_journalist_introduction_and_neighboring_quotation():
    source, candidate, review, body, first, introduction = unlinked_merrin_fixture()
    calls = []

    class Client:
        def get(self, url, **kwargs):
            calls.append(url)
            return body, {}

    ads, status = collect_wordpress(
        Client(), source, "2026-10-30", "2026-11-01", [candidate], [review]
    )
    assert status["state"] == "partial" and len(ads) == 1
    ad = ads[0]
    assert ad["text"] == review["passages"][0]
    assert first not in ad["text"] and introduction not in ad["text"]
    assert ad["alignment"] == "R" and ad["race"] == "OH-09"
    assert ad["sponsor_type"] == "candidate" and ad["media_urls"] == []
    assert ad["phase"] == "unknown" and ad["date_basis"] == "publisher_report_date"
    assert {"original_ad_media_unverified", "ad_legal_payer_unverified"} <= set(ad["quality_flags"])
    assert calls == [review["retrieval_url"]]


@pytest.mark.parametrize(
    "failure", ["candidate", "statement", "too_long", "unselected", "journalism"]
)
def test_merrin_report_rejects_wrong_identity_or_unselected_non_ad_text(failure):
    source, candidate, review, body, first, introduction = unlinked_merrin_fixture()
    if failure == "candidate":
        candidate["candidate_id"] = review["candidate_id"] = "H4OH09999"
    elif failure == "unselected":
        review["passages"] = [first]
    elif failure == "journalism":
        review["passages"] = [introduction]
    else:
        content = body.decode()
        if failure == "statement":
            content = content.replace("he adds in the ad.", "he adds in an interview.")
        else:
            original = review["passages"][0]
            review["passages"][0] += (
                " Additional words push this selected quotation beyond the permitted limit."
            )
            content = content.replace(original, review["passages"][0])
        from bs4 import BeautifulSoup

        paragraph = BeautifulSoup(content, "html.parser").select("article > p.quoted")[0]
        review["reported_ad_text"]["paragraph_sha256"] = digest(paragraph.get_text(" ", strip=True))
        review["content_sha256"] = digest(content)
        body = content.encode()

    class Client:
        def get(self, url, **kwargs):
            return body, {}

    ads, status = collect_wordpress(
        Client(), source, "2026-10-30", "2026-11-01", [candidate], [review]
    )
    assert ads == [] and status["state"] == "error"


def unlinked_kiggans_fixture():
    source, candidate, review, _, _, _ = unlinked_merrin_fixture()
    source = next(s for s in SOURCES if s.id == "kiggans-washingtonreporter")
    candidate.update(
        candidate_id="H2VA02064",
        name="KIGGANS, JENNIFER",
        state="VA",
        district="02",
        reviewed_alias={"full_name": "Jen Kiggans"},
    )
    selected = (
        "This news clip contains enough literal words for substantive analysis "
        "without including either the neighboring quotation or publisher commentary."
    )
    neighbor = "An unselected opponent quotation."
    journalism = "The report discusses a separate opponent quotation"
    paragraph = f"“{selected}” a local news anchor says during the ad. {journalism} “{neighbor}”"
    content = (
        '<meta property="article:published_time" content="2026-10-23T19:16:02+00:00">'
        "<h1>Kiggans ad report</h1><article><p>Jen Kiggans has a new campaign advertisement.</p>"
        f'<p class="quoted">{paragraph}</p></article>'
    )
    url = source.url + "/kiggans-ad-report/"
    review.update(
        source=source.id,
        record_id="20261023",
        source_url=url,
        retrieval_url=url,
        content_sha256=digest(content),
        published="2026-10-23",
        release_title="Kiggans ad report",
        candidate_id=candidate["candidate_id"],
        required_context=["Jen Kiggans"],
        passages=[selected],
        reported_ad_text={
            "paragraph_selector": "article > p.quoted",
            "paragraph_sha256": digest(paragraph),
        },
    )
    return source, candidate, review, content.encode(), neighbor, journalism


def test_kiggans_report_keeps_only_news_clip_explicitly_used_in_ad():
    source, candidate, review, body, neighbor, journalism = unlinked_kiggans_fixture()
    calls = []

    class Client:
        def get(self, url, **kwargs):
            calls.append(url)
            return body, {}

    ads, status = collect_wordpress(
        Client(), source, "2026-10-30", "2026-11-01", [candidate], [review]
    )
    assert status["state"] == "partial" and len(ads) == 1
    ad = ads[0]
    assert ad["text"] == review["passages"][0]
    assert neighbor not in ad["text"] and journalism not in ad["text"]
    assert ad["alignment"] == "R" and ad["race"] == "VA-02"
    assert ad["sponsor_type"] == "candidate" and ad["media_urls"] == []
    assert ad["phase"] == "unknown" and ad["date_basis"] == "publisher_report_date"
    assert {"original_ad_media_unverified", "ad_legal_payer_unverified"} <= set(ad["quality_flags"])
    assert calls == [review["retrieval_url"]]


@pytest.mark.parametrize(
    "failure", ["candidate", "alias", "interview", "too_long", "neighbor", "journalism"]
)
def test_kiggans_report_rejects_unbound_identity_or_non_ad_quotations(failure):
    source, candidate, review, body, neighbor, journalism = unlinked_kiggans_fixture()
    if failure == "candidate":
        candidate["candidate_id"] = review["candidate_id"] = "H2VA02999"
    elif failure == "alias":
        candidate.pop("reviewed_alias")
    elif failure == "neighbor":
        review["passages"].append(neighbor)
    elif failure == "journalism":
        review["passages"].append(journalism)
    else:
        content = body.decode()
        if failure == "interview":
            content = content.replace("during the ad.", "during an interview.")
        else:
            original = review["passages"][0]
            review["passages"][0] += (
                " Additional words push this quotation beyond the permitted limit."
            )
            content = content.replace(original, review["passages"][0])
        from bs4 import BeautifulSoup

        paragraph = BeautifulSoup(content, "html.parser").select("article > p.quoted")[0]
        review["reported_ad_text"]["paragraph_sha256"] = digest(paragraph.get_text(" ", strip=True))
        review["content_sha256"] = digest(content)
        body = content.encode()

    class Client:
        def get(self, url, **kwargs):
            return body, {}

    ads, status = collect_wordpress(
        Client(), source, "2026-10-30", "2026-11-01", [candidate], [review]
    )
    assert ads == [] and status["state"] == "error"


def unlinked_begich_nrcc_fixture():
    source, candidate, review, _, _, _ = unlinked_kiggans_fixture()
    source = next(s for s in SOURCES if s.id == "begich-nrcc-cnbc")
    candidate.update(
        candidate_id="H2AK01083",
        name="BEGICH, NICHOLAS III",
        state="AK",
        district="00",
        reviewed_alias={"full_name": "Nick Begich"},
    )
    selected = (
        "But Nick Begich changed that. This selected ending has enough words "
        "to qualify without acquiring the preceding creative lines,"
    )
    introduction = "The unselected creative introduction."
    paragraph = (
        f'"{introduction} {selected}" says the voiceover in the ad for Begich, '
        "who is seeking a second term as Alaska's at-large representative."
    )
    commentary = "Separate NRCC spokesman press commentary."
    content = (
        '<meta property="article:published_time" content="2026-04-14T11:00:01+0000">'
        "<h1>Begich ad report</h1><article>"
        "<p>National Republican Congressional Committee advertising features Nick Begich.</p>"
        f'<p class="quoted">{paragraph}</p><p>"{commentary}" the spokesman said.</p></article>'
    )
    url = source.url + "/2026/04/14/begich-ad-report.html"
    review.update(
        source=source.id,
        record_id="20260414",
        source_url=url,
        retrieval_url=url,
        content_sha256=digest(content),
        published="2026-04-14",
        release_title="Begich ad report",
        candidate_id=candidate["candidate_id"],
        required_context=["Nick Begich", "National Republican Congressional Committee"],
        passages=[selected],
        reported_ad_text={
            "paragraph_selector": "article > p.quoted",
            "paragraph_sha256": digest(paragraph),
        },
    )
    return source, candidate, review, content.encode(), introduction, commentary


def test_begich_nrcc_report_keeps_only_selected_ending_of_one_alaska_ad():
    source, candidate, review, body, introduction, commentary = unlinked_begich_nrcc_fixture()
    calls = []

    class Client:
        def get(self, url, **kwargs):
            calls.append(url)
            return body, {}

    ads, status = collect_wordpress(
        Client(), source, "2026-10-30", "2026-11-01", [candidate], [review]
    )
    assert status["state"] == "partial" and len(ads) == 1
    ad = ads[0]
    assert ad["text"] == review["passages"][0] and ad["text"].endswith(",")
    assert introduction not in ad["text"] and commentary not in ad["text"]
    assert ad["alignment"] == "R" and ad["race"] == "AK-00"
    assert ad["sponsor_type"] == "party" and ad["media_urls"] == []
    assert ad["phase"] == "unknown" and ad["date_basis"] == "publisher_report_date"
    assert {
        "selected_ending_of_longer_ad_quotation",
        "original_ad_media_unverified",
        "ad_legal_payer_unverified",
    } <= set(ad["quality_flags"])
    assert calls == [review["retrieval_url"]]


@pytest.mark.parametrize(
    "failure",
    ["candidate", "alias", "interview", "too_long", "introduction", "commentary", "duplicate"],
)
def test_begich_nrcc_report_rejects_unbound_identity_or_unselected_words(failure):
    source, candidate, review, body, introduction, commentary = unlinked_begich_nrcc_fixture()
    content = body.decode()
    if failure == "candidate":
        candidate["candidate_id"] = review["candidate_id"] = "H2AK01999"
    elif failure == "alias":
        candidate.pop("reviewed_alias")
    elif failure == "interview":
        content = content.replace("the voiceover in the ad", "the speaker in the interview")
    elif failure == "too_long":
        original = review["passages"][0]
        review["passages"][0] += " These added words exceed the permitted quotation limit."
        content = content.replace(original, review["passages"][0])
    elif failure == "introduction":
        review["passages"].insert(0, introduction)
    elif failure == "commentary":
        review["passages"].append(commentary)
    elif failure == "duplicate":
        from bs4 import BeautifulSoup

        content += str(BeautifulSoup(content, "html.parser").select("article > p.quoted")[0])
        review["reported_ad_text"]["paragraph_selector"] = "p.quoted"
    from bs4 import BeautifulSoup

    paragraph = BeautifulSoup(content, "html.parser").select("p.quoted")[0]
    review["reported_ad_text"]["paragraph_sha256"] = digest(paragraph.get_text(" ", strip=True))
    review["content_sha256"] = digest(content)

    class Client:
        def get(self, url, **kwargs):
            return content.encode(), {}

    ads, status = collect_wordpress(
        Client(), source, "2026-10-30", "2026-11-01", [candidate], [review]
    )
    assert ads == [] and status["state"] == "error"


def unlinked_lisonbee_fixture():
    source, candidate, review, _, _, _ = unlinked_kiggans_fixture()
    source = replace(
        source,
        id="lisonbee-sltrib",
        url="https://www.sltrib.com",
        sponsor="Karianne Lisonbee campaign (publisher-reported; payer unverified)",
        fixed_race="UT-02",
    )
    candidate.update(
        candidate_id="H6UT02523",
        name="LISONBEE, KARIANNE",
        state="UT",
        district="02",
    )
    candidate.pop("reviewed_alias", None)
    selected = [
        "This first selected ad quotation contains fifteen substantive words about restoring "
        "public trust in Congress.",
        "This second sentence finishes the quoted ad.",
    ]
    paragraph = f"“{selected[0]}” she says in the ad. “{selected[1]}”"
    commentary = "Separate candidate press response, not words from the ad."
    content = (
        '<meta itemprop="datePublished" content="2026-06-15T17:00:16.889Z">'
        "<h1 class='headline'>Lisonbee ad report</h1>"
        '<span class="article-byline-author">| June 15, 2026, 11:00 a.m.</span>'
        '<div class="article-body-container">'
        "<p>Karianne Lisonbee shared her campaign ad for Congress. "
        "In the ad itself, Lisonbee describes her background.</p>"
        f'<p class="quoted">{paragraph}</p><p>"{commentary}" she said.</p></div>'
    )
    url = source.url + "/news/politics/2026/06/15/lisonbee-ad-report/"
    review.update(
        source=source.id,
        record_id="20260615",
        source_url=url,
        retrieval_url=url,
        content_sha256=digest(content),
        published="2026-06-15",
        release_title="Lisonbee ad report",
        heading_selector="h1.headline",
        publication_selector="span.article-byline-author",
        publication_date_format="| %B %d, %Y, %H:%M a.m.",
        candidate_id=candidate["candidate_id"],
        required_context=["Karianne Lisonbee", "In the ad itself, Lisonbee"],
        passages=selected,
        reported_ad_text={
            "paragraph_selector": ".article-body-container > p.quoted",
            "paragraph_sha256": digest(paragraph),
        },
    )
    return source, candidate, review, content.encode(), commentary


def test_lisonbee_report_acquires_only_explicit_ad_words_with_bound_dates():
    source, candidate, review, body, commentary = unlinked_lisonbee_fixture()
    calls = []

    class Client:
        def get(self, url, **kwargs):
            calls.append(url)
            return body, {}

    ads, status = collect_wordpress(
        Client(), source, "2026-10-30", "2026-11-01", [candidate], [review]
    )
    assert status["state"] == "partial" and len(ads) == 1
    ad = ads[0]
    assert ad["text"] == "\n".join(review["passages"])
    assert len(ad["text"].split()) == 22 and commentary not in ad["text"]
    assert ad["alignment"] == "R" and ad["race"] == "UT-02"
    assert ad["sponsor_type"] == "candidate" and ad["media_urls"] == []
    assert ad["published"] == "2026-06-15" and ad["phase"] == "unknown"
    assert ad["date_basis"] == "publisher_report_date"
    assert {"original_ad_media_unverified", "ad_legal_payer_unverified"} <= set(
        ad["quality_flags"]
    )
    assert calls == [review["retrieval_url"]]


@pytest.mark.parametrize(
    "failure",
    [
        "candidate",
        "interview",
        "too_long",
        "commentary",
        "duplicate",
        "metadata_date",
        "visible_date",
        "paragraph_hash",
    ],
)
def test_lisonbee_report_rejects_unbound_or_non_ad_evidence(failure):
    from bs4 import BeautifulSoup

    source, candidate, review, body, commentary = unlinked_lisonbee_fixture()
    content = body.decode()
    if failure == "candidate":
        candidate["candidate_id"] = review["candidate_id"] = "H6UT02999"
    elif failure == "interview":
        content = content.replace("she says in the ad", "she says in an interview")
    elif failure == "too_long":
        original = review["passages"][1]
        review["passages"][1] += " These extra words exceed the quotation ceiling."
        content = content.replace(original, review["passages"][1])
    elif failure == "commentary":
        review["passages"].append(commentary)
    elif failure == "duplicate":
        content += str(BeautifulSoup(content, "html.parser").select("p.quoted")[0])
        review["reported_ad_text"]["paragraph_selector"] = "p.quoted"
    elif failure == "metadata_date":
        content = content.replace("2026-06-15T17", "2026-06-16T17")
    elif failure == "visible_date":
        content = content.replace("June 15, 2026", "June 16, 2026")
    paragraph = BeautifulSoup(content, "html.parser").select("p.quoted")[0]
    review["reported_ad_text"]["paragraph_sha256"] = digest(
        paragraph.get_text(" ", strip=True)
    )
    if failure == "paragraph_hash":
        review["reported_ad_text"]["paragraph_sha256"] = "0" * 64
    review["content_sha256"] = digest(content)

    class Client:
        def get(self, url, **kwargs):
            return content.encode(), {}

    ads, status = collect_wordpress(
        Client(), source, "2026-10-30", "2026-11-01", [candidate], [review]
    )
    assert ads == [] and status["state"] == "error"


def unlinked_lawler_fixture():
    source, candidate, review, _, _, _ = unlinked_kiggans_fixture()
    source = next(s for s in SOURCES if s.id == "lawler-tell-her-no")
    candidate.update(
        candidate_id="H2NY17162",
        name="LAWLER, MICHAEL VINCENT",
        state="NY",
        district="17",
        reviewed_alias={"full_name": "Mike Lawler"},
    )
    selected = (
        "This selected interview footage contains enough literal words for substantive "
        "analysis without acquiring neighboring statements or campaign commentary,"
    )
    paragraph = (
        "Pearl River, NY — October 12, 2026 — Today, the Lawler for Congress campaign "
        "launched “Tell Her No,” which will be running on digital, text, and streaming "
        f"platforms. “{selected}” Conley told an interviewer last November, and the ad "
        "lets that sit for a second before it plays what she’s been telling Democratic "
        "audiences ever since."
    )
    commentary = "A separate campaign-manager press statement."
    content = (
        "<h1>News</h1><h2 class='text-center'>Tell Her No release</h2>"
        "<small class='date'>October 12, 2026</small>"
        "<p>Mike Lawler launched an ad featuring Cait Conley.</p>"
        f'<p class="quoted">{paragraph}</p><p>“{commentary}” campaign manager says.</p>'
    )
    url = source.url + "/2026/10/12/tell-her-no/"
    review.update(
        source=source.id,
        record_id="1442",
        source_url=url,
        retrieval_url=url,
        content_sha256=digest(content),
        published="2026-10-12",
        release_title="Tell Her No release",
        heading_selector="h2.text-center",
        publication_selector="small.date",
        candidate_id=candidate["candidate_id"],
        required_context=["Mike Lawler", "Cait Conley"],
        passages=[selected],
        reported_ad_text={
            "paragraph_selector": "p.quoted",
            "paragraph_sha256": digest(paragraph),
        },
    )
    return source, candidate, review, content.encode(), commentary


def test_lawler_release_keeps_only_opponent_interview_clip_explicitly_played_in_ad():
    source, candidate, review, body, commentary = unlinked_lawler_fixture()
    calls = []

    class Client:
        def get(self, url, **kwargs):
            calls.append(url)
            return body, {}

    ads, status = collect_wordpress(
        Client(), source, "2026-10-30", "2026-11-01", [candidate], [review]
    )
    assert status["state"] == "partial" and len(ads) == 1
    ad = ads[0]
    assert ad["text"] == review["passages"][0] and ad["text"].endswith(",")
    assert commentary not in ad["text"]
    assert ad["alignment"] == "R" and ad["race"] == "NY-17"
    assert ad["sponsor_type"] == "candidate" and ad["media_urls"] == []
    assert ad["published"] == "2026-10-12" and ad["phase"] == "unknown"
    assert {
        "campaign_release_quotes_partial_ad_copy",
        "opponent_interview_clip_used_in_ad",
        "original_ad_media_unverified",
        "ad_legal_payer_unverified",
    } <= set(ad["quality_flags"])
    assert calls == [review["retrieval_url"]]


@pytest.mark.parametrize(
    "failure",
    ["candidate", "speaker", "interview_only", "too_long", "commentary", "date", "heading"],
)
def test_lawler_release_rejects_unbound_identity_or_non_ad_evidence(failure):
    source, candidate, review, body, commentary = unlinked_lawler_fixture()
    content = body.decode()
    if failure == "candidate":
        candidate["candidate_id"] = review["candidate_id"] = "H2NY17999"
    elif failure == "speaker":
        content = content.replace("Conley told", "Lawler told")
    elif failure == "interview_only":
        content = content.replace("and the ad lets", "and the interview lets")
    elif failure == "too_long":
        original = review["passages"][0]
        review["passages"][0] += " These additional words exceed the permitted quotation length."
        content = content.replace(original, review["passages"][0])
    elif failure == "commentary":
        review["passages"].append(commentary)
    elif failure == "date":
        content = content.replace(
            "<small class='date'>October 12", "<small class='date'>October 13"
        )
    elif failure == "heading":
        content = content.replace("Tell Her No release</h2>", "A different release</h2>")
    from bs4 import BeautifulSoup

    paragraph = BeautifulSoup(content, "html.parser").select("p.quoted")[0]
    review["reported_ad_text"]["paragraph_sha256"] = digest(paragraph.get_text(" ", strip=True))
    review["content_sha256"] = digest(content)

    class Client:
        def get(self, url, **kwargs):
            return content.encode(), {}

    ads, status = collect_wordpress(
        Client(), source, "2026-10-30", "2026-11-01", [candidate], [review]
    )
    assert ads == [] and status["state"] == "error"


def unlinked_pps_house_fixture():
    source, _, review, _, _, _ = unlinked_kiggans_fixture()
    source = next(s for s in SOURCES if s.id == "pps-house-washingtonreporter")
    candidates = [
        {
            "candidate_id": candidate_id,
            "name": name,
            "state": state,
            "district": district,
            "office": "H",
            "party": "REP",
            "election_year": "2026",
        }
        for candidate_id, name, state, district in [
            ("H2FL04211", "BEAN, AARON P.", "FL", "04"),
            ("H4MO08162", "SMITH, JASON T", "MO", "08"),
            ("H6PA16320", "SMUCKER, LLOYD K.", "PA", "11"),
            ("H8OK01157", "HERN, KEVIN", "OK", "01"),
        ]
    ]
    selected = (
        "This selected footage contains enough literal words to meet the minimum "
        "without acquiring neighboring quotations or publisher commentary."
    )
    introduction = "The ad also includes footage of Rep. Lloyd Smucker and Rep. Aaron Bean saying:"
    paragraph = (
        f"{introduction} “{selected}” The Washington Reporter previously covered that hearing."
    )
    original = "https://x.com/Policy_Solution/status/2059962673865920660?s=20"
    content = (
        '<meta property="article:published_time" content="2026-05-28T16:51:25+00:00">'
        "<h1>House issue-ad report</h1><article>"
        "<p>Jason Smith and Kevin Hern appear with House Republicans in the issue ad.</p>"
        f'<p class="quoted">{paragraph}</p><a href="{original}">new ad</a></article>'
    )
    url = source.url + "/house-issue-ad-report/"
    review.update(
        source=source.id,
        record_id="20260528",
        source_url=url,
        retrieval_url=url,
        content_sha256=digest(content),
        published="2026-05-28",
        release_title="House issue-ad report",
        candidate_id="H2FL04211",
        candidate_ids=sorted(c["candidate_id"] for c in candidates),
        scope_role="current_house_office_not_election_candidacy",
        discovered_original_url=original,
        reviewed_language={
            "language": "en",
            "text_sha256": digest(selected),
            "basis": "Individually reviewed literal English ad quotation.",
        },
        required_context=["House Republicans"],
        passages=[selected],
        reported_ad_text={
            "paragraph_selector": "article > p.quoted",
            "paragraph_sha256": digest(paragraph),
        },
    )
    return source, candidates, review, content.encode(), introduction


def test_pps_house_report_keeps_one_multi_race_ad_without_requesting_original():
    source, candidates, review, body, introduction = unlinked_pps_house_fixture()
    calls = []

    class Client:
        def get(self, url, **kwargs):
            calls.append(url)
            return body, {}

    ads, status = collect_wordpress(
        Client(), source, "2026-10-30", "2026-11-01", candidates, [review]
    )
    assert status["state"] == "partial" and len(ads) == 1
    ad = ads[0]
    assert ad["text"] == review["passages"][0] and introduction not in ad["text"]
    assert ad["alignment"] == "R" and ad["sponsor_type"] == "outside_group"
    assert ad["race"] == "Multi-race" and ad["state"] == "" and ad["chamber"] == "House"
    assert ad["segments"][0]["federal_scope_candidate_ids"] == review["candidate_ids"]
    assert ad["media_urls"] == [] and ad["phase"] == "unknown"
    assert ad["language"] == "en" and ad["language_basis"] == review["reviewed_language"]["basis"]
    assert {"multi_race_house_issue_ad", "original_ad_media_unverified"} <= set(ad["quality_flags"])
    assert calls == [review["retrieval_url"]]


@pytest.mark.parametrize(
    "failure",
    [
        "missing_scope",
        "missing_candidate",
        "senate",
        "district",
        "party",
        "speaker",
        "role",
        "missing_name",
        "missing_link",
        "hearing_only",
        "too_long",
        "journalism",
        "language",
        "language_hash",
    ],
)
def test_pps_house_report_rejects_unverified_scope_or_non_ad_text(failure):
    source, candidates, review, body, introduction = unlinked_pps_house_fixture()
    if failure == "missing_scope":
        review["candidate_ids"].pop()
    elif failure == "missing_candidate":
        candidates.pop()
    elif failure == "senate":
        candidates[-1].update(candidate_id="S6OK04247", office="S", district="00")
        review["candidate_ids"][-1] = "S6OK04247"
    elif failure == "district":
        candidates[-1]["district"] = "02"
    elif failure == "party":
        candidates[-1]["party"] = "DEM"
    elif failure == "speaker":
        review["candidate_id"] = "H8OK01157"
    elif failure == "role":
        review["scope_role"] = "all_are_house_election_candidates"
    elif failure == "journalism":
        review["passages"] = [introduction]
    elif failure == "language":
        review["reviewed_language"]["language"] = "de"
    elif failure == "language_hash":
        review["reviewed_language"]["text_sha256"] = digest("unselected words")
    else:
        content = body.decode()
        if failure == "missing_name":
            content = content.replace("Kevin Hern", "a committee member")
        elif failure == "missing_link":
            content = content.replace(review["discovered_original_url"], "https://example.org/")
        elif failure == "hearing_only":
            content = content.replace(
                "The ad also includes footage", "The hearing includes footage"
            )
        else:
            original = review["passages"][0]
            review["passages"][0] += (
                " Additional words make this selected quotation exceed the permitted limit."
            )
            content = content.replace(original, review["passages"][0])
        from bs4 import BeautifulSoup

        paragraph = BeautifulSoup(content, "html.parser").select("article > p.quoted")[0]
        review["reported_ad_text"]["paragraph_sha256"] = digest(paragraph.get_text(" ", strip=True))
        review["content_sha256"] = digest(content)
        body = content.encode()

    class Client:
        def get(self, url, **kwargs):
            return body, {}

    ads, status = collect_wordpress(
        Client(), source, "2026-10-30", "2026-11-01", candidates, [review]
    )
    assert ads == [] and status["state"] == "error"


@pytest.mark.parametrize("format", ["wordpress", "html"])
@pytest.mark.parametrize("completeness", ["partial_quotation", "marked_script"])
def test_reviewed_release_keeps_only_bound_ad_words_and_explicit_provenance(format, completeness):
    source, candidate, review, body = release_fixture(format, completeness)

    class Client:
        def get(self, url, **kwargs):
            assert url == review["retrieval_url"]
            return body, {}

    ads, status = collect_wordpress(
        Client(), source, "2026-10-30", "2026-10-30", [candidate], [review]
    )
    assert len(ads) == 1
    ad = ads[0]
    assert ad["text"] == review["passages"][0]
    assert "spending" not in ad["text"]
    assert (ad["sponsor"], ad["alignment"], ad["race"]) == (
        "Rhett Marques for Congress",
        "R",
        "AL-02",
    )
    assert ad["segments"][0]["release_evidence"] == review
    assert ad["segments"][0]["federal_scope_candidate_ids"] == ["H6AL01086"]
    assert ad["source_hash"] == review["content_sha256"]
    assert ad["date_basis"] == "publisher_report_date" and ad["delivery_start"] is None
    assert ("publisher_ad_copy_completeness_unverified" in ad["quality_flags"]) == (
        completeness == "partial_quotation"
    )
    assert status["state"] == "partial" and status["discovery_complete"] is False
    assert "portrayal_review" not in ad


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("content_sha256", "0" * 64),
        ("published", "2026-07-13"),
        ("candidate_id", "H0XX00000"),
        ("media_url", "https://www.youtube.com/embed/bbbbbbbbbbb"),
        ("passages", ["A campaign statement that is not present in the actual quoted ad."]),
        ("completeness", "complete_guess"),
        ("required_context", ["An unverified claim about who produced this ad."]),
        ("retrieval_url", "https://another-publisher.example/ad/"),
    ],
)
def test_reviewed_release_failure_preserves_existing_corpus(tmp_path, monkeypatch, field, value):
    source, candidate, review, body = release_fixture()
    monkeypatch.setattr(cli.Client, "get", lambda *args, **kwargs: (body, {}))
    cli.write_json(tmp_path / "data/site/candidates.json", {"candidates": [candidate]})
    ledger = tmp_path / "data/ad-release-reviews.json"
    cli.write_json(ledger, {"reviews": [review]})
    original = cli.collect(tmp_path, "2026-10-30", [source.id])
    review[field] = value
    cli.write_json(ledger, {"reviews": [review]})
    failed = cli.collect(tmp_path, "2026-10-30", [source.id])
    assert failed["ads"] == original["ads"]
    assert failed["sources"][0]["state"] == "error"
    assert failed["sources"][0]["retained_ads"] == 1
    assert failed["sources"][0]["last_success"] == original["sources"][0]["last_success"]


def test_reviewed_release_never_calls_an_unregistered_host():
    source, candidate, review, _ = release_fixture()
    review["retrieval_url"] = "https://another-publisher.example/ad/"

    class Client:
        def get(self, *args, **kwargs):
            pytest.fail("A mismatched publisher must be rejected before requesting")

    assert (
        collect_wordpress(Client(), source, "2026-10-30", "2026-10-30", [candidate], [review])[1][
            "state"
        ]
        == "error"
    )


@pytest.mark.parametrize(
    "linked_url",
    [
        "https://bigal.media/mediaplayer.php?q=publicshare",
        "https://www.washingtonexaminer.com/news/campaigns/congressional/123/ad/",
    ],
)
def test_reviewed_release_binds_explicitly_linked_ad_words(linked_url):
    source, candidate, review, body = release_fixture("html")
    passage = review["passages"][0]
    content = body.decode().replace(passage, "Rhett Marques discussed the campaign.")
    content += f'<a href="{linked_url}">The reported advertisement</a>'
    linked = (
        "<p>The linked publisher quotes Rhett Marques's advertisement.</p>"
        f'<section class="ad-copy"><p>{passage}</p></section>'
        "<p>The reporter's assessment is not part of the ad.</p>"
    )
    review["content_sha256"] = digest(content)
    review["linked_ad_text"] = {
        "url": linked_url,
        "content_sha256": digest(linked),
        "selector": "section.ad-copy",
        "required_context": ["The linked publisher quotes Rhett Marques's advertisement."],
    }
    calls = []

    class Client:
        def get(self, url, **kwargs):
            calls.append(url)
            return (content if url == review["retrieval_url"] else linked).encode(), {}

    ads, status = collect_wordpress(
        Client(), source, "2026-10-30", "2026-10-30", [candidate], [review]
    )
    assert len(ads) == 1 and status["state"] == "partial"
    assert calls == [review["retrieval_url"], linked_url]
    assert ads[0]["text"] == passage
    assert ads[0]["source_hash"] == digest(content)
    assert ads[0]["segments"][0]["release_evidence"]["linked_ad_text"] == review["linked_ad_text"]
    assert "publisher_linked_source_quotes_partial_ad_copy" in ads[0]["quality_flags"]
    assert ads[0]["date_basis"] == "publisher_report_date"
    assert ads[0]["delivery_start"] is None


@pytest.mark.parametrize(
    "failure",
    [
        "unlinked",
        "unregistered_host",
        "login_page",
        "changed_primary_hash",
        "changed_linked_hash",
        "missing_selector",
        "ambiguous_selector",
        "missing_context",
        "wrong_candidate",
        "outside_selected_text",
        "claimed_full_script",
    ],
)
def test_reviewed_linked_ad_text_fails_closed(failure):
    source, candidate, review, body = release_fixture("html")
    passage = review["passages"][0]
    linked_url = "https://bigal.media/mediaplayer.php?q=publicshare"
    if failure == "unregistered_host":
        linked_url = "https://another-publisher.example/ad/"
    elif failure == "login_page":
        linked_url = "https://bigal.media/login.php"
    content = body.decode().replace(passage, "Rhett Marques discussed the campaign.")
    if failure != "unlinked":
        content += f'<a href="{linked_url}">The reported advertisement</a>'
    linked = (
        "<p>The linked publisher quotes Rhett Marques's advertisement.</p>"
        f'<section class="ad-copy"><p>{passage}</p></section>'
    )
    if failure == "ambiguous_selector":
        linked += '<section class="ad-copy">An unrelated second ad.</section>'
    elif failure == "wrong_candidate":
        linked = linked.replace("Rhett Marques", "Another Candidate")
    elif failure == "outside_selected_text":
        linked = linked.replace(
            f'<section class="ad-copy"><p>{passage}</p></section>',
            f'<section class="ad-copy">No recovered words.</section><p>{passage}</p>',
        )
    review["content_sha256"] = "0" * 64 if failure == "changed_primary_hash" else digest(content)
    review["linked_ad_text"] = {
        "url": linked_url,
        "content_sha256": "0" * 64 if failure == "changed_linked_hash" else digest(linked),
        "selector": "section.missing" if failure == "missing_selector" else "section.ad-copy",
        "required_context": [
            "An absent attribution."
            if failure == "missing_context"
            else "The linked publisher quotes"
        ],
    }
    if failure == "claimed_full_script":
        review["completeness"] = "marked_script"
    calls = []

    class Client:
        def get(self, url, **kwargs):
            calls.append(url)
            return (content if url == review["retrieval_url"] else linked).encode(), {}

    ads, status = collect_wordpress(
        Client(), source, "2026-10-30", "2026-10-30", [candidate], [review]
    )
    assert not ads and status["state"] == "error"
    if failure in {
        "unlinked",
        "unregistered_host",
        "login_page",
        "changed_primary_hash",
        "claimed_full_script",
    }:
        assert calls == [review["retrieval_url"]]


@pytest.mark.parametrize("removed", ["h1", "meta"])
def test_reviewed_article_missing_metadata_is_a_source_error_not_a_collection_crash(removed):
    source, candidate, review, body = release_fixture("html")
    body = body.replace(f"<{removed}".encode(), f"<missing-{removed}".encode())

    class Client:
        def get(self, *args, **kwargs):
            return body, {}

    ads, status = collect_wordpress(
        Client(), source, "2026-10-30", "2026-10-30", [candidate], [review]
    )
    assert not ads and status["state"] == "error"


@pytest.mark.parametrize(
    "date_markup", ["single", "missing", "ambiguous", "changed", "conflicting_metadata"]
)
def test_reviewed_article_binds_an_explicit_visible_publication_date(date_markup):
    source, candidate, review, body = release_fixture("html")
    content = body.decode().replace(
        '<meta property="article:published_time" content="2026-07-14T12:00:00">',
        '<p class="storydate">July 14, 2026</p>',
    )
    if date_markup == "missing":
        content = content.replace('class="storydate"', 'class="other"')
    elif date_markup == "ambiguous":
        content += '<p class="storydate">July 14, 2026</p>'
    elif date_markup == "changed":
        content = content.replace("July 14, 2026", "July 15, 2026")
    elif date_markup == "conflicting_metadata":
        content += '<meta property="article:published_time" content="2026-07-15T12:00:00">'
    review["publication_selector"] = "p.storydate"
    review["content_sha256"] = digest(content)

    class Client:
        def get(self, *args, **kwargs):
            return content.encode(), {}

    ads, status = collect_wordpress(
        Client(), source, "2026-10-30", "2026-10-30", [candidate], [review]
    )
    if date_markup == "single":
        assert len(ads) == 1
        assert ads[0]["published"] == "2026-07-14"
        assert ads[0]["date_basis"] == "publisher_report_date"
    else:
        assert not ads and status["state"] == "error"


@pytest.mark.parametrize("format", ["wordpress", "html"])
@pytest.mark.parametrize("selector", ["p.ad-script", "p.missing", "p", "p.report"])
def test_reviewed_script_element_excludes_surrounding_news(format, selector):
    source, candidate, review, body = release_fixture(format, "marked_script")
    passage = review["passages"][0]
    original = f"<p>SCRIPT:</p><p>{passage}</p>"
    replacement = (
        f'<p class="ad-script">Script: <em>{passage}</em></p>'
        '<p class="report">The reporter describes the election and quotes a campaign '
        "spokesperson after the ad script. These words are not in the ad.</p>"
    )
    if format == "wordpress":
        post = json.loads(body)
        content = post["content"]["rendered"].replace(original, replacement)
        post["content"]["rendered"] = content
        body = json.dumps(post).encode()
    else:
        content = body.decode().replace(original, replacement)
        body = content.encode()
    review["content_sha256"] = digest(content)
    review["script_selector"] = selector

    class Client:
        def get(self, *args, **kwargs):
            return body, {}

    ads, status = collect_wordpress(
        Client(), source, "2026-10-30", "2026-10-30", [candidate], [review]
    )
    if selector == "p.ad-script":
        assert status["state"] == "partial" and len(ads) == 1
        assert ads[0]["text"] == passage
        assert "news_publisher_reports_marked_ad_script" in ads[0]["quality_flags"]
        assert "campaign_release_reproduced_by_news_publisher" not in ads[0]["quality_flags"]
        assert ads[0]["segments"][0]["release_evidence"]["script_selector"] == selector
    else:
        assert not ads and status["state"] == "error"


@pytest.mark.parametrize("selector", ["article h1", "h1", "article .missing", "p.not-heading"])
def test_reviewed_article_heading_selection_excludes_navigation(selector):
    source, candidate, review, body = release_fixture("html")
    content = (
        "<h1>State news navigation</h1><article>"
        '<p class="not-heading">A new House ad</p>' + body.decode() + "</article>"
    )
    review["heading_selector"] = selector
    review["content_sha256"] = digest(content)

    class Client:
        def get(self, *args, **kwargs):
            return content.encode(), {}

    ads, status = collect_wordpress(
        Client(), source, "2026-10-30", "2026-10-30", [candidate], [review]
    )
    if selector == "article h1":
        assert len(ads) == 1 and ads[0]["title"] == review["release_title"]
    else:
        assert not ads and status["state"] == "error"


@pytest.mark.parametrize(
    "variant", ["selected", "ambiguous", "nonheading", "changed_title", "conflicting_date"]
)
def test_reviewed_article_can_bind_a_unique_h2_without_accepting_navigation(variant):
    source, candidate, review, body = release_fixture("html", "marked_script")
    title = review["release_title"]
    heading = f'<h2 class="article-title">{title}</h2>'
    content = "<h1>Latest News</h1>" + body.decode().replace(f"<h1>{title}</h1>", heading)
    if variant == "ambiguous":
        content += heading
    elif variant == "nonheading":
        content = content.replace(heading, f'<p class="article-title">{title}</p>')
    elif variant == "changed_title":
        content = content.replace(heading, '<h2 class="article-title">Another ad</h2>')
    elif variant == "conflicting_date":
        content += '<time class="storydate">July 13, 2026</time>'
        review["publication_selector"] = "time.storydate"
    review["heading_selector"] = ".article-title"
    review["content_sha256"] = digest(content)

    class Client:
        def get(self, *args, **kwargs):
            return content.encode(), {}

    ads, status = collect_wordpress(
        Client(), source, "2026-10-30", "2026-10-30", [candidate], [review]
    )
    if variant == "selected":
        assert len(ads) == 1 and ads[0]["title"] == title
        assert ads[0]["text"] == review["passages"][0]
    else:
        assert not ads and status["state"] == "error"


@pytest.mark.parametrize(
    "date_markup", ["matching", "no_format", "conflicting_datetime", "ambiguous", "missing"]
)
def test_reviewed_article_abbreviated_date_binds_visible_and_machine_dates(date_markup):
    source, candidate, review, body = release_fixture("html")
    markup = '<time class="storydate" datetime="2026-07-14T12:00:00">Jul 14, 2026</time>'
    content = body.decode().replace(
        '<meta property="article:published_time" content="2026-07-14T12:00:00">', markup
    )
    if date_markup == "conflicting_datetime":
        content = content.replace("2026-07-14T12:00:00", "2026-07-15T12:00:00")
    elif date_markup == "ambiguous":
        content += markup
    elif date_markup == "missing":
        content = content.replace('class="storydate"', 'class="other"')
    review["publication_selector"] = "time.storydate"
    if date_markup != "no_format":
        review["publication_date_format"] = "%b %d, %Y"
    review["content_sha256"] = digest(content)

    class Client:
        def get(self, *args, **kwargs):
            return content.encode(), {}

    ads, status = collect_wordpress(
        Client(), source, "2026-10-30", "2026-10-30", [candidate], [review]
    )
    if date_markup == "matching":
        assert len(ads) == 1 and ads[0]["published"] == "2026-07-14"
    else:
        assert not ads and status["state"] == "error"


def test_reviewed_script_boundary_cannot_be_applied_to_partial_quotations():
    source, candidate, review, body = release_fixture()
    review["script_selector"] = "p"

    class Client:
        def get(self, *args, **kwargs):
            return body, {}

    ads, status = collect_wordpress(
        Client(), source, "2026-10-30", "2026-10-30", [candidate], [review]
    )
    assert not ads and status["state"] == "error"


@pytest.mark.parametrize("with_alias", [False, True])
def test_reviewed_release_honors_existing_exact_federal_candidate_alias(with_alias):
    source, candidate, review, body = release_fixture()
    canonical = candidate | {"name": "MARQUES, FREDERICK"}
    candidates = [canonical]
    if with_alias:
        candidates.append(
            candidate | {"reviewed_alias": {"basis": "Fixture exact public-name review"}}
        )

    class Client:
        def get(self, *args, **kwargs):
            return body, {}

    ads, status = collect_wordpress(
        Client(), source, "2026-10-30", "2026-10-30", candidates, [review]
    )
    if with_alias:
        assert len(ads) == 1 and status["state"] == "partial"
        assert ads[0]["segments"][0]["federal_scope_candidate_ids"] == [candidate["candidate_id"]]
    else:
        assert not ads and status["state"] == "error"
