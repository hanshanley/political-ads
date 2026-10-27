from copy import deepcopy

import pytest

from political_ads.alignments import apply_alignment_reviews


def fixture():
    ad = {
        "id": "snap-one",
        "source": "publisher-snap",
        "sponsor": "Publisher",
        "source_hash": "original-hash",
        "alignment": "unknown",
        "text": "Unchanged recognized text.",
        "segments": [{"text": "Unchanged recognized text."}],
        "quality_flags": ["machine_extraction"],
        "attribution_basis": "Original identity evidence.",
    }
    review = {
        "id": "publisher-2026",
        "source": ad["source"],
        "sponsor": ad["sponsor"],
        "expected_alignment": "unknown",
        "alignment": "D",
        "status": "aligned",
        "rationale": "Documented electoral program, not formal party registration.",
        "evidence": [{"url": "https://example.org/program"}],
        "records": [{"id": ad["id"], "source_hash": ad["source_hash"]}],
    }
    return ad, {"reviews": [review]}


def test_review_changes_only_alignment_and_retains_complete_provenance():
    ad, ledger = fixture()
    before = deepcopy(ad)
    reviewed = apply_alignment_reviews([ad], ledger)[0]
    assert ad == before
    assert reviewed["alignment"] == "D" and reviewed["original_alignment"] == "unknown"
    assert reviewed["alignment_review"]["reviewed_source_hash"] == ad["source_hash"]
    assert "records" not in reviewed["alignment_review"]
    for key in ("text", "segments", "source_hash", "quality_flags", "attribution_basis"):
        assert reviewed[key] == before[key]
    reviewed["alignment_review"]["evidence"][0]["url"] = "https://example.org/changed"
    assert ledger["reviews"][0]["evidence"][0]["url"] == "https://example.org/program"
    assert apply_alignment_reviews([ad], ledger)[0]["alignment"] == "D"


@pytest.mark.parametrize("key", ["source_hash", "source", "sponsor", "alignment"])
def test_changed_content_identity_or_original_alignment_cannot_inherit_review(key):
    ad, ledger = fixture()
    ad[key] = "changed"
    reviewed = apply_alignment_reviews([ad], ledger)[0]
    assert reviewed["alignment"] == ad["alignment"]
    assert "alignment_review" not in reviewed
    assert reviewed["quality_flags"] == ["machine_extraction", "stale_publisher_alignment_review"]
    assert ad["quality_flags"] == ["machine_extraction"]


def test_bipartisan_unresolved_and_new_unreviewed_records_stay_distinct():
    ad, ledger = fixture()
    ledger["reviews"][0].update(alignment="other", status="bipartisan")
    reviewed = apply_alignment_reviews([ad], ledger)[0]
    assert reviewed["alignment"] == "other"
    assert reviewed["alignment_review"]["status"] == "bipartisan"
    ledger["reviews"][0].update(alignment="unknown", status="unresolved_primary_only")
    reviewed = apply_alignment_reviews([ad], ledger)[0]
    assert reviewed["alignment"] == "unknown"
    assert reviewed["alignment_review"]["status"] == "unresolved_primary_only"
    new = ad | {"id": "snap-new"}
    assert apply_alignment_reviews([new], ledger) == [new]


def test_duplicate_decisions_cannot_silently_overwrite_a_review():
    ad, ledger = fixture()
    ledger["reviews"].append(deepcopy(ledger["reviews"][0]))
    with pytest.raises(ValueError, match="Duplicate alignment review"):
        apply_alignment_reviews([ad], ledger)
