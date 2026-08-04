"""Create the sweet_dreams graph, its ontology, and the owning Zep user.

Idempotent: safe to re-run. Reads ZEP_API_KEY from the environment only.
"""

from __future__ import annotations

import getpass
import os
import sys

from pydantic import Field
from zep_cloud.client import Zep
from zep_cloud.external_clients.ontology import (
    EdgeModel,
    EntityModel,
    EntityText,
)
from zep_cloud.types import EntityEdgeSourceTarget

GRAPH_ID = os.environ.get("SWEET_DREAM_GRAPH_ID", "sweet_dreams")


def _resolve_user_id(cli_value: str | None) -> str:
    """Priority: --user-id (the agent asked the user) > $SWEET_DREAM_USER_ID
    (a previously-saved answer) > OS username > the literal "default_user".
    Never hardcode a real person's name here — this runs on every installer's
    machine, not just the original author's."""
    if cli_value:
        return cli_value
    env_value = os.environ.get("SWEET_DREAM_USER_ID")
    if env_value:
        return env_value
    for var in ("USER", "USERNAME", "LOGNAME"):
        os_user = os.environ.get(var)
        if os_user:
            return os_user
    try:
        return getpass.getuser()
    except Exception:
        return "default_user"

# Stamp written into the graph description on create/adopt. Setup refuses to
# touch an existing graph whose description lacks it — the id may be in use
# for something else entirely, and overwriting its ontology would corrupt it.
OWNERSHIP_MARK = "sweet-dream"


# --- Entity types: nouns the dream consolidator files facts under ------------

class Preference(EntityModel):
    """A stable preference the user expressed about how work should be done:
    tools, style, formatting, communication, workflow choices."""

    category: EntityText = Field(
        description="What the preference is about, e.g. editor, git, testing, communication",
        default=None,
    )
    strength: EntityText = Field(
        description="How firmly it was stated: explicit instruction, repeated habit, or implied",
        default=None,
    )


class Decision(EntityModel):
    """A concrete choice made during a session: architecture, library,
    naming, process. Something that was decided, not merely discussed."""

    rationale: EntityText = Field(
        description="Why this choice was made, if stated",
        default=None,
    )
    status: EntityText = Field(
        description="active, superseded, or revisit-later",
        default=None,
    )


class Correction(EntityModel):
    """A moment the user corrected the assistant: a wrong belief, a wrong
    approach, or an instruction that was misunderstood."""

    wrong_belief: EntityText = Field(
        description="What the assistant believed or did that was wrong",
        default=None,
    )
    corrected_to: EntityText = Field(
        description="The corrected fact or behaviour",
        default=None,
    )


class WorkPattern(EntityModel):
    """A recurring workflow or habit observed across sessions, e.g. commits
    and merges done by the user in the same checkout while the agent works."""

    frequency: EntityText = Field(
        description="How often it recurs: every session, daily, occasional",
        default=None,
    )


class ProjectFact(EntityModel):
    """Durable knowledge about a specific project: architecture, constraints,
    conventions, environment quirks."""

    area: EntityText = Field(
        description="The part of the project it concerns, e.g. backend config, CI, deployment",
        default=None,
    )


class ToolConfig(EntityModel):
    """A tool or environment setting that was configured, e.g. an env var,
    an MCP server, a settings.json key."""

    setting_value: EntityText = Field(
        description="The configured value or state (never secrets - describe, don't quote keys)",
        default=None,
    )


# --- Edge types: verbs connecting them ---------------------------------------

class Prefers(EdgeModel):
    """The user prefers something."""

    confidence: EntityText = Field(
        description="high (explicit instruction) or medium (implied)",
        default=None,
    )
    source_session_date: EntityText = Field(
        description="Absolute date (YYYY-MM-DD) of the session this came from",
        default=None,
    )


class Decided(EdgeModel):
    """The user or team decided on something."""

    rationale: EntityText = Field(
        description="Reason given for the decision, if any",
        default=None,
    )


class Corrected(EdgeModel):
    """The user corrected a belief or behaviour."""

    previous_value: EntityText = Field(
        description="What was believed or done before the correction",
        default=None,
    )


class Recurs(EdgeModel):
    """A pattern recurs in a project or workflow."""

    frequency: EntityText = Field(
        description="How often the pattern shows up",
        default=None,
    )


DESCRIPTION = (
    "Consolidated long-term memory written by sweet-dream runs: "
    "preferences, decisions, corrections, recurring patterns, and "
    "project facts distilled from Claude Code session transcripts."
)


def _is_ours(graph) -> bool:
    return OWNERSHIP_MARK in (graph.description or "")


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--graph-id", default=GRAPH_ID,
                        help="graph id to set up (default: sweet_dreams, or $SWEET_DREAM_GRAPH_ID)")
    parser.add_argument("--adopt", action="store_true",
                        help="claim an existing graph that was not created by sweet-dream")
    parser.add_argument("--reset", action="store_true",
                        help="drop and recreate the graph (only if it is sweet-dream's)")
    parser.add_argument("--user-id", default=None,
                        help="Zep user id to own the graph (default: $SWEET_DREAM_USER_ID, "
                             "then the OS username, then 'default_user')")
    args = parser.parse_args()
    graph_id = args.graph_id
    user_id = _resolve_user_id(args.user_id)

    api_key = os.environ.get("ZEP_API_KEY")
    if not api_key:
        print("ZEP_API_KEY not set in environment", file=sys.stderr)
        return 1

    client = Zep(api_key=api_key)

    # Ownership check before anything touches the graph. A graph with this id
    # may predate sweet-dream and belong to another workload.
    existing = None
    try:
        existing = client.graph.get(graph_id)
    except Exception:
        pass  # not found -> we will create it

    if existing is not None and not _is_ours(existing) and not args.adopt:
        print(
            f"refusing to touch graph '{graph_id}': it already exists and does "
            f"not look like a sweet-dream graph (description: "
            f"{(existing.description or '(empty)')[:120]!r}).\n"
            "Options:\n"
            f"  - adopt it for sweet-dream:      rerun with --adopt "
            "(its ontology WILL be replaced; episodes are kept)\n"
            "  - keep it and use another name:  rerun with --graph-id <other> "
            "and set SWEET_DREAM_GRAPH_ID=<other> so zep_dream.py targets it",
            file=sys.stderr,
        )
        return 2

    if args.reset:
        if existing is None:
            print("reset: graph does not exist, nothing to delete")
        elif not _is_ours(existing) and not args.adopt:
            print("reset refused: graph is not sweet-dream's (see above)", file=sys.stderr)
            return 2
        else:
            client.graph.delete(graph_id)
            existing = None
            print(f"graph deleted: {graph_id}")

    # User (idempotent)
    try:
        client.user.add(user_id=user_id, first_name=user_id.capitalize())
        print(f"user created: {user_id}")
    except Exception as e:
        if "already exists" in str(e).lower() or "409" in str(e) or "bad request" in str(e).lower():
            print(f"user exists: {user_id}")
        else:
            raise

    if existing is None:
        client.graph.create(graph_id=graph_id, name="Sweet Dreams", description=DESCRIPTION)
        print(f"graph created: {graph_id}")
    elif not _is_ours(existing):  # implies --adopt
        client.graph.update(graph_id, description=DESCRIPTION, name=existing.name or "Sweet Dreams")
        print(f"graph adopted: {graph_id} (description stamped, episodes untouched)")
    else:
        print(f"graph exists: {graph_id}")

    # Ontology, scoped to this graph only (does not touch project-wide types)
    client.graph.set_ontology(
        entities={
            "Preference": Preference,
            "Decision": Decision,
            "Correction": Correction,
            "WorkPattern": WorkPattern,
            "ProjectFact": ProjectFact,
            "ToolConfig": ToolConfig,
        },
        edges={
            "PREFERS": (
                Prefers,
                [EntityEdgeSourceTarget(source="User", target="Preference")],
            ),
            "DECIDED": (
                Decided,
                [EntityEdgeSourceTarget(source="User", target="Decision")],
            ),
            "CORRECTED": (
                Corrected,
                [EntityEdgeSourceTarget(source="User", target="Correction")],
            ),
            "RECURS": (
                Recurs,
                [EntityEdgeSourceTarget(source="WorkPattern")],
            ),
        },
        graph_ids=[graph_id],
    )
    print("ontology set for", graph_id)

    # Verify
    types = client.graph.list_entity_types(graph_id=graph_id)
    entity_names = [t.name for t in (types.entity_types or [])]
    edge_names = [t.name for t in (types.edge_types or [])]
    print("entity types:", ", ".join(entity_names))
    print("edge types:", ", ".join(edge_names))
    return 0


if __name__ == "__main__":
    sys.exit(main())
