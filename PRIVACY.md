# Privacy model

The scanner reads public job feeds; it does **not upload candidate profiles, CVs or job-search history** to those APIs. Search-profile processing happens in the local Python program. Job boards will see the network request to their publicly documented GET API, including your network address and user-agent string. If you choose to paste candidate information into a cloud AI service, that is a separate action with that service's own data handling rules.

`python3 -m uk_hunter init` creates `local_config/search_profile.json`, excluded by `.gitignore`. Treat it as private. Other documents, reports and application tracking records should stay in local ignored paths. Do not publish logs containing CV content or personal identifiers.

To contribute, use synthetic roles, fictional locations and placeholder salaries in tests and examples. Review every file that `git add` has staged, including Git history if repository visibility is changing from private to public. **Never make a populated private working repository public in place.** Create a separate clean public repository from this sanitized source.

## Local browser app (v0.3)

The web interface uses a Python HTTP server bound to `127.0.0.1` only. It is not publicly accessible or hosted remotely. The browser sends settings and application-tracker changes to that local server, which saves files under Git-ignored `local_config/` with private file permissions on POSIX systems. No analytics, ads, third-party scripts or CV uploads are included. The app's scan requests fetch job adverts from the configured public employer APIs, explicitly selected company careers pages or, when separately enabled, the licensed Adzuna API. Provider calls do not include personal profile data, but configured search keywords may be included in an Adzuna API query.

The "Preview example jobs" control uses fictional local data. The browser displays employer-provided text as text, not executable HTML. JSON export contains your saved jobs and notes; handle exports as personal data.

**A future hosted version would have a different data-processing model and needs a fresh privacy review, published notice, appropriate security controls and deletion/export policy before launch.**
