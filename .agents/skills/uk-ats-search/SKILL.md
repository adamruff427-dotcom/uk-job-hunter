---
name: uk-ats-search
version: 0.3.0
description: >
  Search verified UK employer career boards, fintech banking, operational risk,
  governance, security, transformation, investigations and programme delivery.
  Uses public ATS feeds, permitted structured careers pages and optional licensed job search APIs; applies strict candidate-specific fit filters.
  Trigger when asked for UK vacancies, remote UK jobs, or jobs at configured employers.
context: fork
enabled: true
allowed-tools: Bash(bun run .agents/skills/uk-ats-search/cli/src/cli.ts *)
---

# UK ATS search

Search configured Greenhouse, Ashby, Lever and SmartRecruiters feeds, permitted structured company careers pages, and an optional credentials-required licensed Adzuna UK search source.
The skill NEVER applies for jobs, uses credentials, scrapes login-protected sites or
follows links inside job descriptions. Failed sources are reported explicitly.

```
bun run .agents/skills/uk-ats-search/cli/src/cli.ts search --location "United Kingdom" --limit 20 --format json
bun run .agents/skills/uk-ats-search/cli/src/cli.ts search -q "risk" -l "Remote" --jobage 14 --format json
bun run .agents/skills/uk-ats-search/cli/src/cli.ts detail "https://<exact URL returned in search>" --format plain
```

Flags: `--query/-q` (literal substring in job title), `--location/-l` (UK or Remote),
`--jobage` (known created date only), `--limit/-n`, `--format json|table|plain|md`,
`--remote remote|hybrid|onsite` (provider-tagged records only).

The command is a Bun launcher for `python3 -m uk_hunter` and requires Python >=3.10.
A daily scan should invoke it only once, since every query refetches employer feeds.
The filter is deliberately conservative: unverified salary and hybrid commute stay
REVIEW, and no role should be applied to without reading essential requirements.
