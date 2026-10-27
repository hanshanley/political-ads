# Static publication

`political-ads build` validates saved evidence and writes `web/public/data/`, `report.html`,
and `preview.svg`. Vite builds `site/` using `/political-ads/` asset paths. Serve the entire
directory, not only its index. No server, database, or secret is shipped to the browser.

**Publication is withdrawn until explicit user authorization.** The
`hanshanley/margin_of_error` host no longer checks out, builds, or stages this project, and
its interactive-analysis directory no longer links to it. Do not restore that integration
or publish local builds without explicit authorization. Research commits may be pushed to
`hanshanley/political-ads` without updating the website; its push-triggered CI only validates.
Automatic evidence refresh is authorized independently of website publication. It updates
this research repository only; neither workflow dispatches or publishes to the website host.

## No-new-cost updates

The refresh uses standard `ubuntu-latest` runners in this public repository, not paid larger
runners. No Actions artifacts or paid APIs are introduced. Official billing documentation:
https://docs.github.com/en/billing/concepts/product-billing/github-actions

`.github/workflows/refresh.yml` refreshes registered public ad-release archives daily at
12:13 UTC through November 4, 2026, inclusive, with a final November 5 reconciliation still
capped at November 4. This covers releases indexed after the final day's morning run
without extending the eligible ad window; the final run follows November 4's close across
U.S. time zones. It updates FEC identities before collecting
scripts; if FEC retrieval fails, it retains the committed candidate registry rather than
discarding identity-gated scripts on a clean runner. It regenerates complete analysis JSON,
CSV and HTML, rebuilds and validates the saved evidence, then commits research inputs and
analysis to main as Hans Hanley. It has no deployment step or host-dispatch credential.
Failed sources retain their last-good partitions and source-specific freshness.
Saved HTTP 401/403/429 denials pause that source on subsequent refreshes without new requests;
successful sources continue updating. A paused source requires access review before resuming.
A successful acquisition is not complete advertising coverage.

Validation allows 25 minutes, and collection plus validation allows 35 minutes, to leave
room for cold-runner Chromium system-package installation. Both jobs remain time-bounded;
no tests or publisher crawl delays are skipped to fit the budget.

Blocked YouTube captions and Google creatives are not retried. Existing caption, image,
Google and Snap extraction partitions are preserved, not re-extracted by this Linux job;
the native OCR pipeline currently requires local macOS Vision. Newly discovered metadata
is not counted as recovered ad text.

After the November 5 final reconciliation routine collection is skipped. Explicit late-index reconciliation:

```bash
gh workflow run refresh.yml --ref main -f until=2026-11-04
```

This recovers late-indexed releases with in-window release dates, not invented delivery evidence
for releases after the cutoff. November 4 releases retain their actual post-election dates;
they are not relabeled as pre-election delivery. A cutoff cannot be later than the current
date, so November 4 is not claimed as observed while it is still in the future.
Do not retry or clear persistent caption/creative access blocks.
Local recognition and analysis may be replayed from successful cached inputs without new
provider requests.

## Verification and rollback

CI tests Python evidence invariants, deterministic rebuilding, complete downloads, TypeScript,
lint, browser filters, keyboard access, and mobile layout against saved real ads.
Host deployment and live URLs must also succeed before reporting the site live.

Verify `/political-ads/`, `report.html`, `data/dataset.json`, `data/ads.csv`, and hashed assets.
Compare live/local snapshot IDs. Deployment files are ignored; `data/site/`, codebook, review
ledger, and validation report are versioned so publication states are rebuildable.

Restore only relevant inputs from a known-good revision into a new main-branch commit and
validate. Do not trigger a host rebuild while website publication is on hold.
Never force-push, introduce another branch, overwrite unrelated work,
or replace failed source partitions with empty lists.
