import csv
import json
import zipfile
from pathlib import Path
from unittest.mock import patch

import pytest

from political_ads.claims import (
    CONTEXT_CHARS,
    MAX_TOKENS,
    MAX_WORDS,
    blocks_for,
    canonical,
    extract_claims,
    identities,
    output_lock,
    prepare,
    strategy,
    validate_response,
)
from political_ads.schema import digest, message_key


def ad(identity="test-ad", text="Jane Smith fights for us. John Doe failed us.", **changes):
    return {
        "id": identity,
        "source": "test",
        "source_url": "https://example.org/ad",
        "source_hash": "source-bytes",
        "sponsor": "Jane Smith for Senate",
        "sponsor_type": "candidate",
        "title": "Jane Smith ad",
        "alignment": "D",
        "published": "2026-10-28",
        "language": "en",
        "text": text,
        "segments": [{"text": text, "kind": "publisher_transcript"}],
        "text_hash": digest(text),
        "message_id": message_key(text),
        "identities": [
            {
                "id": "candidate:D1",
                "name": "Jane Smith",
                "party": "D",
                "basis": "candidate_metadata",
            },
            {"id": "candidate:R1", "name": "John Doe", "party": "R", "basis": "candidate_metadata"},
        ],
        **changes,
    }


def target(**changes):
    return {
        "name": "John Doe",
        "kind": "person",
        "entity_id": "candidate:R1",
        "anchor_unit_id": 1,
        "anchor_quote": "John Doe",
        "role": "opponent",
        "tone": "negative",
        **changes,
    }


def payload(targets=None, **changes):
    return {
        "claims": [
            {
                "claim_text": "John Doe failed the advertiser's constituents.",
                "claim_types": ["characterization"],
                "evidence_ids": [1],
                "voice": "advertiser",
                "targets": targets if targets is not None else [target()],
                **changes,
            }
        ],
        "unresolved_references": [],
    }


def fixture_corpus(root: Path, ads=None):
    directory = root / "data/site"
    directory.mkdir(parents=True)
    (directory / "corpus.json").write_text(
        json.dumps({"until": "2026-10-28", "ads": ads or [ad()], "sources": []})
    )
    (directory / "candidates.json").write_text(
        canonical(
            {
                "candidates": [
                    {
                        "candidate_id": identity,
                        "name": name,
                        "party": party,
                        "state": "NY",
                        "office": "S",
                        "district": "00",
                    }
                    for identity, name, party in (
                        ("D1", "SMITH, JANE", "DEM"),
                        ("R1", "DOE, JOHN", "REP"),
                    )
                ]
            }
        )
    )


def test_target_party_side_and_tone_are_independent():
    block = blocks_for(ad())[0]
    same = target(
        name="Jane Smith", entity_id="candidate:D1", anchor_quote="Jane Smith", tone="negative"
    )
    cross = target(tone="positive")
    claims = validate_response(canonical(payload(targets=[same, cross])), block)
    own, other = claims[0]["targets"]
    assert (own["side"], own["tone"], own["role"]) == ("same_side", "negative", "opponent")
    assert (other["side"], other["tone"]) == ("other_side", "positive")
    for row in claims[0]["targets"]:
        assert ad()["text"][row["anchor_start"] : row["anchor_end"]] == row["anchor_quote"]
    assert strategy(claims, "normalized") == "neither_detected"


def test_unknown_target_is_not_assumed_other_party_or_neutral():
    block = blocks_for(ad())[0]
    claims = validate_response(canonical(payload(targets=[target(entity_id="unknown")])), block)
    assert claims[0]["targets"][0]["side"] == "unknown"
    assert claims[0]["targets"][0]["tone"] == "negative"
    assert strategy(claims, "normalized") == "not_classified"
    no_target = validate_response(canonical(payload(targets=[])), block)
    assert no_target[0]["targets"] == []


def test_contrast_uses_endorsed_targets_and_complete_extraction():
    block = blocks_for(ad())[0]
    own = target(
        name="Jane Smith",
        entity_id="candidate:D1",
        anchor_quote="Jane Smith",
        role="self_or_supported",
        tone="positive",
    )
    claims = validate_response(canonical(payload(targets=[own, target()])), block)
    assert strategy(claims, "normalized") == "contrast"
    assert strategy(claims, "not_run") == "not_classified"
    assert strategy(claims, "unresolved") == "not_classified"
    for voice in ("quoted_opponent", "rebutted_claim"):
        quoted = validate_response(canonical(payload(targets=[own, target()], voice=voice)), block)
        assert strategy(quoted, "normalized") == "neither_detected"
    unclear = validate_response(canonical(payload(voice="unclear")), block)
    assert strategy(unclear, "normalized") == "not_classified"
    unattributed = validate_response(canonical(payload(voice="unclear", targets=[])), block)
    assert strategy(unattributed, "normalized") == "not_classified"


@pytest.mark.parametrize(
    "updates",
    [
        {"anchor_quote": "Not literal"},
        {"anchor_unit_id": 99},
        {"anchor_unit_id": True},
        {"entity_id": "invented:R"},
        {"target_party": "R"},
        {"side": "other_side"},
        {"tone": "mixed"},
        {"tone": []},
        {"kind": {}},
        {"role": []},
    ],
)
def test_bad_target_or_invented_party_is_rejected(updates):
    with pytest.raises(ValueError):
        validate_response(canonical(payload(targets=[target(**updates)])), blocks_for(ad())[0])


@pytest.mark.parametrize(
    "updates",
    [
        {"evidence_ids": [99]},
        {"evidence_ids": [True]},
        {"evidence_ids": [1, 1]},
        {"claim_types": ["ideology"]},
        {"claim_types": [[]]},
        {"voice": []},
        {"claim_text": ""},
        {"confidence": 0.99},
    ],
)
def test_bad_claim_schema_and_evidence_are_rejected(updates):
    with pytest.raises(ValueError):
        validate_response(canonical(payload(**updates)), blocks_for(ad())[0])


def test_target_names_alone_are_not_claims_and_all_bad_labels_are_reported():
    response = payload(claim_text="John Doe.")
    response["claims"].append(
        payload(
            claim_text="Jane Smith",
            targets=[
                target(name="Jane Smith", entity_id="candidate:D1", anchor_quote="Jane Smith")
            ],
        )["claims"][0]
    )
    with pytest.raises(ValueError, match="bare headings") as failure:
        validate_response(canonical(response), blocks_for(ad())[0])
    assert "John Doe." in str(failure.value)
    assert "Jane Smith" in str(failure.value)


def test_bounded_units_preserve_every_source_character_and_evidence_lane():
    text = "Yes. U.S. policy!\n" + " ".join(f"word{i}" for i in range(1200)) + "\nNo?"
    overlay = "John Doe failed us."
    record = ad(
        text=text + "\n" + overlay,
        segments=[{"text": text, "kind": "local_asr"}, {"text": overlay, "kind": "video_ocr"}],
    )
    blocks = blocks_for(record)
    observed = []
    for block in blocks:
        assert sum(len(u["text"].split()) for u in block["units"]) <= MAX_WORDS
        assert len(block["context_before"]) <= CONTEXT_CHARS
        for unit in block["units"]:
            assert record["text"][unit["start"] : unit["end"]] == unit["text"]
            observed.extend(
                position
                for position in range(unit["start"], unit["end"])
                if not record["text"][position].isspace()
            )
    assert observed == [i for i, character in enumerate(record["text"]) if not character.isspace()]
    assert blocks[-1]["units"][-1]["kind"] == "video_ocr"
    with pytest.raises(ValueError, match="segments"):
        blocks_for(record | {"text": "Changed text"})


def test_frozen_inputs_resume_offline_without_model_or_live_corpus(tmp_path):
    fixture_corpus(tmp_path)
    output = tmp_path / "claims"
    with patch("political_ads.claims.LocalGemma") as model:
        first = extract_claims(tmp_path, output, prepare_only=True)
        assert first["blocks_by_status"] == {"not_run": 1}
        assert first["status"] == "incomplete"
        model.assert_not_called()
    attempts = []

    def local(prompt, max_tokens):
        attempts.append(prompt)
        assert max_tokens == MAX_TOKENS
        return {"text": canonical(payload()), "generation_tokens": 100}

    summary = extract_claims(tmp_path, output, extractor=local)
    assert len(attempts) == 2
    assert "PROPOSAL" in attempts[1]
    assert summary["ad_strategy"]["D"]["categories"]["opponent_negative_only"]["count"] == 1
    (tmp_path / "data/site/corpus.json").unlink()
    with patch("political_ads.claims.LocalGemma", side_effect=AssertionError("Must not load")):
        assert extract_claims(tmp_path, output, replay=True) == summary
        assert extract_claims(tmp_path, output) == summary
    with zipfile.ZipFile(output / "complete-evidence.zip") as archive:
        assert {"manifest.json", "ads.json", "claims.json", "targets.csv"} <= set(
            archive.namelist()
        )
        assert json.loads(archive.read("ads.json"))[0]["text"] == ad()["text"]
        response = json.loads(archive.read("responses/test-ad-claims-001.json"))
        assert response["attempts"][0]["request"] == attempts[0]
        assert response["attempts"][1]["request"] == attempts[1]
    with (output / "targets.csv").open(newline="") as stream:
        row = next(csv.DictReader(stream))
        assert (row["side"], row["tone"], row["text"]) == ("other_side", "negative", ad()["text"])


def test_failed_attempts_cannot_reuse_previous_success_and_retries_preserve_history(tmp_path):
    fixture_corpus(tmp_path)
    output = tmp_path / "claims"
    calls = 0

    def fails_on_revision(*_):
        nonlocal calls
        calls += 1
        if calls == 1:
            return {"text": canonical(payload()), "generation_tokens": 100}
        raise RuntimeError("local inference failed")

    summary = extract_claims(tmp_path, output, extractor=fails_on_revision)
    assert summary["blocks_by_status"] == {"validation_failed": 1}
    assert summary["claims"] == 0
    assert summary["ad_strategy"]["D"]["categories"]["not_classified"]["count"] == 1
    raw_path = output / "responses/test-ad-claims-001.json"
    original = json.loads(raw_path.read_text())
    assert original["attempts"][-1]["text"] == ""
    retry_requests = []

    def retry(prompt, _):
        retry_requests.append(prompt)
        return {"text": canonical(payload()), "generation_tokens": 100}

    complete = extract_claims(
        tmp_path,
        output,
        retry_failed=True,
        extractor=retry,
    )
    assert complete["status"] == "complete"
    assert retry_requests[0] != original["attempts"][0]["request"]
    assert "PREVIOUS FAILED RESPONSE" in retry_requests[0]
    assert "local inference failed" in retry_requests[0]
    assert json.loads(next((output / "response-history").glob("*.json")).read_text()) == original


def test_retry_receives_bad_quote_exact_source_and_original_response(tmp_path):
    fixture_corpus(tmp_path)
    output = tmp_path / "claims"
    requests = []
    bad = canonical(payload(targets=[target(anchor_quote="john doe")]))

    def local(prompt, _):
        requests.append(prompt)
        return {"text": bad if len(requests) == 1 else canonical(payload())}

    assert extract_claims(tmp_path, output, extractor=local)["status"] == "complete"
    assert len(requests) == 3
    repair = requests[1]
    assert "PREVIOUS FAILED RESPONSE" in repair
    assert canonical(bad) in repair
    assert "Nonliteral target anchor" in repair
    assert "john doe" in repair
    assert "Exact source:" in repair


def test_unresolved_empty_output_and_truncated_revision_do_not_become_neither(tmp_path):
    fixture_corpus(tmp_path)
    output = tmp_path / "claims"
    unresolved = {"claims": [], "unresolved_references": ["Unclear speaker"]}
    summary = extract_claims(
        tmp_path,
        output,
        extractor=lambda *_: {"text": canonical(unresolved), "generation_tokens": 10},
    )
    assert summary["blocks_by_status"] == {"unresolved": 1}
    assert summary["ad_strategy"]["D"]["categories"]["not_classified"]["count"] == 1
    summary = extract_claims(
        tmp_path,
        output,
        retry_failed=True,
        extractor=lambda *_: {"text": canonical(payload()), "generation_tokens": MAX_TOKENS},
    )
    assert summary["claims"] == 0
    assert summary["blocks_by_status"] == {"validation_failed": 1}


def test_snapshot_identity_bindings_and_limits(tmp_path):
    records = [ad(), ad("second", alignment="R"), ad("foreign", language="es")]
    fixture_corpus(tmp_path, records)
    output = tmp_path / "claims"
    manifest = prepare(tmp_path, output, ["test-ad"])
    assert [row["id"] for row in manifest["ads"]] == ["test-ad"]
    with pytest.raises(ValueError, match="selection"):
        prepare(tmp_path, output, ["second"])
    with pytest.raises(ValueError, match="ineligible"):
        prepare(tmp_path, tmp_path / "bad", ["foreign"])
    damaged = manifest | {"until": "2026-10-29"}
    (output / "manifest.json").write_text(canonical(damaged))
    with pytest.raises(ValueError, match="hash mismatch"):
        prepare(tmp_path, output)
    with pytest.raises(ValueError, match="nonnegative"):
        extract_claims(tmp_path, max_new_blocks=-1)
    with pytest.raises(ValueError, match="downloads"):
        extract_claims(tmp_path, download_model=True, replay=True)
    with pytest.raises(ValueError, match="repository"):
        extract_claims(tmp_path, tmp_path / ".git" / "claims")


def test_output_directory_allows_only_one_writer_and_releases_lock(tmp_path):
    fixture_corpus(tmp_path)
    output = tmp_path / "claims"
    with output_lock(output), pytest.raises(ValueError, match="Another claim process"):
        extract_claims(tmp_path, output, prepare_only=True)
    assert extract_claims(tmp_path, output, prepare_only=True)["ads"] == 1


def test_default_full_run_can_be_prepared_alongside_pilot(tmp_path):
    fixture_corpus(tmp_path)
    pilot = tmp_path / "data/local-claims/pilot"
    extract_claims(tmp_path, pilot, prepare_only=True)
    extract_claims(tmp_path, prepare_only=True)
    assert (pilot / "manifest.json").exists()
    assert (tmp_path / "data/local-claims/full/manifest.json").exists()


@pytest.mark.parametrize(
    "changes",
    [{"model_revision": "a-different-model"}, {"generation": {"temperature": 1}}],
)
def test_changed_model_or_generation_settings_require_new_run(tmp_path, changes):
    fixture_corpus(tmp_path)
    output = tmp_path / "claims"
    manifest = prepare(tmp_path, output)
    config = {k: v for k, v in (manifest | changes).items() if k != "fingerprint"}
    (output / "manifest.json").write_text(
        canonical(config | {"fingerprint": digest(canonical(config))})
    )
    with pytest.raises(ValueError, match="implementation changed"):
        prepare(tmp_path, output)


def test_identity_dictionary_uses_metadata_not_hostile_language():
    record = ad(text="Jane Smith and Donald Trump. Democrats failed us. Woke liberals!")
    candidates = [
        {
            "candidate_id": "D1",
            "name": "SMITH, JANE",
            "party": "DEM",
            "state": "NY",
            "office": "S",
            "district": "00",
        }
    ]
    rows = identities(record, candidates, {"Donald Trump": "R"})
    assert {row["id"]: row["party"] for row in rows} == {
        "advertiser": "D",
        "candidate:D1": "D",
        "national:Donald Trump": "R",
        "party:D": "D",
    }


@pytest.mark.parametrize("field", ["request", "text"])
def test_offline_replay_rejects_damaged_attempts(tmp_path, field):
    fixture_corpus(tmp_path)
    output = tmp_path / "claims"
    extract_claims(tmp_path, output, extractor=lambda *_: {"text": canonical(payload())})
    path = output / "responses/test-ad-claims-001.json"
    record = json.loads(path.read_text())
    record["attempts"][0][field] += " changed"
    path.write_text(canonical(record))
    with pytest.raises(ValueError, match="Damaged response"):
        extract_claims(tmp_path, output, replay=True)


def test_ad_side_tone_counts_messages_once_and_excludes_quoted_and_partial_ads(tmp_path):
    fixture_corpus(
        tmp_path,
        [
            ad(),
            ad("duplicate"),
            ad("quoted", text="John Doe failed us."),
            ad("partial", text="Jane Smith fights for us.\n" + "word " * 500),
        ],
    )
    output = tmp_path / "claims"

    def local(prompt, _):
        response = payload(
            targets=[
                target(),
                target(
                    name="Jane Smith",
                    entity_id="candidate:D1",
                    anchor_quote="Jane Smith",
                    role="opponent",
                    tone="negative",
                ),
            ]
        )
        response["claims"].append(
            response["claims"][0] | {"claim_text": "A second assertion about the same targets."}
        )
        if '"ad_id":"quoted"' in prompt:
            response = payload(voice="quoted_opponent")
        if '"ad_id":"partial"' in prompt:
            units, _ = json.JSONDecoder().raw_decode(prompt.split("\nSOURCE UNITS:\n")[1])
            if not units["[1]"].startswith("Jane Smith"):
                raise RuntimeError("Later block failed")
            response = payload(
                targets=[
                    target(
                        name="Jane Smith",
                        entity_id="candidate:D1",
                        anchor_quote="Jane Smith",
                        role="self_or_supported",
                        tone="positive",
                    )
                ]
            )
        return {"text": canonical(response)}

    extract_claims(tmp_path, output, extractor=local)
    summary = extract_claims(tmp_path, output, replay=True)
    counts = summary["ad_target_side_tone"]["D"]
    assert counts["all_unique_messages"] == 3
    assert counts["normalized_unique_messages"] == 2
    assert counts["side_tone"]["same_side"]["negative"]["count"] == 1
    assert counts["side_tone"]["other_side"]["negative"]["count"] == 1
    assert counts["side_tone"]["other_side"]["negative"]["share"] == 0.5
    assert counts["side_tone"]["same_side"]["positive"]["count"] == 0
    partial = [
        row for row in json.loads((output / "claims.json").read_text()) if row["ad_id"] == "partial"
    ]
    assert partial
    assert all(row["ad_claim_status"] == "validation_failed" for row in partial)
    assert all(row["block_status"] == "normalized" and row["text"] for row in partial)
