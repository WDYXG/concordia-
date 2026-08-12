"""No-API Riverbend runs for tests and truthful frontend playback."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from concordia_riverbend.core import ScriptedAgentController
from concordia_riverbend.core import SimulationConfig
from concordia_riverbend.core import SimulationRun
from concordia_riverbend.core import SimulationRunner
from concordia_riverbend.experiments.world_design import ExperimentPlan
from concordia_riverbend.memory import WorldMemory
from concordia_riverbend.scenarios.election_conditions import (
    ElectionCondition,
)
from concordia_riverbend.scenarios.riverbend_world import (
    build_riverbend_world,
)


_DEMO_VOTES: Mapping[str, Mapping[str, str]] = {
    "baseline": {
        "maya_chen": "Alice",
        "luis_ortiz": "Bob",
        "evelyn_brooks": "Bob",
        "noah_williams": "Alice",
        "jordan_lee": "Alice",
    },
    "placebo": {
        "maya_chen": "Alice",
        "luis_ortiz": "Bob",
        "evelyn_brooks": "Bob",
        "noah_williams": "Alice",
        "jordan_lee": "Alice",
    },
    "employment_evidence": {
        "maya_chen": "Alice",
        "luis_ortiz": "Bob",
        "evelyn_brooks": "Bob",
        "noah_williams": "Alice",
        "jordan_lee": "Bob",
    },
    "pollution_evidence": {
        "maya_chen": "Alice",
        "luis_ortiz": "Alice",
        "evelyn_brooks": "Bob",
        "noah_williams": "Alice",
        "jordan_lee": "Alice",
    },
}


def _first_round_action(
    agent_id: str,
    *,
    initial_location: str,
    source_event_id: str,
) -> tuple[str, Mapping[str, object]]:
    if agent_id == "maya_chen":
        return (
            "speak",
            {
                "message": (
                    "Noah, can you help verify what the election report "
                    "means for community health?"
                ),
                "channel": "private",
                "recipients": ["noah_williams"],
                "source_event_id": source_event_id,
            },
        )
    if agent_id == "evelyn_brooks":
        return (
            "speak",
            {
                "message": (
                    "Downtown businesses need both stable customers and "
                    "predictable public rules."
                ),
                "channel": "public",
                "recipients": [],
            },
        )
    if agent_id == "jordan_lee":
        return (
            "speak",
            {
                "message": (
                    "I want independent evidence before trusting either "
                    "campaign promise."
                ),
                "channel": "public",
                "recipients": [],
            },
        )
    return ("inspect", {"target": initial_location})


def _scripted_vote_reason(agent_id: str, candidate: str) -> str:
    priorities = {
        "maya_chen": "my family's health, the river, and local schools",
        "luis_ortiz": "steady work and my household's economic security",
        "evelyn_brooks": (
            "my business and a town that keeps attracting customers"
        ),
        "noah_williams": "public health and reliable clinic services",
        "jordan_lee": (
            "an affordable, healthy, and economically secure future"
        ),
    }
    return (
        f"I chose {candidate} because I judged that platform to fit "
        f"{priorities[agent_id]} best."
    )


def run_scripted_riverbend_world(
    *,
    condition: ElectionCondition,
    seed: int = 20260727,
    agent_order: Sequence[str] | None = None,
    candidate_order: tuple[str, str] = ("Alice", "Bob"),
    memory_embedder: Any | None = None,
) -> SimulationRun:
    """Run a deterministic three-round world without an LLM or API."""
    scenario = build_riverbend_world(
        condition,
        candidate_order=candidate_order,
    )
    source_event_id = (
        "election_briefing"
        if condition.event is None
        else f"condition_{condition.name}"
    )
    votes = _DEMO_VOTES[condition.name]
    controllers = {
        agent.agent_id: ScriptedAgentController(
            (
                _first_round_action(
                    agent.agent_id,
                    initial_location=agent.initial_location,
                    source_event_id=source_event_id,
                ),
                ("move", {"destination": "town_hall"}),
                (
                    "vote",
                    {
                        "candidate": votes[agent.agent_id],
                        "reason": _scripted_vote_reason(
                            agent.agent_id,
                            votes[agent.agent_id],
                        ),
                    },
                ),
            )
        )
        for agent in scenario.agents
    }
    memory_system = WorldMemory(
        scenario,
        embedder=memory_embedder,
    )
    memory_embedder_name = next(
        iter(memory_system.to_dict().values())
    )["embedder"]
    config = SimulationConfig(
        scenario_id=scenario.scenario_id,
        max_rounds=3,
        seed=seed,
        condition=condition.name,
        model_name=None,
        metadata={
            "candidate_order": candidate_order,
            "scripted_demo": True,
            "memory_embedder": memory_embedder_name,
            "warning": "Scripted demonstration, not a research result.",
        },
    )
    return SimulationRunner(
        scenario=scenario,
        config=config,
        controllers=controllers,
        agent_order=agent_order,
        memory_system=memory_system,
    ).run()


def run_scripted_experiment_plan(
    *,
    plan: ExperimentPlan,
    conditions: Sequence[ElectionCondition],
) -> tuple[SimulationRun, ...]:
    """Execute every planned cell with deterministic no-API controllers."""
    condition_map = {condition.name: condition for condition in conditions}
    missing = {
        run.condition for run in plan.runs
    } - set(condition_map)
    if missing:
        raise ValueError(
            "Missing condition definitions: " + ", ".join(sorted(missing))
        )
    return tuple(
        run_scripted_riverbend_world(
            condition=condition_map[run_plan.condition],
            seed=run_plan.seed,
            agent_order=run_plan.agent_order,
            candidate_order=(
                run_plan.candidate_order[0],
                run_plan.candidate_order[1],
            ),
        )
        for run_plan in plan.runs
    )
