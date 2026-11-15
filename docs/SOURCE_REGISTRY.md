# Current registry status — v0.6

44 employer boards are configured. Seven successfully returned records in the
bounded live sample on 11 November 2026. Wikimedia Foundation and Mozilla were
added after returning 16 and 114 raw records respectively, including overseas
and unknown-eligibility vacancies. Three of the ten sampled boards failed.
Other boards are configured and unverified. See [machine-readable evidence](live-source-check-2026-11-11.json),
[provider review](PROVIDER_REVIEW.md) and [persistent source health](INDEX.md).
Per-source runtime timestamps, errors and record counts live in the local SQLite
registry, not in public Git commits. Commercial redistribution remains unapproved.

## Source repairs — 15 November 2026

- Anduril retains Greenhouse board `andurilindustries`. The full-content feed
  exceeds the 10 MB response limit. An opt-in metadata-first UK discovery route
  keeps that limit and retrieves at most 25 details per refresh. Missing details
  remain visible and force review. The live sample used a stricter two-detail cap.
- Multiverse and Starling were absent from the previous current registry; their
  obsolete Greenhouse targets appeared only in historical check evidence.
- Multiverse is added as Ashby board `multiverse` (employer sector: education).
- Starling is added as Workable board `starling-bank` (financial services), using
  the public canonical widget GET route. Duplicate shortcodes across locations
  are combined before indexing; country and provenance are retained.
- Current bounded evidence: [15 November check](live-source-check-2026-11-15.json).
  Historical evidence is preserved unchanged. Counts distinguish provider rows,
  normalized vacancies and explicit UK eligibility; they are not suitable-role totals.

Private `local_config/sources.json` overrides are not rewritten. If you use one,
apply the same vetted provider/strategy changes there; changing the shipped
registry does not override a private source list.

## Historical v0.5 source notes

# Employer source registry

**Curated registry (11 November 2026): 40 configured employer feeds.** The public careers pages for the 16 new entries were checked for an identifiable live board; the complete APIs, locations and future availability still require monitoring. The original entries have not been independently revalidated in this release.

The industry is the **employer business sector**, not the job function. It is an editorial label, not a classification endorsed by the employer.

| Employer | Industry | Provider | Careers URL |
|---|---|---|---|
| Monzo | banking | greenhouse | https://job-boards.greenhouse.io/monzo |
| Griffin | banking | ashby | https://jobs.ashbyhq.com/griffin |
| Octopus Energy | energy | lever | https://jobs.lever.co/octoenergy |
| Anduril Industries | defence technology | greenhouse | https://job-boards.greenhouse.io/andurilindustries |
| Wise | financial technology | smartrecruiters | https://careers.smartrecruiters.com/Wise |
| Turner & Townsend | consultancy | smartrecruiters | https://careers.smartrecruiters.com/TurnerTownsend |
| Tide | financial-services | greenhouse | https://job-boards.greenhouse.io/tide |
| Zopa | financial-services | lever | https://jobs.lever.co/zopa |
| Tandem Bank | financial-services | greenhouse | https://job-boards.greenhouse.io/tandemmoneylimited |
| Healios | healthcare | greenhouse | https://job-boards.greenhouse.io/healios |
| Skin Analytics | healthcare | ashby | https://jobs.ashbyhq.com/skin-analytics |
| Kaluza | energy-utilities | ashby | https://jobs.ashbyhq.com/kaluza |
| Babyzone | charities | greenhouse | https://job-boards.greenhouse.io/babyzone |
| Lookers | retail-consumer | greenhouse | https://job-boards.greenhouse.io/lookers |
| Plentific | construction-property | ashby | https://jobs.ashbyhq.com/plentific |
| loveholidays | hospitality-leisure | ashby | https://jobs.ashbyhq.com/loveholidays |
| THG Ingenuity | technology | greenhouse | https://job-boards.greenhouse.io/thgingenuity |
| WHOOP | retail-consumer | ashby | https://jobs.ashbyhq.com/whoop |
| Duffel | transport-logistics | ashby | https://jobs.ashbyhq.com/duffel |
| Super Payments | financial-services | greenhouse | https://job-boards.greenhouse.io/superpayments |
| Levels Technologies | construction-property | ashby | https://jobs.ashbyhq.com/levels |
| Adaptyv | healthcare | ashby | https://jobs.ashbyhq.com/adaptyv |
| Trainline | transport-logistics | ashby | https://jobs.ashbyhq.com/trainline |
| Deliveroo | transport-logistics | greenhouse | https://job-boards.greenhouse.io/deliveroo |
| Peregrine | professional-services | greenhouse | https://job-boards.greenhouse.io/peregrine |
| Lendable | financial-services | ashby | https://jobs.ashbyhq.com/lendable |
| Thought Machine | financial-services | ashby | https://jobs.ashbyhq.com/thought-machine |
| Elliptic | financial-services | ashby | https://jobs.ashbyhq.com/elliptic |
| LemFi | financial-services | ashby | https://jobs.ashbyhq.com/lemfi |
| Airwallex | financial-services | ashby | https://jobs.ashbyhq.com/airwallex |
| Ramp | financial-services | ashby | https://jobs.ashbyhq.com/ramp |
| Bjak | financial-services | ashby | https://jobs.ashbyhq.com/bjakcareer |
| Octopus Legacy | professional-services | greenhouse | https://job-boards.greenhouse.io/octopuslegacy |
| tem | energy-utilities | ashby | https://jobs.ashbyhq.com/tem |
| Cambridge Consultants | professional-services | greenhouse | https://job-boards.greenhouse.io/cambridgeconsultantslimited |
| Ogilvy UK | professional-services | greenhouse | https://job-boards.greenhouse.io/ogilvyuk |
| Hanover | professional-services | greenhouse | https://job-boards.greenhouse.io/hanover |
| Nucleus Global | healthcare | greenhouse | https://job-boards.greenhouse.io/nucleus |
| Resolve to Save Lives | charities | greenhouse | https://job-boards.greenhouse.io/resolvetosavelives |
| ClearView Healthcare Partners | professional-services | greenhouse | https://job-boards.greenhouse.io/clearviewhealthcarepartners |

When a source returns an error, the browser records it in **Source coverage and errors**. Never interpret a failed fetch as zero vacancies.

National aggregators are **optional**, require credentials, and must be used in accordance with contractual terms. See [WIDE_SEARCH.md](WIDE_SEARCH.md).
