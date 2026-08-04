"""Create the sweet_dreams graph, its ontology, and the owning Zep user.

Idempotent: safe to re-run. Reads ZEP_API_KEY from the environment only.
"""

from __future__ import annotations

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

GRAPH_ID = "sweet_dreams"
USER_ID = "edoardo"


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


def main() -> int:
    api_key = os.environ.get("ZEP_API_KEY")
    if not api_key:
        print("ZEP_API_KEY not set in environment", file=sys.stderr)
        return 1

    client = Zep(api_key=api_key)

    if "--reset" in sys.argv:
        try:
            client.graph.delete(GRAPH_ID)
            print(f"graph deleted: {GRAPH_ID}")
        except Exception as e:
            print(f"graph delete skipped ({e})")

    # User (idempotent)
    try:
        client.user.add(user_id=USER_ID, first_name="Edoardo")
        print(f"user created: {USER_ID}")
    except Exception as e:
        if "already exists" in str(e).lower() or "409" in str(e) or "bad request" in str(e).lower():
            print(f"user exists: {USER_ID}")
        else:
            raise

    # Graph (idempotent)
    try:
        client.graph.create(
            graph_id=GRAPH_ID,
            name="Sweet Dreams",
            description=(
                "Consolidated long-term memory written by sweet-dream runs: "
                "preferences, decisions, corrections, recurring patterns, and "
                "project facts distilled from Claude Code session transcripts."
            ),
        )
        print(f"graph created: {GRAPH_ID}")
    except Exception as e:
        if "already exists" in str(e).lower() or "409" in str(e) or "bad request" in str(e).lower():
            print(f"graph exists: {GRAPH_ID}")
        else:
            raise

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
        graph_ids=[GRAPH_ID],
    )
    print("ontology set for", GRAPH_ID)

    # Verify
    types = client.graph.list_entity_types(graph_id=GRAPH_ID)
    entity_names = [t.name for t in (types.entity_types or [])]
    edge_names = [t.name for t in (types.edge_types or [])]
    print("entity types:", ", ".join(entity_names))
    print("edge types:", ", ".join(edge_names))
    return 0


if __name__ == "__main__":
    sys.exit(main())
