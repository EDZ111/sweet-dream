#!/usr/bin/env bash
#
# sweet-dream-hook.sh - Stop hook entry point.
#
# Cheap check first; if a dream is due, flag the next session. Never blocks
# and never fails the hook (Claude Code treats non-zero Stop hooks as errors).

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
bash "$SCRIPT_DIR/should-dream.sh" && touch "$HOME/.claude/.sweet-dream-pending"
exit 0
