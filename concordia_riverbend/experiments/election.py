"""Run a shared election observation through independent voter agents."""

from __future__ import annotations

from collections import Counter
from collections.abc import Sequence
from dataclasses import asdict
from dataclasses import dataclass
from typing import Any

from concordia.language_model import language_model

from concordia_riverbend.agents.voter import VoterProfile
from concordia_riverbend.agents.voter import build_voter_agent
from concordia_riverbend.agents.voter import run_vote


@dataclass(frozen=True)
class VoterOutcome:
    """One voter's observable output."""

    voter: str
    candidate: str
    reason: str


@dataclass(frozen=True)
class ElectionResult:
    """All individual outcomes and the aggregate vote count."""

    candidates: tuple[str, ...]
    outcomes: tuple[VoterOutcome, ...]

    @property
    def tally(self) -> dict[str, int]:
        counts = Counter(outcome.candidate for outcome in self.outcomes)
        return {candidate: counts[candidate] for candidate in self.candidates}

    def to_dict(self) -> dict[str, Any]:
        return {
            "candidates": list(self.candidates),
            "tally": self.tally,
            "outcomes": [asdict(outcome) for outcome in self.outcomes],
        }


def run_election(
    *,
    model: language_model.LanguageModel,
    profiles: Sequence[VoterProfile],
    election_observation: str,
    additional_observations: Sequence[str] = (),
    candidates: tuple[str, ...] = ("Alice", "Bob"),
    include_reasons: bool = True,
) -> ElectionResult:
    """Run one independent Concordia voter per profile."""
    if not profiles:
        raise ValueError("At least one voter profile is required.")
    names = [profile.name for profile in profiles]
    if len(set(names)) != len(names):
        raise ValueError("Voter profile names must be unique.")

    outcomes: list[VoterOutcome] = []
    for profile in profiles:
        voter = build_voter_agent(model=model, profile=profile)
        decision = run_vote(
            voter,
            election_observation=election_observation,
            additional_observations=additional_observations,
            candidates=candidates,
            include_reason=include_reasons,
        )
        outcomes.append(
            VoterOutcome(
                voter=profile.name,
                candidate=decision.candidate,
                reason=decision.reason,
            )
        )

    return ElectionResult(candidates=candidates, outcomes=tuple(outcomes))
