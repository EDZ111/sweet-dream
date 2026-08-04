#!/usr/bin/env bash
#
# install.sh - flat (non-plugin) install of the sweet-dream skill.
#
# Prefer the plugin route (see README). This fallback copies the skill and its
# scripts into ~/.claude/skills/sweet-dream/ and can optionally register the
# 24h Stop hook.
#
# Usage:
#   bash install.sh              # skill only (run /sweet-dream manually)
#   bash install.sh --auto       # skill + Stop hook auto-trigger
#   bash install.sh --uninstall  # remove skill and hook

set -euo pipefail

SKILL_DIR="$HOME/.claude/skills/sweet-dream"
SETTINGS_FILE="$HOME/.claude/settings.json"
SRC_DIR="$(cd "$(dirname "$0")" && pwd)"
HOOK_CMD="bash \$HOME/.claude/skills/sweet-dream/sweet-dream-hook.sh"

json_edit() {
  # $1 = add | remove
  python3 - "$1" <<'PYEOF'
import json, os, sys

mode = sys.argv[1]
path = os.path.expanduser("~/.claude/settings.json")
hook_cmd = "bash $HOME/.claude/skills/sweet-dream/sweet-dream-hook.sh"

settings = {}
if os.path.exists(path):
    with open(path, encoding="utf-8") as f:
        settings = json.load(f)

stop = settings.setdefault("hooks", {}).setdefault("Stop", [])

def has_hook(entry):
    return any("sweet-dream-hook.sh" in h.get("command", "")
               for h in entry.get("hooks", []))

if mode == "add":
    if not any(has_hook(e) for e in stop):
        stop.append({"hooks": [{"type": "command", "command": hook_cmd, "timeout": 10}]})
        print("Stop hook registered")
    else:
        print("Stop hook already present")
else:
    settings["hooks"]["Stop"] = [e for e in stop if not has_hook(e)]
    if not settings["hooks"]["Stop"]:
        del settings["hooks"]["Stop"]
    if not settings["hooks"]:
        del settings["hooks"]
    print("Stop hook removed")

with open(path, "w", encoding="utf-8") as f:
    json.dump(settings, f, indent=2)
    f.write("\n")
PYEOF
}

case "${1:-}" in
  --uninstall)
    rm -rf "$SKILL_DIR"
    [ -f "$SETTINGS_FILE" ] && json_edit remove
    echo "sweet-dream removed"
    ;;
  *)
    mkdir -p "$SKILL_DIR"
    cp "$SRC_DIR/skills/sweet-dream/SKILL.md" "$SKILL_DIR/"
    cp "$SRC_DIR/scripts/zep_dream.py" \
       "$SRC_DIR/scripts/zep_graph_setup.py" \
       "$SRC_DIR/scripts/should-dream.sh" \
       "$SRC_DIR/scripts/sweet-dream-hook.sh" \
       "$SKILL_DIR/"
    chmod +x "$SKILL_DIR/should-dream.sh" "$SKILL_DIR/sweet-dream-hook.sh"
    echo "skill installed to $SKILL_DIR"
    if [ "${1:-}" = "--auto" ]; then
      json_edit add
    else
      echo "run again with --auto to register the 24h Stop hook"
    fi
    echo "next: pip install zep-cloud; set ZEP_API_KEY (user env var);"
    echo "      python $SKILL_DIR/zep_graph_setup.py   # one-time graph setup"
    ;;
esac
