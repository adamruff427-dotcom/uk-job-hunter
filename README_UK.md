> UK Job Hunter public preview v0.5 expands direct sources and adds optional credentialled Reed/Adzuna; see docs/WIDE_SEARCH.md.

# UK AI Job Search extension

This is the UK-specific adapter to [AI Job Search](https://github.com/ai-job-search-dev/ai-job-search). It preserves the upstream `/apply`, `/rank`, `/interview`, `/outcome` workflows and installs a new `uk-ats-search` portal skill to support the `/scrape` workflow.

The extension's settings are generic. Run `python3 -m uk_hunter init` after installation to create an ignored local profile, or supply `--profile` on every run. **No candidate profile is bundled with this public release.**

## Installation

From the public repository root:

```bash
git clone --branch v1.7.5 --single-branch https://github.com/ai-job-search-dev/ai-job-search.git ../ai-job-search-local
python3 install_into_upstream.py --target ../ai-job-search-local
cd ../ai-job-search-local
python3 -m uk_hunter init
python3 -m uk_hunter search --format table
```

If the upstream repo is already customised, commit your work and inspect the changes before installation. The installer does not use Git, submit applications or deploy anything. The installer does not overwrite existing local personal profile files but modifies `.claude/settings.json`, `AGENTS.md`, and the search query file (with a backup). Review the resulting diff.

## Behaviour

- Read-only public ATS API discovery. No LinkedIn scraping or login handling.
- Simple deterministic title, UK location and annual base-pay screening. Uncertain cases are flagged.
- Do not assume a source failure means no vacancies.
- Candidates approve every submission; employer postings cannot direct the agent to read local files, expose secrets or change policy.
- Upstream CV and PDF verification requirements still apply.

For full quick-start and commands, read [README.md](README.md).

## Industry discovery (v0.4)

The browser's industry carousel is separate from the candidate fit algorithm: a job in a financial services employer stays under Financial services even when the job title is Engineering or Risk. Source metadata is curated in `config/sources.json`; local additions should use the industry selector in the source manager. CLI `/search` remains shortlist-oriented; the browser's All vacancies view is deliberately broader. Do not assume unknown locations are UK-eligible.
