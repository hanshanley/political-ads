import json
from hashlib import sha256
from io import BytesIO

import pytest
from pypdf import PdfReader, PdfWriter
from pypdf.annotations import Link
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

from political_ads import cli
from political_ads.schema import digest
from political_ads.sources import SOURCES, collect_wordpress


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
