"""Reproducible design and metrics for multi-round Agent experiments."""

from __future__ import annotations

from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass
import random
from typing import Any

from concordia_riverbend.core import SimulationRun


@dataclass(frozen=True)
class ExperimentRunPlan:
    """All randomized choices for one planned simulation run."""

    run_id: str
    execution_index: int
    repetition: int
    seed: int
    condition: str
    agent_order: tuple[str, ...]
    candidate_order: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "execution_index": self.execution_index,
            "repetition": self.repetition,
            "seed": self.seed,
            "condition": self.condition,
            "agent_order": list(self.agent_order),
            "candidate_order": list(self.candidate_order),
        }


@dataclass(frozen=True)
class ExperimentPlan:
    """A reproducible, cross-balanced set of run specifications."""

    base_seed: int
    repetitions_per_condition: int
    runs: tuple[ExperimentRunPlan, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "base_seed": self.base_seed,
            "repetitions_per_condition": self.repetitions_per_condition,
            "runs": [run.to_dict() for run in self.runs],
        }


def build_experiment_plan(
    *,
    conditions: Sequence[str],
    repetitions_per_condition: int,
    agent_ids: Sequence[str],
    candidates: tuple[str, str],
    base_seed: int,
) -> ExperimentPlan:
    """Randomize execution while balancing order within each condition."""
    if not conditions:
        raise ValueError("At least one condition is required.")
    if len(set(conditions)) != len(conditions):
        raise ValueError("Condition names must be unique.")
    if repetitions_per_condition < 1:
        raise ValueError("repetitions_per_condition must be at least 1.")
    if len(agent_ids) < 1 or len(set(agent_ids)) != len(agent_ids):
        raise ValueError("agent_ids must be non-empty and unique.")
    if len(set(candidates)) != 2:
        raise ValueError("Exactly two unique candidates are required.")

    master_rng = random.Random(base_seed)
    cells: list[dict[str, Any]] = []
    for condition in conditions:
        for repetition in range(repetitions_per_condition):
            run_seed = master_rng.randrange(0, 2**31)
            order = list(agent_ids)
            random.Random(run_seed).shuffle(order)
            candidate_order = (
                candidates
                if repetition % 2 == 0
                else tuple(reversed(candidates))
            )
            cells.append(
                {
                    "repetition": repetition,
                    "seed": run_seed,
                    "condition": condition,
                    "agent_order": tuple(order),
                    "candidate_order": candidate_order,
                }
            )
    master_rng.shuffle(cells)
    runs = tuple(
        ExperimentRunPlan(
            run_id=f"run_{index + 1:04d}",
            execution_index=index,
            **cell,
        )
        for index, cell in enumerate(cells)
    )
    return ExperimentPlan(
        base_seed=base_seed,
        repetitions_per_condition=repetitions_per_condition,
        runs=runs,
    )


def analyze_world_run(run: SimulationRun) -> dict[str, Any]:
    """Extract descriptive metrics and manipulation checks from one run."""
    resolved = [
        turn.result for turn in run.turns if turn.result is not None
    ]
    accepted = [result for result in resolved if result.accepted]
    rejected = [result for result in resolved if not result.accepted]
    action_counts = Counter(
        result.request.action_type for result in accepted
    )
    event_counts = Counter(
        event.event_type for event in run.final_state.events
    )
    ballots = dict(run.final_state.variables.get("ballots", {}))
    vote_reasons = dict(
        run.final_state.variables.get("vote_reasons", {})
    )
    unvoted_agent_ids = [
        agent_id
        for agent_id in run.scenario.agent_ids
        if agent_id not in ballots
    ]
    candidate_counts = Counter(ballots.values())
    candidates = tuple(
        str(item)
        for item in run.scenario.metadata.get("candidates", ())
    )
    condition = str(run.scenario.metadata.get("condition", "baseline"))
    condition_event_id = (
        None if condition == "baseline" else f"condition_{condition}"
    )
    observed_by_agent = {
        agent_id: {
            event_id
            for turn in run.turns
            if turn.agent_id == agent_id
            for event_id in turn.observed_event_ids
        }
        for agent_id in run.scenario.agent_ids
    }
    condition_seen_by = (
        list(run.scenario.agent_ids)
        if condition_event_id is None
        else [
            agent_id
            for agent_id, event_ids in observed_by_agent.items()
            if condition_event_id in event_ids
        ]
    )
    relationship_edges = sum(
        len(targets)
        for targets in run.final_state.relationships.values()
    )
    memory_type_counts: Counter[str] = Counter()
    for agent_memory in run.memory_state.values():
        for record in agent_memory.get("records", []):
            memory_type_counts.update([record["memory_type"]])

    total_resolved = len(resolved)
    return {
        "scenario_id": run.scenario.scenario_id,
        "condition": condition,
        "rounds": run.final_state.round_index,
        "turns": len(run.turns),
        "accepted_actions": len(accepted),
        "rejected_actions": len(rejected),
        "acceptance_rate": (
            len(accepted) / total_resolved if total_resolved else 0.0
        ),
        "action_counts": dict(action_counts),
        "event_counts": dict(event_counts),
        "ballots": ballots,
        "vote_reasons": vote_reasons,
        "eligible_voters": len(run.scenario.agent_ids),
        "ballots_cast": len(ballots),
        "unvoted_count": len(unvoted_agent_ids),
        "unvoted_agent_ids": unvoted_agent_ids,
        "candidate_tally": {
            candidate: candidate_counts[candidate]
            for candidate in candidates
        },
        "condition_event_id": condition_event_id,
        "condition_seen_by": condition_seen_by,
        "manipulation_check_passed": (
            set(condition_seen_by) == set(run.scenario.agent_ids)
        ),
        "relationship_edges": relationship_edges,
        "memory_type_counts": dict(memory_type_counts),
    }


def summarize_world_runs(
    runs: Sequence[SimulationRun],
) -> dict[str, Any]:
    """Aggregate descriptive outcomes without treating runs as people."""
    metrics = [analyze_world_run(run) for run in runs]
    by_condition: dict[str, list[dict[str, Any]]] = {}
    for metric in metrics:
        by_condition.setdefault(metric["condition"], []).append(metric)

    condition_summary: dict[str, Any] = {}
    for condition, rows in by_condition.items():
        candidate_totals: Counter[str] = Counter()
        for row in rows:
            candidate_totals.update(row["candidate_tally"])
        total_ballots = sum(candidate_totals.values())
        condition_summary[condition] = {
            "runs": len(rows),
            "candidate_tally": dict(candidate_totals),
            "candidate_shares": {
                candidate: (
                    count / total_ballots if total_ballots else 0.0
                )
                for candidate, count in candidate_totals.items()
            },
            "all_manipulation_checks_passed": all(
                row["manipulation_check_passed"] for row in rows
            ),
            "mean_acceptance_rate": sum(
                row["acceptance_rate"] for row in rows
            )
            / len(rows),
        }
    return {
        "unit_note": (
            "Runs reuse fixed synthetic personas and are not independent "
            "human participants."
        ),
        "runs": metrics,
        "conditions": condition_summary,
    }
