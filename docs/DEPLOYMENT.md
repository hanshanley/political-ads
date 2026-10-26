# Static publication

`political-ads build` validates saved evidence and writes `web/public/data/`, `report.html`,
and `preview.svg`. Vite builds `site/` using `/political-ads/` asset paths. Serve the entire
directory, not only its index. No server, database, or secret is shipped to the browser.

The existing `hanshanley/margin_of_error` host, main branch, stages external analyses in Astro's
`public/`. Deployment checks out this repository's main, builds saved evidence using Python/Node,
and copies `site/` to `public/political-ads/`. Its analysis directory links to the tool; this
does not imply a new essay or personal-site article entry. Twice-daily host deployments pick up
saved data after the daily refresh.

## No-new-cost updates

The refresh uses standard `ubuntu-latest` runners in this public repository, not paid larger
runners. No Actions artifacts or paid APIs are introduced. Official billing documentation:
https://docs.github.com/en/billing/concepts/product-billing/github-actions

`.github/workflows/refresh.yml` refreshes sources daily at 08:13 UTC through November 3, 2026.
It checks known releases, FEC identities, and bounded caption leads, then validates/tests before
committing publication inputs to main. Failed sources retain their last-good partitions and
source-specific freshness. A successful acquisition is not complete advertising coverage.

After Election Day routine collection is skipped. Explicit late-index reconciliation:

```bash
gh workflow run refresh.yml --ref main -f until=2026-11-03
```

This recovers late-indexed releases with in-window release dates, not invented delivery evidence
for after-election releases. Retry caption failures locally with `media-collect --retry-failed`,
respecting rate limits.

## Verification and rollback

CI tests Python evidence invariants, deterministic rebuilding, complete downloads, TypeScript,
lint, browser filters, keyboard access, and mobile layout against saved real ads.
Host deployment and live URLs must also succeed before reporting the site live.

Verify `/political-ads/`, `report.html`, `data/dataset.json`, `data/ads.csv`, and hashed assets.
Compare live/local snapshot IDs. Deployment files are ignored; `data/site/`, codebook, review
ledger, and validation report are versioned so publication states are rebuildable.

Restore only relevant inputs from a known-good revision into a new main-branch commit, validate,
and let the host rebuild. Never force-push, introduce another branch, overwrite unrelated work,
or replace failed source partitions with empty lists.
