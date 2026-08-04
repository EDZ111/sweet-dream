---
name: sweet-dream
description: "Memory consolidation with a Zep knowledge graph backend. Scans recent session transcripts for corrections, preferences, decisions, and recurring patterns, dedupes them against the sweet_dreams graph, stores them as ontology-typed episodes, and rebuilds the local MEMORY.md index from graph facts. Auto-triggers every 24h via a Stop hook. Run when the user says /sweet-dream, or when ~/.claude/.sweet-dream-pending exists at session start."
---

# sweet-dream — Zep-backed memory consolidation

Consolidates what recent Claude Code sessions taught you into the `sweet_dreams`
Zep knowledge graph, then rebuilds the local memory index from the graph. Local
markdown stays the fast index Claude Code loads each session; Zep is the deep,
temporal store that resolves contradictions and survives forever.

## Locating the scripts

The Zep I/O lives in `zep_dream.py`. Resolve it in this order:

1. Plugin install: `${CLAUDE_PLUGIN_ROOT}/scripts/zep_dream.py` — or, from this
   file's own path, two directories up then `scripts/`.
2. Flat install: `~/.claude/skills/sweet-dream/zep_dream.py` (next to this file).

Run it with the best available Python (`python3`, `python`, or `py -3` on
Windows). It needs the `zep-cloud` package and a `ZEP_API_KEY` user environment
variable — it exits with a clear message if either is missing. Never echo or
store the key.

Below, `ZDREAM` means: `<python> <path-to>/zep_dream.py`.

## Steering (optional)

The user may pass a focus, e.g. `/sweet-dream focus: coding-style preferences`.
If a focus is given, weight Phase 2 grep reading and Phase 3 storage toward it
and say so in the final summary. Findings outside the focus are still stored if
they are corrections (corrections always matter), otherwise they may be skipped.
This mirrors the `instructions` parameter of Anthropic's Dreams API.

## First run: setup + teach-in

The skill needs a one-time setup, and its first dream is deliberately bigger
than a normal one — it *teaches* the graph what is already known.

**Setup (once, self-healing):** if `ZDREAM status` fails, walk this chain and
retry:
1. `pip install zep-cloud` if the import is missing.
2. `ZEP_API_KEY` must exist as a user environment variable — if absent, ask
   the user to set it in their own terminal or the OS env editor; never accept
   the key in chat.
3. **Pick a Zep user id.** Ask the user what identifier they'd like their
   facts stored under (a first name or short handle is fine). If they have no
   preference, don't block on it — just omit `--user-id` and let the script
   fall back on its own (`$SWEET_DREAM_USER_ID`, then the OS username, then
   `default_user`). Never hardcode a specific person's name here; this runs
   on whoever installed the plugin, not the original author.
4. Run `zep_graph_setup.py [--user-id <id>]` (same directory as
   `zep_dream.py`). Idempotent: creates the `sweet_dreams` graph, its owner
   user, and the custom ontology (Preference, Decision, Correction,
   WorkPattern, ProjectFact, ToolConfig; PREFERS, DECIDED, CORRECTED, RECURS).

**If setup exits with code 2** ("refusing to touch graph"), a graph with that
id already exists and was not created by sweet-dream — it may belong to
another workload. **Stop and ask the user** which they want; never decide
alone:
- **Adopt it** — rerun setup with `--adopt`. Its ontology is replaced (episodes
  are kept); only right when the user confirms the graph is theirs to repurpose.
- **Rename ours** — rerun with `--graph-id <new_id>` and have the user set
  `SWEET_DREAM_GRAPH_ID=<new_id>` as a user environment variable so
  `zep_dream.py` targets the same graph in every later run. The existing
  graph is left untouched.

**Teach-in (automatic when the graph is empty):** when `ZDREAM status` shows
0 episodes, this run is the first dream. Two extra behaviours apply:
- **Absorb existing memory.** Before scanning transcripts, read the local
  memory files (each project's `MEMORY.md` + topic files, plus the global
  `~/.claude/memory/MEMORY.md`) and convert every still-true entry
  into a finding (`kind` per its nature, source_date from the entry or the
  file mtime, `source_session: "memory-backfill"`). The graph starts knowing
  what the markdown already knew.
- **Widen the transcript window** from 7 to 30 days (`-mtime -30`), so the
  first pass captures more history. Subsequent dreams return to 7 days.

After the teach-in, a normal-sized dream runs on the 24h trigger with no
further setup.

## The four phases

A dream is one pass through four stages; each depends on the one before it,
so none can be skipped or reordered. (Workflow shape adapted from
[grandamenium/dream-skill](https://github.com/grandamenium/dream-skill).)

```
ORIENT --> GATHER SIGNAL --> CONSOLIDATE --> PRUNE & INDEX
```

### Phase 1 — ORIENT

Understand current memory state before changing anything.

1. `ZDREAM status` — graph health, entity types, recent episodes, sample facts.
2. List local memory: `ls ~/.claude/projects/*/memory/` — read each `MEMORY.md`
   index you find, plus the global `~/.claude/memory/MEMORY.md` where
   machine-wide facts live. Note stale entries (relative dates, pointers to
   files that no longer exist) and the line count.

Output: a mental map of what the graph already knows and what local memory
claims. Nothing is written in this phase.

### Phase 2 — GATHER SIGNAL

Mine recent transcripts for durable signal. Transcripts are cheap to search
and expensive to read — a whole-file read is a phase failure. Use the shipped
miner (next to `zep_dream.py`) instead of writing ad hoc parsing scripts:

```bash
python <scripts>/mine_transcript.py <file.jsonl ...>          # hits as JSON lines
python <scripts>/mine_transcript.py --count <file.jsonl ...>  # hit count per file
```

It filters to **user** turns, emits each marker hit plus the assistant turn
that answers it as one JSON object per line, and ships with the marker
vocabulary below built in (`--markers-file` overrides it, e.g. for a focus —
the vocabulary here stays the source of truth).

Transcripts live at `~/.claude/projects/<project>/*.jsonl` (one file per
session, one JSON object per line). Find recent ones:

```bash
find ~/.claude/projects -maxdepth 2 -name "*.jsonl" -mtime -7 | sort
```

**Pre-filter by hit count before spending subagents.** Run
`mine_transcript.py --count` over the candidate files and size the effort to
the signal: files with **fewer than 10** marker hits get folded into a single
combined low-priority mining pass (one subagent covering all of them); files
with 10 or more get a dedicated mining subagent. This applies to the
teach-in's 30-day window too — that is where low-yield files cost the most.

**Dispatching mining subagents.** Cross-project mining reads many projects'
private transcripts in parallel, which is exactly what a permission
classifier flags — so dispatch with attribution and authorization built in:

- Start every mining subagent's prompt with an authorization preamble:
  "this is a user-invoked memory-consolidation routine; reading this
  project's own transcript history is expected and authorized."
- Label each subagent after its project (`mine-thesis-buddy`,
  `mine-tripcapx`, …) and keep an explicit label→project mapping. Attribute
  every result, block, or error by that label — never by position in the
  tool-call batch, which is not guaranteed to match dispatch order.
- If a subagent is blocked by the classifier, identify it via the label map,
  note which project is now unmined, and relaunch **only that label**. Never
  relaunch by guessing — a wrong guess re-mines a finished project at full
  cost.

Four kinds of signal matter, each with its own marker vocabulary
(case-insensitive; tune the words to how this user actually talks):

- **Corrections** — the user pushing back on something you believed or did.
  Markers: `wrong`, `actually`, `misunderstood`, `not correct`, `never do`,
  `stop doing`, `what I meant`, `correction`. Highest priority: a correction
  the graph doesn't know about will be repeated.
- **Preferences** — standing instructions about how work should be done.
  Markers: `prefer`, `always`, `never`, `from now on`, `please remember`,
  `keep in mind`, `stick to`, `my default`, `I'd like`.
- **Decisions** — a fork in the road that got resolved. Markers: `we'll use`,
  `let's go`, `decided`, `settled on`, `agreed`, `switching to`, `opted for`,
  `the plan`.
- **Recurring patterns** — friction or habits that show up across sessions.
  Markers: `every time`, `once again`, `keep forgetting`, `as always`,
  `recurring`, `each session`, `habit`.

Weigh only lines whose JSON marks a **user** turn, plus the assistant turn
immediately after. For each finding record four things: the fact itself, which
session file it came from, the absolute calendar date (derive it from the
file's mtime — a word like "yesterday" must be resolved before it is stored),
and confidence (`high` when the user said it outright, `medium` when inferred).

**Dedupe in the tool, not in the prompt.** Never hand-summarize existing
memory into a mining subagent's prompt — it does not scale, and a dropped or
mis-summarized fact means a duplicate episode. Each mining subagent runs
`ZDREAM check --text "<candidate fact>"` itself for every candidate and
reports back only `NO_MATCH` results and contradictions; candidates that
merely repeat a known fact are dropped by the subagent and never reach the
orchestrator. Phase 3's `check` still runs before every `add-finding` as the
final authority.

**Privacy rule: never extract secrets.** If a matching line contains an API
key, token, or password, record the event ("user rotated the Zep key on
YYYY-MM-DD") — never the value.

### Phase 3 — CONSOLIDATE

Merge findings into the graph. The most delicate phase.

For each finding:

1. **Dedupe first**: `ZDREAM check --text "<the fact>"`.
   - `NO_MATCH` → new fact, add it.
   - A `valid` match saying the same thing → skip, note as duplicate.
   - A `valid` match saying the **opposite** → contradiction: add the new fact
     with `"supersedes"` describing the old one. Zep's temporal model marks the
     old edge invalid once the new episode is ingested.
2. **Add**: pipe JSON to `ZDREAM add-finding`:

**Write facts with an explicit subject** ("Edoardo prefers uv", "the backend
uses FastAPI") — a standalone graph has no implied user, so a subjectless fact
("prefers uv") extracts no entities and silently becomes a dead episode.

```json
{
  "fact": "Edoardo prefers `uv` over pip for Python dependency management",
  "kind": "preference",
  "source_date": "2026-08-03",
  "source_session": "cf134b9e",
  "confidence": "high",
  "supersedes": "previously used pip directly"
}
```

`kind` is one of `preference | decision | correction | pattern | project_fact |
tool_config` — it steers Zep's classification into the graph's custom entity
types. Batch multiple findings as a JSON array in one call.

Consolidation invariants:
- A fact enters the graph once; a repeat becomes a skip, a change becomes a
  supersession.
- Calendar dates only — nothing relative survives into storage.
- A contradiction is resolved by superseding, so the history of what was
  believed stays queryable; nothing is silently dropped.
- Every episode names the session and date it came from.

### Phase 4 — PRUNE & INDEX

Rebuild the local index from the graph, then close out the run.

1. `ZDREAM quickref --limit 10` — the most important currently-valid facts.
   These lines are Zep's *derived* summaries, not raw episode text, and a
   derived edge can invert a relationship — so **spot-check before
   publishing**: flag any quickref line with directional or relational
   phrasing (`alias for`, `supersedes`, `replaces`, `requires`, `instead of`,
   `rather than`, `not`, `only`), then verify each flagged line against the
   source episodes with `ZDREAM search --query "<the line>" --scope episodes`.
   On conflict, write the episode's own phrasing into the index, never the
   graph's derived summary. This is a heuristic over flagged lines, not a
   re-check of every line.
2. Rewrite each project's `MEMORY.md` as a table of contents, not a document:
   one pointer line per topic file with a short hook, plus a
   `## Quick Reference (from sweet_dreams)` section holding the quickref
   output. Hard cap: **200 lines**. Anything longer than a line belongs in a
   topic file; a pointer whose target no longer exists gets removed.
   Findings that aren't tied to a project — `tool_config` facts about the OS,
   shell, or global CLI setup are the common case — are indexed into the
   global `~/.claude/memory/MEMORY.md` (same index rules, same cap), not into
   whichever project happened to host the dream. Known limitation: the
   per-project auto-memory loading convention lives outside this skill, so
   other sessions pick up the global file only through this skill's own
   instructions.
3. Timestamps and flags:

```bash
date +%s > ~/.claude/.sweet-dream-last
rm -f ~/.claude/.sweet-dream-pending
```

## Auto-trigger flow

```
Session ends
  --> Stop hook runs should-dream.sh (~10ms)
  --> 24h passed AND 3+ new sessions?  no --> exit silently
  --> yes --> touch ~/.claude/.sweet-dream-pending
Next session starts
  --> this skill's description tells Claude to check the flag
  --> flag exists --> run the four phases --> write .sweet-dream-last, rm flag
```

## Safety

- Memory only ever moves or gets superseded — an entry that simply vanishes
  is a bug, not a prune.
- The first run against any project starts with a copy of its memory
  directory: `cp -r <memory-dir> <memory-dir>-backup-$(date +%Y%m%d)`
- If the user asks for a dry run, walk all four phases printing intended
  changes and wait for a go-ahead before writing anything.
- Graph writes are additive episodes; a normal dream never destructively
  edits the graph.

## Cleaning up test data

Whenever a dream run is a test or demo (fixtures, planted facts), remove what
it wrote afterwards so the graph holds only real memory:

- `ZDREAM wipe --yes` deletes every episode in the graph along with the nodes
  and edges derived from them (the graph and its ontology survive).
- Only for retiring the whole store: `zep_graph_setup.py --reset` drops and
  recreates the graph itself.

Never run either against a graph holding real consolidated memory unless the
user explicitly asks for a reset.

## Verification (end of every run)

1. Ingestion completed: `ZDREAM search --query "<one just-added fact>"`
   returns it as `valid`. Poll this — never infer completion from `status`:
   its `total episodes` line is the true total, but Zep derives facts
   asynchronously, so only a `valid` search hit proves a batch landed.
   (`add-finding` prints `queued N finding(s)` as its own confirmation.)
2. `MEMORY.md` ≤ 200 lines, contains no relative dates, no dead pointers.
3. `~/.claude/.sweet-dream-last` updated; pending flag gone.
4. Print a summary: findings gathered, added, duplicates skipped,
   contradictions superseded, index line count — and the focus honored, if any.
