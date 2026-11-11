# UK-wide search architecture

Current v0.6 browsing uses the persistent local index and explicit refresh.
See [INDEX.md](INDEX.md) for permission gates, storage, cache and expiry rules.
The connector notes below describe the v0.5 foundations.

## What “Search everything” really does

The browser queries **all enabled sources** and displays **all returned UK-eligible vacancies**, including those that are not a match for the user's profile. It then deduplicates, categorises by *employer industry* where known, and provides keyword and fit filters.

It does not claim access to every advertised UK job. There is no universal public UK jobs API. A useful nationwide index requires continued source expansion, source health monitoring, contractual rights to reuse data, and timely expiry checks.

## Current connectors

| Source | Scope | Credentials | Default |
|---|---|---|---|
| Greenhouse, Ashby, Lever | Curated employers | None | Enabled |
| SmartRecruiters public postings | Curated employers | None | Enabled |
| Structured company careers pages | User-provided careers websites with JobPosting JSON-LD, robots respected | None | Opt-in |
| Reed Jobseeker API | Broad UK search and job information | `REED_API_KEY` | Disabled until configured |
| Adzuna search API | Broad UK job advertisements | `ADZUNA_APP_ID`, `ADZUNA_APP_KEY` | Disabled until configured and licensed |

**Company careers pages and employer APIs remain the preferred source** where both an aggregator and an employer post the same job. A company website being publicly accessible does **not** imply unlimited commercial redistribution rights.

Reed: https://www.reed.co.uk/developers/Jobseeker

Adzuna: https://developer.adzuna.com/docs/search

Adzuna licence: https://developer.adzuna.com/docs/terms_of_service

We intentionally do **not** ingest Active Vacancies' bulk public API into a competing job directory: its terms prohibit scraping, downloading or syndicating aggregated listings in bulk for that purpose without permission. https://activevacancies.com/terms

## Enabling Reed and Adzuna

These sources are deliberately **not on by default**. Add the desired entries from `config/optional_sources.example.json` to your ignored `local_config/sources.json` (which overrides the public source registry). Merge them with the existing companies rather than overwriting the employer list, and set `"enabled": true` only once credentials and usage rights are secured.

```bash
# Use locally; NEVER commit keys or profiles
export REED_API_KEY='YOUR_API_KEY'
export ADZUNA_APP_ID='YOUR_APP_ID'
export ADZUNA_APP_KEY='YOUR_APP_KEY'
python3 -m uk_hunter web --open
```

Both connectors can request broad listings using `"queries": [""]`, which deliberately omits the keyword filter, or search by a selection of roles/subjects. Search breadth is controlled by `max_pages` and `results_per_page`. Defaults are modest to respect rate limits and avoid unexpectedly expensive scans. Tokens are sent only to their corresponding vendor, and never placed in repository configuration or sent to browsers.

## Known limitations

- **No automatic nationwide guarantee.** 40 configured employer feeds provide useful breadth but are not representative of the UK labour market.
- **No permanent index yet.** The local browser holds a 10-minute live-scan cache; a reliable public website needs a scheduled central ingestion service, persistent database, expiration policy, source-change monitoring and explicit permission for hosted reuse.
- **Salary caution.** Reed's search results do not establish salary period, and Adzuna figures can be estimates. Both are left unverified as annual basic salary rather than being treated as guaranteed compensation.
- **Regional and remote eligibility:** clearly overseas-only adverts are excluded, but UK work rights and hybrid office frequency must be confirmed on the listing.
- **Industry attribution:** this means the *employer's sector*, not the advertised occupation. Aggregated roles without verified employer-sector information stay Unclassified.
- **Live checks:** mocked tests check the integration and data handling; live source validation and commercial licensing are independent launch requirements.

## Next production milestones

1. Secure at least one nationwide data licence, verify permitted storage, caching, attribution and refresh frequency.
2. Implement a scheduled, bounded ingester and durable source registry with counts, last-success, errors and freshness; store only licensed/allowed job fields.
3. Maintain a stable job ID and reconcile removals, closed posts, and duplicate records from aggregator and employer APIs.
4. Replace local-only browser service with a hosted API and a user-friendly interface *after* authentication, privacy, security and abuse-prevention work.
5. Verify employer boards across every UK region and industry with real feed health checks rather than assuming configured URLs are live.
