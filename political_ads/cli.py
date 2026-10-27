from __future__ import annotations

import argparse
import json
import os
import sys
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from pathlib import Path

import duckdb

from political_ads.alignments import apply_alignment_reviews
from political_ads.http import Client
from political_ads.registry import enrich, fec_table
from political_ads.schema import END, START, Ad, in_window
from political_ads.sources import SOURCES, collect_wordpress


def read_json(path: Path, fallback):
    return json.loads(path.read_text()) if path.exists() else fallback


def write_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n")
    os.replace(temporary, path)


def load_corpus(root: Path) -> dict:
    corpus = read_json(root / "data/site/corpus.json", None)
    if corpus is None:
        raise ValueError("Collect ad text first")
    media = read_json(root / "data/site/media.json", {"ads": [], "sources": []})
    images = read_json(root / "data/site/images.json", {"ads": [], "sources": []})
    google = read_json(root / "data/site/google.json", {"ads": [], "sources": []})
    snap = read_json(root / "data/site/snap.json", {"ads": [], "sources": []})
    result = corpus | {
        "ads": corpus["ads"]
        + [
            ad
            for ad in media["ads"] + images["ads"] + google["ads"] + snap["ads"]
            if in_window(
                ad.get("delivery_start") or ad["published"],
                ad.get("delivery_end") if ad.get("delivery_start") else ad["published"],
                corpus["until"],
            )
        ],
        "sources": corpus["sources"]
        + media["sources"]
        + images["sources"]
        + google["sources"]
        + snap["sources"],
    }
    result["ads"] = apply_alignment_reviews(
        result["ads"], read_json(root / "data/publisher-alignments.json", {"reviews": []})
    )
    return result


def collect(root: Path, until: str, source_ids: list[str], offline: bool = False) -> dict:
    if not START <= until <= min(date.today().isoformat(), END):
        raise ValueError("Cutoff must be between 2026-01-01 and today/the final collection cutoff")
    client = Client(root / "data/raw/http", offline)
    public = root / "data/site"
    old = read_json(public / "corpus.json", {"ads": [], "sources": []})
    selected = [s for s in SOURCES if not source_ids or s.id in source_ids]
    candidates = read_json(root / "data/processed/registry.json", {}).get("candidates", [])
    by_id = {candidate["candidate_id"]: candidate for candidate in candidates}
    for alias in read_json(root / "data/snap-candidate-aliases.json", []):
        if alias["candidate_id"] in by_id:
            candidates.append(
                by_id[alias["candidate_id"]] | {"name": alias["name"], "reviewed_alias": alias}
            )
    old_ads = {s.id: [a for a in old["ads"] if a["source"] == s.id] for s in SOURCES}
    statuses = {s["source"]: s for s in old["sources"]}
    with ThreadPoolExecutor(max_workers=3) as executor:
        results = executor.map(
            lambda source: (
                source,
                *collect_wordpress(client, source, until, None, candidates),
            ),
            selected,
        )
        for source, ads, status in results:
            if status["state"] in {"ok", "partial"}:
                # Keep first observation stable when source contents have not changed.
                previous = {a["id"]: a for a in old_ads[source.id]}
                for ad in ads:
                    prior = previous.get(ad["id"])
                    if prior and prior["source_hash"] == ad["source_hash"]:
                        ad["observed"] = prior["observed"]
                if status["state"] == "partial":
                    previous.update({ad["id"]: ad for ad in ads})
                    ads = list(previous.values())
                    status["retained_ads"] = len(ads)
                old_ads[source.id] = ads
                status["languages"] = dict(Counter(ad["language"] for ad in ads))
                status["last_success"] = until
            else:
                status["retained_ads"] = len(old_ads[source.id])
                status["last_success"] = statuses.get(source.id, {}).get("last_success")
            statuses[source.id] = status
            print(json.dumps(status), flush=True)
    ads = sorted(
        (
            a
            for partition in old_ads.values()
            for a in partition
            if in_window(a["published"], a["published"], until)
        ),
        key=lambda a: (a["published"], a["id"]),
    )
    for ad in ads:
        Ad(**{key: value for key, value in ad.items() if key in Ad.__dataclass_fields__}).validate()
    snapshot = {
        "schema_version": "1",
        "until": until,
        "ads": ads,
        "sources": sorted(statuses.values(), key=lambda s: s["source"]),
    }
    if not ads:
        raise ValueError("No real ad text acquired; refusing to publish an empty corpus")
    write_json(public / "corpus.json", snapshot)
    return snapshot


def registry(root: Path, offline: bool = False) -> dict:
    client = Client(root / "data/raw/http", offline)
    candidates = [
        row
        for row in fec_table(client, "cn")
        if row["office"] in {"H", "S"} and row["election_year"] == "2026"
    ]
    committees = fec_table(client, "cm")
    result = {"candidates": candidates, "committees": committees}
    write_json(root / "data/processed/registry.json", result)
    write_json(
        root / "data/site/candidates.json",
        {
            "source": "FEC 2026 candidate master",
            "url": "https://www.fec.gov/data/browse-data/",
            "candidates": [
                {
                    key: row[key]
                    for key in (
                        "candidate_id",
                        "name",
                        "party",
                        "election_year",
                        "state",
                        "office",
                        "district",
                        "principal_committee",
                    )
                }
                for row in candidates
            ],
        },
    )
    print(f"Registry: {len(candidates)} federal candidates, {len(committees)} committees")
    return result


def parquet(root: Path) -> None:
    corpus = load_corpus(root)
    registry_data = read_json(root / "data/site/candidates.json", {"candidates": []})
    records = [enrich(ad, registry_data["candidates"]) for ad in corpus["ads"]]
    output = root / "data/processed"
    output.mkdir(parents=True, exist_ok=True)
    write_json(output / "ads.json", records)
    connection = duckdb.connect()
    connection.read_json(str(output / "ads.json")).write_parquet(str(output / "ads.parquet"))
    connection.close()
    print(f"Persisted {len(records)} ads to {output / 'ads.parquet'}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Reproducible political-ad evidence pipeline")
    parser.add_argument("--root", type=Path, default=Path.cwd())
    subcommands = parser.add_subparsers(dest="command", required=True)
    for command in (
        "collect",
        "registry",
        "parquet",
        "build",
        "validate",
        "update",
        "media-collect",
        "media-discover",
        "image-collect",
        "google-discover",
        "google-collect",
        "snap-discover",
        "snap-collect",
        "analyze",
    ):
        command_parser = subcommands.add_parser(command)
        command_parser.add_argument("--offline", action="store_true")
        if command in {
            "collect",
            "update",
            "media-collect",
            "media-discover",
            "image-collect",
            "google-discover",
            "google-collect",
            "snap-discover",
            "snap-collect",
        }:
            command_parser.add_argument("--until", default=min(date.today().isoformat(), END))
        if command in {"collect", "update", "media-collect", "media-discover"}:
            command_parser.add_argument(
                "--source",
                action="append",
                choices=[s.id for s in SOURCES]
                + (["cfg-action", "protect-freedom"] if command == "media-discover" else []),
            )
        if command == "media-collect":
            command_parser.add_argument("--limit", type=int, default=24)
            command_parser.add_argument("--retry-failed", action="store_true")
        if command in {"google-collect", "snap-collect"}:
            command_parser.add_argument("--limit", type=int, default=0)
    args = parser.parse_args()
    root = args.root.resolve()
    try:
        if args.command == "snap-discover":
            from political_ads.snap import discover_snap

            discover_snap(root, args.until)
        if args.command == "snap-collect":
            from political_ads.snap import collect_snap

            collect_snap(root, args.until, limit=args.limit, offline=args.offline)
        if args.command == "google-discover":
            from political_ads.google import discover_google

            discover_google(root, args.until)
        if args.command == "google-collect":
            from political_ads.google import collect_google

            collect_google(root, args.until, args.limit, args.offline)
        if args.command == "image-collect":
            from political_ads.images import collect_images

            collect_images(root, args.until, args.offline)
        if args.command == "media-discover":
            from political_ads.media import inventory_media

            inventory_media(root, args.until, args.source or [], args.offline)
        if args.command in {"collect", "update"}:
            collect(root, args.until, args.source or [], args.offline)
        if args.command == "media-collect":
            from political_ads.media import collect_media

            collect_media(
                root, args.until, args.source or ["hmp", "slf"], args.limit, args.retry_failed
            )
        if args.command in {"registry", "update"}:
            registry(root, args.offline)
        if args.command in {"parquet", "update"}:
            parquet(root)
        if args.command in {"build", "update"}:
            from political_ads.publication import build

            build(root)
        if args.command == "validate":
            from political_ads.publication import validate

            validate(root)
        if args.command == "analyze":
            from political_ads.research import research

            research(root)
            print("Local analysis saved to outputs/analysis.html and complete JSON/CSV")
    except (OSError, ValueError, KeyError, duckdb.Error) as error:
        print(f"{type(error).__name__}: {error}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
