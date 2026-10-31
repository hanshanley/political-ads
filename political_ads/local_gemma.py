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
CPU_GENERATION = {
    "backend": "mlx-vlm.cpu-sharded-greedy",
    "device": "cpu",
    "float_dtype": "float32",
    "cpu_streams": 8,
    "prefill_tokens": 128,
    "prefill_kernel": "streamed-dequantized-matmul",
    "decode_kernel": "quantized-matmul",
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

    def batch(
        self, prompts: list[str], max_tokens: int, *, prefill_batch_size: int | None = None
    ) -> list[dict]:
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
            prefill_batch_size=min(prefill_batch_size or len(prompts), len(prompts)),
            completion_batch_size=len(prompts),
        )
        uids = generator.insert(encoded, max_tokens)
        tokens = {uid: [] for uid in uids}
        results = {}
        started = time.perf_counter()
        last_progress = started
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
                now = time.perf_counter()
                if now - last_progress >= 60:
                    print(
                        f"Native batch: {len(results)}/{len(prompts)} complete; "
                        f"{sum(len(value) for value in tokens.values())} generated tokens; "
                        f"{now - started:.0f}s",
                        flush=True,
                    )
                    last_progress = now
        elapsed = time.perf_counter() - started
        return [
            results[uid]
            | {
                "prompt_tokens": len(encoded[index]),
                "batch_size": len(prompts),
                "prefill_batch_size": min(prefill_batch_size or len(prompts), len(prompts)),
                "batch_seconds": elapsed,
                "peak_memory": mx.get_peak_memory() / 1e9,
            }
            for index, uid in enumerate(uids)
        ]


def prepare_cpu_language_model(model):
    import mlx.core as mx
    import mlx.nn as nn
    from mlx.utils import tree_unflatten

    streams = [mx.new_stream(mx.cpu) for _ in range(CPU_GENERATION["cpu_streams"])]

    class CpuQuantizedModule(nn.Module):
        def __init__(self, layer):
            super().__init__()
            self.layer = layer

        @property
        def weight(self):
            return self.layer.weight

        def __call__(self, inputs):
            if isinstance(self.layer, nn.QuantizedEmbedding):
                return self.layer(inputs)
            return self.as_linear(inputs)

        def as_linear(self, inputs):
            layer = self.layer
            width = layer.weight.shape[0]
            count = min(len(streams), width)
            options = {"group_size": layer.group_size, "bits": layer.bits}
            if hasattr(layer, "mode"):
                options["mode"] = layer.mode
            outputs = []
            for index in range(count):
                start, end = index * width // count, (index + 1) * width // count
                stream = streams[index]
                args = (layer.weight[start:end], layer.scales[start:end], layer.biases[start:end])
                if inputs.ndim > 1 and inputs.shape[-2] > 1:
                    weight = mx.dequantize(*args, **options, stream=stream)
                    result = mx.matmul(
                        inputs, mx.swapaxes(weight, -1, -2, stream=stream), stream=stream
                    )
                else:
                    result = mx.quantized_matmul(
                        inputs, *args, transpose=True, **options, stream=stream
                    )
                outputs.append(result)
            result = mx.concatenate(outputs, axis=-1)
            if "bias" in layer:
                result = result + layer.bias
            # Release temporary dense weights before advancing to another layer.
            mx.eval(result)
            return result

    model.set_dtype(mx.float32)
    mx.eval(model.parameters())
    replacements = [
        (name, CpuQuantizedModule(layer))
        for name, layer in model.named_modules()
        if isinstance(layer, (nn.QuantizedLinear, nn.QuantizedEmbedding))
    ]
    model.update_modules(tree_unflatten(replacements))


class LocalGemmaCpu(LocalGemma):
    def __init__(self, *, download: bool = False):
        import mlx.core as mx

        mx.set_default_device(mx.cpu)
        mx.random.seed(0)
        super().__init__(download=download)
        started = time.perf_counter()
        prepare_cpu_language_model(self.model.language_model)
        self.metadata |= CPU_GENERATION | {"cpu_prepare_seconds": time.perf_counter() - started}
        eos = self.config.get("eos_token_id")
        if eos is None:
            eos = self.processor.tokenizer.eos_token_id
        self.eos = {eos} if isinstance(eos, int) else set(eos or [])
        if not self.eos:
            raise ValueError("Pinned CPU model has no end-of-sequence token configuration")
        print("CPU model ready: packed weights, float32 arithmetic, eight CPU streams", flush=True)

    def __call__(self, prompt: str, max_tokens: int) -> dict:
        import mlx.core as mx

        with mx.stream(mx.cpu):
            mx.random.seed(0)
            tokenizer = self.processor.tokenizer
            encoded = tokenizer.encode(
                self.template(self.processor, self.config, prompt, num_images=0),
                add_special_tokens=not hasattr(self.processor, "chat_template"),
            )
            if not encoded:
                raise ValueError("CPU model prompt has no tokens")
            model = self.model.language_model
            cache = model.make_cache()
            started = time.perf_counter()
            step = CPU_GENERATION["prefill_tokens"]
            for first in range(0, len(encoded), step):
                result = model(
                    mx.array([encoded[first : first + step]], dtype=mx.int32), cache=cache
                )
                token = mx.argmax(result.logits[:, -1, :], axis=-1)
                mx.eval(token)
                print(
                    f"CPU prefill: {min(first + step, len(encoded))}/{len(encoded)} tokens; "
                    f"{time.perf_counter() - started:.0f}s",
                    flush=True,
                )
            tokens = []
            finish = "length"
            last_progress = time.perf_counter()
            for index in range(max_tokens):
                token = mx.argmax(result.logits[:, -1, :], axis=-1)
                mx.eval(token)
                value = token.item()
                if value in self.eos:
                    finish = "stop"
                    break
                tokens.append(value)
                now = time.perf_counter()
                if now - last_progress >= 60:
                    print(
                        f"CPU generation: {len(tokens)} tokens; {now - started:.0f}s",
                        flush=True,
                    )
                    last_progress = now
                if index + 1 < max_tokens:
                    result = model(token[:, None], cache=cache)
            return {
                "text": tokenizer.decode(tokens),
                "prompt_tokens": len(encoded),
                "generation_tokens": len(tokens),
                "finish_reason": finish,
                "seconds": time.perf_counter() - started,
                "batch_size": 1,
                "prefill_batch_size": 1,
            }

    def batch(
        self, prompts: list[str], max_tokens: int, *, prefill_batch_size: int | None = None
    ) -> list[dict]:
        return [self(prompt, max_tokens) for prompt in prompts]
