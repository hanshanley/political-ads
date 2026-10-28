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
    import json
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
    figures = tmp_path / "web/public/figures"
    first_figures = {path.name: path.read_bytes() for path in figures.iterdir()}
    manifest = json.loads(first_figures["manifest.json"])
    assert len(manifest["charts"]) == 11 and manifest["publication_status"] == "local_only"
    assert not any(name.endswith(".svg") for name in first_figures)
    chart_data = json.loads(first_figures["chart-data.json"])
    for chart in manifest["charts"]:
        assert all(chart[extension] in first_figures for extension in ("png", "csv"))
        assert "svg" not in chart
        for row in chart_data["data"][chart["id"]]["rows"]:
            assert row["count"] == len(row["ad_ids"])
            if "total" in row:
                assert row["share"] == (row["count"] / row["total"] if row["total"] else None)
    dataset = json.loads(first["dataset.json"])
    article = json.loads((tmp_path / "outputs/article-data.json").read_text())
    assert article["snapshot_id"] == dataset["snapshot_id"]
    editions = {
        name: (tmp_path / "outputs" / name).read_bytes()
        for name in ("substack.md", "themarginoferror.html", "article-data.json")
    }
    for name in ("substack.md", "themarginoferror.html"):
        assert dataset["snapshot_id"].encode() in editions[name]
        assert b"DRAFT - NOT PUBLISHED" in editions[name]
        assert b".svg" not in editions[name]
        assert all(chart["png"].encode() in editions[name] for chart in manifest["charts"])
    assert (tmp_path / "web/public/article.html").exists()
    assert chart_data["snapshot_id"] == dataset["snapshot_id"]
    by_id = {ad["id"]: ad for ad in dataset["ads"]}
    portrayals = json.loads(first_figures["portrayal-evidence.json"])
    assert "descriptor-evidence.json" not in first_figures
    for hit in portrayals["evidence"]:
        ad = by_id[hit["ad_id"]]
        assert hit["source_hash"] == ad["source_hash"]
        assert ad["text"][hit["start"] : hit["end"]] == hit["quote"]
        assert ad["text"][hit["target_start"] : hit["target_end"]] == hit["target_quote"]
        assert hit["phrase"] in hit["quote"]
    build(tmp_path)
    assert editions == {name: (tmp_path / "outputs" / name).read_bytes() for name in editions}
    assert first == {path.name: path.read_bytes() for path in output.iterdir()}
    assert first_figures == {path.name: path.read_bytes() for path in figures.iterdir()}
    assert gzip.decompress(first["dataset.json.gz"]) == first["dataset.json"]
    for path, replacement, error in (
        (
            figures / "manifest.json",
            first_figures["manifest.json"].replace(dataset["snapshot_id"].encode(), b"stale"),
            "Figure manifest",
        ),
        (figures / manifest["charts"][0]["png"], b"truncated PNG", "Figure asset hash"),
        (figures / manifest["charts"][0]["csv"], b"metadata only", "Figure asset hash"),
        (figures / "chart-data.json", b"{}", "Chart data hash"),
        (tmp_path / "outputs/substack.md", b"Stale article", "Research draft or report"),
    ):
        original = path.read_bytes()
        path.write_bytes(replacement)
        with pytest.raises(ValueError, match=error):
            validate(tmp_path)
        path.write_bytes(original)
    (output / "ads.csv").write_bytes(
        first["ads.csv"].replace(dataset["ads"][0]["source_hash"].encode(), b"tampered", 1)
    )
    with pytest.raises(ValueError, match="Evidence downloads"):
        validate(tmp_path)
    (output / "ads.csv").write_bytes(first["ads.csv"])
    (output / "dataset.json.gz").write_bytes(gzip.compress(b"{}"))
    with pytest.raises(ValueError, match="Compressed evidence"):
        validate(tmp_path)


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
    for name in (
        "codebook.json",
        "reviews.json",
        "publisher-alignments.json",
        "portrayal-codebook.json",
        "portrayal-reviews.json",
    ):
        shutil.copy(ROOT / "data" / name, tmp_path / "data" / name)
    result = research(tmp_path)
    assert any(ad["portrayal_review"]["descriptions"] for ad in result["dataset"]["ads"])
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
