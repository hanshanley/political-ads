"""Run the frozen claim corpus on one NVIDIA CUDA GPU; never fall back to CPU."""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if not (ROOT / "political_ads").is_dir():
    ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from political_ads.claim_checkpoints import _verify_snapshot  # noqa: E402
from political_ads.claims import (  # noqa: E402
    FAST_VERSION,
    MAX_TOKENS,
    PROMPT,
    REVIEW_PROMPT,
    canonical,
    checked_record,
    disposition,
    export_results,
    extract_batches,
    output_lock,
    verify_manifest,
)
from political_ads.cli import read_json, write_json  # noqa: E402
from political_ads.schema import digest  # noqa: E402

MODEL = "google/gemma-3-27b-it"
REVISION = "005ad3404e59d6023443cb575daa05336842228a"
RUNTIME = {
    "torch": "2.10.0",
    "torchvision": "0.25.0",
    "transformers": "5.1.0",
    "accelerate": "1.12.0",
    "bitsandbytes": "0.49.1",
}


def cuda_manifest(source: dict, quantization: str, initial_tokens: int) -> dict:
    verify_manifest(source)
    if source["prompt"] != PROMPT or source["review_prompt"] != REVIEW_PROMPT:
        raise ValueError("Frozen source prompts differ from the bundled implementation")
    config = {key: value for key, value in source.items() if key != "fingerprint"}
    config |= {
        "version": FAST_VERSION,
        "model": MODEL,
        "model_revision": REVISION,
        "input_fingerprint": source["fingerprint"],
        "runner_sha256": digest(Path(__file__).read_text()),
        "claims_code_sha256": digest((ROOT / "political_ads/claims.py").read_text()),
        "runtime_versions": RUNTIME,
        "generation": {
            "backend": "transformers.cuda.greedy",
            "device": "cuda:0",
            "quantization": quantization,
            "compute_dtype": "bfloat16_if_supported_else_float16",
            "temperature": 0.0,
            "seed": 0,
            "max_tokens": MAX_TOKENS,
            "max_attempts": 2,
            "batch_size": 1,
            "initial_tokens": initial_tokens,
        },
    }
    return config | {"fingerprint": digest(canonical(config))}


class CudaGemma:
    def __init__(self, quantization: str, *, download: bool = False):
        import torch
        from huggingface_hub import snapshot_download
        from transformers import AutoModelForImageTextToText, AutoTokenizer, BitsAndBytesConfig

        installed = {name: importlib.metadata.version(name).split("+")[0] for name in RUNTIME}
        if installed != RUNTIME:
            raise ValueError(
                f"Use the bundled pinned requirements; installed versions: {installed}"
            )
        if not torch.cuda.is_available():
            raise ValueError(
                "CUDA GPU unavailable. Install CUDA PyTorch; CPU fallback is disabled."
            )
        model_path = snapshot_download(
            MODEL,
            revision=REVISION,
            local_files_only=not download,
            allow_patterns=["*.json", "*.safetensors", "*.model", "*.jinja", "*.txt"],
        )
        os.environ["HF_HUB_OFFLINE"] = "1"
        dtype = torch.bfloat16 if torch.cuda.is_bf16_supported() else torch.float16
        options = {}
        if quantization != "none":
            options["quantization_config"] = BitsAndBytesConfig(
                load_in_4bit=quantization == "4bit",
                load_in_8bit=quantization == "8bit",
                bnb_4bit_quant_type="nf4",
                bnb_4bit_use_double_quant=True,
                bnb_4bit_compute_dtype=dtype,
            )
        self.torch = torch
        self.tokenizer = AutoTokenizer.from_pretrained(model_path, local_files_only=True)
        self.model = AutoModelForImageTextToText.from_pretrained(
            model_path,
            local_files_only=True,
            device_map={"": "cuda:0"},
            dtype=dtype,
            attn_implementation="sdpa",
            **options,
        ).eval()
        self.metadata = {
            "model": MODEL,
            "revision": REVISION,
            "runtime_versions": installed,
            "gpu": torch.cuda.get_device_name(0),
            "gpu_memory_bytes": torch.cuda.get_device_properties(0).total_memory,
            "cuda_version": torch.version.cuda,
            "compute_dtype": str(dtype),
            "quantization": quantization,
        }
        print(json.dumps(self.metadata, indent=2), flush=True)

    def batch(self, prompts: list[str], max_tokens: int) -> list[dict]:
        results = []
        for prompt in prompts:
            inputs = self.tokenizer.apply_chat_template(
                [{"role": "user", "content": prompt}],
                add_generation_prompt=True,
                tokenize=True,
                return_dict=True,
                return_tensors="pt",
            ).to("cuda:0")
            prompt_tokens = inputs["input_ids"].shape[-1]
            self.torch.manual_seed(0)
            self.torch.cuda.reset_peak_memory_stats()
            started = time.perf_counter()
            with self.torch.inference_mode():
                generated = self.model.generate(
                    **inputs, max_new_tokens=max_tokens, do_sample=False, use_cache=True
                )[0, prompt_tokens:].tolist()
            self.torch.cuda.synchronize()
            eos = self.model.generation_config.eos_token_id
            stops = set(eos if isinstance(eos, list) else [eos])
            stopped = bool(generated and generated[-1] in stops)
            results.append(
                {
                    "text": self.tokenizer.decode(generated, skip_special_tokens=True),
                    "seconds": time.perf_counter() - started,
                    "prompt_tokens": prompt_tokens,
                    "generation_tokens": len(generated),
                    "finish_reason": "stop" if stopped else "length",
                    "peak_memory": self.torch.cuda.max_memory_allocated() / 1e9,
                    "batch_size": 1,
                }
            )
        return results


def pending_blocks(output: Path, manifest: dict, *, retry: bool) -> list[dict]:
    states = {
        block["id"]: disposition(checked_record(output, manifest, block), block)[0]
        for block in manifest["blocks"]
    }
    if not retry:
        return [block for block in manifest["blocks"] if states[block["id"]] == "not_run"]
    if "not_run" in states.values():
        raise ValueError("Finish the initial corpus pass before --retry-failed")
    path = output / "retry-pass.json"
    baseline = read_json(path, None)
    if baseline is None:
        baseline = {
            "fingerprint": manifest["fingerprint"],
            "records": {
                block["id"]: digest((output / "responses" / f"{block['id']}.json").read_text())
                for block in manifest["blocks"]
                if states[block["id"]] in {"validation_failed", "unresolved"}
            },
        }
        write_json(path, baseline)
    if baseline["fingerprint"] != manifest["fingerprint"]:
        raise ValueError("Retry baseline belongs to another run")
    return [
        block
        for block in manifest["blocks"]
        if block["id"] in baseline["records"]
        and digest((output / "responses" / f"{block['id']}.json").read_text())
        == baseline["records"][block["id"]]
    ]


def verified_export(output: Path, manifest: dict) -> dict:
    summary = export_results(output, manifest)
    paths = [output / "manifest.json"]
    for directory in ("responses", "response-history"):
        paths.extend((output / directory).glob("*.json"))
    _verify_snapshot(
        output,
        manifest,
        {
            path.relative_to(output).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in paths
        },
    )
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=ROOT / "data/manifest.json")
    parser.add_argument("--output", type=Path, default=ROOT / "results")
    parser.add_argument("--quantization", choices=("4bit", "8bit", "none"), default="4bit")
    parser.add_argument("--initial-tokens", type=int, default=2048)
    parser.add_argument("--download-model", action="store_true")
    parser.add_argument("--download-only", action="store_true")
    parser.add_argument("--prepare-only", action="store_true")
    parser.add_argument("--replay", action="store_true")
    parser.add_argument("--retry-failed", action="store_true")
    parser.add_argument("--max-new-blocks", type=int, default=0)
    args = parser.parse_args()
    if not 1 <= args.initial_tokens <= MAX_TOKENS or args.max_new_blocks < 0:
        parser.error("Initial tokens must be 1..8192; max-new-blocks must be nonnegative")
    if sum((args.prepare_only, args.replay, args.download_only)) > 1 or (
        (args.prepare_only or args.replay) and (args.retry_failed or args.download_model)
    ):
        parser.error("Preparation/replay/download-only modes cannot be combined")
    if args.download_only:
        from huggingface_hub import snapshot_download

        print(
            snapshot_download(
                MODEL,
                revision=REVISION,
                allow_patterns=["*.json", "*.safetensors", "*.model", "*.jinja", "*.txt"],
            )
        )
        return
    output = args.output.resolve()
    source_path = args.input.resolve()
    if output == ROOT or output in ROOT.parents or source_path.is_relative_to(output):
        parser.error("Output must be separate from the bundle root and frozen source")
    with output_lock(output):
        source = read_json(source_path, None)
        expected = cuda_manifest(source, args.quantization, args.initial_tokens)
        path = output / "manifest.json"
        if path.exists():
            manifest = read_json(path, None)
            verify_manifest(manifest)
            if manifest != expected:
                raise ValueError("Frozen CUDA settings/code differ; use a new output directory")
        else:
            if any(item.name != ".claims.lock" for item in output.iterdir()):
                raise ValueError("New output directory must be empty")
            write_json(path, expected)
            manifest = expected
        if args.prepare_only or args.replay:
            summary = verified_export(output, manifest)
        else:
            pending = pending_blocks(output, manifest, retry=args.retry_failed)
            if args.max_new_blocks:
                pending = pending[: args.max_new_blocks]
            if pending:
                extractor = CudaGemma(args.quantization, download=args.download_model)
                extract_batches(output, manifest, pending, extractor)
            summary = verified_export(output, manifest)
        print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
