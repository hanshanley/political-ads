import csv
import gzip
import io
from pathlib import Path

import pytest

from political_ads.publication import (
    build,
    csv_export,
    prepare,
    spreadsheet_cell,
    validate,
    validate_dataset,
)

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
    dataset = prepare(ROOT)
    ad = next(ad for ad in dataset["ads"] if ad.get("alignment_review"))
    ad["alignment_review"]["reviewed_source_hash"] = "changed"
    with pytest.raises(ValueError, match="Publisher alignment review mismatch"):
        validate_dataset(dataset)


def test_local_analysis_keeps_full_text_and_evidence_without_building_website(tmp_path):
    import json
    import shutil

    from political_ads.research import research

    shutil.copytree(ROOT / "data/site", tmp_path / "data/site")
    for name in ("codebook.json", "reviews.json", "publisher-alignments.json"):
        shutil.copy(ROOT / "data" / name, tmp_path / "data" / name)
    result = research(tmp_path)
    output = tmp_path / "outputs"
    assert json.loads((output / "analysis.json").read_text()) == result
    csv_text = (output / "analysis-ads.csv").read_text()
    csv.field_size_limit(max(csv.field_size_limit(), len(csv_text)))
    records = list(csv.DictReader(io.StringIO(csv_text)))
    assert {row["id"]: row["text"] for row in records} == {
        ad["id"]: spreadsheet_cell(ad["text"]) for ad in result["dataset"]["ads"]
    }
    content = (output / "analysis.html").read_text()
    assert "LOCAL ONLY" in content and "Historical coverage" in content
    assert "rel='canonical'" not in content
    assert not (tmp_path / "web").exists()
