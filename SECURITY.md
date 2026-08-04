# Security

## Reporting a vulnerability

Please report vulnerabilities privately via GitHub's
[security advisories](../../security/advisories/new) for this repository.
Do not open a public issue for security problems.

## Secrets

This project never stores credentials:

- `ZEP_API_KEY` is read from the environment only (`zep_dream.py`,
  `zep_graph_setup.py`). It is never written to any file, log, or setting.
- Never paste an API key into a chat with an AI assistant, a commit message,
  or an issue. If a key leaks anywhere, rotate it at
  [app.getzep.com](https://app.getzep.com) immediately.
- The consolidation skill has an explicit rule to never extract secret values
  from transcripts into memory — only the fact that a secret event happened.

## Scope notes

- The Stop hook (`should-dream.sh`) runs locally, reads only file mtimes, and
  touches a single flag file; it makes no network calls.
- All network traffic goes to the Zep Cloud API over HTTPS via the official
  `zep-cloud` SDK.
