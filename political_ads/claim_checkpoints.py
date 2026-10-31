from __future__ import annotations

import csv
import hashlib
import json
import shutil
import tempfile
import zipfile
from pathlib import Path

from political_ads.claims import canonical, extract_claims, output_lock, verify_manifest
from political_ads.cli import read_json, write_json

FILES = (
    "summary.json",
    "claims.json",
    "claims.csv",
    "targets.csv",
    "block-status.json",
    "complete-evidence.zip",
)


def _verify_snapshot(snapshot: Path, manifest: dict, input_hashes: dict[str, str]) -> None:
    ads = read_json(snapshot / "ads.json", None)
    if (
        not isinstance(ads, list)
        or len(ads) != len(manifest["ads"])
        or any(
            not isinstance(exported, dict)
            or any(key not in exported or exported[key] != value for key, value in original.items())
            for original, exported in zip(manifest["ads"], ads, strict=True)
        )
    ):
        raise ValueError("Checkpoint JSON must preserve every complete frozen ad")

    def spreadsheet_safe(value: str) -> str:
        return "'" + value if value.lstrip().startswith(("=", "+", "-", "@")) else value

    limit = csv.field_size_limit()
    try:
        csv.field_size_limit(max(limit, 2**31 - 1))
        with (snapshot / "ads.csv").open(newline="") as stream:
            rows = list(csv.DictReader(stream))
    finally:
        csv.field_size_limit(limit)
    expected = {
        spreadsheet_safe(ad["id"]): (
            spreadsheet_safe(ad["text"]),
            hashlib.sha256(ad["text"].encode()).hexdigest(),
        )
        for ad in manifest["ads"]
    }
    if (
        len(rows) != len(expected)
        or {row.get("id"): (row.get("text"), row.get("text_hash")) for row in rows} != expected
    ):
        raise ValueError("Checkpoint CSV must preserve every complete frozen ad and text hash")

    hashes = input_hashes | {
        name: hashlib.sha256((snapshot / name).read_bytes()).hexdigest()
        for name in (*FILES, "ads.json", "ads.csv")
        if name != "complete-evidence.zip"
    }
    with zipfile.ZipFile(snapshot / "complete-evidence.zip") as archive:
        names = archive.namelist()
        if len(names) != len(hashes) or set(names) != set(hashes):
            raise ValueError("Checkpoint archive must contain all inputs, outputs and raw history")
        if archive.testzip() is not None:
            raise ValueError("Checkpoint archive failed its CRC check")
        for name, expected_hash in hashes.items():
            if hashlib.sha256(archive.read(name)).hexdigest() != expected_hash:
                raise ValueError(f"Checkpoint archive changed evidence bytes: {name}")


def publish_claim_checkpoint(
    root: Path, source: Path | None = None, output: Path | None = None
) -> dict:
    root = root.resolve()
    source = (source or root / "data/local-claims/full").resolve()
    output = (output or root / "outputs/local-claims").resolve()
    if (
        output == root
        or output in root.parents
        or output == source
        or source in output.parents
        or output in source.parents
    ):
        raise ValueError("Checkpoint output must be separate from the repository and active run")
    with output_lock(output), tempfile.TemporaryDirectory(prefix="claim-checkpoint-") as directory:
        snapshot = Path(directory) / "run"
        snapshot.mkdir()
        manifest = (source / "manifest.json").read_bytes()
        frozen = json.loads(manifest)
        verify_manifest(frozen)
        (snapshot / "manifest.json").write_bytes(manifest)
        shutil.copystat(source / "manifest.json", snapshot / "manifest.json")
        hashes = {"manifest.json": hashlib.sha256(manifest).hexdigest()}
        skipped = []
        for folder in ("responses", "response-history"):
            for path in sorted((source / folder).glob("*.json")):
                data = path.read_bytes()
                name = f"{folder}/{path.name}"
                try:
                    json.loads(data)
                except (ValueError, UnicodeDecodeError):
                    # The inference worker may still be writing this block's record.
                    skipped.append(name)
                    continue
                destination = snapshot / name
                destination.parent.mkdir(exist_ok=True)
                destination.write_bytes(data)
                shutil.copystat(path, destination)
                hashes[name] = hashlib.sha256(data).hexdigest()
        fingerprint = hashlib.sha256(canonical([hashes, skipped]).encode()).hexdigest()
        previous = read_json(output / "checkpoint.json", {})
        if (
            previous.get("evidence_verified") is True
            and previous.get("source_sha256") == fingerprint
            and all(
                (output / name).is_file()
                and hashlib.sha256((output / name).read_bytes()).hexdigest()
                == previous.get("files", {}).get(name)
                for name in FILES
            )
        ):
            return read_json(output / "summary.json", {})
        summary = extract_claims(root, snapshot, replay=True)
        _verify_snapshot(snapshot, frozen, hashes)
        for name in FILES:
            temporary = output / f"{name}.tmp"
            shutil.copy2(snapshot / name, temporary)
            temporary.replace(output / name)
        write_json(
            output / "checkpoint.json",
            {
                "source_sha256": fingerprint,
                "run_fingerprint": summary["fingerprint"],
                "evidence_verified": True,
                "skipped_incomplete_records": skipped,
                "files": {
                    name: hashlib.sha256((output / name).read_bytes()).hexdigest() for name in FILES
                },
            },
        )
        return summary
