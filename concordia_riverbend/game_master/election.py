"""A deterministic Concordia Game Master for a secret-ballot election."""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
import threading

from concordia.agents import entity_agent_with_logging
from concordia.components import game_master as gm_components
from concordia.environment import engine as engine_lib
from concordia.environment.engines import sequential
from concordia.language_model import language_model
from concordia.language_model import no_language_model
from concordia.typing import entity
from concordia.typing import entity_component

from concordia_riverbend.agents.voter import BuiltVoter
from concordia_riverbend.agents.voter import VoterProfile
from concordia_riverbend.agents.voter import build_voter_agent
from concordia_riverbend.experiments.election import ElectionResult
from concordia_riverbend.experiments.election import VoterOutcome
from concordia_riverbend.scenarios.election_conditions import ElectionCondition


class VoteLedger:
    """A grounded, deterministic record that accepts one valid vote per voter."""

    def __init__(
        self,
        *,
        voter_names: Sequence[str],
        candidates: Sequence[str],
    ) -> None:
        if not voter_names:
            raise ValueError("Vote ledger requires at least one voter.")
        if len(set(voter_names)) != len(voter_names):
            raise ValueError("Voter names must be unique.")
        if len(candidates) < 2 or len(set(candidates)) != len(candidates):
            raise ValueError("Candidates must contain unique choices.")
        self._voter_names = tuple(voter_names)
        self._candidates = tuple(candidates)
        self._votes: dict[str, str] = {}
        self._lock = threading.Lock()

    @property
    def voter_names(self) -> tuple[str, ...]:
        return self._voter_names

    @property
    def candidates(self) -> tuple[str, ...]:
        return self._candidates

    def record(self, voter: str, candidate: str) -> None:
        with self._lock:
            if voter not in self._voter_names:
                raise ValueError(f"Unknown voter: {voter!r}.")
            if candidate not in self._candidates:
                raise ValueError(f"Invalid candidate: {candidate!r}.")
            if voter in self._votes:
                raise ValueError(f"Voter {voter!r} has already voted.")
            self._votes[voter] = candidate

    @property
    def is_complete(self) -> bool:
        with self._lock:
            return len(self._votes) == len(self._voter_names)

    @property
    def votes(self) -> dict[str, str]:
        with self._lock:
            return dict(self._votes)

    @property
    def tally(self) -> dict[str, int]:
        with self._lock:
            counts = Counter(self._votes.values())
            return {
                candidate: counts[candidate]
                for candidate in self._candidates
            }

    def set_votes(self, votes: Mapping[str, str]) -> None:
        with self._lock:
            self._votes = {}
        for voter in self._voter_names:
            if voter in votes:
                self.record(voter, votes[voter])


class VoteAdministration(entity_component.ContextComponent):
    """Supplies vote action specs, resolves votes, and ends the episode."""

    def __init__(self, ledger: VoteLedger) -> None:
        super().__init__()
        self._ledger = ledger
        self._last_observation = ""

    def pre_observe(self, observation: str) -> str:
        self._last_observation = observation
        return ""

    def _record_putative_vote(self) -> str:
        tag = sequential.PUTATIVE_EVENT_TAG
        if not self._last_observation.startswith(tag):
            raise ValueError(
                "Vote resolution requires a putative event, received: "
                f"{self._last_observation!r}"
            )
        action = self._last_observation.removeprefix(tag).strip()
        voter, separator, candidate = action.partition(":")
        if not separator:
            raise ValueError(f"Could not parse vote action: {action!r}.")
        voter = voter.strip()
        candidate = candidate.strip()
        self._ledger.record(voter, candidate)
        return f"Vote recorded for {voter}."

    def pre_act(self, action_spec: entity.ActionSpec) -> str:
        if action_spec.output_type == entity.OutputType.TERMINATE:
            return "Yes" if self._ledger.is_complete else "No"
        if action_spec.output_type == entity.OutputType.NEXT_ACTION_SPEC:
            vote_spec = entity.ActionSpec(
                call_to_action=(
                    "{name}, cast your secret ballot. Choose exactly one "
                    "candidate."
                ),
                output_type=entity.OutputType.CHOICE,
                options=self._ledger.candidates,
                tag="vote",
            )
            return engine_lib.action_spec_to_string(vote_spec)
        if action_spec.output_type == entity.OutputType.RESOLVE:
            return self._record_putative_vote()
        return ""

    def get_state(self) -> entity_component.ComponentState:
        return {
            "last_observation": self._last_observation,
            "votes": self._ledger.votes,
        }

    def set_state(self, state: entity_component.ComponentState) -> None:
        self._last_observation = str(state.get("last_observation", ""))
        self._ledger.set_votes(state.get("votes", {}))


@dataclass(frozen=True)
class DeterministicElectionGameMaster:
    """Concordia GM entity and its grounded experimental state."""

    agent: entity_agent_with_logging.EntityAgentWithLogging
    ledger: VoteLedger
    broadcasts: tuple[str, ...]
    condition_name: str


@dataclass(frozen=True)
class GMElectionRun:
    """One completed GM-administered election."""

    election: ElectionResult
    game_master: DeterministicElectionGameMaster

    def game_master_record(self) -> dict[str, object]:
        return {
            "name": self.game_master.agent.name,
            "deterministic": True,
            "condition": self.game_master.condition_name,
            "broadcasts": list(self.game_master.broadcasts),
            "ledger": self.game_master.ledger.votes,
            "tally": self.game_master.ledger.tally,
        }


def build_election_game_master(
    *,
    voter_names: Sequence[str],
    candidates: tuple[str, ...],
    base_observation: str,
    condition: ElectionCondition,
) -> DeterministicElectionGameMaster:
    """Build a Concordia GM whose control flow never calls an LLM."""
    gm_model = no_language_model.NoLanguageModel()
    ledger = VoteLedger(voter_names=voter_names, candidates=candidates)
    administration = VoteAdministration(ledger)

    observation_component = gm_components.make_observation.MakeObservation(
        model=gm_model,
        player_names=voter_names,
        allow_llm_fallback=False,
    )
    broadcasts = [base_observation]
    if condition.event:
        broadcasts.append(condition.event)
    for broadcast in broadcasts:
        observation_component.add_to_queue("all", broadcast)

    next_acting = gm_components.next_acting.NextActingInFixedOrder(
        sequence=voter_names
    )
    context_components = {
        gm_components.next_acting.DEFAULT_NEXT_ACTING_COMPONENT_KEY: (
            next_acting
        ),
        gm_components.next_acting.DEFAULT_NEXT_ACTION_SPEC_COMPONENT_KEY: (
            administration
        ),
        gm_components.terminate.DEFAULT_TERMINATE_COMPONENT_KEY: administration,
        gm_components.make_observation.DEFAULT_MAKE_OBSERVATION_COMPONENT_KEY: (
            observation_component
        ),
        gm_components.event_resolution.DEFAULT_RESOLUTION_COMPONENT_KEY: (
            administration
        ),
    }
    act_component = gm_components.switch_act.SwitchAct(
        model=gm_model,
        entity_names=voter_names,
    )
    gm_agent = entity_agent_with_logging.EntityAgentWithLogging(
        agent_name="Riverbend Election Game Master",
        act_component=act_component,
        context_components=context_components,
    )
    return DeterministicElectionGameMaster(
        agent=gm_agent,
        ledger=ledger,
        broadcasts=tuple(broadcasts),
        condition_name=condition.name,
    )


def run_gm_election(
    *,
    model: language_model.LanguageModel,
    profiles: Sequence[VoterProfile],
    base_observation: str,
    condition: ElectionCondition,
    candidates: tuple[str, ...] = ("Alice", "Bob"),
) -> GMElectionRun:
    """Build fresh voter agents and administer one election through the GM."""
    voters: list[BuiltVoter] = [
        build_voter_agent(model=model, profile=profile)
        for profile in profiles
    ]
    game_master = build_election_game_master(
        voter_names=[voter.profile.name for voter in voters],
        candidates=candidates,
        base_observation=base_observation,
        condition=condition,
    )
    engine = sequential.Sequential()
    engine.run_loop(
        game_masters=[game_master.agent],
        entities=[voter.agent for voter in voters],
        max_steps=len(voters),
        verbose=False,
    )
    if not game_master.ledger.is_complete:
        raise RuntimeError("Election ended before every voter cast a ballot.")

    votes = game_master.ledger.votes
    election = ElectionResult(
        candidates=candidates,
        outcomes=tuple(
            VoterOutcome(
                voter=profile.name,
                candidate=votes[profile.name],
                reason="",
            )
            for profile in profiles
        ),
    )
    return GMElectionRun(election=election, game_master=game_master)
