from __future__ import annotations

import argparse
import json
import os
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from pathlib import Path

import duckdb

from political_ads.http import Client
from political_ads.registry import enrich, fec_table
from political_ads.schema import END, START, Ad, eligible
from political_ads.sources import SOURCES, collect_wordpress


def read_json(path: Path, fallback):
    return json.loads(path.read_text()) if path.exists() else fallback


def write_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n")
    os.replace(temporary, path)


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
                status["last_success"] = until
            else:
                status["retained_ads"] = len(old_ads[source.id])
                status["last_success"] = statuses.get(source.id, {}).get("last_success")
            statuses[source.id] = status
            print(json.dumps(status), flush=True)
    ads = sorted(
        (a for partition in old_ads.values() for a in partition if eligible(a, until)),
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
    print(f"Registry: {len(candidates)} federal candidates, {len(committees)} committees")
    return result


def parquet(root: Path) -> None:
    corpus = read_json(root / "data/site/corpus.json", None)
    if not corpus:
        raise ValueError("Collect ad text first")
    registry_data = read_json(root / "data/processed/registry.json", {"candidates": []})
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
    for command in ("collect", "registry", "parquet", "build", "validate", "update"):
        command_parser = subcommands.add_parser(command)
        command_parser.add_argument("--offline", action="store_true")
        if command in {"collect", "update"}:
            command_parser.add_argument("--until", default=min(date.today().isoformat(), END))
            command_parser.add_argument(
                "--source", action="append", choices=[s.id for s in SOURCES]
            )
    args = parser.parse_args()
    root = args.root.resolve()
    try:
        if args.command in {"collect", "update"}:
            collect(root, args.until, args.source or [], args.offline)
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
