"""Repeat fresh election simulations and aggregate their distributions."""

from __future__ import annotations

from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from concordia.language_model import language_model

from concordia_riverbend.agents.voter import VoterProfile
from concordia_riverbend.experiments.election import ElectionResult
from concordia_riverbend.experiments.election import run_election


@dataclass(frozen=True)
class RepeatedElectionResult:
    """Independent election runs and aggregate descriptive statistics."""

    candidates: tuple[str, ...]
    runs: tuple[ElectionResult, ...]

    @property
    def total_tally(self) -> dict[str, int]:
        counts: Counter[str] = Counter()
        for run in self.runs:
            counts.update(run.tally)
        return {candidate: counts[candidate] for candidate in self.candidates}

    @property
    def vote_shares(self) -> dict[str, float]:
        tally = self.total_tally
        total = sum(tally.values())
        return {
            candidate: tally[candidate] / total
            for candidate in self.candidates
        }

    @property
    def choices_by_voter(self) -> dict[str, dict[str, int]]:
        counts_by_voter: dict[str, Counter[str]] = {}
        for run in self.runs:
            for outcome in run.outcomes:
                counts_by_voter.setdefault(outcome.voter, Counter()).update(
                    [outcome.candidate]
                )
        return {
            voter: {
                candidate: counts[candidate]
                for candidate in self.candidates
            }
            for voter, counts in counts_by_voter.items()
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            "num_runs": len(self.runs),
            "candidates": list(self.candidates),
            "total_tally": self.total_tally,
            "vote_shares": self.vote_shares,
            "choices_by_voter": self.choices_by_voter,
            "runs": [run.to_dict() for run in self.runs],
        }


def run_repeated_election(
    *,
    model: language_model.LanguageModel,
    profiles: Sequence[VoterProfile],
    election_observation: str,
    num_runs: int,
    additional_observations: Sequence[str] = (),
    candidates: tuple[str, ...] = ("Alice", "Bob"),
    include_reasons: bool = False,
) -> RepeatedElectionResult:
    """Run independent elections; every run creates fresh agent memories."""
    if num_runs < 1:
        raise ValueError("num_runs must be at least 1.")

    runs = tuple(
        run_election(
            model=model,
            profiles=profiles,
            election_observation=election_observation,
            additional_observations=additional_observations,
            candidates=candidates,
            include_reasons=include_reasons,
        )
        for _ in range(num_runs)
    )
    return RepeatedElectionResult(candidates=candidates, runs=runs)
