# v0.6.0 — persistent local index preview

- Published public code and a separate minimal private-workspace launcher.
- Added SQLite vacancy snapshots, per-source registry and refresh audit history,
  conditional ATS requests, bounded retries/backoff and cautious stale handling.
- Added explicit browser refresh, offline indexed browsing, provenance-preserving
  dedupe and filters for published pay, occupation, source, eligibility and freshness.
- Added two sampled employer feeds; recorded seven successes and three failures
  from a bounded ten-board sample without claiming complete UK coverage.
- Added mocked browser regression and axe accessibility checks; fixed text contrast.
- Preserved source attribution and local profile/tracker boundaries.

## v0.5.0 — Wider UK search (11 November 2026)

- Expanded publicly visible employer registry from 24 to 40 board starting points across several industries.
- Added an optional, credentialled Reed Jobseeker API search adapter; no personal or employer credentials in code.
- Improved optional Adzuna search with paginated, bounded, nationwide unfiltered and keyword modes.
- Added enable/disable toggles in source JSON and a per-source coverage/error breakdown in the browser.
- Enforced unverified-salary treatment on Reed search data and Adzuna estimates.
- Added `docs/WIDE_SEARCH.md`, `GITHUB_SETUP.md` and pre-publication hygiene check.
- Added mocked source, privacy, error and pagination tests (106 pass).
- NOT published to GitHub or live-validated as a full UK job index; provider usage rights remain a launch gate.

## v0.4.1 — Search Everything mode

- Added prominent **Search everything** (default) and **Search for me** choices above the industry browser. Both query every configured source; only the result view differs.
- Search everything resets stale keyword/industry/match filters and shows all available vacancies, including those outside the user's saved career profile.
- Added `python3 -m uk_hunter search --all` to export all discovered feed records rather than just shortlist/review outcomes.
- Keyword search now also checks vacancy descriptions, including jobs outside the chosen professional background.
- Added visible result counts and clearer coverage wording: every **connected source**, not the entire UK market.

## v0.4.0 — Industry browsing and expanded employer discovery (11 November 2026)

- Added horizontally scrollable industry carousel with accurate per-scan vacancy counts and a sector-specific browsing view.
- Public discovery shows all returned UK-plausible vacancies by default; optional matching filters remain separate.
- Added a conservative industry taxonomy (employer business, not vacancy function), including an explicit Unclassified category.
- Expanded the default employer board registry to 24 starting sources, with new finance, healthcare, energy, property, consumer, travel, transport and charity sources.
- Source setup now lets users label the employer industry; no personal candidate fields go into the public config.
- Excluded clearly overseas-only locations while retaining ambiguous UK eligibility for review.
- Tests expanded to 90 and browser interactions smoke-checked with fictional responses. Live feed and licence validation remain to be done.

# Changelog

## 0.3.0 — search sources and company website-to-API (2026-11-11)

- Added SmartRecruiters public company Posting API adapter and two verified-board examples.
- Added opt-in same-site company website adapter for schema.org JobPosting metadata, with robots, HTTPS, size, path, redirect and DNS checks.
- Added optional credentials-required Adzuna UK connector (not enabled by default; licensing/attribution required).
- Extended local browser source manager to add company website URLs with approved job page path prefixes.
- Added cross-source deduplication preferring employer feeds; estimated aggregator pay stays unverified.
- Added source architecture and safety documentation, and additional mocked integration tests.
- Still a **local-only preview**: provider live-coverage and a hosted service are not validated.


## 0.2.0 — local browser product preview (2026-11-11)

- Responsive, keyboard-friendly local browser interface; no new Python dependencies.
- Editable generic candidate preferences, kept in private local files.
- Search across configured employer feeds with source health/errors and transparent fit reasons.
- Supported Greenhouse, Lever and Ashby board editor with strict host allowlist.
- Saved-job tracker, application statuses, private notes and JSON export.
- Fictional demo mode, local-only host and origin protection, Content Security Policy.
- Additional security, API and product-level tests.
- Added Quickstart and phased product roadmap.

## 0.1.0 — public preview (2026-11-11)

- Configurable, generic UK candidate search profile (no personal defaults).
- Read-only employer-published ATS feeds for Greenhouse, Lever and Ashby.
- Explicit role, commute, annual basic pay and date triage.
- Git-ignored `local_config/` created by `python3 -m uk_hunter init`.
- Optional installer for the MIT-licensed AI Job Search workflow framework.
- Local unit tests and no-credentials GitHub Actions test workflow.
