"""Fixture-based tests for scripts/mine_transcript.py (stdlib unittest)."""

import contextlib
import io
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

import mine_transcript  # noqa: E402

FIXTURES = os.path.join(
    os.path.dirname(__file__), "fixtures", "projects", "C--fake-app"
)


def run_mine(*argv):
    """Run main() with argv, capturing stdout; return (exit_code, output)."""
    buf = io.StringIO()
    argv0 = sys.argv
    sys.argv = ["mine_transcript", *argv]
    try:
        with contextlib.redirect_stdout(buf):
            code = mine_transcript.main()
    finally:
        sys.argv = argv0
    return code, buf.getvalue()


def records(output):
    return [json.loads(line) for line in output.splitlines() if line.strip()]


class FixtureMining(unittest.TestCase):
    def test_correction_and_preference_hits_pair_with_answers(self):
        code, out = run_mine(os.path.join(FIXTURES, "session-aaa1.jsonl"))
        self.assertEqual(code, 0)
        recs = records(out)
        self.assertEqual(len(recs), 4)  # 2 hits x (user + assistant answer)
        self.assertEqual([r["role"] for r in recs],
                         ["user", "assistant", "user", "assistant"])
        self.assertIn("PostgreSQL 16", recs[0]["text"])
        self.assertIn("pytest", recs[2]["text"])
        # the assistant record answers its user record
        self.assertIn("pytest", recs[3]["text"])

    def test_count_mode_matches_full_mode(self):
        files = sorted(
            os.path.join(FIXTURES, f)
            for f in os.listdir(FIXTURES) if f.endswith(".jsonl")
        )
        code, out = run_mine("--count", *files)
        self.assertEqual(code, 0)
        lines = out.strip().splitlines()
        self.assertEqual(len(lines), len(files))
        for line, path in zip(lines, files):
            n, p = line.split("\t")
            self.assertEqual(p, path)
            self.assertEqual(n, "2")  # each fixture plants 2 signal lines
            _, full = run_mine(path)
            self.assertEqual(int(n) * 2, len(records(full)))


class SyntheticTranscripts(unittest.TestCase):
    def write_jsonl(self, entries):
        fd, path = tempfile.mkstemp(suffix=".jsonl")
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            for e in entries:
                if isinstance(e, str):
                    f.write(e + "\n")  # raw line (e.g. unparseable)
                else:
                    f.write(json.dumps(e) + "\n")
        self.addCleanup(os.unlink, path)
        return path

    def user(self, text):
        return {"type": "user", "message": {"role": "user", "content": text},
                "timestamp": "2026-08-01T00:00:00Z"}

    def assistant(self, text):
        return {"type": "assistant",
                "message": {"role": "assistant", "content": text},
                "timestamp": "2026-08-01T00:00:01Z"}

    def test_assistant_lines_never_match(self):
        path = self.write_jsonl([
            self.user("plain status update, nothing to see"),
            self.assistant("You are wrong, I always prefer this."),
        ])
        code, out = run_mine(path)
        self.assertEqual((code, out.strip()), (0, ""))

    def test_block_content_and_bad_lines(self):
        blocks = {"type": "user", "timestamp": "2026-08-01T00:00:00Z",
                  "message": {"role": "user", "content": [
                      {"type": "text", "text": "We decided to switch."},
                      {"type": "tool_use", "name": "x"}]}}
        path = self.write_jsonl(["{not json", blocks, self.assistant("ok")])
        code, out = run_mine(path)
        self.assertEqual(code, 0)
        recs = records(out)
        self.assertEqual(len(recs), 2)
        self.assertEqual(recs[0]["text"], "We decided to switch.")

    def test_consecutive_user_hits_have_no_dangling_answer(self):
        path = self.write_jsonl([
            self.user("Actually that's wrong."),
            self.user("And I prefer the other way."),
            self.assistant("Both noted."),
        ])
        recs = records(run_mine(path)[1])
        self.assertEqual([r["role"] for r in recs],
                         ["user", "user", "assistant"])

    def test_markers_override(self):
        path = self.write_jsonl([self.user("ship it friday")])
        _, out = run_mine("--markers", "friday", path)
        self.assertEqual(len(records(out)), 1)
        _, out = run_mine("--markers", "monday", path)
        self.assertEqual(out.strip(), "")


if __name__ == "__main__":
    unittest.main()
