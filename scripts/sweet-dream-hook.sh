#!/usr/bin/env bash
#
# sweet-dream-hook.sh - hook entry point (Stop and PreCompact).
#
# Cheap check first; if a dream is due, flag the next session. Never blocks
# and never fails the hook (Claude Code treats non-zero hook exits as errors).
# PreCompact callers set SWEET_DREAM_MIN_SESSIONS=1: the compaction itself
# is the activity proof, so the 3-session gate doesn't apply.

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
bash "$SCRIPT_DIR/should-dream.sh" && touch "$HOME/.claude/.sweet-dream-pending"
exit 0
