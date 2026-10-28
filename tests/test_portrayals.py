import copy

import pytest

from political_ads.portrayals import (
    apply_portrayal_reviews,
    bind_reviews,
    portrayal_summary,
    tone_category,
    validate_portrayal_review,
)
from political_ads.schema import digest

CODEBOOK = {
    "version": "test",
    "method": "Contextual review",
    "frames": {"integrity": "Integrity", "record": "Record"},
    "voices": ["advertiser", "adopted_clip", "quoted_opponent", "rebutted_claim", "unclear"],
}


def ad(identity, text="Alex is corrupt. Alex delivered reform.", **changes):
    return {
        "id": identity,
        "text": text,
        "text_hash": digest(text),
        "source_hash": "page-v1",
        "message_id": digest(text.casefold()),
        "published": "2026-10-01",
        "alignment": "D",
        "sponsor": "Campaign",
        "source": "official",
        "source_url": "https://example.org/ad",
    } | changes


def description(**changes):
    return {
        "target": "Alex",
        "target_party": "R",
        "target_kind": "person",
        "target_role": "opponent",
        "party_basis": "explicit_text",
        "frame": "integrity",
        "tone": "negative",
        "voice": "advertiser",
        "phrase": "corrupt",
        "quote": "Alex is corrupt.",
        "target_quote": "Alex",
    } | changes


def reviewed(record, descriptions, **changes):
    review = {key: record[key] for key in ("alignment", "sponsor", "text_hash", "source_hash")}
    review |= {
        "ad_id": record["id"],
        "status": "reviewed",
        "reason": "",
        "descriptions": descriptions,
    }
    review.update(changes)
    return {"version": CODEBOOK["version"], "reviews": [review]}


def attach(record, descriptions, **changes):
    return apply_portrayal_reviews([record], reviewed(record, descriptions, **changes), CODEBOOK)[0]


def test_positive_opponent_passage_makes_mixed_not_a_new_self_portrayal():
    record = attach(
        ad("mixed"),
        [
            description(),
            description(
                tone="positive",
                frame="record",
                phrase="delivered reform",
                quote="Alex delivered reform.",
            ),
        ],
    )
    result = portrayal_summary([record], CODEBOOK)["scopes"]
    group = result["opponents"]["D"]
    assert group["tones"]["mixed"]["count"] == 1
    assert group["tones"]["negative_only"]["count"] == 0
    assert all(group["inclusive_tones"][tone]["share"] == 1 for tone in ("positive", "negative"))
    assert result["self"]["D"]["described"]["count"] == 0
    assert all(value["count"] == 1 for value in group["frames"].values())


def test_contrast_ad_does_not_mix_opponent_attack_with_supported_candidate_praise():
    record = attach(
        ad("contrast", text="Alex is corrupt. Casey delivered reform."),
        [
            description(),
            description(
                target="Casey",
                target_party="D",
                target_role="self_or_supported",
                tone="positive",
                frame="record",
                phrase="delivered reform",
                quote="Casey delivered reform.",
                target_quote="Casey",
            ),
        ],
    )
    result = portrayal_summary([record], CODEBOOK)
    scopes = result["scopes"]
    assert scopes["opponents"]["D"]["tones"]["negative_only"]["count"] == 1
    assert scopes["self"]["D"]["tones"]["positive_only"]["count"] == 1
    assert all(
        scopes[scope]["D"]["tones"]["mixed"]["count"] == 0 for scope in ("opponents", "self")
    )
    assert result["ad_strategy"]["parties"]["D"]["contrast"]["ad_ids"] == ["contrast"]


@pytest.mark.parametrize("party,other", [("D", "R"), ("R", "D")])
def test_same_ad_strategy_partitions_all_messages_with_mirrored_party_direction(party, other):
    praise = description(
        target="Casey",
        target_party=party,
        target_role="self_or_supported",
        tone="positive",
        frame="record",
        phrase="delivered reform",
        quote="Casey delivered reform.",
        target_quote="Casey",
    )
    attack = description(target_party=other)
    positive = attach(ad("praise", text="Casey delivered reform.", alignment=party), [praise])
    negative = attach(ad("attack", text="Alex is corrupt.", alignment=party), [attack])
    contrast = attach(
        ad("contrast", text="Alex is corrupt. Casey delivered reform.", alignment=party),
        [attack, praise],
    )
    collective = attach(
        ad(
            "collective",
            text="Alex is corrupt. Casey delivered reform. A different creative.",
            alignment=party,
        ),
        [
            attack | {"target_kind": "collective", "voice": "adopted_clip"},
            praise | {"target_kind": "collective"},
        ],
    )
    neither = attach(
        ad("neither", text="An election date.", alignment=party),
        [],
        reason="No attributed description",
    )
    records = [
        positive,
        negative,
        contrast,
        collective,
        neither,
        positive | {"id": "praise-mirror", "source": "mirror"},
        ad("unreviewed", text="No saved review.", alignment=party),
        attach(
            ad("uncertain", text="Uncertain evidence.", alignment=party),
            [],
            status="uncertain",
            reason="Unclear extraction",
        ),
        ad("stale", text="Changed evidence.", alignment=party)
        | {"portrayal_review": {"status": "stale", "descriptions": []}},
    ]
    result = portrayal_summary(records, CODEBOOK)
    group = result["ad_strategy"]["parties"][party]
    assert {key: value["count"] for key, value in group.items()} == {
        "own_positive_only": 1,
        "contrast": 2,
        "opponent_negative_only": 1,
        "neither": 1,
        "not_reviewed": 3,
    }
    assert all(value["total"] == 8 for value in group.values())
    assert sum(value["share"] for value in group.values()) == 1
    assert group["own_positive_only"]["ad_ids"] == ["praise"]
    assert set(group["contrast"]["ad_ids"]) == {"contrast", "collective"}
    assert all(value["share"] is None for value in result["ad_strategy"]["parties"][other].values())
    assert all(
        value["total"] == 0
        for value in result["sensitivity"]["ad_strategy"]["parties"][party].values()
    )
    filtered = portrayal_summary([records[5]], CODEBOOK)["ad_strategy"]["parties"][party]
    assert filtered["own_positive_only"]["ad_ids"] == ["praise-mirror"]


def test_strategy_does_not_infer_praise_or_attack_from_reverse_tones_or_unknown_parties():
    record = attach(
        ad("other"),
        [
            description(tone="positive"),
            description(target_party="D", target_role="self_or_supported"),
            description(target_party="unknown", party_basis="unknown"),
            description(
                target_party="unknown",
                target_role="self_or_supported",
                party_basis="unknown",
                tone="positive",
            ),
        ],
    )
    result = portrayal_summary([record], CODEBOOK)["ad_strategy"]["parties"]["D"]
    assert result["neither"]["ad_ids"] == ["other"]


@pytest.mark.parametrize("voice", ["quoted_opponent", "rebutted_claim", "unclear"])
def test_quoted_or_rebutted_accusation_does_not_count_as_endorsed_attack(voice):
    result = portrayal_summary([attach(ad("quote"), [description(voice=voice)])], CODEBOOK)
    assert result["scopes"]["opponents"]["D"]["described"]["count"] == 0
    assert result["evidence"][0]["voice"] == voice
    assert result["ad_strategy"]["parties"]["D"]["neither"]["count"] == 1


@pytest.mark.parametrize(
    "change,scope",
    [
        ({"target_party": "D"}, "same_party_opponents"),
        ({"target_kind": "collective"}, "collective_opponents"),
        ({"target_role": "self_or_supported", "tone": "positive"}, "self"),
    ],
)
def test_same_party_rivals_collectives_and_supported_candidates_are_separate(change, scope):
    result = portrayal_summary([attach(ad("separate"), [description(**change)])], CODEBOOK)
    assert result["scopes"]["opponents"]["D"]["described"]["count"] == 0
    assert result["scopes"][scope]["D"]["described"]["count"] == 1


def test_unknown_target_identity_is_not_inferred_from_hostility():
    result = portrayal_summary(
        [
            attach(
                ad("unknown-target"), [description(target_party="unknown", party_basis="unknown")]
            )
        ],
        CODEBOOK,
    )
    assert result["scopes"]["opponents"]["D"]["described"]["count"] == 0
    assert result["evidence"][0]["target_party"] == "unknown"


def test_no_description_uncertain_and_unreviewed_are_not_neutral():
    records = [
        attach(ad("none"), [], reason="No attributable personal description"),
        attach(ad("neutral", message_id="neutral"), [description(tone="neutral")]),
        attach(
            ad("uncertain", message_id="uncertain"),
            [description()],
            status="uncertain",
            reason="Unclear ASR target",
        ),
        ad("unreviewed", message_id="unreviewed"),
    ]
    result = portrayal_summary(records, CODEBOOK)
    coverage = result["coverage"]["D"]
    assert {status: value["count"] for status, value in coverage.items()} == {
        "reviewed": 2,
        "uncertain": 1,
        "unreviewed": 1,
        "stale": 0,
    }
    group = result["scopes"]["opponents"]["D"]
    assert group["no_description"]["count"] == 1
    assert group["described"]["total"] == 2
    assert group["tones"]["neutral_only"]["count"] == group["tones"]["neutral_only"]["total"] == 1
    assert result["scopes"]["opponents"]["R"]["tones"]["negative_only"]["share"] is None
    with pytest.raises(ValueError, match="not a neutral"):
        tone_category([])


def test_exact_mirrors_reuse_only_same_sponsor_alignment_and_text_after_filtering():
    original = ad("a")
    mirror = original | {"id": "b", "source": "mirror"}
    different_speaker = original | {"id": "c", "sponsor": "Other campaign"}
    different_party = original | {"id": "d", "alignment": "R"}
    records = apply_portrayal_reviews(
        [original, mirror, different_speaker, different_party],
        reviewed(original, [description()]),
        CODEBOOK,
    )
    assert records[1]["portrayal_review"]["reused_exact_text"]
    assert all(records[i]["portrayal_review"]["status"] == "unreviewed" for i in (2, 3))
    result = portrayal_summary(records[:2], CODEBOOK)
    assert result["scopes"]["opponents"]["D"]["described"]["count"] == 1
    filtered = portrayal_summary([records[1]], CODEBOOK)
    assert filtered["scopes"]["opponents"]["D"]["described"]["ad_ids"] == ["b"]


def test_unchanged_text_retains_original_review_hash_but_changed_text_is_withheld():
    original = ad("a")
    ledger = reviewed(original, [description()])
    changed_page = apply_portrayal_reviews(
        [original | {"source_hash": "page-v2"}], ledger, CODEBOOK
    )[0]
    review = changed_page["portrayal_review"]
    assert review["status"] == "reviewed" and review["source_hash_changed"]
    assert review["source_hash"] == "page-v1" and changed_page["source_hash"] == "page-v2"
    changed_text = original | {"text": "Not Alex.", "text_hash": digest("Not Alex.")}
    stale = apply_portrayal_reviews([changed_text], ledger, CODEBOOK)[0]
    assert stale["portrayal_review"]["status"] == "stale"
    assert stale["portrayal_review"]["descriptions"] == []


@pytest.mark.parametrize(
    "change",
    [
        {"quote": "Invented quotation"},
        {"phrase": "Not in the passage"},
        {"target_quote": "Invented target"},
        {"target_role": "self"},
        {"target_party": "R", "party_basis": "unknown"},
    ],
)
def test_review_application_rejects_nonliteral_evidence_and_unjustified_identities(change):
    with pytest.raises(ValueError, match="Portrayal|portrayal|Invalid"):
        attach(ad("bad"), [description(**change)])


def test_attached_span_and_identity_mutation_fail_validation():
    record = attach(ad("span"), [description()])
    validate_portrayal_review(record, CODEBOOK)
    changed = copy.deepcopy(record)
    changed["portrayal_review"]["descriptions"][0]["start"] += 1
    with pytest.raises(ValueError, match="offsets"):
        validate_portrayal_review(changed, CODEBOOK)
    changed = copy.deepcopy(record)
    changed["alignment"] = "R"
    with pytest.raises(ValueError, match="identity"):
        validate_portrayal_review(changed, CODEBOOK)


def test_frozen_review_binding_requires_complete_unique_decisions_and_original_text():
    record = ad("frozen")
    decision = {
        "ad_id": "frozen",
        "status": "reviewed",
        "reason": "",
        "descriptions": [description()],
    }
    bound = bind_reviews([record], [decision], CODEBOOK, snapshot_id="original-snapshot")
    assert bound["input_snapshot_id"] == "original-snapshot"
    assert bound["reviews"][0]["source_hash"] == record["source_hash"]
    assert bound["reviews"][0]["descriptions"][0]["start"] == 0
    with pytest.raises(ValueError, match="Incomplete"):
        bind_reviews([record], [], CODEBOOK, snapshot_id="original-snapshot")
    with pytest.raises(ValueError, match="Duplicate or unexpected"):
        bind_reviews([record], [decision, decision], CODEBOOK, snapshot_id="original-snapshot")
    with pytest.raises(ValueError, match="hash mismatch"):
        bind_reviews([record | {"text": "Changed text"}], [decision], CODEBOOK, snapshot_id="s")
    with pytest.raises(ValueError, match="outcome"):
        bind_reviews([record], [decision | {"reason": None}], CODEBOOK, snapshot_id="s")


def test_reviewed_offsets_are_preserved_when_the_same_words_occur_twice():
    text = "Alex is corrupt. A quoted repeat: Alex is corrupt."
    start = text.rindex("Alex")
    record = attach(
        ad("repeated", text=text),
        [description(start=start, end=len(text), target_start=start, target_end=start + 4)],
    )
    saved = record["portrayal_review"]["descriptions"][0]
    assert saved["start"] == saved["target_start"] == start
    validate_portrayal_review(record, CODEBOOK)
