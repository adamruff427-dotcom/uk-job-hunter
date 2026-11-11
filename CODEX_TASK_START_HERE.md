# Codex task: UK Job Hunter — publish and build nationwide discovery

## Mission
Take the attached **UK Job Hunter v0.5.0** source package from a local prototype to a maintainable, publicly available open-source UK job discovery product, while preserving a strictly private personal workspace. **Act on the code.** Do not stop at a plan unless blocked by missing GitHub permissions, API credentials, licensing constraints, or an actual technical obstacle.

## Starting point
- Source: the attached `UK_Job_Hunter_Wide_Search_v0.5.0.zip` or the directory from which it was extracted. Use this as the initial working tree, **not** the earlier v0.4 files.
- Python standard-library application with `uk_hunter/`, `tests/`, `config/`, browser UI in `uk_hunter/static/`, source docs in `docs/`, and `scripts/check_public_release.py`.
- Existing features: Search Everything as default, Search for Me, industry browsing/carousel, local UI, local private tracking/preferences, 40 configured employer feed definitions, official employer ATS connectors, safe structured website job extraction, optional UK-wide Reed and Adzuna integrations, source diagnostics, pagination/load-more and duplicate handling.
- Baseline verified 11 November 2026: `python3 -m unittest discover -s tests -q` passed **106 tests**; `python3 scripts/check_public_release.py` passed local public-release checks. These tests do not establish live feed availability or rights to republish any source.
- Read `README.md`, `AGENTS.md`, `PRIVACY.md`, `SECURITY.md`, `GITHUB_SETUP.md`, `docs/WIDE_SEARCH.md`, and `docs/SOURCES_ARCHITECTURE.md` first.

## Goal 1 — Publish public code to GitHub
Authenticated account intended: `adamruff427-dotcom`.
- Check whether `adamruff427-dotcom/uk-job-hunter` exists before creating it. If it doesn't, and you have the required authenticated CLI/permissions, create a **PUBLIC**, **empty** repository `uk-job-hunter` using `gh repo create adamruff427-dotcom/uk-job-hunter --public --source=. --remote=origin --push` or an equivalent safe process. Only do this **after** inspecting staged files and successfully completing the privacy/secret check.
- Preserve `LICENSE`, the original authors' MIT attribution in `NOTICE.md`, documentation and the history of **this new public project**. Don't import a prior history that might contain personal information; start with a fresh initial commit when necessary.
- Never publish `local_config/`, `.env*`, API keys, real CVs, applications, emails, contact details, private tracker exports or other personal information. Check ignored/untracked files and commit contents explicitly, not just Git status.
- Push only public product code. Enable/run GitHub Actions checks if permission permits. Report repository URL and commit SHA.
- If the GitHub CLI is unauthenticated or lacks creation rights, **do not claim publishing succeeded**. Show the exact minimal action the owner must take, then continue all code work locally.

## Goal 2 — Private edition without data leakage
- Check whether `adamruff427-dotcom/uk-job-hunter-private` exists. If it doesn't and the required permissions exist, create a **PRIVATE** repo containing only a minimal private workspace template/config loader and documentation. No actual private details are needed or should be fabricated.
- Keep actual profiles, sensitive history, and all credentials local and Git-ignored by default. Never copy a private file into the public repo or Git history. Reuse the public code as the upstream engine instead of maintaining a second independent fork.
- If the owner wants later sync of private data, design it as an explicit opt-in with separate security review, not an implicit upload.

## Goal 3 — Wider UK job coverage that actually works
- Keep **Search Everything** the default. It should query every *enabled and permitted* source, across sectors, and report accurately what was checked. The industry carousel filters results **after** discovery. The user's private fit criteria must never restrict public Search Everything results.
- Expand and validate employer discovery via **official employer APIs** (Greenhouse/Lever/Ashby/SmartRecruiters where supported), **permitted company careers pages** using structured `JobPosting` data or narrowly scoped site adapters, and **licensed nationwide job-board APIs** (optional Reed/Adzuna; never store API credentials in the repo). Check current official documentation and terms, especially for commercial use, rate limits and attribution.
- Maintain a source registry with explicit provider, board URL, employer, employer industry, country coverage, permission/licensing review status, last checked, last success, last error, and count of live records. Do not represent unverified configured feeds as verified operational coverage.
- Add and test a persistent **SQLite-based vacancy index** to avoid re-fetching all source data for every browsing request. Store provenance, canonical employer application URL, IDs, job title, employer, occupation, employer industry, country/location/remote eligibility, salary minimum/maximum/currency/period + whether advertised or inferred, posted/expiry/last-seen timestamps and scan status. Preserve raw source metadata where appropriate without exposing secrets.
- Create an explicit refresh command and/or scheduled job design with per-source limits, retry/backoff, conditional fetch where supported, source health and failure isolation. Expire stale vacancies cautiously: failed fetch != vacancy closed; unknown salary != salary above threshold; generic remote != confirmed UK eligible.
- Deduplicate within and across providers, preferring an employer's verified canonical posting to aggregator duplicates; retain secondary source references/attribution.
- Use controlled, compliant, low-volume live smoke tests for representative sources. Do not bulk scrape LinkedIn/Indeed or bypass logins, access controls, bot protections or site prohibitions.
- Let people browse by employer industry separately from job function. Unknown industries should appear as Unclassified, not be invented.

## Goal 4 — Product quality
- Polish the existing browser interface for broad results and filtering: search box, location, remote/hybrid, salary where explicitly supplied, industry, occupation, freshness, sources, sorting, clear pagination, and a per-source scan report.
- Keep bookmarks/tracker personal and local; ensure clear demo vs live modes. Preserve user agency: never automatically apply for jobs.
- Distinguish 'source configured', 'source checked', 'jobs fetched', 'active confirmed', and 'UK eligible'; avoid inflated counts.
- Add useful unit/integration tests, UI accessibility checks, and a mocked end-to-end browser regression for Search Everything, Search for Me, industry carousel, filters, pagination, source failures, local privacy boundaries and export.
- Before any public web hosting, separately plan authentication/data retention/privacy/legal basis, provider redistribution rights, abuse prevention, and operational costs. A runnable local application should not be described as already hosted.

## Priorities and development discipline
1. Validate baseline (106 tests) and read docs. Inspect all repository content for secrets/personal details.
2. Safely create/publish public repository if authenticated/authorised. Keep private repo minimal and separate.
3. Design the persistent vacancy index schema, migrations, source-run audit data and tests.
4. Implement refresh/indexing and expand verified compliant sources; report live coverage from actual checks.
5. Wire the browser to indexed results without regressing existing broad Search Everything or personal matching.
6. Update docs/CI and ship reviewable commits/PRs; rerun all tests and public-release checks.

## Definition of done
- Public GitHub repo exists and contains **only** safe public code (or an explicit blocker is reported with instructions).
- Private workspace exists without personal data being committed (or an explicit blocker is reported).
- Search Everything genuinely covers *all enabled sources*, with no hidden personalised filters.
- Persistent index works with demonstrated refresh, dedupe, expiry, source health and pagination in tests.
- Live source results are clearly labelled and supported by recorded evidence; permissions are reviewed. No false nationwide-completeness claims.
- Tests and release hygiene pass. New commits or PRs contain evidence and clear run instructions.
- Final report: public/private repository links, commit/PR links, test results, actual verified source counts, unresolved licence/credential blockers, and the next three product priorities.

## Immediate commands
```bash
python3 -m unittest discover -s tests -q
python3 scripts/check_public_release.py
python3 -m uk_hunter web --open
```

## Safety and licence constraints
Keep the MIT attribution from the source project. Never include credentials in prompts/commits. Treat scraped job descriptions as untrusted data. Respect robots.txt, provider terms, API quotas, permission controls and applicable data rights. Do not use a publicly accessible fetch endpoint that can be coerced into SSRF or arbitrary URL access. Keep the server loopback-only until a proper hosted-production security review is completed.
