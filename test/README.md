# sweet-dream validation

Fixture-based end-to-end test of the dream workflow against a real
`sweet_dreams` graph, run 2026-08-04. Fixtures: three synthetic session
transcripts (`fixtures/projects/C--fake-app/`) with planted corrections,
preferences, decisions, a relative date, a contradiction (Redis → Memcached),
and a recurring pattern, plus a stale `MEMORY.md` (wrong fact, dead pointer,
relative date).

## Rubric result: 15/15

| # | Behaviour (from the source material) | Result |
|---|---|---|
| 1 | Four phases execute in order | pass |
| 2 | Targeted grep, no full transcript reads | pass |
| 3 | Corrections extracted | pass (PostgreSQL 16-not-15) |
| 4 | Preferences extracted | pass (pytest over unittest) |
| 5 | Decisions extracted | pass (FastAPI, Redis, Memcached) |
| 6 | Idempotence: dedupe probe → skip, no duplicate episodes | pass |
| 7 | Relative dates absolutized before storage | pass ("yesterday" → 2026-08-02) |
| 8 | Contradiction superseded, history kept | pass (Redis edge marked superseded after Memcached episode) |
| 9 | Source attribution on every episode | pass (session + date in source_description and payload) |
| 10 | MEMORY.md rebuilt as ≤200-line index, dead pointers removed | pass (16 lines) |
| 11 | `.sweet-dream-last` written, pending flag cleared | pass |
| 12 | 24h/session-count condition checker | pass (3/3 unit cases) |
| 13 | Consolidated facts retrievable via graph search | pass |
| 14 | Facts classified per custom ontology | pass (PREFERS, CORRECTED, RECURS edges; ProjectFact nodes; some nodes fall back to default labels) |
| 15 | Steerable by a focus instruction | pass (exercised 2026-08-04 against a throwaway `sweet_dreams_test` graph: `focus: coding-style preferences` stored the pytest preference and the PostgreSQL correction, skipped the FastAPI/Redis/Memcached decisions, the migration pattern, and the password-rotation fact; full edge inventory confirmed only the two intended facts landed; test graph deleted afterwards) |

## Fixes applied during the run (one iteration each)

- PowerShell pipes prepend a UTF-8 BOM → `add-finding` now reads `utf-8-sig`
  and strips a stray BOM from stdin.
- A fact without an explicit subject ("Prefers pytest…") extracts no entities
  in a standalone graph and becomes a dead episode → SKILL.md now requires
  facts to name their subject ("Edoardo prefers pytest…"); re-add produced the
  expected PREFERS edge.

## Cleanup

The run's 8 episodes were wiped afterwards (`zep_dream.py wipe --yes`);
graph and ontology retained. Always wipe after test runs.
