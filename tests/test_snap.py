import json
from urllib.error import HTTPError

import pytest

from political_ads.cli import load_corpus, write_json
from political_ads.schema import digest
from political_ads.snap import (
    apply_language_review,
    collect_snap,
    native_asset,
    snap_ad,
    snap_leads,
)
from political_ads.video import transcribe_with_alignment_fallback, video_segments

VIEWER = "https://www.snap.com/political-ads/asset/" + "a" * 64 + "?mediaType=png"
NATIVE = "https://storage.googleapis.com/ad-manager-political-ads-dump-shadow/" + "a" * 64 + ".png"


def row(**overrides):
    return {
        "ADID": "one",
        "CreativeUrl": VIEWER,
        "CountryCode": "UNITED STATES",
        "StartDate": "2026/08/01 00:00:00Z",
        "EndDate": "2026/09/01 00:00:00Z",
        "Impressions": "100",
        "PayingAdvertiserName": "NRSC",
        "CommitteeIdentificationNumber": "",
    } | overrides


def leads(rows):
    return snap_leads(rows, [], [dict(name="NRSC", committee_id="C00027466")], {}, "2026-10-26")


def ocr():
    return dict(
        image_frame_count=1,
        engine="Local OCR",
        coordinate_system="normalized bottom-left",
        lines=[dict(text="Vote to protect Social Security.", confidence=1, bounds=[0, 0, 1, 1])],
    )


def test_federal_selection_requires_exact_identity_positive_impressions_and_us_dates():
    records = [
        row(),
        row(ADID="wrong-name", PayingAdvertiserName="Republicans for America"),
        row(ADID="no-delivery", Impressions="0"),
        row(ADID="future", StartDate="2026/11/01", EndDate="2026/11/02"),
        row(ADID="foreign", CountryCode="CANADA"),
        row(ADID="conflicting", CommitteeIdentificationNumber="C00000935"),
    ]
    result = leads(records)
    assert len(result) == 1
    assert result[0]["publisher"]["alignment"] == "R"
    assert [p["ad_id"] for p in result[0]["placements"]] == ["one"]
    assert leads([row(PayingAdvertiserName="nrsc")])
    assert not snap_leads(
        [row()],
        [],
        [dict(name="NRSC", committee_id="C00027466"), dict(name="NRSC", committee_id="C00000935")],
        {},
        "2026-10-26",
    )
    rejected = []
    assert not snap_leads(
        [row(StartDate="2026/09/02", EndDate="2026/08/01")],
        [],
        [dict(name="NRSC", committee_id="C00027466")],
        {},
        "2026-10-26",
        rejected,
    )
    assert rejected[0]["reason"] == "Delivery end precedes start"


def test_reviewed_alias_and_declared_id_paths_remain_distinct_from_platform_reported_ids():
    alias = {
        "exact payer": dict(
            committee_id="C00027466",
            evidence="Reviewed crosswalk",
            evidence_url="https://evidence.example/committee",
        )
    }
    matched = snap_leads([row(PayingAdvertiserName="Exact Payer")], [], [], alias, "2026-10-26")
    assert matched[0]["publisher"]["identity_basis"] == "Reviewed crosswalk"
    assert not snap_leads(
        [row(PayingAdvertiserName="Exact Payer", CommitteeIdentificationNumber="C00000935")],
        [],
        [],
        alias,
        "2026-10-26",
    )
    direct = snap_leads(
        [row(PayingAdvertiserName="Different name", CommitteeIdentificationNumber="C00027466")],
        [],
        [],
        {},
        "2026-10-26",
    )
    assert direct[0]["publisher"]["identity_basis"].startswith("Snap reports FEC")


def test_unmatched_payer_audit_preserves_safe_in_scope_inventory_not_billing_or_targeting():
    unmatched = []
    records = [
        row(
            ADID="unmatched",
            PayingAdvertiserName="Unreviewed payer",
            CommitteeIdentificationNumber="C12345678",
            CreativeProperties="Landing Page URL: https://campaign.example/ad?tracking=value",
            CandidateBallotInformation="Candidate for Congress",
            BillingAddress="Excluded billing field",
            TargetingLocation="Excluded targeting field",
        ),
        row(ADID="duplicate-creative", PayingAdvertiserName="Unreviewed payer"),
        row(ADID="future", PayingAdvertiserName="Future payer", StartDate="2026/11/01"),
        row(ADID="zero", PayingAdvertiserName="Zero payer", Impressions="0"),
        row(ADID="foreign", PayingAdvertiserName="Foreign payer", CountryCode="CANADA"),
    ]
    assert not snap_leads(records, [], [], {}, "2026-10-26", unmatched=unmatched)
    assert len(unmatched) == 1
    payer = unmatched[0]
    assert payer["review_state"] == "unreviewed_identity_and_scope"
    assert payer["platform_ad_ids"] == ["duplicate-creative", "unmatched"]
    assert payer["creative_urls"] == [VIEWER]
    assert payer["reported_fec_ids"] == ["C12345678"]
    assert payer["landing_hosts"] == ["campaign.example"]
    assert payer["candidate_ballot_information"] == ["Candidate for Congress"]
    assert "Excluded" not in json.dumps(unmatched)
    assert "tracking" not in json.dumps(unmatched)
    rejected_alias = []
    snap_leads(
        [row(PayingAdvertiserName="Reviewed payer", CommitteeIdentificationNumber="C00000935")],
        [],
        [],
        {"Reviewed payer": {"committee_id": "C00027466"}},
        "2026-10-26",
        unmatched=rejected_alias,
    )
    assert rejected_alias[0]["review_state"] == "reviewed_alias_constraints_not_met"


def test_native_asset_excludes_footer_images_posters_and_unrelated_urls():
    assert (
        native_asset(f'<img src="https://other.example/x"><img src="{NATIVE}">'.encode(), VIEWER)
        == NATIVE
    )
    for html in [
        b'<video poster="https://other.example/x"></video>',
        b'<img src="https://other.example/x">',
    ]:
        with pytest.raises(ValueError):
            native_asset(html, VIEWER)
    with pytest.raises(ValueError):
        native_asset(
            f'<img src="{NATIVE}">'.encode(), VIEWER.replace("www.snap.com", "bad.example")
        )


def test_reviewed_candidacy_resolves_reused_committee_without_guessing_a_race():
    candidates = [
        dict(
            candidate_id=identity,
            name="SMITH, JANE",
            election_year="2026",
            office=office,
            state="OH",
            district="01" if office == "H" else "00",
            party="DEM",
            principal_committee="C12345678",
        )
        for identity, office in (("H-test", "H"), ("S-test", "S"))
    ]
    records = [row(PayingAdvertiserName="Jane for Senate")]
    committees = [dict(name="Jane for Senate", committee_id="C12345678")]
    assert not snap_leads(records, candidates, committees, {}, "2026-10-26")
    review = dict(
        committee_id="C12345678",
        candidate_id="S-test",
        evidence="Official current Senate campaign and FEC principal committee",
        evidence_url="https://evidence.example/senate",
    )
    result = snap_leads(records, candidates, committees, {"Jane for Senate": review}, "2026-10-26")
    assert result[0]["publisher"]["race"] == "OH-Senate"
    assert result[0]["publisher"]["candidate_id"] == "S-test"
    assert review["evidence"] in result[0]["publisher"]["identity_basis"]
    for changed in (
        {"candidate_id": "unknown"},
        {"committee_id": "C87654321"},
    ):
        assert not snap_leads(
            records, candidates, committees, {"Jane for Senate": review | changed}, "2026-10-26"
        )


def test_reviewed_advocacy_payers_need_federal_content_and_never_receive_invented_fec_ids():
    alias = {
        "Advocacy group": {
            "publisher": dict(
                source="advocacy",
                sponsor="Advocacy group",
                alignment="R",
                sponsor_type="outside_group",
                chamber="Senate",
                race="Unresolved",
                state="",
            ),
            "evidence": "Reviewed first-party identity and alignment",
            "evidence_url": "https://evidence.example/",
        }
    }
    lead = snap_leads([row(PayingAdvertiserName="Advocacy group")], [], [], alias, "2026-10-26")[0]
    candidate = dict(
        candidate_id="S-test",
        name="SMITH, JANE",
        election_year="2026",
        office="S",
        state="OH",
        district="00",
        party="REP",
    )
    with pytest.raises(ValueError, match="no full 2026 federal"):
        snap_ad(lead, "hash", ocr(), candidates=[candidate])
    named_ocr = ocr()
    named_ocr["lines"][0]["text"] = "Tell Jane Smith to protect Social Security."
    ad = snap_ad(lead, "hash", named_ocr, candidates=[candidate])
    assert ad["segments"][0]["fec_committee_id"] is None
    assert "without an assigned FEC committee ID" in ad["attribution_basis"]
    assert "no noncommittee disclosure ID is assigned" in ad["attribution_basis"]
    with pytest.raises(ValueError, match="no full 2026 federal"):
        snap_ad(lead, "hash", named_ocr, candidates=[candidate | {"election_year": "2024"}])
    assert not snap_leads(
        [row(PayingAdvertiserName="Advocacy group", CommitteeIdentificationNumber="C00000935")],
        [],
        [],
        alias,
        "2026-10-26",
    )
    line = named_ocr["lines"][0]
    named_ocr["lines"] = [line | {"text": "Tell Jane"}, line | {"text": "Smith to act."}]
    ad = snap_ad(lead, "hash", named_ocr, candidates=[candidate])
    assert ad["race"] == "OH-Senate"
    assert "Jane\nSmith" in ad["text"]
    assert ad["segments"][0]["federal_scope_evidence"][0]["text"] == "Tell Jane Smith to act."
    speech = dict(
        engine="Local ASR",
        model="base",
        model_revision="revision",
        language="en",
        language_probability=1,
        segments=[dict(text="Protect health care.", start_seconds=0, end_seconds=2)],
    )
    frames = dict(
        duration_seconds=2,
        sample_interval_seconds=1,
        engine="Local OCR",
        coordinate_system="normalized bottom-left",
        frames=[
            dict(seconds=0, lines=[line | {"text": "Tell Jane"}]),
            dict(seconds=1, lines=[line | {"text": "Smith to act."}]),
        ],
    )
    with pytest.raises(ValueError, match="no full 2026 federal"):
        snap_ad(lead, "hash", frames, speech, candidates=[candidate])
    frames["frames"] = [dict(seconds=0, lines=[line | {"text": "Smith to act."}])]
    speech["segments"][0]["text"] = "Tell Jane"
    with pytest.raises(ValueError, match="no full 2026 federal"):
        snap_ad(lead, "hash", frames, speech, candidates=[candidate])


def test_reviewed_advocacy_ids_and_owned_landing_hosts_do_not_merge_conflicting_payers():
    publisher = dict(
        source="reviewed",
        sponsor="Reviewed group",
        alignment="D",
        sponsor_type="outside_group",
        chamber="",
        race="Unresolved",
        state="",
    )
    review = dict(
        publisher=publisher,
        noncommittee_disclosure_ids=["C30000001", "C90000001"],
        landing_hosts=["reviewed.example"],
        evidence="Reviewed legal disclosures and first-party landing-page disclaimer",
        evidence_url="https://reviewed.example",
    )
    aliases = {"Reviewed group": review}
    committees = [
        dict(name="Reviewed group", committee_id=identity)
        for identity in review["noncommittee_disclosure_ids"]
    ]
    record = row(
        PayingAdvertiserName="Reviewed group",
        CreativeProperties="web_view_url:https://www.reviewed.example/ad",
    )
    lead = snap_leads([record], [], committees, aliases, "2026-10-26")[0]
    assert lead["publisher"]["committee_id"] == ""
    candidate = dict(
        candidate_id="S-test",
        name="SMITH, JANE",
        election_year="2026",
        office="S",
        state="OH",
        district="00",
        party="REP",
    )
    named_ocr = ocr()
    named_ocr["lines"][0]["text"] = "Tell Jane Smith to protect Social Security."
    ad = snap_ad(lead, "hash", named_ocr, candidates=[candidate])
    assert ad["segments"][0]["fec_committee_id"] is None
    assert ad["segments"][0]["fec_noncommittee_disclosure_ids"] == [
        "C30000001",
        "C90000001",
    ]
    for changed in (
        {"CreativeProperties": ""},
        {"CreativeProperties": "web_view_url:https://reviewed.example.evil/ad"},
        {"CreativeProperties": "web_view_url:https://different-payer.example/ad"},
        {"CommitteeIdentificationNumber": "C99999999"},
    ):
        assert not snap_leads([record | changed], [], committees, aliases, "2026-10-26")
    pac_review = {k: v for k, v in review.items() if k != "noncommittee_disclosure_ids"}
    pac_review["committee_id"] = "C12345678"
    pac_lead = snap_leads([record], [], [], {"Reviewed group": pac_review}, "2026-10-26")[0]
    ad = snap_ad(pac_lead, "hash", named_ocr, candidates=[candidate])
    assert ad["segments"][0]["fec_committee_id"] == "C12345678"
    assert "with an evidenced FEC committee ID" in ad["attribution_basis"]


def test_repeated_placements_are_one_creative_with_explicit_scheduled_dates_and_full_provenance():
    lead = leads([row(), row(ADID="two", StartDate="2026/10/01", EndDate="2026/12/01")])[0]
    ad = snap_ad(lead, "hash", ocr())
    assert len(lead["placements"]) == 2
    assert ad["date_basis"] == "scheduled_delivery"
    assert (ad["delivery_start"], ad["delivery_end"]) == ("2026-08-01", "2026-12-01")
    assert ad["segments"][0]["snap_ad_ids"] == ["one", "two"]
    assert "scheduled" in ad["attribution_basis"]
    with pytest.raises(ValueError):
        snap_ad(lead, "hash", ocr() | {"image_frame_count": 2})


def test_federal_scope_review_requires_matching_hash_quotes_and_candidate():
    lead = leads([row()])[0]
    lead["publisher"]["requires_federal_mention"] = True
    image = ocr()
    image["lines"][0]["text"] = "Call Senator Smith to protect federal benefits."
    candidate = dict(
        candidate_id="S-test",
        name="SMITH, JANE",
        election_year="2026",
        office="S",
        state="OH",
        district="00",
        party="REP",
    )
    review = dict(
        source_hash=digest(json.dumps([lead, "hash", image, None], sort_keys=True)),
        candidate_ids=["S-test"],
        quotes=["Senator Smith", "federal benefits"],
        evidence_url="https://evidence.example/senator",
        basis="Reviewed federal office identity",
    )
    with pytest.raises(ValueError, match="no full 2026 federal"):
        snap_ad(lead, "hash", image, candidates=[candidate])
    ad = snap_ad(lead, "hash", image, candidates=[candidate], scope_review=review)
    assert ad["race"] == "OH-Senate"
    assert ad["text"] == image["lines"][0]["text"]
    assert ad["segments"][0]["federal_scope_evidence"][0]["review"] == review
    for override, error in [
        ({"source_hash": "changed"}, "source hash"),
        ({"quotes": ["Unobserved quote"]}, "quotes"),
        ({"candidate_ids": ["unknown"]}, "actual 2026 federal candidates"),
    ]:
        with pytest.raises(ValueError, match=error):
            snap_ad(lead, "hash", image, candidates=[candidate], scope_review=review | override)


def test_video_keeps_speech_and_novel_overlays_once_with_timed_duplicate_and_rejected_evidence():
    line = dict(text="Lower taxes", confidence=1, bounds=[0, 0, 1, 1])
    novel = line | {"text": "Protect Social Security"}
    rejected = line | {"text": "PIOTECT S0CAL", "confidence": 0.4}
    frames = dict(
        duration_seconds=2,
        sample_interval_seconds=1,
        engine="Local OCR",
        coordinate_system="normalized bottom-left",
        frames=[dict(seconds=t, lines=[line, novel, rejected]) for t in (0, 1)],
    )
    speech = dict(
        engine="Local ASR",
        model="base",
        model_revision="revision",
        segments=[dict(text="Lower taxes for families.", start_seconds=0, end_seconds=2)],
    )
    segments = video_segments(frames, speech, "hash")
    assert [s["text"] for s in segments] == ["Lower taxes for families.", "Protect Social Security"]
    assert len(segments[1]["frame_observations"]) == 2
    assert segments[0]["speech_duplicate_ocr_observations"][0]["text"] == "Lower taxes"
    assert len(segments[0]["excluded_low_confidence_ocr_observations"]) == 2
    assert segments[1]["start_seconds"] == segments[1]["end_seconds"] == 0


def test_implausible_speech_timing_stays_in_review_evidence_not_text_or_scope_matches():
    line = dict(text="Protect health care for working families.", confidence=1, bounds=[0, 0, 1, 1])
    frames = dict(
        duration_seconds=15,
        sample_interval_seconds=1,
        engine="Local OCR",
        coordinate_system="normalized bottom-left",
        frames=[dict(seconds=0, lines=[line])],
    )
    invalid = dict(text="Jane Smith " * 40, start_seconds=0.1, end_seconds=0.11)
    speech = dict(
        engine="Local ASR",
        model="base",
        model_revision="revision",
        language="en",
        language_probability=0.5,
        segments=[invalid],
    )
    segments = video_segments(frames, speech, "hash")
    assert [s["text"] for s in segments] == [line["text"]]
    assert segments[0]["excluded_implausible_asr_segments"][0]["text"] == invalid["text"]
    lead = leads([row()])[0]
    ad = snap_ad(lead, "hash", frames, speech)
    assert ad["text"] == line["text"]
    assert ad["language"] == "en"
    assert "implausible_asr_timing_excluded_retained_for_review" in ad["quality_flags"]
    lead["publisher"]["requires_federal_mention"] = True
    candidate = dict(
        candidate_id="S-test",
        name="SMITH, JANE",
        election_year="2026",
        office="S",
        state="OH",
        district="00",
        party="REP",
    )
    with pytest.raises(ValueError, match="no full 2026 federal"):
        snap_ad(lead, "hash", frames, speech, candidates=[candidate])
    normal = speech | {"segments": [invalid | {"end_seconds": 30}]}
    assert video_segments(frames, normal, "hash")[0]["kind"] == "local_asr"


def test_rate_limit_retains_existing_text_and_persistently_stops_requests(tmp_path, monkeypatch):
    lead = leads([row()])[0]
    ad = snap_ad(lead, "hash", ocr())
    write_json(tmp_path / "data/site/snap.json", {"ads": [ad], "sources": []})
    write_json(
        tmp_path / "outputs/snap-discovery.json",
        {"until": "2026-10-26", "leads": [lead], "archive_sha256": "hash"},
    )
    calls = []

    def blocked(*args, **kwargs):
        calls.append(kwargs)
        raise HTTPError(VIEWER, 429, "Too many requests", {}, None)

    monkeypatch.setattr("political_ads.snap.Client.get", blocked)
    result = collect_snap(tmp_path, "2026-10-26")
    assert result["ads"] == [ad]
    assert result["sources"][0]["blocked"].startswith("HTTP 429")
    assert collect_snap(tmp_path, "2026-10-26")["ads"] == [ad]
    assert calls == [{"retry": False}]
    write_json(
        tmp_path / "data/site/corpus.json", {"until": "2026-10-26", "ads": [], "sources": []}
    )
    assert load_corpus(tmp_path)["ads"] == [ad]


def test_contextual_language_review_is_hash_bound_and_preserves_automatic_label():
    ad = snap_ad(leads([row()])[0], "hash", ocr()) | {"language": "unknown"}
    ledger = {
        "basis": "Reviewed complete recovered English text",
        "english_source_hashes": {ad["id"]: ad["source_hash"]},
    }
    reviewed = apply_language_review(ad, ledger)
    assert reviewed["language"] == "en"
    assert reviewed["segments"][0]["language_review"]["automatic_language"] == "unknown"
    with pytest.raises(ValueError, match="source hash"):
        apply_language_review(ad | {"source_hash": "changed"}, ledger)
    assert apply_language_review(ad, {}) == ad


@pytest.mark.parametrize("extraction_fails", [False, True])
def test_replay_withdraws_invalid_scope_but_preserves_prior_text_on_extraction_failure(
    tmp_path, monkeypatch, extraction_fails
):
    lead = leads([row()])[0]
    prior = snap_ad(lead, "hash", ocr())
    lead["publisher"]["requires_federal_mention"] = True
    write_json(tmp_path / "data/site/snap.json", {"ads": [prior], "sources": []})
    write_json(
        tmp_path / "outputs/snap-discovery.json",
        {"until": "2026-10-26", "leads": [lead], "archive_sha256": "hash"},
    )
    write_json(
        tmp_path / "data/raw/snap-progress.json",
        {"records": {lead["id"]: {"state": "text"}}, "blocked": ""},
    )
    monkeypatch.setattr(
        "political_ads.snap.Client.get",
        lambda self, url, **kwargs: (
            f'<img src="{NATIVE}">'.encode() if url == VIEWER else b"image",
            {},
        ),
    )

    def recognize(*args):
        if extraction_fails:
            raise ValueError("Invalid cached extraction")
        return "hash", ocr()

    monkeypatch.setattr("political_ads.snap.recognize_image", recognize)
    result = collect_snap(tmp_path, "2026-10-26", offline=True)
    assert result["ads"] == ([prior] if extraction_fails else [])
    progress = json.loads((tmp_path / "data/raw/snap-progress.json").read_text())
    assert progress["records"][lead["id"]]["state"] == "unprocessed"


def test_local_word_alignment_failure_falls_back_to_real_segment_timestamps():
    calls = []

    class Model:
        def transcribe(self, audio, **settings):
            calls.append(settings["word_timestamps"])

            def segments():
                if settings["word_timestamps"]:
                    raise IndexError("empty word alignment")
                yield "actual decoded segment"

            return segments(), "actual language info"

    settings = {"word_timestamps": True}
    segments, info, error = transcribe_with_alignment_fallback(Model(), "waveform", settings)
    assert calls == [True, False]
    assert segments == ["actual decoded segment"] and info == "actual language info"
    assert settings == {"word_timestamps": False} and error == "empty word alignment"


def test_selected_offline_replay_never_rewrites_or_requests_unselected_ads(tmp_path, monkeypatch):
    selected, untouched = leads(
        [row(), row(ADID="two", CreativeUrl=VIEWER.replace("a" * 64, "b" * 64))]
    )
    prior = snap_ad(untouched, "prior-hash", ocr())
    write_json(tmp_path / "data/site/snap.json", {"ads": [prior], "sources": []})
    write_json(
        tmp_path / "outputs/snap-discovery.json",
        {"until": "2026-10-26", "leads": [selected, untouched], "archive_sha256": "hash"},
    )
    write_json(
        tmp_path / "data/raw/snap-progress.json",
        {
            "records": {
                selected["id"]: {"state": "unprocessed"},
                untouched["id"]: {"state": "text"},
            },
            "blocked": "",
        },
    )

    def cached(self, url, **kwargs):
        assert url in {VIEWER, NATIVE}, "Unselected original must never be requested"
        return (f'<img src="{NATIVE}">'.encode() if url == VIEWER else b"image"), {}

    monkeypatch.setattr("political_ads.snap.Client.get", cached)
    monkeypatch.setattr("political_ads.snap.recognize_image", lambda *args: ("hash", ocr()))
    result = collect_snap(tmp_path, "2026-10-26", offline=True, ad_ids=[selected["id"]])
    assert next(ad for ad in result["ads"] if ad["id"] == prior["id"]) == prior
    assert {ad["id"] for ad in result["ads"]} == {selected["id"], untouched["id"]}
    with pytest.raises(ValueError, match="discovery inventory"):
        collect_snap(tmp_path, "2026-10-26", offline=True, ad_ids=["not-in-inventory"])


@pytest.mark.parametrize("saved_state", ["text", "unprocessed"])
def test_offline_cli_replays_cached_text_even_when_online_collection_is_blocked(
    tmp_path, monkeypatch, saved_state
):
    from political_ads.cli import main

    lead = leads([row()])[0]
    lead["publisher"]["requires_federal_mention"] = True
    candidate = dict(
        candidate_id="S-test",
        name="SMITH, JANET",
        election_year="2026",
        office="S",
        state="OH",
        district="00",
        party="REP",
    )
    alias = dict(
        candidate_id="S-test",
        name="SMITH, JANE",
        full_name="Jane M. Smith",
        evidence_url="https://evidence.example/campaign",
        basis="Reviewed campaign name",
    )
    write_json(tmp_path / "data/processed/registry.json", {"candidates": [candidate]})
    write_json(tmp_path / "data/snap-candidate-aliases.json", [alias])
    write_json(
        tmp_path / "outputs/snap-discovery.json",
        {
            "until": "2026-10-26",
            "leads": [lead],
            "archive_sha256": "hash",
        },
    )
    write_json(
        tmp_path / "data/raw/snap-progress.json",
        {
            "records": {lead["id"]: {"state": saved_state}},
            "blocked": "HTTP 429",
        },
    )
    modes = []

    class CachedClient:
        def __init__(self, path, offline):
            modes.append(offline)

        def get(self, url, **kwargs):
            assert modes == [True]
            return (f'<img src="{NATIVE}">'.encode() if url == VIEWER else b"image"), {}

    monkeypatch.setattr("political_ads.snap.Client", CachedClient)
    named_ocr = ocr()
    named_ocr["lines"][0]["text"] = "Tell Jane M. Smith to protect Social Security."
    monkeypatch.setattr("political_ads.snap.recognize_image", lambda *args: ("hash", named_ocr))
    monkeypatch.setattr(
        "sys.argv",
        [
            "political-ads",
            "--root",
            str(tmp_path),
            "snap-collect",
            "--until",
            "2026-10-26",
            "--offline",
            "--limit",
            "1",
        ],
    )
    main()
    import json

    result = json.loads((tmp_path / "data/site/snap.json").read_text())
    assert result["ads"][0]["id"] == lead["id"]
    evidence = result["ads"][0]["segments"][0]["federal_scope_evidence"]
    assert evidence[0]["candidate_mentions"][0]["reviewed_alias"] == alias
    assert json.loads((tmp_path / "data/processed/registry.json").read_text())["candidates"] == [
        candidate
    ]
    assert result["sources"][0]["blocked"] == "HTTP 429"
