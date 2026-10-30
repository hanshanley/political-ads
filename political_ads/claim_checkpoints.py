from __future__ import annotations

import hashlib
import json
import shutil
import tempfile
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
        verify_manifest(json.loads(manifest))
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
        if previous.get("source_sha256") == fingerprint and all(
            (output / name).is_file()
            and hashlib.sha256((output / name).read_bytes()).hexdigest()
            == previous.get("files", {}).get(name)
            for name in FILES
        ):
            return read_json(output / "summary.json", {})
        summary = extract_claims(root, snapshot, replay=True)
        for name in FILES:
            temporary = output / f"{name}.tmp"
            shutil.copy2(snapshot / name, temporary)
            temporary.replace(output / name)
        write_json(
            output / "checkpoint.json",
            {
                "source_sha256": fingerprint,
                "run_fingerprint": summary["fingerprint"],
                "skipped_incomplete_records": skipped,
                "files": {
                    name: hashlib.sha256((output / name).read_bytes()).hexdigest() for name in FILES
                },
            },
        )
        return summary
