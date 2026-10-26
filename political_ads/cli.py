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
    return corpus | {
        "ads": corpus["ads"]
        + [
            ad
            for ad in media["ads"]
            if in_window(ad["published"], ad["published"], corpus["until"])
        ],
        "sources": corpus["sources"] + media["sources"],
    }


def collect(root: Path, until: str, source_ids: list[str], offline: bool = False) -> dict:
    if not START <= until <= min(date.today().isoformat(), END):
        raise ValueError("Cutoff must be between 2026-01-01 and today/Election Day")
    client = Client(root / "data/raw/http", offline)
    public = root / "data/site"
    old = read_json(public / "corpus.json", {"ads": [], "sources": []})
    selected = [s for s in SOURCES if not source_ids or s.id in source_ids]
    old_ads = {s.id: [a for a in old["ads"] if a["source"] == s.id] for s in SOURCES}
    statuses = {s["source"]: s for s in old["sources"]}
    with ThreadPoolExecutor(max_workers=3) as executor:
        results = executor.map(
            lambda source: (source, *collect_wordpress(client, source, until)),
            selected,
        )
        for source, ads, status in results:
            if status["state"] == "ok":
                # Keep first observation stable when source contents have not changed.
                previous = {a["id"]: a for a in old_ads[source.id]}
                for ad in ads:
                    prior = previous.get(ad["id"])
                    if prior and prior["source_hash"] == ad["source_hash"]:
                        ad["observed"] = prior["observed"]
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
    ):
        command_parser = subcommands.add_parser(command)
        command_parser.add_argument("--offline", action="store_true")
        if command in {"collect", "update", "media-collect"}:
            command_parser.add_argument("--until", default=min(date.today().isoformat(), END))
            command_parser.add_argument(
                "--source", action="append", choices=[s.id for s in SOURCES]
            )
        if command == "media-collect":
            command_parser.add_argument("--limit", type=int, default=24)
            command_parser.add_argument("--retry-failed", action="store_true")
    args = parser.parse_args()
    root = args.root.resolve()
    try:
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
    except (OSError, ValueError, KeyError, duckdb.Error) as error:
        print(f"{type(error).__name__}: {error}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
