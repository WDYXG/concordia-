"""Compare repeated Riverbend elections across information treatments."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from concordia.language_model import language_model

from concordia_riverbend.agents.voter import VoterProfile
from concordia_riverbend.experiments.repeated_election import (
    RepeatedElectionResult,
)
from concordia_riverbend.experiments.repeated_election import (
    run_repeated_election,
)
from concordia_riverbend.scenarios.election_conditions import ElectionCondition


@dataclass(frozen=True)
class ConditionOutcome:
    """The repeated-election distribution for one treatment level."""

    condition: ElectionCondition
    result: RepeatedElectionResult
    game_master_runs: tuple[dict[str, Any], ...] = ()


@dataclass(frozen=True)
class ConditionExperimentResult:
    """Outcomes for all conditions and share differences from control."""

    control_condition: str
    outcomes: tuple[ConditionOutcome, ...]

    def _outcome_map(self) -> dict[str, ConditionOutcome]:
        return {outcome.condition.name: outcome for outcome in self.outcomes}

    def candidate_share_deltas(
        self,
        candidate: str,
    ) -> dict[str, float]:
        outcome_map = self._outcome_map()
        control_share = outcome_map[
            self.control_condition
        ].result.vote_shares[candidate]
        return {
            name: outcome.result.vote_shares[candidate] - control_share
            for name, outcome in outcome_map.items()
        }

    def candidate_contrasts(self, candidate: str) -> dict[str, float]:
        """Return the three pre-specified information-treatment contrasts."""
        outcome_map = self._outcome_map()
        shares = {
            name: outcome.result.vote_shares[candidate]
            for name, outcome in outcome_map.items()
        }
        required = {
            "baseline",
            "placebo",
            "employment_evidence",
            "pollution_evidence",
        }
        missing = required - set(shares)
        if missing:
            raise ValueError(
                "Cannot compute pre-specified contrasts; missing conditions: "
                + ", ".join(sorted(missing))
            )
        return {
            "announcement_effect": shares["placebo"] - shares["baseline"],
            "employment_information_effect": (
                shares["employment_evidence"] - shares["placebo"]
            ),
            "pollution_information_effect": (
                shares["pollution_evidence"] - shares["placebo"]
            ),
        }

    def to_dict(self) -> dict[str, Any]:
        candidates = self.outcomes[0].result.candidates
        return {
            "control_condition": self.control_condition,
            "candidate_share_deltas": {
                candidate: self.candidate_share_deltas(candidate)
                for candidate in candidates
            },
            "candidate_contrasts": {
                candidate: self.candidate_contrasts(candidate)
                for candidate in candidates
            },
            "conditions": [
                {
                    "name": outcome.condition.name,
                    "description": outcome.condition.description,
                    "event": outcome.condition.event,
                    "result": outcome.result.to_dict(),
                    "game_master_runs": list(outcome.game_master_runs),
                }
                for outcome in self.outcomes
            ],
        }


def run_condition_experiment(
    *,
    model: language_model.LanguageModel,
    profiles: Sequence[VoterProfile],
    base_observation: str,
    conditions: Sequence[ElectionCondition],
    num_runs_per_condition: int,
    control_condition: str = "baseline",
    candidates: tuple[str, ...] = ("Alice", "Bob"),
    include_reasons: bool = False,
) -> ConditionExperimentResult:
    """Run fresh agents under each controlled information treatment."""
    if not conditions:
        raise ValueError("At least one experimental condition is required.")
    condition_names = [condition.name for condition in conditions]
    if len(set(condition_names)) != len(condition_names):
        raise ValueError("Experimental condition names must be unique.")
    if control_condition not in condition_names:
        raise ValueError(
            f"Control condition {control_condition!r} was not provided."
        )

    outcomes = tuple(
        ConditionOutcome(
            condition=condition,
            result=run_repeated_election(
                model=model,
                profiles=profiles,
                election_observation=base_observation,
                additional_observations=(
                    (condition.event,) if condition.event else ()
                ),
                num_runs=num_runs_per_condition,
                candidates=candidates,
                include_reasons=include_reasons,
            ),
        )
        for condition in conditions
    )
    return ConditionExperimentResult(
        control_condition=control_condition,
        outcomes=outcomes,
    )
