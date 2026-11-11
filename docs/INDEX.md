# Persistent local vacancy index (v0.6)

Refresh explicitly, then browse without provider requests:

```sh
python3 -m uk_hunter refresh
python3 -m uk_hunter search --indexed --all --limit 250
python3 -m uk_hunter web --open
```

In the browser, **Refresh sources** updates due sources; **Search everything** and
**Search for me** read the same saved index. Personal matching happens after discovery.
The industry carousel and location, workplace, annual advertised GBP pay, occupation,
source, posting age and explicit UK eligibility controls filter discovered records.
Unknown pay is excluded when a minimum is set. Unknown dates are excluded when an
age filter is set. Generic remote work is not confirmed UK eligibility. Sorting
and Load more operate on the filtered set, 60 records at a time.

The CLI's existing `search` without `--indexed` remains a direct network scan.
Both CLI and browser prefer `local_config/sources.json` when present. Copy the
public sources there before adding private optional-source configuration.

## Storage and migration

By default, `local_config/vacancies.sqlite3` is local and Git-ignored. Set
`UK_HUNTER_DATA_DIR` to an absolute private directory to isolate profile, tracker,
sources and index together. The separate private workspace launcher does this.
Files are created with POSIX mode 0600; a newly created data directory uses 0700.
No source credentials, HTTP request URLs/headers, raw API response blobs or
candidate profiles are written into the index. A small metadata allowlist keeps
published department/employment-type information; API keys remain in environment
variables. Treat descriptions as untrusted text. The index is not encrypted.

SQLite `user_version=1` defines the initial schema. Newer unknown versions fail
closed. There is no import from old private Git history. Back up the local file
before upgrading a future schema version; the cache can also be rebuilt by refresh.

- `sources`: provider, board URL, employer, employer industry, country coverage,
  rights-review status, checked/success/error times, last raw count, persisted
  retry state and conditional HTTP validators.
- `records`: source key and vacancy ID, first/last seen, scan status and normalized
  JSON payload. Payload includes canonical source application URL, title, employer,
  occupation (when published), industry, country/location/UK eligibility, workplace,
  salary min/max/currency/period/basis, posted/expiry dates and safe source metadata.
  Unknown fields remain null or unknown; inferred salary never becomes an annual
  base-pay pass. Aggregator URLs remain aggregator links unless a matching direct
  employer posting is already independently present.
- `runs`: each attempted source refresh, timestamps, outcome, attempts and count.
  Errors retain only exception type, never upstream request text or credentials.

Source keys hash source identity and bounded query configuration, so changing a
query creates a distinct snapshot. Removed or disabled sources cannot leak old
records back into browsing. Dedupe prefers direct employer feeds and preserves
secondary source references; title/company/location matching is limited to an aggregator record with one
unambiguous direct candidate. Distinct direct requisitions stay separate.

## Refresh and expiry rules

Sources are refreshed sequentially, at most once per hour by default. A database
claim suppresses simultaneous automatic refreshes. Each source has at most one
retry by default (configurable 0–2), exponential retry delays and persisted failure
backoff capped at one day. Every network request retains the adapters' fixed hosts,
redirect blocking, timeouts, size bounds and page/detail caps. A source's failure
is isolated from other sources. Greenhouse, Ashby and Lever send conditional GETs
when ETag or Last-Modified is available; 304 reconfirms the existing seen snapshot.

A failed request never closes or deletes a vacancy. A successfully refreshed
snapshot marks absent records **unconfirmed**, retaining them for review for up
to 30 days after last seen. Feed caps and search windows mean absence cannot prove
closure. Explicit past expiry dates hide a record. Failed-source records are
labelled **source_unavailable**. Records beyond the 30-day visibility window remain
in the local database as history; they are not asserted closed. Delete the local
index to purge the cache and audit history. `live_count` means records seen in a
successful snapshot, including overseas records, not independently confirmed UK
vacancies or nationwide market size. Eligibility is reported separately per job.

Manual diagnostics can use `refresh --force --retries 0 --index /private/path/cache.sqlite3`.
`--force` bypasses intervals; do not put it into a frequent scheduler. The interval
can be set from 60 to 86400 seconds with `--interval` after checking provider quotas.

A local hourly scheduler may run the ordinary refresh command with an absolute
working directory and private environment. No schedule is installed automatically.
No GitHub Actions ingestion, public job database or cloud data upload is configured.
Provider-specific retention obligations may require a shorter cache policy or
purging a source; verify these before enabling a licensed source.

## Rights and coverage

Public employer GET APIs are used for local personal discovery. This is not a
commercial redistribution clearance. Optional Reed, Adzuna and website sources
remain blocked in the index until enabled **and** `permission_status` is explicitly
`personal_use_reviewed`, `licensed` or `employer_permission` after the appropriate
review. `review_required`, `blocked` and `denied` prevent refresh. A reachable API
and permissive robots.txt do not by themselves grant republication rights.

See [live evidence](live-source-check-2026-11-11.json) and [provider review](PROVIDER_REVIEW.md).
There are 42 configured employer boards, only seven successfully sampled during
this implementation. None of these figures establishes nationwide completeness.
