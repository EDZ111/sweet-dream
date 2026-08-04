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
stop_cmd = "bash $HOME/.claude/skills/sweet-dream/sweet-dream-hook.sh"
compact_cmd = "SWEET_DREAM_MIN_SESSIONS=1 " + stop_cmd

settings = {}
if os.path.exists(path):
    with open(path, encoding="utf-8") as f:
        settings = json.load(f)

hooks_cfg = settings.setdefault("hooks", {})

def has_hook(entry):
    return any("sweet-dream-hook.sh" in h.get("command", "")
               for h in entry.get("hooks", []))

if mode == "add":
    stop = hooks_cfg.setdefault("Stop", [])
    if not any(has_hook(e) for e in stop):
        stop.append({"hooks": [{"type": "command", "command": stop_cmd, "timeout": 10}]})
        print("Stop hook registered")
    else:
        print("Stop hook already present")
    pre = hooks_cfg.setdefault("PreCompact", [])
    if not any(has_hook(e) for e in pre):
        pre.append({"matcher": "auto",
                    "hooks": [{"type": "command", "command": compact_cmd, "timeout": 10}]})
        print("PreCompact hook registered")
    else:
        print("PreCompact hook already present")
else:
    for key in ("Stop", "PreCompact"):
        if key in hooks_cfg:
            hooks_cfg[key] = [e for e in hooks_cfg[key] if not has_hook(e)]
            if not hooks_cfg[key]:
                del hooks_cfg[key]
    if not hooks_cfg:
        del settings["hooks"]
    print("hooks removed")

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
       "$SRC_DIR/scripts/mine_transcript.py" \
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
