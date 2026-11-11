## v0.5 complete locally / outstanding production checks

- [x] 40 configured employer feed starting points across industries
- [x] Optional Reed UK and Adzuna UK wide search adapters with bounded pagination and credential isolation
- [x] Browser source health, disabled sources, and industry browsing
- [x] Deterministic tests for connector input, limits and error handling
- [ ] API credentials and commercial publisher licences where required
- [ ] Live feed/expiry validation for each company
- [ ] Durable scheduled index and stale-posting reconciliation
- [ ] Public/private GitHub repositories and CI publication
- [ ] Hosted-service security and privacy review

# UK Job Hunter — product direction and release gates

## The customer problem

People who are changing jobs or careers spend too much time on unsuitable vacancies, job-board duplicates, unclear salaries and repeated application documents. A job title alone is a poor proxy for career fit.

**Product promise:** Help a UK jobseeker find a small number of credible, live opportunities, understand why they might be suitable, and take the next step without manufacturing qualifications or sending applications without consent.

## Intended customers

- Career changers whose experience is transferable but whose previous titles do not match target job titles.
- Experienced professionals who want fewer, better matches, not bulk applications.
- UK jobseekers who want salary, location, remote-eligibility and availability claims distinguished from unknowns.

We should test the proposition with jobseekers outside the maintainer's own career path before changing the ranking rules.

## Core workflow

**Set preferences → Find employer adverts → Explain the match and uncertainty → Save/skip → Prepare an honest application → Track and follow up.**

Decisions should be reversible and auditable. The user decides whether to apply.

## v0.2: local browser prototype (included in this package)

- Local web UI launched using `python3 -m uk_hunter web --open`.
- Editable, privately saved role, salary and commute preferences.
- Read-only Greenhouse, Lever and Ashby employer board integrations.
- Add/remove supported employer boards using their public career-site URLs.
- Clearly differentiated SHORTLIST, REVIEW and REJECT states, with evidence and limitations.
- Save jobs, add notes, track outcomes and export data as JSON.
- Fully fictional, prominently labelled demo mode.
- No login, tracking pixels, cloud accounts or automatic applications.
- Loopback-only service with host and origin checks; browser HTML escapes untrusted content.

**Not yet delivered:** hosted service, full UK market coverage, CV upload, LLM-powered career analysis, universal qualifications validation, production monitoring, live end-to-end ATS certification.

## v0.3: expanded connector preview (included, not yet validated live)

- SmartRecruiters public company postings adapter, initial two company examples.
- Opt-in company website `JobPosting` JSON-LD extraction, same-host and robots controls.
- Optional Adzuna UK provider (requires user credentials and approved use).
- Conservative cross-source deduplication, direct employer source preference.
- Additional deterministic source/website safety tests.

**Still pending:** live feed verification, source permissions/licensing register, broad UK coverage, monitoring, end-to-end user acceptance tests, full hosted security review. See `SOURCES_ARCHITECTURE.md`.

## v0.4: industry browsing and wider seeded employer coverage (included preview)

- Horizontally scrollable, keyboard-accessible industry carousel with count of **discovered jobs** in each sector; no fabricated market-wide totals.
- Show all discovered jobs by default; fit filtering is a separate deliberate action.
- 14 named employer industries plus *Unclassified*; employer-sector metadata takes precedence over job title, and unknown/ambiguous industry is never guessed.
- Public employer source list expanded from 6 to 24 boards with documented starting URLs. Live API behaviour remains unverified.
- Users can choose an industry when adding a new supported careers source.
- Exclude adverts that explicitly name only overseas locations, but flag unknown UK eligibility rather than assuming UK remote access.
- Tests cover categories, sources, country screening and mocked browser interactions.

## v0.5: validated nationwide job-data coverage (priority 1)

1. Verify every included employer board in controlled live tests and record last successful sync, count and error state.
2. Add broad UK data only under terms that support the intended public distribution. Investigate licensed data sources such as Adzuna and freehire commercial plans, plus employers giving explicit use permission. Do not assume a public GET endpoint grants downstream republication rights.
3. Expand the curated employer registry to include genuine non-technical and regional roles as well as technology, finance and defence.
4. Normalize salary period, currency, remote-eligibility, genuine posting date, deadline, requisition ID, and employer application URL; label missing data as unverified.
5. Dedupe by canonical employer requisition ID and original posting URL; verify closed jobs before recommending them.
6. Run repeatable tests against representative real adverts in multiple sectors and UK regions.

**Gate:** A user outside the original target sectors can get at least a handful of genuinely suitable listings without manually finding four employer-specific career URLs. Do not claim to cover all UK vacancies.

## v0.6: better fit and application preparation

1. Add voluntary structured experience profiles and importers, with editable evidence for employment dates, duties and achievements.
2. Separate hard eligibility checks from ranking: licence, certification, right to work, professional registration, experience, salary and practical commute.
3. Produce explainable transferable-skill suggestions, explicit gaps and confidence. Keep the original advert and source visible.
4. Integrate upstream document drafting and second-pass factual review, but make them optional and work with the user's choice of model or no AI at all.
5. Add accessible CV export and manual application checklists. No autonomous submissions.

**Gate:** At least 10 representative users can explain why a vacancy was shortlisted; no fabricated CV claims in a structured test set.

## v1.0: public self-service release

- Hosted option with no mandatory account for browsing, or a polished installer for local-first use.
- Real security review, privacy assessment, accessible keyboard/mobile workflow, backups and deletion/export controls.
- Source-licence register, attribution and takedown procedure, clear coverage and freshness indicators.
- Operational monitoring and incident process; published limitation that matches are not guarantees.
- Transparent costs if optional AI assistance is offered. Free discovery and tracking should remain useful without payment.

**Gate:** Tested with people who were not involved in development, across sectors and UK locations; measured job relevance and false positives; accepted privacy, source-rights and accessibility reviews.

## Success metrics (not vanity metrics)

- Percentage of shortlisted listings users judge genuinely suitable after reading the original advert.
- Percentage of candidates able to explain why the product matched or rejected a vacancy.
- Percentage of saved jobs still live when the user opens them.
- Time taken to find and save 3 credible roles.
- False-positive rate for salary floor, location and must-have qualifications.
- Follow-through: saved → applied → interview (tracked only by users who choose to record this).

Do not optimize for generated application count, scraped vacancy volume or AI calls. A user who discards a bad role quickly is also seeing value.

## Repository/edition model

- **Public:** shared source code, product UI, generic configuration, tests and fictional fixtures.
- **Private personal workspace:** user-specific profile, CV, application records, contacts and sensitive preferences; Git-ignored and never pushed to the public repository.
- **Upstream AI Job Search:** optional external MIT-licensed workflows, with original copyright and licence preserved when reused.

The public UI must not contain any hard-coded candidate name, home location, CV, salary requirement or application details.

## Decisions deliberately deferred

- Hosting stack and whether accounts are needed at all.
- Consumer paid model, if any; establish real use and repeat usage first.
- Use of automated browser agents to submit applications (excluded from v1).
- Premium job data and licences until supplier terms/costs are evaluated.
