# GitHub publication

Public code: https://github.com/adamruff427-dotcom/uk-job-hunter

Private minimal workspace: https://github.com/adamruff427-dotcom/uk-job-hunter-private

Both repositories were created from new sanitized histories. The private repository
contains a launcher and documentation only; profiles, credentials and trackers stay
local and ignored. The public engine is reused rather than forked privately.

The local CLI token could create repositories and push code but could not upload
GitHub Actions files without the `workflow` scope. The connected GitHub app was
able to create the workflow using its separate permissions. Future workflow edits
through the CLI may require `gh auth refresh -h github.com -s workflow`, or the
connected app. This scope does not prevent ordinary code pushes.

Before every publication, run Python and browser tests, inspect staged file names
and contents and run the release hygiene checker. Never add local configuration,
SQLite databases, tracker exports, personal reports or credentials. Preserve LICENSE
and NOTICE.md. GitHub Actions tests use synthetic data, not live provider credentials.
