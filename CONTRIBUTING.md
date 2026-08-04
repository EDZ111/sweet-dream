# Contributing

Issues and pull requests are welcome.

## Ground rules

- **Never commit secrets.** No API keys, tokens, or real session transcripts —
  `.env*` files are gitignored; keep them that way. See
  [SECURITY.md](SECURITY.md) for the full policy.
- **Test data stays synthetic.** Fixtures under `test/` use planted facts
  about fake projects. If a test run touches a real Zep graph, wipe it
  afterwards (`python scripts/zep_dream.py wipe --yes`) or, better, use a
  throwaway `SWEET_DREAM_GRAPH_ID`.
- **Python is stdlib-only** except `zep-cloud` (Zep I/O only). Don't add
  dependencies without an issue first.
- **Shell scripts are bash with LF endings** — `.gitattributes` enforces this;
  don't fight it.

## Before opening a PR

Run the same checks CI runs:

```bash
python -m unittest test.test_mine_transcript
python -m py_compile scripts/zep_dream.py scripts/mine_transcript.py scripts/zep_graph_setup.py
bash -n install.sh scripts/should-dream.sh scripts/sweet-dream-hook.sh
```

If you change the dream workflow (`skills/sweet-dream/SKILL.md`), say in the
PR description which rubric item from `test/README.md` it affects.
