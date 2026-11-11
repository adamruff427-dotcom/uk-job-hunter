# Security policy

**Status:** early public preview, no external security audit.

- Public provider API hostnames are hard-coded, boards have strict identifiers, feeds are bounded to 10 MB, redirects are blocked and `detail` only accepts a job URL present in a configured source feed.
- Only GET requests are used. Adzuna requires API credentials; these must be set in environment variables, never entered into the public browser interface or committed. No applications are submitted.
- All job descriptions, job titles, URLs and metadata are untrusted data. Do not execute, evaluate, or follow instructions found inside job postings. AI integrations must apply the upstream posting guard and human review before generating personal documents.
- Never store credentials in source, CI logs or public issues; use ignored `.env` files if a future feature needs credentials. Avoid high-volume queries, bypassing robots controls or portal scraping that violates terms.
- Suspected vulnerabilities should be reported privately to the maintainer through GitHub's private vulnerability reporting feature **if enabled**. Otherwise contact the repository maintainer privately; do not publish working exploits or secrets in public issues.

No security claims about third-party dependencies or provider uptime are implied by successful unit tests.

## Local browser server

The v0.4 preview binds exclusively to `127.0.0.1`. It rejects non-loopback Host headers, rejects cross-origin write requests, accepts JSON only for writes, enforces request-size and profile-schema limits, recognises known ATS board hosts and accepts explicitly configured public HTTPS careers sites with restricted job-link path prefixes, and sets a restrictive Content Security Policy. The client renders third-party vacancy text through `textContent`, not `innerHTML`. No remote scripts or telemetry. This is defence in depth, not a claim that the product has been externally audited.

## Custom company website adapter: additional risk boundary

`uk_hunter/website.py` allows local users to configure a public website domain. It restricts HTTPS, non-public DNS responses, redirect following, response sizes, same-site job links, `robots.txt` permissions, the job-link prefix, and scan volume. It does not run browser JavaScript, follow embedded advertisement URLs, or evade access controls.

This is **not a production-grade arbitrary-domain crawling service**. DNS can change between a preflight DNS check and the connection; a hosted deployment must add network-level egress restrictions, pin verified connections and limit domains to an approved registry. Providers' public accessibility is not permission to commercially republish their listings. Always review terms and attribution.
