#!/usr/bin/env bash
#
# should-dream.sh - decide whether a dream run is due.
#
# Exit 0 (yes) when BOTH hold:
#   - 24+ hours since the last dream (~/.claude/.sweet-dream-last, epoch seconds)
#   - at least MIN_SESSIONS session transcripts were modified since then
# Exit 1 (no) otherwise. Designed to run from a Stop hook in ~10ms.

set -u

LAST_FILE="$HOME/.claude/.sweet-dream-last"
PROJECTS_DIR="${SWEET_DREAM_PROJECTS_DIR:-$HOME/.claude/projects}"
MIN_INTERVAL_SECONDS=$((24 * 60 * 60))
MIN_SESSIONS="${SWEET_DREAM_MIN_SESSIONS:-3}"

now=$(date +%s)
last=0
[ -f "$LAST_FILE" ] && last=$(cat "$LAST_FILE" 2>/dev/null || echo 0)
case "$last" in (*[!0-9]*|"") last=0 ;; esac

elapsed=$((now - last))
[ "$elapsed" -lt "$MIN_INTERVAL_SECONDS" ] && exit 1

# Count transcripts newer than the last dream. -newermt needs a date; use
# a reference file when we have one, otherwise any transcript counts.
if [ "$last" -gt 0 ] && [ -f "$LAST_FILE" ]; then
  count=$(find "$PROJECTS_DIR" -maxdepth 2 -name "*.jsonl" -newer "$LAST_FILE" 2>/dev/null | wc -l)
else
  count=$(find "$PROJECTS_DIR" -maxdepth 2 -name "*.jsonl" -mtime -7 2>/dev/null | wc -l)
fi

[ "$count" -ge "$MIN_SESSIONS" ] && exit 0
exit 1
