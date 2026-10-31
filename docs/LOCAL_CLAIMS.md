# Local claim extraction, target side and tone

This is the replacement **annotation pipeline**, adapted from the local-Gemma claim
extraction architecture in `hanshanley/dsa`. It does not use Copilot agents, GPT
annotations, or hosted inference. Gemma is still an LLM: local inference improves
control and auditability, not automatically semantic accuracy.

The existing article, figures and `data/portrayal-reviews.json` are unchanged.
Local results are separate until their quality and effects on the findings have
been assessed. Neither the old GPT labels nor their validation status are transferred.

## What it produces

The pipeline freezes the current eligible English corpus, advertiser alignment and
identity metadata. It reads `data/site/*.json` directly; no processed Parquet or
media cache is required.

Each extracted claim has:

- Standalone claim text, claim types, exact supporting source units and original
  character offsets. Original ad text and speech/OCR segments remain intact.
- Voice: advertiser, adopted clip, quoted opponent, rebutted claim or unclear.
- Zero or more targets, each with a literal source anchor, identity reference,
  supported/opponent/unclear role and positive/negative/neutral/uncertain tone.
- Target party and **same-side / other-side / other-party / unknown / not-partisan**
  classification calculated by Python from the supplied identity metadata.

Tone and side are independent. An attack on another Democrat by a Democratic
advertiser is **same-side, negative**, not automatically other-side. Praise of a
Republican by a Democratic advertiser is **other-side, positive**. This describes
party relationship, not whether the advertiser supports the target.

Gemma selects an identity reference from the supplied candidate metadata, explicit
party mentions, national-figure crosswalk or advertiser identity. It cannot supply
an arbitrary party label. Candidate recognition uses conservative full-name matches
and saved exact aliases; absent identity evidence remains unknown. Mapping the
passage to the right identity still involves a model judgment.
Targets with unknown identities do not acquire a party from insults or policy words.
An unaffiliated policy/other subject is not-partisan, not a neutral person portrayal.
An empty target list means no attributable target was extracted, not neutral tone.

## Local model and reproducibility controls

The model is `mlx-community/gemma-3-27b-it-8bit`, pinned to revision
`524cdc4f56a58ef94949ba65dc63a29c48362b1a`, using the same isolated MLX versions as
DSA's extraction script. It runs on Apple Silicon with temperature 0 and seed 0.
This is not a guarantee of byte-identical fresh generations across hardware or
runtime changes. The response records retain runtime versions.

Source text is split into contiguous windows at word boundaries,
with at most 240 source words per chunk and at most 1,200 preceding characters
of reference-only context. Original line breaks remain inside each window:
OCR line wrapping must not separate a candidate's name from its predicate.
Adjacent `image_ocr` segments can share a window only when their image hashes
and capture timestamps match. Speech segments, different images, different
timestamps and OCR without an image hash remain separate. Original segments,
including OCR coordinates, remain intact in the frozen manifest.
Claims and anchors can cite only target units, never reference-only context.
The first local pass extracts claims; a second local pass revises the full
structured result for source fidelity, target attribution, voice and tone.
The second pass is **the same model**, not an independent evaluator.

Both stages have at most two attempts. Invalid schemas, fabricated identity IDs,
nonliteral anchors, invalid evidence IDs and output truncation fail structural
validation. Claim text that only repeats a target name is rejected as a bare label,
not an assertion; this narrow guard is not a general linguistic validity test.
Every attempt retains the exact request, response, request hash and
diagnostics. Retrying preserves the previous response record in history.
An explicit retry starts with the saved failed proposal and its diagnostics,
rather than repeating an identical deterministic request with no failure context.
Unresolved references and failed blocks remain explicit.

The manifest contains the complete frozen input, identities, units, prompts,
settings and a SHA-256 fingerprint. Resume/replay uses this snapshot, not a silently
updated live corpus. Changed selection or prompts require a **new output directory**.
To analyze newly collected ads, prepare a new run rather than reusing the old directory.
Already completed blocks do not cause another model call.

### Batched acceleration

`scripts/extract_claims_fast.py` uses the same pinned 27B 8-bit model, prompts,
source units and structural checks, but runs independent requests through
MLX-VLM's native batch generator. Both extraction and source-fidelity revision
remain mandatory. The conservative default completion batch size is eight, with
prompt prefills limited to two requests at a time to bound activation memory.
Each stage initially allows 2,048 generated tokens; a failed or truncated attempt is retried with the
full 8,192-token budget. Truncated output is never accepted, even when it happens
to parse as JSON. Infrastructure failures stop the worker rather than turning
unprocessed ads into exclusions.

These are different generation settings, recorded as protocol
`local-ad-claims-4` in a **new output directory**. The fast runner copies the
original frozen ads, metadata and source units from an existing manifest instead
of rereading potentially changed live corpus files. It retains that input
fingerprint. The baseline manifest and saved responses are not modified or mixed
into the new run. Batched numerical execution can change fresh model outputs;
neither batching nor structural acceptance establishes semantic accuracy.

An initial throughput-only benchmark on eight frozen inputs took 83.11 seconds
sequentially and 37.63 seconds batched (2.21x faster), with the original worker
sharing the GPU. This used 64-token completions, not accepted annotations; it is
not a full-pipeline speed or accuracy measurement.

A second controlled test repeated the same eight-input distribution at batch
sizes 16 and 32. Throughput rose from 14.83 to 18.09 generated tokens per second
(22% higher), again with another worker sharing the GPU and 64-token completions.
Those measurements used full-batch prefills. A subsequent overlapping production
handoff stalled Metal, including a standalone tiny GPU computation; the exact
driver cause has not been established. Do not treat those timings as evidence of
whole-corpus stability or end-to-end speed. Run only one large model worker at a
time, and verify device health before restarting after a stall. The original,
16-way and experimental 32-way artifacts remain intact.

The bounded-prefill configuration is frozen separately in `full-fast-safe`.
It does not change any previous manifest and must pass real-runtime checks
before it is described as a working full-corpus run.

```bash
# Freeze the exact original corpus with separately recorded fast settings.
uv run --with-editable . scripts/extract_claims_fast.py --prepare-only

# Process every pending frozen chunk, using the same isolated pinned runtime.
uv run --with-editable . scripts/extract_claims_fast.py

# Retry failed/unresolved chunks, retaining their previous raw attempts.
uv run --with-editable . scripts/extract_claims_fast.py --retry-failed

# Publish complete fast-run evidence without interrupting inference.
.venv/bin/python scripts/publish_claim_checkpoint.py --input data/local-claims/full-fast-safe
```

`--batch-size`, `--prefill-batch-size` and `--initial-tokens` are frozen settings,
not live tuning knobs.
Use a new directory when changing them. `--ad-id`, `--max-new-blocks`,
`--prepare-only` and `--replay` also support separate bounded pilots.
Ordinary offline replay and the checkpoint publisher infer the saved generation
settings from either protocol's manifest.

## Commands

Run from the repository root. Preparation and replay use the ordinary README
environment and never load Gemma:

```bash
# Freeze the full current corpus; export complete inputs with not-run statuses.
.venv/bin/python -m political_ads.cli extract-claims --prepare-only

# Alternatively freeze a small, explicitly selected pilot in a separate directory.
.venv/bin/python -m political_ads.cli extract-claims --prepare-only \
  --output data/local-claims/pilot --ad-id barr-1387-0
```

Inference uses an isolated `uv` script environment, not the project's Whisper/Torch
environment. `uv` may retrieve Python packages; model weights are cache-only unless
`--download-model` is explicitly supplied. Downloading weights does not send source
text to a hosted inference service.

```bash
# Bounded real-model smoke run; cached weights required.
uv run --with-editable . scripts/extract_claims.py \
  --output data/local-claims/pilot --max-new-blocks 1

# Full local run, resuming the default frozen corpus.
uv run --with-editable . scripts/extract_claims.py

# Explicitly authorize first-time download of the pinned model if not cached.
uv run --with-editable . scripts/extract_claims.py --download-model

# Retry only structurally failed or unresolved blocks; preserve earlier attempts.
uv run --with-editable . scripts/extract_claims.py --retry-failed --max-new-blocks 3

# Rebuild exports from saved responses without model calls or live-source requests.
.venv/bin/python -m political_ads.cli extract-claims --replay
```

`--max-new-blocks 0` means all pending blocks; a positive value bounds the run.
`incomplete` in the summary means unprocessed chunks remain, not that a background
worker is running. Preparation does not start one.
`--ad-id` is repeatable and controls the frozen corpus selection, not an
after-the-fact filter. `--offline` is an alias for **replay**, not fresh inference.
Fresh inference already defaults to cached local weights.
Nothing automatically starts inference during builds, refreshes or CI.

While inference is running, publish a separate complete checkpoint without taking
the inference lock or restarting the model:

```bash
.venv/bin/python scripts/publish_claim_checkpoint.py
```

This writes `outputs/local-claims/`, including CSV/JSON results and
`complete-evidence.zip` with complete inputs, saved responses and history.
The large input manifest and ad-input JSON/CSV are inside the ZIP, not duplicated
as loose Git files. Unfinished records stay
not-run; failures stay excluded. Identical checkpoints are not rewritten.
Commit this directory to publish progress without replacing the article's legacy
results. The active inference run remains in `data/local-claims/full/`.

If your package proxy supports `pip` but not `uv`, the equivalent isolated
environment (with Python 3.12+ selected as `python3`) is:

```bash
python3 -m venv .venv-claims
.venv-claims/bin/python -m pip install -e . \
  'mlx==0.32.4' 'mlx-vlm==0.3.12' 'mlx-lm==0.30.7' 'transformers==5.1.0'
.venv-claims/bin/python scripts/extract_claims.py --max-new-blocks 1
```

Do not install these packages into the existing media/transcription environment.
The loader rejects runtime versions that differ from the pinned stack.

## Outputs and counting

The default run directory is `data/local-claims/full/`. The parent
`data/local-claims/` is ignored by Git because it contains local inference artifacts.
A custom `--output` directory retains separate pilots alongside the full run.

| File | Contents |
|---|---|
| `manifest.json` | Complete frozen ads, identity metadata, source units, prompts, settings and fingerprint |
| `responses/*.json` | Every request/reply attempt, runtime provenance and diagnostics |
| `response-history/*.json` | Original response records superseded by explicit retries |
| `ads.json`, `ads.csv` | All selected source records with full text, extraction status, claim IDs and derived strategy |
| `claims.json`, `claims.csv` | Extracted claims, nested target labels, evidence, full original ad text and block/ad completion status |
| `targets.csv` | One row per claim-target pair, with explicit side, tone, role, voice, evidence, full ad text and completion status |
| `block-status.json` | Not-run, failed, unresolved or normalized disposition for every block |
| `summary.json` | Coverage, claim-target references and unique-message side/tone and strategy counts/IDs |
| `complete-evidence.zip` | All the above, including complete inputs and raw response history; not metadata-only |

Each response is saved immediately; aggregate exports checkpoint every ten processed
blocks and at the end. An interrupted run resumes the saved blocks. Replay rebuilds
exports from those responses. A single-writer lock rejects a second process trying
to use the same directory while a run or replay is active.

Claim-target references are **not ad percentages**: an ad can supply multiple claims
or targets; `target_side_tone` includes quoted and rebutted claims for auditing.
The `ad_target_side_tone` summary counts a message at most once in each side/tone cell.
It includes only normalized unique messages and advertiser/adopted-clip voices,
reports that denominator alongside all selected messages, and allows overlapping cells.
Unlike the strategy summary, it does not require the supported/opponent role: it
includes same-party attacks and cross-party praise explicitly.

The separate ad-strategy summary selects one earliest exact party/message
representative, using the existing whitespace/case normalization and ad-ID tie-breaker.
Its denominator is all selected unique D/R messages; a verbose ad has no extra weight.
It recomputes own-side praise, other-side opponent criticism, both, neither detected,
or not classified. Only advertiser/adopted-clip voices supply signals.

Not-run, failed and unresolved ads are not classified. Uncertain tone/voice or
unknown person/collective identity/role prevents a definitive one-signal/neither
category; an already explicit pair of eligible signals still establishes contrast.
“Neither detected” is not a certified absence, neutrality or positive sentiment.
Unknown/other advertisers remain in full exports but outside the D/R strategy summary.

## What the checks cannot establish

Structural validation proves neither that a paraphrase is supported by its cited unit
nor that the model found every claim. Side is deterministic **conditional on the
model's identity reference**; selecting the wrong reference still creates a wrong side.
Tone, role, voice and claim boundaries are also semantic judgments.

For example, a local smoke test produced extra speaker targets on general
statements about social groups. Literal "I" anchors existed in the source window,
but did not establish that each statement was about the speaker. `normalized`
means schema/anchor checks passed, not human-certified accuracy.

No human accuracy benchmark is created by this pipeline. Before replacing the
article's results, independently evaluate extraction omissions, identity attribution,
side, tone and voice, including party/source-specific errors. Keep the existing and
new methods distinguishable rather than merging their judgments into a purportedly
independent review.
