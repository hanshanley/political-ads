from __future__ import annotations

import csv
import json
import platform
from collections import Counter
from hashlib import sha256
from importlib.metadata import version
from pathlib import Path

from political_ads.analysis import publisher
from political_ads.cli import read_json
from political_ads.portrayals import AD_STRATEGIES
from political_ads.publication import prepare, validate_dataset
from political_ads.schema import message_key, observation_date


def audit_ad_strategy(ads: list[dict], portrayals: dict) -> dict:
    # Do not call the production strategy classifier, summary or deduplication helper.
    def classify(records):
        representatives = {}
        for ad in sorted(records, key=lambda ad: (observation_date(ad), ad["id"])):
            representatives.setdefault((ad["alignment"], message_key(ad["text"])), ad)
        rows = []
        for ad in representatives.values():
            review = ad.get("portrayal_review", {})
            praise, criticism = [], []
            if review.get("status") == "reviewed":
                for index, description in enumerate(review["descriptions"]):
                    if description["voice"] not in ("advertiser", "adopted_clip"):
                        continue
                    if (
                        description["target_party"] == ad["alignment"]
                        and description["target_role"] == "self_or_supported"
                        and description["tone"] == "positive"
                    ):
                        praise.append(index)
                    if (
                        description["target_party"] == ("R" if ad["alignment"] == "D" else "D")
                        and description["target_role"] == "opponent"
                        and description["tone"] == "negative"
                    ):
                        criticism.append(index)
                category = {
                    (True, False): "own_positive_only",
                    (True, True): "contrast",
                    (False, True): "opponent_negative_only",
                    (False, False): "neither",
                }[bool(praise), bool(criticism)]
            else:
                category = "not_reviewed"
            rows.append(
                {
                    **{
                        key: ad[key]
                        for key in (
                            "id",
                            "alignment",
                            "message_id",
                            "sponsor",
                            "source",
                            "source_url",
                            "source_hash",
                            "text_hash",
                            "text",
                        )
                    },
                    "selection_date": observation_date(ad),
                    "category": category,
                    "review": review,
                    "own_praise_description_indices": praise,
                    "opponent_criticism_description_indices": criticism,
                }
            )
        return rows

    records = [ad for ad in ads if ad["alignment"] in ("D", "R")]
    excluded = {}
    for party in ("D", "R"):
        counts = Counter(publisher(ad) for ad in records if ad["alignment"] == party)
        if counts:
            excluded[party] = sorted(counts, key=lambda name: (-counts[name], name))[0]
    if excluded != portrayals["sensitivity"]["excluded_publishers"]:
        raise ValueError("Same-ad audit mismatch: excluded publishers")
    full = classify(records)
    reduced = classify([ad for ad in records if publisher(ad) != excluded.get(ad["alignment"])])
    summaries = {}
    for name, rows, saved in (
        ("full", full, portrayals["ad_strategy"]["parties"]),
        (
            "excluding_largest_publishers",
            reduced,
            portrayals["sensitivity"]["ad_strategy"]["parties"],
        ),
    ):
        summaries[name] = {}
        for party in ("D", "R"):
            group = [row for row in rows if row["alignment"] == party]
            summaries[name][party] = {}
            for category in AD_STRATEGIES:
                ids = [row["id"] for row in group if row["category"] == category]
                metric = {
                    "count": len(ids),
                    "total": len(group),
                    "share": len(ids) / len(group) if group else None,
                    "ad_ids": ids,
                }
                if saved[party][category] != metric:
                    raise ValueError(f"Same-ad audit mismatch: {name}/{party}/{category}")
                summaries[name][party][category] = {
                    key: value for key, value in metric.items() if key != "ad_ids"
                }
    full_ids = {row["id"] for row in full}
    return {
        "audit_version": "same-ad-strategy-audit-1",
        "verified_metric_groups": sum(
            len(group) for summary in summaries.values() for group in summary.values()
        ),
        "excluded_publishers": excluded,
        "summary": summaries,
        "messages": full,
        "source_excluded_message_ids": [row["id"] for row in reduced],
        "source_excluded_replacement_messages": [
            row for row in reduced if row["id"] not in full_ids
        ],
    }


def audit_strategy(root: Path) -> dict:
    saved = read_json(root / "outputs/analysis.json", {})
    dataset = prepare(root)
    validate_dataset(dataset)
    if saved.get("dataset") != dataset:
        raise ValueError("Same-ad audit: saved analysis differs from the canonical inputs; rebuild")
    audit = audit_ad_strategy(dataset["ads"], saved["person_portrayals"])
    expected = {
        (party, category): {
            **metric,
            "ad_ids": [
                row["id"]
                for row in audit["messages"]
                if row["alignment"] == party and row["category"] == category
            ],
        }
        for party, group in audit["summary"]["full"].items()
        for category, metric in group.items()
    }
    with (root / "outputs/figures/ad-strategy.csv").open(newline="") as stream:
        rows = list(csv.DictReader(stream))
    seen = set()
    for row in rows:
        key = row["party"], row["key"]
        metric = {
            "count": int(row["count"]),
            "total": int(row["total"]),
            "share": float(row["share"]) if row["share"] else None,
            "ad_ids": json.loads(row["ad_ids"]),
        }
        if (
            key in seen
            or expected.get(key) != metric
            or row["snapshot_id"] != dataset["snapshot_id"]
            or row["until"] != dataset["until"]
            or row["scope"] != "all"
        ):
            raise ValueError(f"Same-ad audit mismatch: chart CSV/{key}")
        seen.add(key)
    if seen != set(expected):
        raise ValueError("Same-ad audit mismatch: chart CSV category coverage")
    inputs = [
        *(
            root / "data/site" / f"{name}.json"
            for name in ("corpus", "media", "images", "google", "snap", "candidates")
        ),
        *(
            root / "data" / f"{name}.json"
            for name in (
                "codebook",
                "reviews",
                "publisher-alignments",
                "portrayal-codebook",
                "portrayal-reviews",
            )
        ),
    ]
    ledger = read_json(root / "data/portrayal-reviews.json", {})
    return audit | {
        "snapshot_id": dataset["snapshot_id"],
        "until": dataset["until"],
        "verified_chart_rows": len(rows),
        "input_sha256": {
            str(path.relative_to(root)): sha256(path.read_bytes()).hexdigest()
            for path in inputs
            if path.exists()
        },
        "annotation_provenance": {key: value for key, value in ledger.items() if key != "reviews"},
        "runtime": {
            "python": platform.python_version(),
            "packages": {
                name: version(name)
                for name in (
                    "beautifulsoup4",
                    "duckdb",
                    "langdetect",
                    "matplotlib",
                    "textblob",
                )
            },
        },
    }
