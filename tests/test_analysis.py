import pytest

from political_ads.analysis import (
    annotate,
    apply_reviews,
    comparison,
    matches,
    stratified_comparisons,
)


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


def test_strata_distinguish_first_release_month_from_source_repeats_and_missing_parties():
    codebook = {"issues": {"tax": ["tax"]}, "portrayal_language": {"trust": ["lies"]}}
    ads = annotate(
        [
            {
                "id": identity,
                "text": text,
                "alignment": party,
                "published": published,
                "source": source,
                "chamber": "House",
                "sponsor_type": "party",
                "phase": "unknown",
                "race": "PA-10",
            }
            for identity, text, party, published, source in [
                ("a", "Tax relief", "R", "2026-01-01", "committee"),
                ("b", "Tax relief", "R", "2026-02-01", "campaign"),
                ("c", "Health care", "R", "2026-02-02", "campaign"),
                ("d", "No more lies", "D", "2026-02-03", "other"),
            ]
        ],
        codebook,
    )
    result = stratified_comparisons(ads, codebook)
    february = result["month"]["2026-02"]
    assert february["coverage"]["R"]["records"] == 2
    assert february["coverage"]["R"]["message_ad_ids"] == ["c"]
    assert february["issues"][0]["R"] == {"count": 0, "total": 1, "share": 0.0, "ad_ids": []}
    assert result["source"]["campaign"]["issues"][0]["R"]["ad_ids"] == ["b"]
    assert result["month"]["2026-01"]["issues"][0]["D"]["share"] is None
    assert result["overall"]["portrayals"][0]["D"]["ad_ids"] == ["d"]
    assert result["sensitivity"]["excluded_publishers"] == {"D": "other", "R": "campaign"}
    reduced = result["sensitivity"]["without_largest_publisher_per_party"]
    assert reduced["coverage"]["R"]["message_ad_ids"] == ["a"]
    assert reduced["coverage"]["D"]["records"] == 0
    assert reduced["issues"][0]["D"]["share"] is None
