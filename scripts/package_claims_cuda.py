"""Create a self-contained CUDA runner ZIP from the complete original frozen corpus."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from political_ads.claims import verify_manifest, write_csv  # noqa: E402
from political_ads.cli import write_json  # noqa: E402


def package(source: Path, destination: Path) -> dict:
    manifest = json.loads(source.read_text())
    verify_manifest(manifest)
    files = {
        "run_gemma.py": ROOT / "scripts/run_claims_cuda.py",
        "requirements.txt": ROOT / "requirements-claims-cuda.txt",
        "README.md": ROOT / "docs/CLAIMS_CUDA_BUNDLE_README.md",
        "data/manifest.json": source,
    }
    # Only modules needed by the frozen extraction and evidence-verification pipeline.
    for name in (
        "__init__",
        "claims",
        "claim_checkpoints",
        "local_gemma",
        "analysis",
        "cli",
        "alignments",
        "http",
        "registry",
        "schema",
        "sources",
    ):
        files[f"political_ads/{name}.py"] = ROOT / f"political_ads/{name}.py"
    if destination.resolve() in {path.resolve() for path in files.values()}:
        raise ValueError("Bundle destination must not overwrite its inputs")
    with tempfile.TemporaryDirectory(prefix="gemma-cuda-bundle-") as directory:
        temporary = Path(directory)
        write_json(temporary / "ads.json", manifest["ads"])
        write_csv(
            temporary / "ads.csv",
            manifest["ads"],
            [
                "id",
                "text",
                "text_hash",
                "title",
                "sponsor",
                "alignment",
                "source_url",
                "segments",
                "identities",
            ],
        )
        files |= {"data/ads.json": temporary / "ads.json", "data/ads.csv": temporary / "ads.csv"}
        metadata = {
            "source_fingerprint": manifest["fingerprint"],
            "ads": len(manifest["ads"]),
            "chunks": len(manifest["blocks"]),
            "sha256": {
                name: hashlib.sha256(path.read_bytes()).hexdigest() for name, path in files.items()
            },
        }
        write_json(temporary / "bundle.json", metadata)
        files["bundle.json"] = temporary / "bundle.json"
        destination.parent.mkdir(parents=True, exist_ok=True)
        staging = destination.with_suffix(destination.suffix + ".tmp")
        try:
            with zipfile.ZipFile(staging, "w", zipfile.ZIP_DEFLATED) as archive:
                for name, path in sorted(files.items()):
                    archive.write(path, f"gemma-cuda-bundle/{name}")
            with zipfile.ZipFile(staging) as archive:
                if archive.testzip() is not None:
                    raise ValueError("Bundle CRC verification failed")
                if len(archive.namelist()) != len(files) or set(archive.namelist()) != {
                    f"gemma-cuda-bundle/{name}" for name in files
                }:
                    raise ValueError("Bundle membership mismatch")
                for name, sha256 in metadata["sha256"].items():
                    if (
                        hashlib.sha256(archive.read(f"gemma-cuda-bundle/{name}")).hexdigest()
                        != sha256
                    ):
                        raise ValueError(f"Bundle hash mismatch: {name}")
                saved = json.loads(archive.read("gemma-cuda-bundle/data/manifest.json"))
                if (
                    saved != manifest
                    or json.loads(archive.read("gemma-cuda-bundle/data/ads.json"))
                    != manifest["ads"]
                ):
                    raise ValueError("Bundle lost complete original source fields")
            staging.replace(destination)
        finally:
            staging.unlink(missing_ok=True)
    return metadata | {
        "path": str(destination),
        "bytes": destination.stat().st_size,
        "zip_sha256": hashlib.sha256(destination.read_bytes()).hexdigest(),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=ROOT / "data/local-claims/full/manifest.json")
    parser.add_argument("--output", type=Path, default=ROOT / "outputs/gemma-cuda-bundle.zip")
    args = parser.parse_args()
    print(json.dumps(package(args.input, args.output), indent=2))


if __name__ == "__main__":
    main()
