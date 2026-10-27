from urllib.error import HTTPError

import pytest

from political_ads.cli import load_corpus, write_json
from political_ads.google import (
    collect_google,
    federal_advertisers,
    preview_ad,
    preview_images,
    us_delivery,
)


def lead():
    return {
        "Ad_ID": "CR1",
        "Ad_URL": "https://adstransparency.google.com/advertiser/AR1/creative/CR1",
        "Ad_Type": "TEXT",
        "Advertiser_ID": "AR1",
        "Regions": "US",
        "Date_Range_Start": "2025-12-01",
        "Date_Range_End": "2026-02-01",
        "publisher": {
            "source": "nrsc",
            "sponsor": "NRSC",
            "alignment": "R",
            "sponsor_type": "party",
            "chamber": "Senate",
            "race": "Unresolved",
            "state": "",
            "committee_id": "C00027466",
            "candidate_id": "",
        },
    }


def ocr():
    return {
        "image_frame_count": 1,
        "engine": "Local OCR",
        "coordinate_system": "normalized bottom-left",
        "lines": [
            {"text": "Paid for by NRSC", "confidence": 1, "bounds": [0, 0.9, 1, 0.1]},
            {
                "text": "Vote to lower the cost of living for American families.",
                "confidence": 0.9,
                "bounds": [0, 0.1, 1, 0.5],
            },
        ],
    }


def test_fec_join_requires_unambiguous_federal_principal_committee_not_name_keywords():
    candidates = [
        {
            "candidate_id": "H123",
            "principal_committee": "C12345678",
            "name": "SMITH, JANE",
            "party": "REP",
            "office": "H",
            "election_year": "2026",
            "state": "OH",
            "district": "03",
        }
    ]
    advertisers = [
        dict(Advertiser_ID="AR1", Advertiser_Name="Smith", Public_IDs_List="FEC ID C12345678"),
        dict(Advertiser_ID="AR2", Advertiser_Name="Republicans", Public_IDs_List="EIN 12-34567"),
        dict(
            Advertiser_ID="AR3",
            Advertiser_Name="Mixed",
            Public_IDs_List="FEC ID C12345678, C00027466",
        ),
    ]
    joined = federal_advertisers(advertisers, candidates)
    assert set(joined) == {"AR1"}
    assert joined["AR1"]["race"] == "OH-03"
    assert joined["AR1"]["alignment"] == "R"
    assert (
        federal_advertisers(advertisers, candidates + [candidates[0] | {"candidate_id": "H456"}])
        == {}
    )


def test_only_direct_native_image_previews_not_video_posters_or_external_images():
    url = "https://tpc.googlesyndication.com/archive/simgad/1"
    payload = {
        "1": {
            "5": [
                {"3": {"2": f'<img src="{url}">'}},
                {
                    "3": {
                        "2": f'<iframe src="https://youtube.com/embed/x"></iframe><img src="{url}">'
                    }
                },
                {"3": {"2": '<img src="https://outside.example/image">'}},
                {"3": {"2": f'<img src="{url}">'}},
            ]
        }
    }
    assert preview_images(payload) == [url]


def test_us_dates_and_preview_variants_preserve_text_and_reject_animation_and_disclaimers():
    row = lead()
    payload = {"1": {"17": [{"1": 2840, "4": 20260104, "5": 20260201}]}}
    assert us_delivery(row | {"Regions": "US,GU"}, payload) == ("2026-01-04", "2026-02-01")
    with pytest.raises(ValueError):
        us_delivery(row | {"Regions": "US,GU"}, {})
    ad = preview_ad(row, {}, "https://image.example/a", "hash", ocr())
    variant = preview_ad(row, {}, "https://image.example/b", "hash", ocr())
    assert ad["id"] != variant["id"]
    assert ad["text"] == "\n".join(line["text"] for line in ocr()["lines"])
    assert ad["date_basis"] == "delivery" and ad["delivery_start"] == "2025-12-01"
    assert ad["segments"][0]["fec_committee_id"] == "C00027466"
    with pytest.raises(ValueError):
        preview_ad(row, {}, "https://image.example/a", "hash", ocr() | {"image_frame_count": 2})
    with pytest.raises(ValueError):
        preview_ad(
            row, {}, "https://image.example/a", "hash", ocr() | {"lines": ocr()["lines"][:1]}
        )


def test_collection_retains_good_text_on_rate_limit_and_never_retries(tmp_path, monkeypatch):
    row = lead()
    ad = preview_ad(row, {}, "https://image.example/a", "hash", ocr())
    write_json(tmp_path / "data/site/google.json", {"ads": [ad], "sources": []})
    write_json(
        tmp_path / "data/raw/google-discovery.json",
        {"until": "2026-10-26", "leads": [row], "updated": "2026-10-26", "scope": "test"},
    )
    calls = []

    def blocked(*args):
        calls.append(args)
        raise HTTPError(row["Ad_URL"], 429, "Too many requests", {}, None)

    monkeypatch.setattr("political_ads.google.creative_payload", blocked)
    result = collect_google(tmp_path, "2026-10-26", 0)
    assert result["ads"] == [ad] and result["sources"][0]["blocked"].startswith("HTTP 429")
    assert collect_google(tmp_path, "2026-10-26", 0)["ads"] == [ad]
    assert len(calls) == 1
    write_json(
        tmp_path / "data/site/corpus.json", {"until": "2026-10-26", "ads": [], "sources": []}
    )
    assert load_corpus(tmp_path)["ads"] == [ad]
