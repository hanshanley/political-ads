# The language of political ads

An evidence-linked report and static dashboard comparing Democratic- and Republican-aligned
advertising language in the **2026 U.S. House and Senate cycle**. Read issue-language patterns,
contextual opponent portrayals, and complete source transcripts behind the comparisons.

**Publication withdrawn:** collection and analysis are local only. Do not publish, push
pending expansion data, or restore website integration without explicit user authorization.

This is an evolving collection of official ad releases, **not a census of paid placements**.
It includes publisher transcripts, public captions, local image OCR, native Google previews,
and locally transcribed/OCR'd Snap creatives. Candidate, party, and
outside-group publishers remain separately filterable. Dates are release dates unless documented
otherwise. Google reports parent-creative delivery; Snap reports scheduled dates and positive
impressions, not independently verified delivery days. Spending, reach and persuasion are not inferred.
Party differences are confounded by source and race coverage. See [methodology](docs/METHODOLOGY.md).

## Reproduce the saved publication

Requires Python 3.10+ and Node 22.19+. No paid API, credentials, model calls, or live source
requests are needed to build the committed snapshot.

```bash
python3.12 -m venv .venv
.venv/bin/python -m pip install -e '.[dev]'
.venv/bin/python -m political_ads.cli build
.venv/bin/python -m political_ads.cli validate
npm ci --prefix web
npm run build --prefix web
npm run preview --prefix web
# Open http://127.0.0.1:4173/political-ads/
```

The deployable output is `site/`; the base path defaults to `/political-ads/`.
Override with `SITE_BASE=/ npm run build --prefix web` for root hosting.
The static `report.html` works without JavaScript.

## Refresh and expand collection

```bash
.venv/bin/python -m political_ads.cli update
# Optional public captions; no ASR model or paid service required:
.venv/bin/python -m pip install -e '.[captions]'
.venv/bin/python -m political_ads.cli media-collect --source slf --source hmp --limit 24
.venv/bin/python -m political_ads.cli parquet
.venv/bin/python -m political_ads.cli build
.venv/bin/python -m political_ads.cli validate
# Reconcile late-indexed releases within the election window:
.venv/bin/python -m political_ads.cli update --until 2026-11-03
```

`collect --source dccc` selects one source. `--offline` on the transcript collector and registry
reuses saved HTTP responses. Caption collection checkpoints attempts, preserves prior text,
and stops caption requests across all sources on rate limits. The current YouTube and Google
HTTP 429 blocks must not be retried or bypassed with alternate methods.
The per-source acquisition limit is not a coverage claim. Missing authorization or text never
silently becomes zero advertising.

`data/site/` contains versioned, rebuildable publication inputs. `data/raw/`, `data/media/`,
`data/processed/`, and model files are local-only. `parquet` creates a DuckDB-readable table.
Complete CSV/JSON exports retain transcripts, segments, evidence offsets, hashes, publisher
provenance, and extraction quality notes.
Hash-bound publisher reviews in `data/publisher-alignments.json` distinguish electoral
alignment from formal party registration. Exports retain original labels and review evidence;
reviewed bipartisan programs remain separate from genuinely unresolved affiliations.

Analyze the saved corpus without building or publishing the website:

```bash
.venv/bin/python -m political_ads.cli analyze
# Open outputs/analysis.html; complete evidence/text: outputs/analysis.json and analysis-ads.csv
```

The local report compares wording over release/reported-delivery/scheduled-start months and by
source, chamber, race, sponsor type, placement, format and election phase.
A largest-publisher exclusion check exposes source-composition
sensitivity; lexical matches are not semantic attack rates or national prevalence estimates.

Native platform recovery is local and resumable:

```bash
# Requires the official Google/Snap ZIPs in data/raw/ and a saved FEC registry.
.venv/bin/python -m political_ads.cli google-discover
# Current Google HTTP 429 stop is persistent: do not retry online collection.
.venv/bin/python -m political_ads.cli google-collect --offline
# Snap video recovery needs the existing media extra, macOS Vision/Swift and FFmpeg.
.venv/bin/python -m pip install -e '.[media]'
.venv/bin/python -m political_ads.cli snap-discover
.venv/bin/python -m political_ads.cli snap-collect
.venv/bin/python -m political_ads.cli snap-collect --offline
```

`--limit 0` (the default) processes all eligible platform creatives. Snap stores every matched
federal or reviewed-advocacy lead separately in `outputs/snap-discovery.json`; these are not
analyzed text until the creative and any required federal-candidate evidence are recovered.
Public model weights download once; audio/video never goes to a hosted
recognition service. Offline replay uses cached payloads/extractions and does not retry blocked
providers. The complete recovered text and evidence remain in local JSON/CSV exports.

## Checks

```bash
.venv/bin/python -m ruff check political_ads tests
.venv/bin/python -m ruff format --check political_ads tests
.venv/bin/python -m pytest -q
npm run lint --prefix web
npm test --prefix web
npm run build --prefix web
cd web && npx playwright install chromium && npm run test:e2e
```

Tests cover pagination/failure retention, language scope, press-commentary boundaries, candidate
ambiguity, exact-message denominators, reviewed evidence, full-text downloads, synchronized
filters, keyboard access, mobile overflow, and non-root asset paths.

## Publication and updates

All work stays on **main**, authored as Hans Hanley. Automatic evidence refresh is disabled.
The host integration, page, interactive-analysis card and sitemap entry have been removed.
Do not restore them or push pending data without explicit authorization.
Local collection is bounded to **November 3, 2026**; manual reconciliation remains available.
No paid provider or runtime hosted model is used.
See [deployment](docs/DEPLOYMENT.md) and [source capabilities](docs/SOURCES.md).

Source material remains attributable to its original publishers. No ownership of third-party
advertisements is asserted. This is a research comparison with original-source links, not a
licensed comprehensive ad catalog.