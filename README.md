# UK Job Hunter

**Open-source, configurable UK job discovery and evidence-led shortlisting, now with a private local browser interface.**

**Latest: v0.5 wide-search connector preview.** The user-facing browser app lets jobseekers configure their preferences, scan jobs, explore industries in a horizontally scrollable carousel, explain each match, add employer boards, save job adverts, update application statuses and export their own tracker. No account or third-party Python package is required. This is not yet a hosted or production-validated service.

```bash
python3 -m uk_hunter web --open
```

Visit `http://127.0.0.1:8765` if the browser does not open. See [Quick start](QUICKSTART.md) and [Product roadmap](docs/PRODUCT_ROADMAP.md).


UK Job Hunter reads employer-published jobs from Greenhouse, Ashby, Lever and SmartRecruiters public APIs. An opt-in website adapter can also normalize schema.org JobPosting records from permitted public company careers pages. Optional credentialled **Reed UK and Adzuna UK** search connectors allow much broader discovery when enabled and appropriately licensed. They support pagination, bounded search requests and blank-keyword wide searches. The browser shows **all plausible UK vacancies returned by configured sources** by default and groups them by employer industry. Its separate fit filters screen against **your own** role, salary and working-location rules and produce a shortlist for review. No sign-in, automated applications, recruitment-site account scraping or personal data upload is required to run the scanner.

This repository is a **standalone UK scanner** and an optional extension for [AI Job Search](https://github.com/ai-job-search-dev/ai-job-search), which supplies the broader CV/letter/interview workflows. It is not endorsed by any of the job boards or employers.

## First run (Python 3.10+)

```bash
# After cloning or downloading the public repository:
python3 -m uk_hunter init
# Edit local_config/search_profile.json with the roles, pay and locations you want.
python3 -m uk_hunter search --format table
python3 -m uk_hunter search --format md --write-report reports/uk-shortlist.md
python3 -m unittest discover -s tests -v
```

There are no required third-party Python packages. If you do not run `init`, a **generic example** profile is used. That example has **no salary floor or home location** and does not pretend to match an individual's work history. Most roles will require human review until you configure your own profile.

### Configure your own search

1. Run `python3 -m uk_hunter init` to create `local_config/search_profile.json`.
2. Change `target_roles` and `related_terms` to suit real experience. Titles are matched by simple substrings, not AI inference.
3. Set `minimum_basic_salary_gbp` to an annual GBP amount (e.g. `45000`) or `null` for no threshold. Bonuses, OTE and commission are not counted as basic pay.
4. Fill `nearby_places` with places where you **would** commute; `hybrid_review_places` with places needing further checking; and `excluded_commute_places` with places you have ruled out. Empty lists mean **unknown**, not an assumed rejection.
5. Edit `config/sources.json` or provide an alternative source file using `--sources`. Greenhouse, Ashby, Lever, SmartRecruiters, opted-in structured company pages and optional Reed/Adzuna nationwide search are supported.

A personal local configuration is ignored by Git. **Never commit CVs, salary preferences, contact details, job-search history or API credentials to a public repository.**

### CLI

```bash
python3 -m uk_hunter search --format json --limit 15
python3 -m uk_hunter search --all --limit 250 --format table
python3 -m uk_hunter search -q "risk" --jobage 14 --format table
python3 -m uk_hunter search --remote remote --format md
python3 -m uk_hunter search --profile /path/to/profile.json --sources /path/to/sources.json
python3 -m uk_hunter detail "https://exact-job-url-returned-by-search" --format plain
```

`detail` does not fetch arbitrary URLs. It matches a job from the configured source feeds. Sources that fail are reported; when all sources fail, the CLI exits non-zero rather than claiming there are no jobs.

## Verdicts

| Verdict | Meaning |
|---|---|
| `SHORTLIST` | Direct title match, verified viable location and salary passes configured minimum (or no minimum is set). Still verify requirements. |
| `REVIEW` | Missing salary, unclear location or adjacent role; make a human decision. |
| `REJECT` | Explicit title exclusion, known pay below the minimum, UK-ineligible location or absent target-role match. |
| `SKIP_OLD` | The feed provides a reliable posted/created date older than the selected window. |

The numeric score is **a transparent sorting heuristic, not a qualification assessment or probability of an interview**. Employer boards may not disclose all essential requirements in structured fields; read the posting carefully before applying. Greenhouse `updated_at` is deliberately not treated as a posting date.

## Industry browsing and search coverage

The v0.5 browser defaults to **Search everything**, which retrieves vacancies from all configured sources across industries without applying personal suitability gates. **Search for me** runs the same broad discovery but displays only the matched/review subset. Either mode can be narrowed by industry or free-text search (including job descriptions). The command-line equivalent is `python3 -m uk_hunter search --all` (use `--limit` for more output). These modes do **not** search every UK website; they only cover configured sources.

The browser has a **horizontal industry carousel** with counts and a separate **Relevant to me** filter. Selecting an industry shows every discovered vacancy in that sector, including jobs that do not match the local candidate profile. Counts represent records returned by the configured sources **at scan time**, not UK-wide vacancy totals. Choosing *All industries* returns to the complete discovery set.

An industry describes the **employer's business**: a technology role in a bank belongs under Financial services. The system prefers the source registry's employer sector, then explicit industry metadata, then limited strong evidence in the posting; it uses *Unclassified* when uncertain. Employer sector is user-editable when adding a careers source. This categorisation is heuristic, not an official industry register.

The expanded registry includes **40 public company careers boards** spanning finance, technology, healthcare, defence, energy, property, consumer retail, transport, hospitality, charities and consulting, including Monzo, Octopus Energy, Wise, Healios, Kaluza, Trainline and Babyzone. The newly added company boards were checked against publicly visible careers pages on 11 November 2026; the complete live API feeds and future access still need end-to-end validation. Board slugs and access may change, and a reachable source is no guarantee of an active suitable vacancy. The two optional wider UK APIs provide a path to nationwide discovery, **not a guarantee of full UK labour-market coverage**. See [Wide search](docs/WIDE_SEARCH.md) for how to enable them, fair-use and licence requirements.

Clearly overseas-only adverts are excluded from the UK browsing view. Remote or unspecified postings whose UK eligibility cannot be established **remain visible for review**, not confirmed UK-eligible. Never infer permission to live or work in the UK from "Remote" alone.

Check each official careers site and its permitted use before deploying at scale. Respect API terms, attribution, rate limits and access controls.

## Using the upstream AI application workflows

If you want the original project's `/apply`, `/rank`, `/interview` and tracking workflows:

```bash
git clone --branch v1.7.5 --single-branch https://github.com/ai-job-search-dev/ai-job-search.git base-ai-job-search
python3 install_into_upstream.py --target ./base-ai-job-search
cd base-ai-job-search
python3 -m unittest discover -s tests -p 'test_uk_hunter_extension.py' -v
```

The installer preserves the original application workflows. It saves the original search-query configuration, installs the UK portal, and disables other portals by default (re-enable explicitly after reviewing their usage terms). It **never copies a personal profile from this public package** and will not overwrite an existing `config/search_profile.json`. Read the [UK extension guide](README_UK.md) and [Codex instructions](AGENTS.md).

## Security, privacy and licence

The ATS scanner executes read-only GET requests against fixed provider hosts. Optional website sources are user-configured, but require HTTPS, public DNS, robots permission, an explicit same-site job URL prefix and no redirect; they are NOT cleared for deployment as a hosted arbitrary-domain crawler. Employer descriptions are untrusted content. Never instruct an AI agent to execute text obtained from an advertisement. There is no auto-submit function.

Personal information stays in files on the user's computer **unless the user separately passes it to an external AI assistant or publishes it**. This scanner itself does not send candidate profiles to the job board APIs. Read [SECURITY.md](SECURITY.md) and [PRIVACY.md](PRIVACY.md).

For the source model, permissions and custom website setup, see [Source architecture](docs/SOURCES_ARCHITECTURE.md). For publishing instructions, see [PUBLISH.md](PUBLISH.md).

UK Job Hunter is released under the [MIT License](LICENSE). The optional upstream integration is derived from the public [AI Job Search](https://github.com/ai-job-search-dev/ai-job-search) workflow pattern (MIT; copyright © 2026 Mads Lorentzen). Preserve the original licence and copyright when redistributing its code. See [NOTICE.md](NOTICE.md).

## Development status

**Public product preview v0.5.** 106 automated tests passed locally, including Reed/Adzuna pagination, disabled sources and per-source error reporting. Live ATS API access and a full upstream end-to-end run have **not yet** been validated in this build environment. Features should not be described as production proven. Improvements and verified UK ATS sources are welcome via issues and pull requests.

## Publishing this version

**This ZIP is not yet pushed to GitHub.** A new empty public repository must first be created in the GitHub account. See [GitHub setup](GITHUB_SETUP.md) and run `python3 scripts/check_public_release.py` before the first commit. Keep your private `local_config/` out of public history.
