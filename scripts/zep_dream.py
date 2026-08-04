"""Zep I/O for the sweet-dream skill.

All graph reads/writes for a dream run go through this CLI so the model never
handles the API key. Subcommands:

  status                       Orient: graph health, entity types, recent facts
  check --text "..."           Dedupe probe: search existing facts before adding
  add-finding [--file f]       Add one finding (JSON on stdin or --file)
  search --query Q [...]       Search the graph (edges/nodes/episodes)
  quickref [--limit N]         Top facts for the MEMORY.md Quick Reference

ZEP_API_KEY is read from the environment; on Windows it falls back to the
user-scope registry value so sessions started before `setx` still work.
"""

from __future__ import annotations

import argparse
import json
import os
import sys

GRAPH_ID = os.environ.get("SWEET_DREAM_GRAPH_ID", "sweet_dreams")


def _api_key() -> str:
    key = os.environ.get("ZEP_API_KEY")
    if key:
        return key
    if sys.platform == "win32":
        try:
            import winreg

            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as h:
                key = winreg.QueryValueEx(h, "ZEP_API_KEY")[0]
                if key:
                    return key
        except OSError:
            pass
    print(
        "error: ZEP_API_KEY not set. Set it as a user environment variable "
        "(never paste it into a chat).",
        file=sys.stderr,
    )
    sys.exit(1)


def _client():
    try:
        from zep_cloud.client import Zep
    except ImportError:
        print(
            "error: zep-cloud not installed. Run: pip install zep-cloud",
            file=sys.stderr,
        )
        sys.exit(1)
    return Zep(api_key=_api_key())


def cmd_status(args: argparse.Namespace) -> int:
    client = _client()
    graph = client.graph.get(GRAPH_ID)
    print(f"graph: {graph.graph_id} ({graph.name})")

    types = client.graph.list_entity_types(graph_id=GRAPH_ID)
    print("entity types:", ", ".join(t.name for t in (types.entity_types or [])))
    print("edge types:", ", ".join(t.name for t in (types.edge_types or [])))

    try:
        # No total-count API exists; count a large fetch and stay honest
        # when the request bound itself is hit ("N+").
        bound = 1000
        episodes = client.graph.episode.get_by_graph_id(GRAPH_ID, lastn=bound)
        eps = sorted(episodes.episodes or [], key=lambda e: e.created_at or "")
        total = f"{len(eps)}+" if len(eps) >= bound else str(len(eps))
        shown = eps[-args.lastn:]
        print(f"total episodes: {total} (showing last {len(shown)})")
        for ep in shown:
            desc = (ep.source_description or "")[:60]
            print(f"  - {ep.created_at}  {desc}")
    except Exception as e:  # episode listing is orientation, not critical
        print(f"episodes: unavailable ({e})")

    results = client.graph.search(graph_id=GRAPH_ID, query="preference decision correction pattern", scope="edges", limit=args.lastn)
    edges = results.edges or []
    print(f"sample facts: {len(edges)}")
    for edge in edges:
        validity = "" if edge.invalid_at is None else "  [superseded]"
        print(f"  - ({edge.name}) {edge.fact}{validity}")
    return 0


def cmd_check(args: argparse.Namespace) -> int:
    client = _client()
    results = client.graph.search(graph_id=GRAPH_ID, query=args.text, scope="edges", limit=args.limit)
    edges = results.edges or []
    if not edges:
        print("NO_MATCH")
        return 0
    for edge in edges:
        validity = "valid" if edge.invalid_at is None else "superseded"
        print(f"{validity}\t({edge.name})\t{edge.fact}")
    return 0


def cmd_add_finding(args: argparse.Namespace) -> int:
    raw = open(args.file, encoding="utf-8-sig").read() if args.file else sys.stdin.read()
    # PowerShell pipes prepend a UTF-8 BOM; strip it so stdin JSON parses.
    finding = json.loads(raw.lstrip("﻿"))

    findings = finding if isinstance(finding, list) else [finding]
    client = _client()
    for f in findings:
        for required in ("fact", "kind", "source_date"):
            if required not in f:
                print(f"error: finding missing '{required}': {f}", file=sys.stderr)
                return 1
        payload = {
            "fact": f["fact"],
            "kind": f["kind"],  # preference|decision|correction|pattern|project_fact|tool_config
            "source_date": f["source_date"],  # absolute YYYY-MM-DD
            "source_session": f.get("source_session", "unknown"),
            "confidence": f.get("confidence", "medium"),
        }
        if f.get("supersedes"):
            payload["supersedes"] = f["supersedes"]
        episode = client.graph.add(
            graph_id=GRAPH_ID,
            type="json",
            data=json.dumps(payload),
            source_description=f"sweet-dream consolidation from session {payload['source_session']} on {payload['source_date']}",
        )
        print(f"added episode {episode.uuid_} ({payload['kind']}): {payload['fact'][:80]}")
    print(f"queued {len(findings)} finding(s) for ingestion")
    return 0


def cmd_search(args: argparse.Namespace) -> int:
    client = _client()
    results = client.graph.search(graph_id=GRAPH_ID, query=args.query, scope=args.scope, limit=args.limit)
    if args.scope == "edges":
        for edge in results.edges or []:
            validity = "valid" if edge.invalid_at is None else "superseded"
            print(f"{validity}\t({edge.name})\t{edge.fact}")
    elif args.scope == "nodes":
        for node in results.nodes or []:
            labels = ",".join(node.labels or [])
            print(f"[{labels}]\t{node.name}\t{(node.summary or '')[:120]}")
    else:
        for ep in results.episodes or []:
            print(f"{ep.created_at}\t{(ep.content or '')[:160]}")
    return 0


def cmd_quickref(args: argparse.Namespace) -> int:
    client = _client()
    seen: set[str] = set()
    lines: list[str] = []
    for query in (
        "user preferences and instructions",
        "decisions made and their rationale",
        "corrections of wrong behaviour",
        "recurring workflow patterns and project facts",
    ):
        results = client.graph.search(graph_id=GRAPH_ID, query=query, scope="edges", limit=args.limit)
        for edge in results.edges or []:
            if edge.invalid_at is not None or edge.fact in seen:
                continue
            seen.add(edge.fact)
            lines.append(f"- {edge.fact}")
    for line in lines[: args.limit]:
        print(line)
    return 0


def cmd_wipe(args: argparse.Namespace) -> int:
    if not args.yes:
        print("refusing to wipe without --yes (deletes every episode in the graph)", file=sys.stderr)
        return 1
    client = _client()
    deleted = 0
    while True:
        episodes = client.graph.episode.get_by_graph_id(GRAPH_ID, lastn=100)
        eps = episodes.episodes or []
        if not eps:
            break
        for ep in eps:
            client.graph.episode.delete(ep.uuid_)
            deleted += 1
    print(f"wiped {deleted} episode(s) from {GRAPH_ID}; graph and ontology kept")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(prog="zep_dream")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("status")
    p.add_argument("--lastn", type=int, default=10)
    p.set_defaults(fn=cmd_status)

    p = sub.add_parser("check")
    p.add_argument("--text", required=True)
    p.add_argument("--limit", type=int, default=5)
    p.set_defaults(fn=cmd_check)

    p = sub.add_parser("add-finding")
    p.add_argument("--file")
    p.set_defaults(fn=cmd_add_finding)

    p = sub.add_parser("search")
    p.add_argument("--query", required=True)
    p.add_argument("--scope", choices=["edges", "nodes", "episodes"], default="edges")
    p.add_argument("--limit", type=int, default=10)
    p.set_defaults(fn=cmd_search)

    p = sub.add_parser("quickref")
    p.add_argument("--limit", type=int, default=10)
    p.set_defaults(fn=cmd_quickref)

    p = sub.add_parser("wipe", help="delete every episode (test-data cleanup)")
    p.add_argument("--yes", action="store_true")
    p.set_defaults(fn=cmd_wipe)

    args = parser.parse_args()
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
