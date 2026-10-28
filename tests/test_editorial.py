import copy

import pytest

from political_ads.editorial import (
    context_illustrations,
    margin_html,
    portrayal_excerpt,
    substack_markdown,
)


def test_article_excerpt_keeps_the_characterization_not_just_the_passage_opening():
    quote = " ".join(["Context"] * 30) + " Alex sold out working families to donors."
    excerpt = portrayal_excerpt({"quote": quote, "phrase": "sold out working families"})
    assert "sold out working families" in excerpt
    assert excerpt.startswith("... ")
    assert len(excerpt.removeprefix("... ").removesuffix(" ...").split()) <= 22
    assert portrayal_excerpt({"quote": "Alex is honest.", "phrase": "honest"}) == "Alex is honest."
    phrase = (
        "stands up for working families and fights to lower their costs while protecting "
        "their healthcare, retirement benefits, wages, civil rights, safety and access to housing"
    )
    long_quote = "Candidate Alex " + phrase + ". More context."
    assert phrase in portrayal_excerpt({"quote": long_quote, "phrase": phrase})


def test_context_illustrations_bind_quote_alignment_and_source_hash():
    ad = {
        "id": "test",
        "text": "Republicans say violent crime is down.",
        "source_hash": "original",
        "alignment": "R",
        "source_url": "https://example.org/ad",
    }
    review = {
        "ad_id": "test",
        "source_hash": "original",
        "alignment": "R",
        "word": "violent",
        "quote": "violent crime is down",
        "interpretation": "Describes crime, not Republicans.",
    }
    result = context_illustrations({"ads": [ad]}, {"reviews": [review]})[0]
    assert ad["text"][result["start"] : result["end"]] == review["quote"]
    assert result["source_url"] == ad["source_url"]
    for field, value in (
        ("source_hash", "changed"),
        ("alignment", "D"),
        ("quote", "missing"),
        ("word", "unmatched"),
    ):
        changed = copy.deepcopy(review) | {field: value}
        with pytest.raises(ValueError, match="re-review"):
            context_illustrations({"ads": [ad]}, {"reviews": [changed]})
    assert context_illustrations({"ads": []}, {"reviews": [review]}) == []


def test_draft_renderers_share_copy_and_keep_local_evidence_paths_and_safe_markup():
    article = {
        "title": "The collection",
        "subtitle": "A draft",
        "until": "2026-10-27",
        "snapshot_id": "hash",
        "blocks": [
            {"kind": "paragraph", "text": "The shared finding."},
            {"kind": "heading", "text": "Context"},
            {
                "kind": "quote",
                "text": "<script>not executable</script>",
                "caption": "Quoted, not endorsed.",
                "source_url": "https://example.org/?q='",
            },
            {
                "kind": "figure",
                "png": "chart.png",
                "csv": "chart.csv",
                "description": "Exact counts",
            },
        ],
    }
    markdown, html, web = (
        substack_markdown(article),
        margin_html(article),
        margin_html(
            article,
            web=True,
        ),
    )
    for edition in (markdown, html, web):
        assert "The shared finding." in edition and "DRAFT - NOT PUBLISHED" in edition
        assert "figures/chart.png" in edition and ".svg" not in edition
    assert "<script>" not in html and "&lt;script&gt;" in html
    assert "q=&#x27;" in html
    assert "analysis-ads.csv" in html and "analysis.json" in html
    assert "data/ads.csv" in web and "data/dataset.json.gz" in web
    assert "report.html" in web and "rel='canonical'" not in html
