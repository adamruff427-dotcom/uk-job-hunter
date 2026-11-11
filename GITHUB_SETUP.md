# Publish UK Job Hunter — GitHub steps

The GitHub connection available to this project can work with existing repositories but cannot create a new repository. Nothing in this release has been pushed to GitHub.

## 1. Create the PUBLIC repository

In your GitHub account, create a **new empty public repository** named `uk-job-hunter`. Do **not** auto-add a README, `.gitignore`, or licence because this release already includes them.

GitHub repository creation: https://github.com/new

Extract the downloaded zip into a local directory, open Terminal there, and run:

```bash
python3 -m unittest discover -s tests
python3 scripts/check_public_release.py
git init -b main
git add .
git status --short
git commit -m "feat: UK-wide search preview with optional Reed and Adzuna APIs"
git remote add origin https://github.com/YOUR_GITHUB_USERNAME/uk-job-hunter.git
git push -u origin main
```

Confirm the commit contains **only public code and example configuration** before pushing. Run `git status --short` and inspect files, even when the safety checker passes. GitHub may ask you to authenticate to push.

## 2. Keep your own version PRIVATE

Create a second, **private** repository called `uk-job-hunter-private` for any separately maintained personal configuration or private application workflows. Do not push an existing public repo with personal information in its history.

The public build writes profiles and tracking data into `local_config/`, which is excluded from Git. Keeping private information on disk is the safest default; it does not have to be committed to your private repo at all. If you later add a private synchronisation workflow, keep `.env` and credentials excluded there too.

## 3. Long-term maintenance

Treat the public repository as the upstream source. Pull new public releases into your personal version and keep the private configuration isolated. Contributors should open PRs to the public repository, and CI must run tests and privacy checks before merging.

## Before announcing a public launch

The included test suite is mocked and deterministic. The production checklist must include live source checks, data-provider licensing, search quality, expiration reconciliation, data protection, and user support. The local preview should not be described as a hosted service or a complete nationwide UK jobs index.
