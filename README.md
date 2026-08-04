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

## How it works

```
Session ends
  └─ Stop hook: should-dream.sh (~10ms)
       24h elapsed AND 3+ new sessions? ──no──> exit silently
       └─yes─> touch ~/.claude/.sweet-dream-pending
Next session
  └─ skill sees the flag ─> 4-phase dream
       ORIENT       graph + local memory state
       GATHER       targeted grep over recent *.jsonl transcripts
       CONSOLIDATE  dedupe → supersede contradictions → graph.add episodes
       PRUNE&INDEX  MEMORY.md ≤200 lines, Quick Reference from graph.search
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

## Install (plugin — recommended)

```
/plugin marketplace add EDZ111/sweet-dream
/plugin install sweet-dream@sweet-dream
```

The Stop hook registers automatically with the plugin. Then run the one-time
graph setup:

```bash
pip install zep-cloud
python <plugin-cache>/sweet-dream/scripts/zep_graph_setup.py
```

(or just ask Claude to run the sweet-dream onboarding — the skill knows how).

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
status                    graph health, ontology, recent episodes and facts
check --text "..."        dedupe probe before adding
add-finding [--file f]    add finding(s) as JSON episodes
search --query Q          search edges / nodes / episodes
quickref                  top valid facts for the MEMORY.md Quick Reference
wipe --yes                delete all episodes (test-data cleanup)
```

`scripts/zep_graph_setup.py [--reset]` creates (or drops and recreates) the
graph, user, and ontology. Idempotent.

## Test

`test/` contains fixture transcripts with planted signals and the 15-item
rubric the workflow was validated against (14/15). After any test run, clean
the graph: `python scripts/zep_dream.py wipe --yes`.
