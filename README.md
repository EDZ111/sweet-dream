# sweet-dream

Memory consolidation for Claude Code with a **Zep knowledge-graph backend**.

While you sleep, your agent dreams: it mines recent session transcripts for
corrections, preferences, decisions, and recurring patterns, stores them as
ontology-typed facts in the `sweet_dreams` Zep graph, and rebuilds the local
`MEMORY.md` as a lean index fed from the graph. Zep's temporal model resolves
contradictions automatically — a superseded fact stays queryable as history
instead of being deleted.

**Attribution:** the four-phase consolidation workflow (Orient → Gather Signal
→ Consolidate → Prune & Index) and the 24-hour Stop-hook trigger are adapted
from [grandamenium/dream-skill](https://github.com/grandamenium/dream-skill),
re-expressed and re-backed onto Zep. The dream concept mirrors Anthropic's
[managed-agents Dreams](https://platform.claude.com/docs/en/managed-agents/dreams)
and [memory stores](https://platform.claude.com/docs/en/managed-agents/memory).

## Privacy & data processing

**sweet-dream sends your data to a third party.** Everything a dream run
extracts — facts mined from your session transcripts (corrections,
preferences, decisions, project details, workflow patterns) — is stored in
**Zep Cloud**, a hosted service operated by Zep Software, Inc. That means
excerpts of how you work, and the substance of what you tell your agent,
leave your machine and are processed under Zep's terms, not yours.

Before using sweet-dream, read
[Zep's Terms of Service](https://www.getzep.com/legal/terms/) and
[Zep's Privacy Policy](https://www.getzep.com/legal/privacy/) **carefully**
and decide whether you are comfortable with that processing — including
retention, subprocessors, and any use of data for service improvement.
Do not run sweet-dream on transcripts containing employer-confidential,
client-confidential, or otherwise restricted material unless you have
verified Zep's terms permit it.

sweet-dream never extracts secrets by design (see
[SECURITY.md](SECURITY.md)), but "no secrets" is not "no personal data" —
the facts it stores are still about you. If you want memory consolidation
without third-party processing, follow the planned work on local GraphRAG
backends in the issue tracker.

## How it works

```
Session ends
  └─ Stop hook: should-dream.sh (~10ms)
       24h elapsed AND 3+ new sessions? ──no──> exit silently
       └─yes─> touch ~/.claude/.sweet-dream-pending
Context fills up mid-session
  └─ PreCompact hook (auto): should-dream.sh with MIN_SESSIONS=1
       24h elapsed? ──no──> exit silently
       └─yes─> touch the same flag
Next session
  └─ skill sees the flag ─> 4-phase dream
       ORIENT       graph + local memory state (per-project + global)
       GATHER       mine_transcript.py over recent *.jsonl, hit-count pre-filter
       CONSOLIDATE  dedupe in the tool → supersede contradictions → graph.add
       PRUNE&INDEX  MEMORY.md ≤200 lines, spot-checked Quick Reference
```

Facts are classified against a custom graph ontology:

| Entities | Edges |
|---|---|
| Preference, Decision, Correction, WorkPattern, ProjectFact, ToolConfig | PREFERS, DECIDED, CORRECTED, RECURS |

## Requirements

- A [Zep Cloud](https://app.getzep.com) account and API key, exposed as a
  **user environment variable** `ZEP_API_KEY` (never commit it, never paste it
  into a chat).
- Python 3.10+ with `pip install zep-cloud`.
- Git Bash on Windows (hook scripts are bash).

## Getting a free Zep API key

1. Go to [app.getzep.com](https://app.getzep.com) and sign up — Zep offers a
   free tier that's enough to run sweet-dream.
2. Once you're in the dashboard, create a project (or use the default one).
3. Open the project's **API Keys** settings and generate a new key.
4. Set it as a **user-scope environment variable** named `ZEP_API_KEY` —
   never put it in a `.env` file that could get committed, and never paste it
   into a chat, commit message, or issue.

   ```bash
   # macOS / Linux — add to ~/.zshrc or ~/.bashrc, then restart your shell
   export ZEP_API_KEY="your-key-here"
   ```

   ```powershell
   # Windows — sets it at user scope; restart your terminal/Claude Code session after
   setx ZEP_API_KEY "your-key-here"
   ```

   On Windows, a Claude Code session started before the variable was set won't
   see it — start a fresh session (or a fresh shell) after running `setx`.

5. Verify it's picked up: `python scripts/zep_dream.py status` should print
   graph info instead of an API-key error.

If a key ever leaks, rotate it immediately from the same **API Keys** page at
[app.getzep.com](https://app.getzep.com). See [SECURITY.md](SECURITY.md) for
the full secrets policy.

## Install (plugin — recommended)

```
/plugin marketplace add EDZ111/sweet-dream
/plugin install sweet-dream@sweet-dream
```

The Stop hook registers automatically with the plugin. Then run the one-time
graph setup:

```bash
pip install zep-cloud
python <plugin-cache>/sweet-dream/scripts/zep_graph_setup.py --user-id you
```

`--user-id` is optional — omit it and the script falls back to
`$SWEET_DREAM_USER_ID`, then your OS username, then `default_user`.

(or just ask Claude to run the sweet-dream onboarding — the skill knows how,
including asking you what user id to use).

## Install (flat fallback)

```bash
bash install.sh --auto
```

## Use

- `/sweet-dream` — run a dream now.
- `/sweet-dream focus: coding-style preferences` — steer the run; corrections
  are always kept, other out-of-focus findings may be skipped.
- Or let the 24h auto-trigger flag it and the next session dream on its own.

## Tooling

`scripts/zep_dream.py` is the only thing that touches Zep:

```
status                    graph health, ontology, true episode total + facts
check --text "..."        dedupe probe before adding
add-finding [--file f]    add finding(s); prints "queued N" when done
search --query Q          search edges / nodes / episodes
quickref                  top valid facts for the MEMORY.md Quick Reference
wipe --yes                delete all episodes (test-data cleanup)
```

`scripts/mine_transcript.py [--count] [--markers-file F] <file.jsonl ...>`
does the transcript reading for Phase 2: filters to user turns matching the
signal-marker vocabulary (built in, overridable), emits each hit plus the
assistant turn that answers it as structured JSON, and `--count` prints
per-file hit counts for the pre-filter. Stdlib-only — no Zep needed.

Local memory is per-project under `~/.claude/projects/<project>/memory/`,
plus a global `~/.claude/memory/MEMORY.md` for machine-wide facts (OS, shell,
global CLI setup) that belong to no single project.

`scripts/zep_graph_setup.py [--graph-id ID] [--user-id ID] [--adopt] [--reset]`
creates the graph, user, and ontology. Idempotent, and **ownership-aware**: if a graph
with the target id already exists but wasn't created by sweet-dream, setup
refuses (exit 2) instead of overwriting its ontology. You then choose:
`--adopt` to claim it (episodes kept, ontology replaced), or `--graph-id`
plus a `SWEET_DREAM_GRAPH_ID` env var to use a different name and leave the
existing graph alone. `--reset` honors the same guard.

## Test

`test/` contains fixture transcripts with planted signals, the 15-item rubric
the workflow was validated against (14/15), and a stdlib unittest suite for
the miner:

```bash
python -m unittest test.test_mine_transcript
```

After any test run against the real graph, clean it:
`python scripts/zep_dream.py wipe --yes`.

## License

[MIT](LICENSE). Security policy in [SECURITY.md](SECURITY.md).
