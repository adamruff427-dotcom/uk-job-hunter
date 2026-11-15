# Employer source repair validation — 15 November 2026

Base: `1d745bf6d59fa437f4ab8a51dd804e1276c705c5`.
Validation branch: `fix/reliable-employer-sources`. No deployment performed.

## Changes

- Restore Multiverse using existing Ashby board `multiverse`.
- Add Starling's canonical public Workable GET adapter. Combine repeated
  shortcodes across locations before indexing, preserving all location evidence.
- Keep Anduril's correct Greenhouse board but use bounded metadata/detail GETs
  instead of its oversized full-content response. Retain metadata-only and stale
  detail records explicitly; force review for missing details or uncertain freshness.
- Persist safe diagnostic categories/HTTP status and completeness facts, display
  them in the browser and CLI, and preserve prior records during partial refreshes.
- Correct the shared UK location helper so New South Wales and New England do not
  falsely signal a UK location. Mixed explicit UK/overseas postings remain visible.
- Preserve privacy, permissions, source attribution and historical November 11 evidence.

## Automated validation

- `python -m unittest discover -s tests -q`: 148 tests passed (26 new regression tests).
- `python -m compileall -q uk_hunter`: passed.
- `python scripts/check_public_release.py`: passed; local worktree check, not a history audit.
- `node --check uk_hunter/static/app.js`: passed.
- `git diff --check`: passed.
- Installer verified on a clean upstream `v1.7.5` clone pinned to
  `2b3f613fdaacee90373131652e38454400a0b1c4`; all 38 copied extension tests passed.
- `npx playwright test --list`: all three browser tests parse and are discovered.
- `npm run test:browser`: blocked before tests execute because the matching
  Playwright browser binary is unavailable. A separate attempt with installed
  Chromium also fails before tests execute: this environment denies Chromium's
  process-singleton socket operation. Browser interaction, accessibility and
  layout checks therefore remain unverified. No sandbox/permission controls were changed.

The new tests cover public GET errors/redirects/byte limits, Anduril detail/time/
byte caps, missing-detail discovery, unconditional multi-request snapshots,
Workable location merging, UK eligibility, source identity, schema migration,
partial/stale index behavior, safe errors, retry handling and CLI/browser API reports.

## Bounded live check

See [machine-readable evidence](live-source-check-2026-11-15.json). Anduril was
capped at two details/30 seconds; the shipping configuration allows 25 details/60
seconds. Only this small sample was live-tested, not all 44 registry entries.

| Source | Provider rows | Normalized vacancies | Explicit UK | Unknown eligibility | Details |
|---|---:|---:|---:|---:|---|
| Anduril | 2,598 | 43 UK-plausible | 22 | 21 | 2 succeeded; 41 pending; partial |
| Multiverse | 25 | 25 | 25 | 0 | Full single-response feed |
| Starling | 93 | 49 distinct | 46 | 0 | Full single-response feed; 3 non-UK |

These are observed records, not suitability, guaranteed availability or UK-market
totals. Workable's 93 rows are not 93 distinct vacancies. Anduril's ambiguous
records remain reviewable; no full-detail coverage is claimed. Commercial
redistribution permission is still unapproved. Existing private source overrides
are not rewritten automatically.
