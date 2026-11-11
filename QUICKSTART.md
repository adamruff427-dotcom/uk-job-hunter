# UK Job Hunter — getting started

This release is a **local browser product preview**, not a hosted website. You need Python 3.10+ on a Mac, Windows or Linux computer. No pip packages or account are required to use the browser interface.

1. Extract this ZIP to a directory on your computer.
2. Open Terminal (macOS/Linux) or PowerShell (Windows) in that directory.
3. Start the app:

   ```bash
   python3 -m uk_hunter web --open
   ```

   On Windows, use `py -m uk_hunter web --open` if `python3` is unavailable.
4. The app opens at **http://127.0.0.1:8765**. If the browser doesn't open automatically, paste that address into it.
5. Select **My preferences** to enter roles, annual base salary and the areas you would commute to. Save.
6. Choose **Preview example jobs** to explore 10 *fictional* vacancies across several industries, or **Scan live jobs** to query the configured employer sources.
7. Swipe or use the arrows on **Explore by industry** and select a sector. Select **All industries** to reset; use **Relevant to me** to limit results to roles that passed the initial profile triage. To cover more companies, use **My preferences → Employer sources** and add an employer's public Greenhouse, Lever, Ashby or SmartRecruiters career-board URL. Pick that employer's industry to classify its jobs.
8. To add a **normal company website** (not one of the four ATS services), provide its HTTPS careers URL plus a *job detail page path prefix* such as `/careers/jobs/`. The website must publish schema.org JobPosting data and allow this access via `robots.txt`. No structured data = explicit failure rather than invented vacancies. More details in [Source architecture](docs/SOURCES_ARCHITECTURE.md).
9. To expand beyond the 42 configured employer feeds, configure optional credentialled **Reed and Adzuna** integrations for broad UK search. Copy source examples to your ignored local sources override and set the API keys in your environment, never the repository. Review commercial terms before publication. See [Wide search](docs/WIDE_SEARCH.md).
10. Save promising real vacancies under **My applications**, add notes, update their status or export the tracker as JSON.
11. Press **Ctrl+C** in the terminal to stop the app.

## Persistent browsing (v0.6)

Run `python3 -m uk_hunter refresh`, or select **Refresh sources** in the local app.
Search buttons then read the saved index. Use `python3 -m uk_hunter search --indexed --all`
for offline CLI browsing. Optional licensed and website sources require explicit
permission review in addition to credentials/enabling; see [Index](docs/INDEX.md).

## Important limitations

The scanner knows only the employer sources and optional licensed providers configured under `config/sources.json` or locally through the app. 42 configured employer boards are included as starting sources across several industries; this is not comprehensive UK job search. Some industries have no default coverage. An employer may change board provider or restrict API access, and requests can fail. A failed feed is shown as a source error, not evidence that no jobs exist.

Industry reflects the employer, not the job title, and may be unclassified when evidence is missing. Overseas-only adverts are excluded when this is unambiguous; remote eligibility can still be unknown. The product does not verify your qualifications, write applications, import CVs, submit forms or check the latest state of a job when you open it later. The initial matching is conservative keyword/rule triage, not an AI opinion or a prediction of being hired. Always read the employer's advert.

All preferences, notes and tracking history are stored in `local_config/` on your computer; the app does not transmit them to job sources. It only listens on your computer's loopback address and includes no third-party tracking scripts. Public employer APIs still receive standard requests from your computer, including IP address.

## Development and tests

```bash
python3 -m unittest discover -s tests -v
```

For technical and product priorities see `docs/PRODUCT_ROADMAP.md`. For developer instructions see `CODEX_HANDOFF.md`.

## Search everything (v0.4.1)

Click **Search everything** on the Discover tab to retrieve all available listings from every configured source, without limiting results to your profile. The industry carousel and text box narrow the results *after* discovery. Click **Search for me** to show only potential matches from those same sources. **Search everything** clears prior text and industry filters so no opportunities disappear silently.

From Terminal, run `python3 -m uk_hunter search --all --limit 250 --format table`. This is **all connected sources**, not every website in the UK; add more supported employers under My preferences.

## What is new in v0.5

Search Everything still shows all records returned by enabled feeds (rather than filtering to your experience). New: **Source coverage and errors** expands to show each employer/API's status and raw result count. Optional UK-wide Reed/Adzuna sources have capped pagination; disabled providers make no requests. Live provider results are not yet end-to-end verified.
