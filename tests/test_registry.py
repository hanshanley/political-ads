from political_ads.registry import candidate_mentions, enrich


def candidate(name="SMITH, JANE"):
    return {
        "candidate_id": "H6PA01001",
        "name": name,
        "party": "DEM",
        "state": "PA",
        "office": "H",
        "district": "01",
    }


def test_surname_alone_does_not_establish_identity():
    assert candidate_mentions("Smith is wrong.", [candidate()]) == []
    assert len(candidate_mentions("Jane Smith is wrong.", [candidate()])) == 1
    assert candidate_mentions("Jane Smithson is wrong.", [candidate()]) == []
    assert candidate_mentions("NotJane Smith is wrong.", [candidate()]) == []
    assert len(candidate_mentions("JANE SMITH will help.", [candidate()])) == 1


def test_conflicting_races_are_not_guessed():
    other = candidate("JONES, JAMES") | {"state": "OH"}
    ad = {"text": "Jane Smith and James Jones", "title": "", "race": "Unresolved"}
    assert enrich(ad, [candidate(), other])["race"] == "Unresolved"


def test_unique_full_name_can_resolve_race():
    ad = {"text": "Jane Smith is wrong.", "title": "", "race": "Unresolved"}
    assert enrich(ad, [candidate()])["race"] == "PA-01"


def test_multi_ad_release_title_does_not_override_creative_specific_race():
    other = candidate("JONES, JAMES") | {"state": "OH"}
    ad = {
        "text": "James Jones is wrong.",
        "title": "New ads calling out Jane Smith and James Jones",
        "race": "Unresolved",
    }
    assert enrich(ad, [candidate(), other])["race"] == "OH-01"
