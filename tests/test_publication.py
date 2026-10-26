import csv
import gzip
import io
from pathlib import Path

import pytest

from political_ads.publication import build, csv_export, prepare, validate, validate_dataset

ROOT = Path(__file__).resolve().parents[1]


def test_csv_preserves_full_text_evidence_and_protects_formulas():
    text = '=not a formula\n"Quoted," complete text.'
    exported = csv_export(
        [
            {
                "id": "ad",
                "text": text,
                "issues": [{"label": "test", "start": 0, "end": 2}],
                "segments": [{"text": text}],
            },
            {
                "id": "apostrophe",
                "text": "'an original apostrophe",
                "quality_flags": ["captions_not_independently_verified"],
                "release_title": "Original release",
            },
        ]
    )
    rows = list(csv.DictReader(io.StringIO(exported)))
    assert rows[0]["text"] == "'" + text
    assert rows[0]["issues"] == '[{"label": "test", "start": 0, "end": 2}]'
    assert rows[1]["text"] == "'an original apostrophe"
    assert rows[1]["quality_flags"] == '["captions_not_independently_verified"]'
    assert rows[1]["release_title"] == "Original release"


def test_real_snapshot_rebuild_is_deterministic_and_downloads_are_complete(tmp_path):
    import shutil

    shutil.copytree(
        ROOT / "data",
        tmp_path / "data",
        ignore=shutil.ignore_patterns(
            "raw",
            "processed",
            "media",
            "models",
        ),
    )
    build(tmp_path)
    validate(tmp_path)
    output = tmp_path / "web/public/data"
    first = {path.name: path.read_bytes() for path in output.iterdir()}
    build(tmp_path)
    assert first == {path.name: path.read_bytes() for path in output.iterdir()}
    assert gzip.decompress(first["dataset.json.gz"]) == first["dataset.json"]


def test_real_metrics_or_evidence_tampering_fails():
    dataset = prepare(ROOT)
    dataset["issues"][0]["D"]["count"] += 1
    with pytest.raises(ValueError, match="metrics"):
        validate_dataset(dataset)
    dataset = prepare(ROOT)
    ad = next(ad for ad in dataset["ads"] if ad["issues"])
    ad["issues"][0]["start"] += 1
    with pytest.raises(ValueError, match="offsets"):
        validate_dataset(dataset)
    dataset = prepare(ROOT)
    dataset["methodology"].append("Changed publication context")
    with pytest.raises(ValueError, match="snapshot"):
        validate_dataset(dataset)
