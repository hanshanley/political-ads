import pytest

from political_ads.analysis import annotate, apply_reviews, comparison, matches


def test_phrase_boundaries_offsets_and_caption_line_breaks():
    text = "Not taxation; HEALTH\nCARE is quoted here. Tax and taxes are different."
    result = matches(text, {"care": ["health care"], "tax": ["tax"]})
    assert [(match["label"], match["text"]) for match in result] == [
        ("care", "HEALTH\nCARE"),
        ("tax", "Tax"),
    ]
    assert all(text[match["start"] : match["end"]] == match["text"] for match in result)


def test_message_denominators_dedup_within_party_but_not_across_parties():
    ads = [
        {"id": str(index), "text": text, "alignment": party, "published": "2026-10-01"}
        for index, (text, party) in enumerate(
            [
                ("Tax relief", "D"),
                ("Tax  relief", "D"),
                ("Protect health care", "D"),
                ("Tax relief", "R"),
            ]
        )
    ]
    annotated = annotate(ads, {"issues": {"tax": ["tax"]}, "portrayal_language": {}})
    row = comparison(annotated, ["tax"])[0]
    assert row["D"] == {"count": 1, "total": 2, "share": 0.5, "ad_ids": ["0"]}
    assert row["R"] == {"count": 1, "total": 1, "share": 1, "ad_ids": ["3"]}
    assert comparison(annotated[:3], ["tax"])[0]["R"]["share"] is None


def test_stale_editorial_quote_or_source_must_fail_publication():
    ad = {
        "id": "a",
        "text": "A bad policy.",
        "source_hash": "original",
        "alignment": "D",
        "race": "NC-Senate",
        "source_url": "https://example.org/ad",
        "published": "2026-10-01",
    }
    review = {
        "ad_id": "a",
        "source_hash": "original",
        "quote": "bad policy",
        "target_party": "R",
    }
    assert apply_reviews([ad], {"examples": [review]})[0]["start"] == 2
    for changed in ({"source_hash": "changed"}, {"quote": "invented quote"}):
        with pytest.raises(ValueError, match="re-review"):
            apply_reviews([ad], {"examples": [review | changed]})
