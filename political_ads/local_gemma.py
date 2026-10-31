from __future__ import annotations

import importlib.metadata
import os
import platform
import time
from pathlib import Path

from political_ads.schema import digest

MODEL = "mlx-community/gemma-3-27b-it-8bit"
REVISION = "524cdc4f56a58ef94949ba65dc63a29c48362b1a"
# This revision's index names stale 12-part files; MLX loads the actual six shards.
WEIGHT_FILES = tuple(f"model-{i:05d}-of-00006.safetensors" for i in range(1, 7))
RUNTIME_VERSIONS = {
    "mlx": "0.32.4",
    "mlx-vlm": "0.3.12",
    "mlx-lm": "0.30.7",
    "transformers": "5.1.0",
}


class LocalGemma:
    def __init__(self, *, download: bool = False):
        try:
            from huggingface_hub import snapshot_download
            from mlx_vlm import generate, load
            from mlx_vlm.prompt_utils import apply_chat_template
            from mlx_vlm.utils import load_config
        except ImportError as error:
            raise ValueError(
                "Local Gemma requires the isolated MLX environment. Run "
                "`uv run --with-editable . scripts/extract_claims.py`; "
                "see docs/LOCAL_CLAIMS.md."
            ) from error
        runtime = {name: importlib.metadata.version(name) for name in RUNTIME_VERSIONS}
        if runtime != RUNTIME_VERSIONS:
            raise ValueError(
                "Local Gemma runtime differs from the pinned stack. "
                "Use scripts/extract_claims.py with uv; see docs/LOCAL_CLAIMS.md."
            )
        model_path = snapshot_download(
            MODEL,
            revision=REVISION,
            local_files_only=not download,
            allow_patterns=["*.json", "*.safetensors", "*.model", "*.jinja", "*.txt"],
        )
        if any(not (Path(model_path) / name).is_file() for name in WEIGHT_FILES):
            raise ValueError(
                "Pinned Gemma weights are incomplete in the local cache. "
                "Use --download-model to fetch them before local inference."
            )
        os.environ["HF_HUB_OFFLINE"] = "1"
        started = time.perf_counter()
        self.model, self.processor = load(model_path)
        self.config = load_config(model_path)
        self.generate = generate
        self.template = apply_chat_template
        self.metadata = {
            "model": MODEL,
            "revision": REVISION,
            "runtime_versions": runtime | {"mlx-metal": importlib.metadata.version("mlx-metal")},
            "system": platform.system(),
            "architecture": platform.machine(),
            "macos_version": platform.mac_ver()[0],
            "model_config_sha256": digest((Path(model_path) / "config.json").read_text()),
            "model_load_seconds": time.perf_counter() - started,
        }

    def __call__(self, prompt: str, max_tokens: int) -> dict:
        import mlx.core as mx

        mx.random.seed(0)
        formatted = self.template(self.processor, self.config, prompt, num_images=0)
        started = time.perf_counter()
        result = self.generate(
            self.model,
            self.processor,
            formatted,
            max_tokens=max_tokens,
            temperature=0.0,
            verbose=False,
        )
        return {
            "text": result.text,
            "seconds": time.perf_counter() - started,
            **{
                key: getattr(result, key)
                for key in ("prompt_tokens", "generation_tokens", "peak_memory")
                if hasattr(result, key)
            },
        }

    def batch(self, prompts: list[str], max_tokens: int) -> list[dict]:
        import mlx.core as mx
        from mlx_vlm.generate import BatchGenerator, generation_stream, wired_limit

        if not prompts:
            return []
        mx.random.seed(0)
        tokenizer = self.processor.tokenizer
        encoded = [
            tokenizer.encode(
                self.template(self.processor, self.config, prompt, num_images=0),
                add_special_tokens=not hasattr(self.processor, "chat_template"),
            )
            for prompt in prompts
        ]
        generator = BatchGenerator(
            self.model.language_model,
            self.processor,
            prefill_batch_size=len(prompts),
            completion_batch_size=len(prompts),
        )
        uids = generator.insert(encoded, max_tokens)
        tokens = {uid: [] for uid in uids}
        results = {}
        started = time.perf_counter()
        with wired_limit(self.model, [generation_stream]):
            while responses := generator.next():
                for response in responses:
                    if response.finish_reason != "stop":
                        tokens[response.uid].append(response.token)
                    if response.finish_reason is not None:
                        results[response.uid] = {
                            "text": tokenizer.decode(tokens[response.uid]),
                            "seconds": time.perf_counter() - started,
                            "generation_tokens": len(tokens[response.uid]),
                            "finish_reason": response.finish_reason,
                        }
        elapsed = time.perf_counter() - started
        return [
            results[uid]
            | {
                "prompt_tokens": len(encoded[index]),
                "batch_size": len(prompts),
                "batch_seconds": elapsed,
                "peak_memory": mx.get_peak_memory() / 1e9,
            }
            for index, uid in enumerate(uids)
        ]
