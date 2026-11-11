# UK search guidance (public template)

Run `uk-ats-search` first for supported Greenhouse, Lever, Ashby and SmartRecruiters employer feeds.
Company board identifiers and public careers links are configured in `config/sources.json`.

**The example is not a candidate profile.** Before running `/scrape`, each user should edit
`local_config/search_profile.json`: target titles, adjacent job functions, minimum basic pay,
acceptable commute areas and exclusions. Do not copy another person's career or constraints.

## Example query categories

### Operations and risk — optional example

#### Plain terms (portal CLIs)
```
operations manager
risk manager
change manager
```

#### WebSearch-only (`site:` fallback)
```
site:job-boards.greenhouse.io "operations manager" "United Kingdom"
site:jobs.ashbyhq.com "risk manager" "Remote UK"
```

### Project and programme delivery — optional example

#### Plain terms (portal CLIs)
```
project manager
programme manager
```

#### WebSearch-only (`site:` fallback)
```
site:jobs.lever.co "programme manager" "United Kingdom"
```

## Review rules

- Prefer official employer job pages or published ATS feeds to syndicated index snippets.
- Never assume salaries from bonuses, OTE or role title; unknown basic pay is a REVIEW if the user sets a minimum.
- `updated_at` is not proof of initial publication.
- A user's commute rules must come from that user. Unknown city = REVIEW, not automatic FAIL.
- Candidate qualifications must be verified before `/apply`.
- Do not run unattended high-volume scraping or automatically submit applications.
