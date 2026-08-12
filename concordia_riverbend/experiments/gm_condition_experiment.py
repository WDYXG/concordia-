"""Run all information conditions through the deterministic Concordia GM."""

from __future__ import annotations

from collections.abc import Sequence

from concordia.language_model import language_model

from concordia_riverbend.agents.voter import VoterProfile
from concordia_riverbend.experiments.condition_experiment import (
    ConditionExperimentResult,
)
from concordia_riverbend.experiments.condition_experiment import (
    ConditionOutcome,
)
from concordia_riverbend.experiments.repeated_election import (
    RepeatedElectionResult,
)
from concordia_riverbend.game_master.election import run_gm_election
from concordia_riverbend.scenarios.election_conditions import ElectionCondition


def run_gm_condition_experiment(
    *,
    model: language_model.LanguageModel,
    profiles: Sequence[VoterProfile],
    base_observation: str,
    conditions: Sequence[ElectionCondition],
    num_runs_per_condition: int,
    candidates: tuple[str, ...] = ("Alice", "Bob"),
) -> ConditionExperimentResult:
    """Run fresh GM-administered elections under every condition."""
    if num_runs_per_condition < 1:
        raise ValueError("num_runs_per_condition must be at least 1.")
    condition_names = [condition.name for condition in conditions]
    if len(set(condition_names)) != len(condition_names):
        raise ValueError("Experimental condition names must be unique.")
    if "baseline" not in condition_names:
        raise ValueError("The baseline condition must be provided.")

    outcomes: list[ConditionOutcome] = []
    for condition in conditions:
        gm_runs = tuple(
            run_gm_election(
                model=model,
                profiles=profiles,
                base_observation=base_observation,
                condition=condition,
                candidates=candidates,
            )
            for _ in range(num_runs_per_condition)
        )
        outcomes.append(
            ConditionOutcome(
                condition=condition,
                result=RepeatedElectionResult(
                    candidates=candidates,
                    runs=tuple(run.election for run in gm_runs),
                ),
                game_master_runs=tuple(
                    run.game_master_record() for run in gm_runs
                ),
            )
        )

    return ConditionExperimentResult(
        control_condition="baseline",
        outcomes=tuple(outcomes),
    )
