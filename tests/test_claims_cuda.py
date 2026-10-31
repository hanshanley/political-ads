import json
import subprocess
import sys
import zipfile
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from test_claims import ad, fixture_corpus, payload

from political_ads.claims import canonical, extract_batches, prepare
from political_ads.cli import write_json
from scripts.package_claims_cuda import package
from scripts.run_claims_cuda import (
    MODEL,
    RUNTIME,
    CudaGemma,
    cuda_manifest,
    pending_blocks,
    verified_export,
)


def test_cuda_manifest_keeps_sources_and_rejects_mixed_responses(tmp_path):
    fixture_corpus(tmp_path)
    source = prepare(tmp_path, tmp_path / "original")
    manifest = cuda_manifest(source, "4bit", 2048)
    assert manifest["ads"] == source["ads"]
    assert manifest["blocks"] == source["blocks"]
    assert manifest["fingerprint"] != source["fingerprint"]
    assert manifest["model"] == MODEL
    output = tmp_path / "cuda"
    write_json(output / "manifest.json", manifest)
    summary = verified_export(output, manifest)
    assert summary["blocks_by_status"] == {"not_run": 1}
    with pytest.raises(ValueError, match="hash mismatch"):
        cuda_manifest(source | {"ads": []}, "4bit", 2048)


def test_cuda_retry_resumes_without_retrying_already_failed_retry_again(tmp_path):
    fixture_corpus(tmp_path, [ad(), ad("second")])
    source = prepare(tmp_path, tmp_path / "original")
    manifest = cuda_manifest(source, "4bit", 2048)
    output = tmp_path / "cuda"
    write_json(output / "manifest.json", manifest)
    with pytest.raises(ValueError, match="Finish the initial"):
        pending_blocks(output, manifest, retry=True)
    requests = []

    def failed(prompts, budget):
        requests.extend(prompts)
        return [{"text": "bad JSON", "generation_tokens": 2} for _ in prompts]

    extractor = SimpleNamespace(batch=failed)
    extract_batches(output, manifest, manifest["blocks"], extractor)
    pending = pending_blocks(output, manifest, retry=True)
    assert len(pending) == 2
    extract_batches(output, manifest, pending[:1], extractor)
    pending = pending_blocks(output, manifest, retry=True)
    assert [block["ad_id"] for block in pending] == ["test-ad"]
    assert "PREVIOUS FAILED RESPONSE" in requests[-1]
    extractor.batch = lambda prompts, budget: [
        {"text": canonical(payload()), "generation_tokens": 100} for _ in prompts
    ]
    extract_batches(output, manifest, pending, extractor)
    assert pending_blocks(output, manifest, retry=True) == []
    assert pending_blocks(output, manifest, retry=False) == []
    assert len(list((output / "response-history").glob("*.json"))) == 2
    assert verified_export(output, manifest)["blocks_by_status"] == {
        "normalized": 1,
        "validation_failed": 1,
    }


def test_bundle_runs_independently_and_preserves_complete_source(tmp_path):
    fixture_corpus(tmp_path, [ad(text="=Jane Smith fights for us.\nJohn Doe failed us.")])
    source = prepare(tmp_path, tmp_path / "original")
    destination = tmp_path / "bundle.zip"
    metadata = package(tmp_path / "original/manifest.json", destination)
    assert metadata["ads"] == 1
    with zipfile.ZipFile(destination) as archive:
        assert json.loads(archive.read("gemma-cuda-bundle/data/ads.json")) == source["ads"]
        archive.extractall(tmp_path / "extracted")
    bundle = tmp_path / "extracted/gemma-cuda-bundle"
    result = subprocess.run(
        [sys.executable, "run_gemma.py", "--prepare-only"],
        cwd=bundle,
        capture_output=True,
        text=True,
        check=True,
    )
    assert json.loads(result.stdout)["blocks_by_status"] == {"not_run": 1}
    replay = subprocess.run(
        [sys.executable, "run_gemma.py", "--replay"],
        cwd=bundle,
        capture_output=True,
        text=True,
        check=True,
    )
    assert json.loads(replay.stdout) == json.loads(result.stdout)
    changed = subprocess.run(
        [sys.executable, "run_gemma.py", "--prepare-only", "--quantization", "8bit"],
        cwd=bundle,
        capture_output=True,
        text=True,
    )
    assert changed.returncode != 0
    assert "use a new output directory" in changed.stderr
    with pytest.raises(ValueError, match="overwrite"):
        package(tmp_path / "original/manifest.json", tmp_path / "original/manifest.json")


def test_cuda_unavailable_refuses_download_and_cpu_fallback(monkeypatch):
    download = Mock()
    monkeypatch.setitem(
        sys.modules, "torch", SimpleNamespace(cuda=SimpleNamespace(is_available=lambda: False))
    )
    monkeypatch.setitem(sys.modules, "huggingface_hub", SimpleNamespace(snapshot_download=download))
    monkeypatch.setitem(
        sys.modules,
        "transformers",
        SimpleNamespace(
            AutoModelForImageTextToText=Mock(), AutoTokenizer=Mock(), BitsAndBytesConfig=Mock()
        ),
    )
    monkeypatch.setattr("importlib.metadata.version", lambda name: RUNTIME[name])
    with pytest.raises(ValueError, match="CPU fallback is disabled"):
        CudaGemma("4bit", download=True)
    download.assert_not_called()
