# Current registry status — v0.6

42 employer boards are configured; seven successfully returned records in the
bounded live sample on 11 November 2026. Wikimedia Foundation and Mozilla were
added after returning 16 and 114 raw records respectively, including overseas
and unknown-eligibility vacancies. Three of the ten sampled boards failed.
Other boards are configured and unverified. See [machine-readable evidence](live-source-check-2026-11-11.json),
[provider review](PROVIDER_REVIEW.md) and [persistent source health](INDEX.md).
Per-source runtime timestamps, errors and record counts live in the local SQLite
registry, not in public Git commits. Commercial redistribution remains unapproved.

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
