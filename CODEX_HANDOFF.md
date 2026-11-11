> Current source-expansion baseline: v0.5, 40 employer feeds, optional Reed/Adzuna, per-source diagnostics. Review docs/WIDE_SEARCH.md and GITHUB_SETUP.md. The repository has not been pushed to GitHub.

# UK Job Hunter v0.4 — Codex handoff

This archive is the **public local browser preview**. Preserve the working industry carousel, source classification and private profile isolation. Do not treat a vacancy's occupation as evidence of its employer industry. All vacancies exposed in browsing must retain the original source link and source provenance.

## Next implementation priorities

1. Validate and continuously health-check the 24 seed employer feeds, with source-specific rate limits, response snapshots, record counts and last-successful checks; quarantine stale/invalid feeds instead of silently presenting nothing.
2. Improve UK-only eligibility handling using country-code fields from each ATS. Keep unknown remote eligibility as unknown rather than advertising as UK-based.
3. Add employer/industry registry management with vetted source provenance, update timestamps and site-specific permissions. Audit whether commercial republishing of each feed is permitted before hosted deployment.
4. Add properly licensed UK-wide search APIs with attribution and pagination. Preserve separate **industry** (employer sector) and **occupation** (job family) fields.
5. Add industry-aware source coverage indicators, pagination and sorting. A carousel count must represent scanned records, not all UK job openings.
6. Extend E2E browser tests, accessibility and mobile layout. Current automated tests plus a mocked browser interaction are not a deployed acceptance test.
7. Do not publish personal profiles, API keys, tracker records or internal scans to the public repository. Keep `local_config/` out of git.

## Commands

```bash
python3 -m unittest discover -s tests -v
python3 -m uk_hunter web --open
```

The basic matching engine is deterministic keyword triage; the original AI Job Search repository provides separate application-writing workflows. No auto-application should be enabled.

# Codex handoff — UK Job Hunter public edition

Work on the open-source source repository without including any real candidate data. The code in this repo is public. Read README.md, SECURITY.md, PRIVACY.md and AGENTS.md before modifying anything.

## Priorities

1. Run `python3 -m unittest discover -s tests -v` and fix failures without changing intended public semantics.
2. Check all provider adapters against their official documentation and make **read-only**, low-volume live tests on the six example boards, reporting missing/malformed/closed boards rather than disguising failures.
3. Confirm the installer works with a clean pinned upstream AI Job Search release while preserving `/apply`, `/rank`, `/interview` and `/outcome` and the upstream MIT notice.
4. Improve common UK salary and location edge cases using minimal reproducible fixtures. Any ambiguous case must become REVIEW, not a fabricated PASS.
5. Keep all personal profiles at `local_config/` or `private/` and excluded from Git. Never add a real CV, salary goal, named candidate or application correspondence to the public repository.
6. Add verified UK employer ATS feeds only with source URL and board identifier documentation. No portal login, LinkedIn guest scraping, bulk harvesting or automated submission.
7. Submit changes as reviewable commits or pull requests; do not change repo visibility or push without the maintainer's authorization.

## Release criteria

- Clean tests/CI; source failure returns non-zero if all configured boards are unavailable.
- Public docs match actual features; no unsupported live-coverage claims.
- Secret and personal-data scan before tagging a release.
- No candidate-specific location/salary assumptions in source or tests.
- Preserve upstream MIT licence and copyright if its files are redistributed.

## v0.3 source coverage extension

Run `python3 -m uk_hunter web --open` and inspect the user experience on desktop and mobile. The UI is in `uk_hunter/static/`, the loopback-only web API in `uk_hunter/webapp.py`, and product milestones in `docs/PRODUCT_ROADMAP.md`. Preserve host/origin checks, local-file privacy and strict ATS URL allowlisting. Do not declare the app publicly hosted, secure against all threats, or UK-wide until live API tests and source-licensing review have been completed.

## Website-to-API extension

`uk_hunter/website.py` extracts structured public JobPosting data from a configured company site, without unbounded crawling. `uk_hunter/extra_providers.py` supports SmartRecruiters public postings and Adzuna UK with external credentials. Test safe URL handling, robots rules and source failures before expanding. For live public use, check provider rights and network egress isolation, not just code tests. See `docs/SOURCES_ARCHITECTURE.md`.
