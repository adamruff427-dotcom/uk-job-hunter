# UK Job Hunter — Job Source Architecture (v0.5 preview)

The local product exposes **`GET /api/jobs`** as a normalized JSON endpoint. Every connector maps public vacancy metadata to a common record:

`id`, `title`, `company`, `location`, `url`, `date`, `description`, `workplace_type`, `salary_min`, `salary_max`, `source`.

Search is **read only**. It does not send user CVs, salary preferences or application history to providers, and does not submit applications.

## Three acquisition routes

1. **Published employer ATS APIs**: Greenhouse, Lever, Ashby, SmartRecruiters. Read only public listings on a configured board. SmartRecruiters retrieves limited job details using its public Posting API; first 100 board entries are considered, and a configured maximum of 25 UK details are fetched by default. It is not a comprehensive full-board mirror.
2. **Configured company careers website → our API**: A page may embed schema.org `JobPosting` JSON-LD. The `website` connector fetches a configured public careers landing page, discovers up to 10 same-host detail links under explicit permitted path prefixes, parses structured job metadata, and emits standard records. It obeys `robots.txt`, limits requests, restricts HTTPS, checks public DNS addresses and refuses redirects. It fails visibly when there are no structured postings, a site is JavaScript-rendered, or permission is denied. This does not bypass CAPTCHA, login or site restrictions. There remains a DNS rebinding TOCTOU risk in the stdlib network stack; do **not** expose the user-configurable website connector to a multi-tenant public server without network egress isolation, pinned DNS connections and an approved source registry.
3. **Licensed broader job APIs**: Optional Reed and Adzuna UK connectors using `ADZUNA_APP_ID` and `ADZUNA_APP_KEY` environment variables. Searches bounded keyword or blank-query broad result pages. It is disabled without credentials; commercial operation requires a separate licence/permission review. Attribution must be added to any public presentation of Adzuna content. Salary estimates are not promoted to verified annual base pay; the candidate should confirm details at the original employer website.

## Adding a normal company website

In the browser's **Settings → Employer sources**, enter an HTTPS careers URL and the path prefix used by its individual job pages. Example:

- Careers page: `https://careers.example.org/careers`
- Job link path: `/careers/jobs/`

Or add a vetted entry to **your private local** `local_config/sources.json` (create it by copying `config/sources.json`):

```json
{
  "name": "Example company",
  "provider": "website",
  "url": "https://careers.example.org/careers",
  "job_path_prefixes": ["/careers/jobs/"],
  "max_details": 10,
  "sector": "unspecified"
}
```

This is an **example only**, not a live approved source. The company page must expose crawlable links and structured `JobPosting` data or a bespoke company adapter will be required. Many sites use JavaScript or ATS-backed feeds; use the official published feed wherever possible.

## Enabling Adzuna for a permitted use

- Review [Adzuna API terms](https://developer.adzuna.com/docs/terms_of_service), including commercial licensing, attribution and trial restrictions.
- Obtain developer credentials; set `ADZUNA_APP_ID` and `ADZUNA_APP_KEY` in your local shell, not in Git, HTML, client-side JavaScript, or commits.
- Copy the appropriate provider object from `config/optional_sources.example.json` into your **local** sources list.
- Run `python3 -m uk_hunter search`. The URL and credentials are not logged on failures.

For a public hosted version, agreements and correct attribution are release gates, not optional housekeeping.

## Quality rules

- Prefer first-party employer data over syndicated aggregator results.
- Treat unknown pay, UK remote eligibility, professional qualifications and posting date as **unknown**, not verified.
- Deduplicate by ID and URL; additionally merge obvious title/company/location duplicates **across** sources, preferring the employer feed. Never merge two distinct requisitions solely because one employer has the same job title twice.
- Honour source robots and terms; cache or rate-limit recurring requests. The local UI caches scans for 10 minutes.
- Report failed sources separately from "no matching vacancies".
- Preserve provenance; each result includes its `source` and an original URL.
- A public production crawler will require a permitted-source registry, monitoring, takedown process, egress/network controls and full licence/rights review.

## Next steps

1. Validate the included providers against live public boards with low-volume requests.
2. Curate 30–50 employer feeds across financial services, defence, energy, healthcare, public services and nationwide employers, and track last sync and license/reuse status.
3. Build site-specific adapters for approved companies whose pages have no JSON-LD; never silently infer job descriptions from titles.
4. Validate browser-side UK search filters and full end-to-end user flow across non-technical users.
5. Only then design a hosted, scaled source ingestion service and user-facing website.

## v0.4: Industry browsing

The user interface groups all UK-plausible discovered vacancies by the **employer's sector**. It does not infer employer industry from a vacancy's occupation (e.g. a software engineer can work for a bank). The source registry can carry `sector`; users adding a company can choose one of the named categories. When metadata is absent, only highly specific textual evidence is used and ambiguity stays `unclassified`.

The JSON response from `/api/jobs` includes each job's `industry` and `industry_basis`, and an `industries` summary array with `count` (all collected vacancies) and `matched` (initial profile triage shortlist or review). The counts describe **this scan**, not national industry vacancy totals. Job sites such as Adzuna classify many adverts by *occupation*, not necessarily employer industry; those categories must never be misrepresented as employer sectors.

Source registry entries are starting URLs for public careers boards, not permissions for commercial syndication. Before hosted product launch, log each provider's terms, robots policy if site fetching is involved, redistribution rights, attribution, permitted request frequency, and data retention limits. Broad UK coverage depends on licensed sources plus a maintained permitted employer registry, not just multiplying unverified board slugs.

See [Source registry](SOURCE_REGISTRY.md) for the initial boards (not evidence of live API access).

## v0.5: Reed, wide search and source diagnostics

Reed Jobseeker API uses an `REED_API_KEY` provided via environment, and authenticates using HTTPS Basic auth (key as username, blank password) to the vendor host. Reed search pay is **not treated as annual basic salary**, because a pay period cannot be trusted from search rows alone. Its result URLs are taken from `jobUrl` when given, otherwise constructed from the public Reed title-and-ID permalink pattern, which should be confirmed during live validation.

Adzuna and Reed support `queries:[""]` for broad searches, with bounded `max_pages` and `results_per_page` to manage rate limits. Both remain off until credentials are supplied and use is permitted.

The browser now shows a per-source reachability and raw-record count report. Individual source errors remain visible. Search Everything continues to query every enabled source and exposes more than 250 results using **Load more jobs**, without applying profile restrictions. See [Wide UK search](WIDE_SEARCH.md).
