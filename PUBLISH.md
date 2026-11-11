# Current publication

Public code and the minimal private workspace have been published. See
[GITHUB_SETUP.md](GITHUB_SETUP.md) for repository links and workflow permissions.
No public web hosting or private-data synchronization is enabled.

> For current step-by-step instructions for a new PUBLIC repository, see [GITHUB_SETUP.md](GITHUB_SETUP.md). The v0.5 baseline and subsequent index implementation are published.

# Publish UK Job Hunter as a new public GitHub repository

**Do not convert any personal/private job-search repository to public visibility.** This project must begin with a fresh Git history using this clean public-source folder.

Before publishing, inspect the included files, the `config/profile.example.json` template and `.gitignore`, and run the tests.

```bash
cd /path/to/uk-job-hunter-public
python3 -m unittest discover -s tests -v
# GitHub CLI: https://cli.github.com (install and authenticate if needed)
gh auth status
# Initialise a completely new repository with no private history.
git init -b main
git add .
git status --short
# Inspect the exact staged file list and sensitive-looking content before commit.
git diff --cached --name-only
git diff --cached --check
git commit -m "Initial public preview of UK Job Hunter"
# Publishes openly on GitHub — check staged files before executing.
gh repo create uk-job-hunter --public --source=. --remote=origin --push
```

Once published, turn on **GitHub private vulnerability reporting** if available, review repository Actions settings and branch protection, and confirm that CI is green. Do not upload actual CVs, local profiles, interview notes or application tracking records to GitHub Issues or pull requests.

If `uk-job-hunter` is already taken, choose another descriptive repository name. The public repository contains only the standalone UK scanner and optional overlay installer; the full upstream AI Job Search application workflow remains a separate MIT-licensed project.

For personal use, clone this public repository into a separate private working environment and create `local_config/search_profile.json` via `python3 -m uk_hunter init`. Keep private files out of any future public pull requests.
