# Frozen political-ad analysis on an NVIDIA GPU

This bundle contains every original field and complete recognized ad text for
1,792 ads and all 2,016 frozen chunks, not metadata-only inputs. `data/ads.json`
and `data/ads.csv` are convenient exports; `data/manifest.json` is the actual
inference input, including source units, offsets, identities, prompts and hashes.
CSV formula-like text is spreadsheet-escaped; JSON retains the exact original text.
No source-web retrieval, ASR, OCR or hosted inference is required.

## Requirements and downloads

Use Linux (or WSL2) with an NVIDIA CUDA GPU and Python 3.12. This is **not** an
AMD or Apple Metal runner. It refuses CPU fallback and CPU/disk weight offload.
Default loading uses 4-bit NF4 quantization, one request at a time. Budget at least
24 GB GPU memory; 32 GB or more gives safer room for long repair prompts and KV
cache. Actual memory depends on the input and GPU. Use `--quantization 8bit` or
`--quantization none` only on a GPU with sufficient memory, in a new output directory.

Model weights are **not included**. Accept the Gemma access terms at
https://huggingface.co/google/gemma-3-27b-it and authenticate with your own account.
Expect roughly 55 GB of original weights to download even for 4-bit loading;
allow at least 80 GB free disk space plus room for result evidence.
The model revision is pinned to `005ad3404e59d6023443cb575daa05336842228a`.

```bash
unzip gemma-cuda-bundle.zip
cd gemma-cuda-bundle
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install torch==2.10.0 torchvision==0.25.0 --index-url https://download.pytorch.org/whl/cu128
python -m pip install -r requirements.txt
hf auth login
python -c "import torch; print(torch.cuda.get_device_name(0)); assert torch.cuda.is_available()"
python run_gemma.py --download-only
```

The CUDA 12.8 wheels require a compatible installed NVIDIA driver. If necessary,
install the appropriate CUDA build of the same pinned PyTorch versions using the
official selector at https://pytorch.org/get-started/locally/.
Download/authentication errors require accepting access terms, logging in, and
rerunning the download. Your credentials are not part of this bundle.

## Run, resume and verify

```bash
# Verify full inputs and export evidence without loading a model:
python run_gemma.py --prepare-only

# Optional two-chunk smoke test; its saved results count toward the full run:
HF_HUB_OFFLINE=1 python run_gemma.py --max-new-blocks 2

# Initial full pass. Repeating this command resumes only missing saved chunks:
HF_HUB_OFFLINE=1 python run_gemma.py

# After every chunk has an initial disposition, perform one feedback-aware retry:
HF_HUB_OFFLINE=1 python run_gemma.py --retry-failed

# Repeating --retry-failed resumes an interrupted pass, not a fresh retry loop.
# Rebuild and verify all exports without loading a model:
python run_gemma.py --replay
```

Run only one process against a given results directory. A lock enforces this.
Each chunk receives extraction, structural checks and mandatory same-model
source-fidelity revision. Initial attempts have 2,048-token budgets; failed
attempts may use 8,192 tokens. These long repairs can still be slow. Progress is
printed per stage and completed chunk; results are saved atomically per chunk.
Ctrl-C preserves completed chunks; resume using the same command and settings.
CUDA out-of-memory does not silently switch to CPU. Stop the process and use a
GPU with more memory; changed settings require a new output directory.

`results/complete-evidence.zip` contains the complete source manifest, full
ad JSON/CSV exports, claims, targets, block dispositions, raw attempts and
response history. `results/summary.json` reports accepted/failed/unresolved/
not-run coverage. Export verification checks complete original JSON/CSV text,
text hashes, archive membership, member hashes and CRC. Also retain
`results/retry-pass.json`, the baseline used to resume the single retry pass.

This is a **separate CUDA experiment**, not a resume of the Apple MLX 8-bit run.
The upstream weights, quantization and inference backend differ, so outputs
need not match the Mac run. Inputs, extraction prompts and validation semantics
are preserved. Never merge its raw response files into the Mac run. Failures
and unresolved chunks are explicit exclusions, not neutral/no-claim labels.
Same-model review is not independent human semantic accuracy certification.
Weight loading and generation must be smoke-tested on your actual CUDA GPU;
the bundle was prepared and offline-verified on the Mac, not CUDA-benchmarked.

## Bundle integrity

`bundle.json` gives the original fingerprint, corpus counts and SHA-256 for all
bundled inputs, Python modules and instructions. From the extracted directory:

```bash
python - <<'PY'
import hashlib, json
from pathlib import Path
metadata = json.loads(Path("bundle.json").read_text())
for name, expected in metadata["sha256"].items():
    assert hashlib.sha256(Path(name).read_bytes()).hexdigest() == expected, name
print(metadata["ads"], "ads;", metadata["chunks"], "chunks; all hashes verified")
PY
```
