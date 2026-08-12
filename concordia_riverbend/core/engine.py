"""Deterministic multi-round orchestration for Agent world simulations."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any
from typing import Protocol

from concordia_riverbend.core.models import ActionRequest
from concordia_riverbend.core.models import ActionResult
from concordia_riverbend.core.models import AgentSpec
from concordia_riverbend.core.models import ScenarioSpec
from concordia_riverbend.core.models import SimulationConfig
from concordia_riverbend.core.models import WorldEvent
from concordia_riverbend.core.models import WorldState
from concordia_riverbend.core.skills import SkillRegistry
from concordia_riverbend.core.skills import visible_events_for


@dataclass(frozen=True)
class AgentTurnContext:
    """The bounded world view available to one Agent for one turn."""

    agent: AgentSpec
    round_index: int
    location_id: str
    new_events: tuple[WorldEvent, ...]
    recalled_memories: tuple[Mapping[str, Any], ...]
    own_relationships: Mapping[str, float]
    public_variables: Mapping[str, Any]


class AgentController(Protocol):
    """Decision boundary implemented by scripted or LLM-backed Agents."""

    def choose_action(
        self,
        context: AgentTurnContext,
    ) -> ActionRequest | None:
        """Return one proposed action or wait for this turn."""

    def receive_result(self, result: ActionResult) -> None:
        """Receive grounded feedback from the Game Master."""


class RoundScheduler(Protocol):
    """Applies deterministic world changes at the start of each round."""

    def start_round(self, game_master: WorldGameMaster) -> None:
        """Advance scheduled events, phases, and world state."""


@dataclass(frozen=True)
class TurnRecord:
    """One Agent turn and its optional resolved action."""

    round_index: int
    agent_id: str
    observed_event_ids: tuple[str, ...]
    recalled_memory_ids: tuple[str, ...]
    result: ActionResult | None
    state_after: Mapping[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "round_index": self.round_index,
            "agent_id": self.agent_id,
            "observed_event_ids": list(self.observed_event_ids),
            "recalled_memory_ids": list(self.recalled_memory_ids),
            "result": self.result.to_dict() if self.result else None,
            "state_after": dict(self.state_after),
        }


@dataclass(frozen=True)
class SimulationRun:
    """Complete replayable result of one deterministic orchestration run."""

    scenario: ScenarioSpec
    config: SimulationConfig
    turns: tuple[TurnRecord, ...]
    snapshots: tuple[Mapping[str, Any], ...]
    final_state: WorldState
    memory_state: Mapping[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "scenario": self.scenario.to_dict(),
            "config": self.config.to_dict(),
            "turns": [turn.to_dict() for turn in self.turns],
            "snapshots": [dict(snapshot) for snapshot in self.snapshots],
            "final_state": self.final_state.to_dict(),
            "memory_state": dict(self.memory_state),
        }


class ScriptedAgentController:
    """Deterministic controller used for tests and no-API browser demos."""

    def __init__(
        self,
        actions: Sequence[tuple[str, Mapping[str, Any]]],
    ) -> None:
        self._actions = tuple(actions)
        self._index = 0
        self.results: list[ActionResult] = []
        self.contexts: list[AgentTurnContext] = []

    def choose_action(
        self,
        context: AgentTurnContext,
    ) -> ActionRequest | None:
        self.contexts.append(context)
        if self._index >= len(self._actions):
            return None
        action_type, parameters = self._actions[self._index]
        self._index += 1
        return ActionRequest(
            actor_id=context.agent.agent_id,
            action_type=action_type,
            parameters=dict(parameters),
            round_index=context.round_index,
        )

    def receive_result(self, result: ActionResult) -> None:
        self.results.append(result)


class WorldGameMaster:
    """Owns grounded state and resolves all proposed actions."""

    def __init__(
        self,
        *,
        scenario: ScenarioSpec,
        state: WorldState | None = None,
        skill_registry: SkillRegistry | None = None,
    ) -> None:
        self.scenario = scenario
        self.state = state or WorldState.from_scenario(scenario)
        self.skill_registry = skill_registry or SkillRegistry()
        self._event_sequence = len(self.state.events)

    def _next_event_id(self) -> str:
        self._event_sequence += 1
        return (
            f"round_{self.state.round_index:03d}_"
            f"event_{self._event_sequence:04d}"
        )

    def resolve(self, request: ActionRequest) -> ActionResult:
        allowed_actions = self.state.variables.get("allowed_actions")
        if (
            isinstance(allowed_actions, Sequence)
            and not isinstance(allowed_actions, (str, bytes))
            and request.action_type not in allowed_actions
        ):
            phase = self.state.variables.get("phase", "current")
            return ActionResult(
                request=request,
                accepted=False,
                reason=(
                    f"Action {request.action_type!r} is not available "
                    f"during the {phase} phase."
                ),
            )
        return self.skill_registry.execute(
            request,
            scenario=self.scenario,
            state=self.state,
            event_id_factory=self._next_event_id,
        )


class SimulationRunner:
    """Runs one action per Agent per round through a grounded Game Master."""

    def __init__(
        self,
        *,
        scenario: ScenarioSpec,
        config: SimulationConfig,
        controllers: Mapping[str, AgentController],
        game_master: WorldGameMaster | None = None,
        agent_order: Sequence[str] | None = None,
        memory_system: Any | None = None,
        round_scheduler: RoundScheduler | None = None,
    ) -> None:
        if config.scenario_id != scenario.scenario_id:
            raise ValueError("SimulationConfig targets a different scenario.")
        missing = set(scenario.agent_ids) - set(controllers)
        unknown = set(controllers) - set(scenario.agent_ids)
        if missing:
            raise ValueError(
                "Missing controllers: " + ", ".join(sorted(missing))
            )
        if unknown:
            raise ValueError(
                "Unknown controller IDs: " + ", ".join(sorted(unknown))
            )
        self.scenario = scenario
        self.config = config
        self.controllers = dict(controllers)
        self.game_master = game_master or WorldGameMaster(
            scenario=scenario
        )
        self.agent_order = tuple(agent_order or scenario.agent_ids)
        self.memory_system = memory_system
        self.round_scheduler = round_scheduler
        if set(self.agent_order) != set(scenario.agent_ids):
            raise ValueError(
                "agent_order must contain every scenario agent exactly once."
            )
        if len(self.agent_order) != len(set(self.agent_order)):
            raise ValueError("agent_order must not contain duplicates.")
        self._seen_event_ids: dict[str, set[str]] = {
            agent_id: set() for agent_id in scenario.agent_ids
        }

    def _context_for(self, agent_id: str) -> AgentTurnContext:
        state = self.game_master.state
        visible = visible_events_for(agent_id, state.events)
        new_events = tuple(
            event
            for event in visible
            if event.event_id not in self._seen_event_ids[agent_id]
        )
        self._seen_event_ids[agent_id].update(
            event.event_id for event in new_events
        )
        agent = next(
            item for item in self.scenario.agents
            if item.agent_id == agent_id
        )
        public_variables = {
            key: value
            for key, value in state.variables.items()
            if key not in {"ballots", "vote_reasons", "private"}
        }
        recalled_memories: tuple[Mapping[str, Any], ...] = ()
        if self.memory_system is not None:
            self.memory_system.observe(agent_id, new_events)
            query = " ".join(
                (
                    agent.goal,
                    state.agent_locations[agent_id],
                    *(event.content for event in new_events),
                )
            )
            recalled_memories = tuple(
                self.memory_system.recall(
                    agent_id,
                    query,
                    current_round=state.round_index,
                    limit=5,
                )
            )
        return AgentTurnContext(
            agent=agent,
            round_index=state.round_index,
            location_id=state.agent_locations[agent_id],
            new_events=new_events,
            recalled_memories=recalled_memories,
            own_relationships=dict(
                state.relationships.get(agent_id, {})
            ),
            public_variables=public_variables,
        )

    def run(self) -> SimulationRun:
        turns: list[TurnRecord] = []
        snapshots: list[Mapping[str, Any]] = [
            self.game_master.state.to_dict()
        ]
        for _ in range(self.config.max_rounds):
            self.game_master.state.advance_round()
            if self.round_scheduler is not None:
                self.round_scheduler.start_round(self.game_master)
            for agent_id in self.agent_order:
                context = self._context_for(agent_id)
                controller = self.controllers[agent_id]
                request = controller.choose_action(context)
                result = (
                    self.game_master.resolve(request)
                    if request is not None
                    else None
                )
                if result is not None:
                    controller.receive_result(result)
                turns.append(
                    TurnRecord(
                        round_index=context.round_index,
                        agent_id=agent_id,
                        observed_event_ids=tuple(
                            event.event_id
                            for event in context.new_events
                        ),
                        recalled_memory_ids=tuple(
                            str(memory["memory_id"])
                            for memory in context.recalled_memories
                        ),
                        result=result,
                        state_after=self.game_master.state.to_dict(),
                    )
                )
            snapshots.append(self.game_master.state.to_dict())
        return SimulationRun(
            scenario=self.scenario,
            config=self.config,
            turns=tuple(turns),
            snapshots=tuple(snapshots),
            final_state=self.game_master.state,
            memory_state=(
                self.memory_system.to_dict()
                if self.memory_system is not None
                else {}
            ),
        )
