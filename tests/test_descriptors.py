import math

from political_ads.analysis import annotate
from political_ads.descriptors import adjective_vocabulary, descriptive_language, mention_contexts


def record(identity, text, party="D", published="2026-10-01", sponsor="Shared publisher", **extra):
    return annotate(
        [
            {
                "id": identity,
                "text": text,
                "alignment": party,
                "published": published,
                "source": "fixture",
                "sponsor": sponsor,
                "source_hash": "source-" + identity,
                "candidate_mentions": [],
                "chamber": "House",
                "sponsor_type": "party",
                "phase": "unknown",
                "race": "PA-01",
                **extra,
            }
        ],
        {"issues": {}, "portrayal_language": {}},
    )[0]


def snapshot(ads, until="2026-10-27"):
    return {"ads": ads, "snapshot_id": "fixture-snapshot", "until": until}


def test_contexts_preserve_negation_offsets_and_exclude_mixed_parties_and_generic_democratic():
    ad = record(
        "a",
        '"Democrats are not dangerous." Republicans and Democrats are bad. '
        "Our democratic process is good.",
    )
    targets, hits = mention_contexts(ad, [], adjective_vocabulary())
    assert targets == {"D"}
    assert [hit["word"] for hit in hits] == ["dangerous"]
    assert "not dangerous" in hits[0]["context"]
    assert hits[0]["status"] == "unreviewed_mention_cooccurrence"
    for hit in hits:
        assert ad["text"][hit["start"] : hit["end"]] == hit["text"]
        assert ad["text"][hit["context_start"] : hit["context_end"]] == hit["context"]
        assert all(ad["text"][m["start"] : m["end"]] == m["text"] for m in hit["mentions"])


def test_full_names_reviewed_aliases_and_name_overlap_do_not_create_descriptors():
    candidate = {"candidate_id": "H6PA01001", "name": "NICE, JOHN", "party": "REP"}
    ad = record("a", "John Nice is bad. Nice is good.", candidate_mentions=[candidate])
    targets, hits = mention_contexts(ad, [], adjective_vocabulary())
    assert targets == {"R"}
    assert [hit["word"] for hit in hits] == ["bad"]
    alias = candidate | {"reviewed_alias": {"full_name": "Johnny Nice"}}
    ad = record("b", "Johnny Nice is dangerous.")
    assert not mention_contexts(ad, [], adjective_vocabulary())[0]
    assert mention_contexts(ad, [alias], adjective_vocabulary())[0] == {"R"}
    assert not mention_contexts(
        record("c", "Unrelated text.", candidate_mentions=[candidate], title="John Nice is bad"),
        [],
        adjective_vocabulary(),
    )[0]


def test_continuous_speech_can_match_but_independent_overlay_cannot_supply_a_word():
    segments = [
        {"kind": "local_asr", "text": "Republicans are"},
        {"kind": "local_asr", "text": "not dangerous."},
        {"kind": "video_ocr", "text": "Democrats"},
        {"kind": "video_ocr", "text": "bad"},
    ]
    ad = record("a", "\n".join(s["text"] for s in segments), segments=segments)
    targets, hits = mention_contexts(ad, [], adjective_vocabulary())
    assert targets == {"D", "R"}
    assert [(hit["word"], hit["target_party"]) for hit in hits] == [("dangerous", "R")]
    assert ad["text"][hits[0]["start"] : hits[0]["end"]] == "dangerous"


def test_nearby_words_are_bounded_and_denominators_include_no_word_hits_and_deduplicate():
    distant = "Republicans " + "legislation " * 30 + "dangerous."
    assert mention_contexts(record("far", distant), [], adjective_vocabulary()) == ({"R"}, [])
    ads = [
        record(
            f"{party}-{i}",
            f"Republicans {'are bad' if party == 'D' and i < 4 else 'discuss legislation'} {i}.",
            party,
        )
        for party in ("D", "R")
        for i in range(10)
    ]
    ads += [
        ads[0] | {"id": "mirror", "published": "2026-10-02"},
        record("excluded", "Republicans are bad.", "unknown"),
        record("unmentioned", "This is bad."),
    ]
    result = descriptive_language(snapshot(ads))
    group = result["targets"]["R"]
    assert {party: scope["total"] for party, scope in group["coverage"].items()} == {
        "D": 10,
        "R": 10,
    }
    bad = next(row for row in group["words"] if row["word"] == "bad")
    assert bad["D"]["count"] == 4 and bad["D"]["share"] == 0.4
    assert bad["R"]["count"] == 0 and bad["R"]["share"] == 0
    assert bad["log2_odds"] == math.log2((4.5 / 6.5) / (0.5 / 10.5))
    assert set(bad["D"]["ad_ids"]) == {f"D-{i}" for i in range(4)}
    assert not result["targets"]["D"]["rankable"]


def test_adjacent_windows_use_first_observation_and_expose_publisher_mix_sensitivity():
    ads = []
    for period, day in (("previous", "2026-06-01"), ("recent", "2026-09-01")):
        for shared in (True, False):
            for i in range(12):
                bad = shared == (period == "recent")
                ads.append(
                    record(
                        f"{period}-{shared}-{i}",
                        f"Republicans {'are bad' if bad else 'discuss legislation'} "
                        f"{period} {shared} {i}.",
                        published=day,
                        sponsor="Shared" if shared else period,
                    )
                )
    ads.append(ads[0] | {"id": "repeat-in-recent", "published": "2026-09-02"})
    result = descriptive_language(snapshot(ads))
    assert result["periods"] == {
        "recent": {"start": "2026-07-30", "end": "2026-10-27"},
        "previous": {"start": "2026-05-01", "end": "2026-07-29"},
    }
    change = result["changes"]["D"]
    assert change["common_publisher_names"] == ["Shared"]
    all_group, common = change["all_publishers"], change["common_publishers"]
    assert all_group["coverage"]["previous"]["total"] == 24
    assert all_group["coverage"]["recent"]["total"] == 24
    assert common["coverage"]["previous"]["total"] == 12
    assert common["coverage"]["recent"]["total"] == 12
    assert next(row for row in all_group["words"] if row["word"] == "bad")["log2_odds"] == 0
    assert next(row for row in common["words"] if row["word"] == "bad")["log2_odds"] > 9


def test_insufficient_groups_do_not_receive_rankings_or_invent_early_scope_messages():
    result = descriptive_language(
        snapshot(
            [record(str(i), f"Republicans are bad {i}.", published="2026-01-01") for i in range(3)],
            until="2026-01-02",
        )
    )
    group = result["targets"]["R"]
    assert group["words"][0]["log2_odds"] is None
    assert group["words"][0]["R"]["share"] is None
    assert result["changes"]["D"]["all_publishers"]["coverage"]["previous"]["total"] == 0
