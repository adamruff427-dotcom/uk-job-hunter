# Provider documentation and rights review — 11 November 2026

This records a technical documentation review for local discovery, not employer
consent or a legal opinion. Commercial hosting, syndication and scaled ingestion
remain blocked until agreements and individual source rights are confirmed.

| Provider | Official documentation reviewed | Finding / limit |
|---|---|---|
| Greenhouse | https://docs.greenhouse.io/job-board.html | GET endpoints are public without authentication; published jobs include ID, URL, content and departments. `updated_at` is not a posted date. Public access is not a blanket employer redistribution licence. |
| Lever | https://github.com/lever/postings-api | Published JSON posting API and hosted application links. Its documented application POST rate limit is not a GET quota; no POST application requests are used here. Check tenant region and local usage rights. |
| Ashby | https://developers.ashbyhq.com/docs/public-job-posting-api | Public board API, compensation opt-in, department and country fields. Data is intended for careers-page integration; employer republication rights remain separate. |
| SmartRecruiters | https://developers.smartrecruiters.com/docs/posting-api | Public posting API intended for customer career sites. Bounded list pagination and UK-filtered detail fetching; sample capped at two details per board. Permission to aggregate employer content needs separate confirmation. |
| Reed | https://www.reed.co.uk/developers/Jobseeker | Basic-auth API key, up to 100 search rows per request, offset pagination. Search salary has no reliable annual-period guarantee. Commercial/storage/attribution agreement and account quotas were not established; disabled without credentials and explicit review. |
| Adzuna | https://developer.adzuna.com/docs/terms_of_service | Free access is evaluation-oriented; organisation/commercial use has trial and written-licence restrictions. Per-advert linked Adzuna credit is required; higher limits depend on account/plan. Licensed source remains disabled. |
| Company websites | Each employer's terms and robots policy | No new site scraping enabled. Explicit employer permission/local review required in addition to existing HTTPS, DNS, robots and same-site path restrictions. |

The refresh engine uses conservative local limits, not invented vendor-approved
quotas. Ask the provider for approved usage, caching, attribution, termination and
commercial redistribution terms before operating a public index. There are no
Reed/Adzuna credentials bundled with this project, and no live licensed-board
requests were made in this implementation.

The sampled run made one listing request per Greenhouse/Ashby/Lever board.
SmartRecruiters was limited to one list page plus at most two details per board.
Seven of ten sampled feeds returned normalized records. Three failed; no successful
coverage is claimed for them. The two successful additions are Wikimedia Foundation
and Mozilla. The configured registry's other unsampled entries remain explicitly
unverified. The JSON evidence records request times and returned/eligibility counts,
not advert text. Its normalized counts are neither national totals nor proof a
listing remains open now. Generic remote and ambiguous locations stay unknown.


## Source repair review — 15 November 2026

Multiverse's official careers HTML calls Ashby's public posting API with board
`multiverse`. The existing Ashby adapter works for that board. Its historical
Greenhouse target returns 404 today; the original generic error does not prove
what happened on 11 November.

Workable documents an unauthenticated public jobs endpoint in
[its troubleshooting guide](https://help.workable.com/hc/en-us/articles/4903195036183-Troubleshooting-API-issues).
For `starling-bank`, the documented legacy URL redirects to
`https://apply.workable.com/api/v1/widget/accounts/starling-bank?details=true`.
A direct GET to the canonical route succeeds with redirects disabled. The adapter
uses this narrow public route, not credentialed SPI APIs or application endpoints.
The careers board is https://apply.workable.com/starling-bank/ and the employer
careers page is https://www.starlingbank.com/careers/. Repeated shortcodes denote
one vacancy advertised in multiple locations, not additional vacancies.
This documents public GET access for local discovery, not employer consent or
commercial redistribution clearance; commercial reuse remains review-required.

Anduril's Greenhouse board is correct. The existing full-content GET reproduces
`response_too_large`, while metadata listing and an individual detail GET work.
The new bounded route uses the documented Greenhouse list and detail GET APIs.
The smaller route does not establish complete detail coverage. The historical
error alone does not prove the same cause occurred on 11 November.

See [new bounded evidence](live-source-check-2026-11-15.json). No Reed/Adzuna
credentials, permissions or enabled states changed. No new website crawling,
authenticated access, automated applications or hosted publication is enabled.
