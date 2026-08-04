"""Transcript miner for the sweet-dream skill.

Mining subagents call this instead of writing ad hoc parsing scripts: it
parses Claude Code JSONL transcripts, keeps user-turn lines matching the
signal-marker vocabulary, and emits each hit plus the assistant turn that
answers it as structured output — never a full file.

  mine_transcript.py [options] <file.jsonl ...>

Options:
  --markers-file F   one marker phrase per line (replaces the defaults)
  --markers w1,w2    comma-separated marker phrases (replaces the defaults)
  --count            print only "<hits>\\t<file>" per file (pre-filter mode)

Default mode emits one JSON object per line:
  {"file", "timestamp", "role", "text"}

The default marker vocabulary mirrors SKILL.md Phase 2 (corrections,
preferences, decisions, recurring patterns); tune it there or via the
options above. Matching is case-insensitive on user turns only. Unparseable
lines are skipped silently.
"""

from __future__ import annotations

import argparse
import json
import sys

DEFAULT_MARKERS = [
    # corrections
    "wrong", "actually", "misunderstood", "not correct", "never do",
    "stop doing", "what I meant", "correction",
    # preferences
    "prefer", "always", "never", "from now on", "please remember",
    "keep in mind", "stick to", "my default", "i'd like",
    # decisions
    "we'll use", "let's go", "decided", "settled on", "agreed",
    "switching to", "opted for", "the plan",
    # recurring patterns
    "every time", "once again", "keep forgetting", "as always",
    "recurring", "each session", "habit",
]


def _text_of(entry: dict) -> str:
    """Extract plain text from a transcript entry's message content."""
    content = (entry.get("message") or {}).get("content")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return " ".join(
            block.get("text", "") for block in content
            if isinstance(block, dict) and block.get("type") == "text"
        )
    return ""


def _iter_entries(path: str):
    with open(path, encoding="utf-8-sig") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError:
                continue


def _load_markers(args: argparse.Namespace) -> list[str]:
    if args.markers_file:
        with open(args.markers_file, encoding="utf-8-sig") as f:
            return [m.strip() for m in f if m.strip()]
    if args.markers:
        return [m.strip() for m in args.markers.split(",") if m.strip()]
    return DEFAULT_MARKERS


def mine_file(path: str, markers: list[str], count_only: bool) -> int:
    """Print hits (or just count them) for one transcript; return hit count."""
    lowered = [m.lower() for m in markers]
    hits = 0
    pending_follow = False  # previous line was a hit: emit its assistant answer
    for entry in _iter_entries(path):
        entry_type = entry.get("type")
        if pending_follow:
            if entry_type == "assistant":
                if not count_only:
                    print(json.dumps({
                        "file": path,
                        "timestamp": entry.get("timestamp", ""),
                        "role": "assistant",
                        "text": _text_of(entry),
                    }, ensure_ascii=False))
                pending_follow = False
                continue
            if entry_type != "user":
                continue  # skip meta lines while looking for the answer
        if entry_type != "user":
            continue
        text = _text_of(entry)
        if any(m in text.lower() for m in lowered):
            hits += 1
            if not count_only:
                print(json.dumps({
                    "file": path,
                    "timestamp": entry.get("timestamp", ""),
                    "role": "user",
                    "text": text,
                }, ensure_ascii=False))
            pending_follow = True
        else:
            pending_follow = False
    return hits


def main() -> int:
    parser = argparse.ArgumentParser(prog="mine_transcript")
    parser.add_argument("--markers-file")
    parser.add_argument("--markers")
    parser.add_argument("--count", action="store_true",
                        help="print only per-file marker-hit counts")
    parser.add_argument("files", nargs="+")
    args = parser.parse_args()

    markers = _load_markers(args)
    if not markers:
        print("error: no markers to match", file=sys.stderr)
        return 1

    for path in args.files:
        try:
            hits = mine_file(path, markers, args.count)
        except OSError as e:
            print(f"error: {path}: {e}", file=sys.stderr)
            return 1
        if args.count:
            print(f"{hits}\t{path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
