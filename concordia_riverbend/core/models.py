"""Validated data contracts shared by scenarios, agents, and frontends."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from dataclasses import field
from typing import Any


def _require_text(value: str, field_name: str) -> None:
    if not value.strip():
        raise ValueError(f"{field_name} must not be empty.")


def _require_unique(values: tuple[str, ...], field_name: str) -> None:
    if len(set(values)) != len(values):
        raise ValueError(f"{field_name} must contain unique values.")


@dataclass(frozen=True)
class AgentSpec:
    """Stable identity and capabilities for one agent in any scenario."""

    agent_id: str
    name: str
    role: str
    goal: str
    initial_location: str
    initial_memories: tuple[str, ...] = ()
    allowed_actions: tuple[str, ...] = ()
    attributes: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for field_name in (
            "agent_id",
            "name",
            "role",
            "goal",
            "initial_location",
        ):
            _require_text(str(getattr(self, field_name)), field_name)
        _require_unique(self.allowed_actions, "allowed_actions")

    def to_dict(self) -> dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "name": self.name,
            "role": self.role,
            "goal": self.goal,
            "initial_location": self.initial_location,
            "initial_memories": list(self.initial_memories),
            "allowed_actions": list(self.allowed_actions),
            "attributes": dict(self.attributes),
        }


@dataclass(frozen=True)
class LocationSpec:
    """A named place that can appear in a scenario world."""

    location_id: str
    name: str
    description: str
    attributes: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _require_text(self.location_id, "location_id")
        _require_text(self.name, "name")
        _require_text(self.description, "description")

    def to_dict(self) -> dict[str, Any]:
        return {
            "location_id": self.location_id,
            "name": self.name,
            "description": self.description,
            "attributes": dict(self.attributes),
        }


@dataclass(frozen=True)
class ActionSpec:
    """One world action that agents may request from the Game Master."""

    action_type: str
    description: str
    parameter_names: tuple[str, ...] = ()
    optional_parameter_names: tuple[str, ...] = ()
    allowed_roles: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _require_text(self.action_type, "action_type")
        _require_text(self.description, "description")
        _require_unique(self.parameter_names, "parameter_names")
        _require_unique(
            self.optional_parameter_names,
            "optional_parameter_names",
        )
        overlap = set(self.parameter_names) & set(
            self.optional_parameter_names
        )
        if overlap:
            raise ValueError(
                "Required and optional parameters must not overlap."
            )
        _require_unique(self.allowed_roles, "allowed_roles")

    def to_dict(self) -> dict[str, Any]:
        return {
            "action_type": self.action_type,
            "description": self.description,
            "parameter_names": list(self.parameter_names),
            "optional_parameter_names": list(
                self.optional_parameter_names
            ),
            "allowed_roles": list(self.allowed_roles),
        }


@dataclass(frozen=True)
class WorldEvent:
    """An observable fact emitted by the world or an accepted action."""

    event_id: str
    round_index: int
    event_type: str
    content: str
    actor_id: str | None = None
    location_id: str | None = None
    audience: tuple[str, ...] = ()
    is_public: bool = True
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _require_text(self.event_id, "event_id")
        _require_text(self.event_type, "event_type")
        _require_text(self.content, "content")
        if self.round_index < 0:
            raise ValueError("round_index must be non-negative.")
        _require_unique(self.audience, "audience")
        if not self.is_public and not self.audience:
            raise ValueError("A private event requires at least one audience member.")

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id,
            "round_index": self.round_index,
            "event_type": self.event_type,
            "content": self.content,
            "actor_id": self.actor_id,
            "location_id": self.location_id,
            "audience": list(self.audience),
            "is_public": self.is_public,
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class ScenarioSpec:
    """Complete static definition of one reusable simulation scenario."""

    scenario_id: str
    title: str
    description: str
    agents: tuple[AgentSpec, ...]
    locations: tuple[LocationSpec, ...]
    actions: tuple[ActionSpec, ...]
    initial_events: tuple[WorldEvent, ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _require_text(self.scenario_id, "scenario_id")
        _require_text(self.title, "title")
        _require_text(self.description, "description")
        if not self.agents:
            raise ValueError("A scenario requires at least one agent.")
        if not self.locations:
            raise ValueError("A scenario requires at least one location.")

        agent_ids = tuple(agent.agent_id for agent in self.agents)
        location_ids = tuple(location.location_id for location in self.locations)
        action_types = tuple(action.action_type for action in self.actions)
        _require_unique(agent_ids, "agent IDs")
        _require_unique(location_ids, "location IDs")
        _require_unique(action_types, "action types")

        known_locations = set(location_ids)
        known_actions = set(action_types)
        known_agents = set(agent_ids)
        for agent in self.agents:
            if agent.initial_location not in known_locations:
                raise ValueError(
                    f"Agent {agent.agent_id!r} starts at unknown location "
                    f"{agent.initial_location!r}."
                )
            unknown_actions = set(agent.allowed_actions) - known_actions
            if unknown_actions:
                raise ValueError(
                    f"Agent {agent.agent_id!r} has unknown actions: "
                    + ", ".join(sorted(unknown_actions))
                )

        event_ids = tuple(event.event_id for event in self.initial_events)
        _require_unique(event_ids, "initial event IDs")
        for event in self.initial_events:
            if event.location_id and event.location_id not in known_locations:
                raise ValueError(
                    f"Event {event.event_id!r} uses unknown location "
                    f"{event.location_id!r}."
                )
            unknown_audience = set(event.audience) - known_agents
            if unknown_audience:
                raise ValueError(
                    f"Event {event.event_id!r} has unknown audience members: "
                    + ", ".join(sorted(unknown_audience))
                )

    @property
    def agent_ids(self) -> tuple[str, ...]:
        return tuple(agent.agent_id for agent in self.agents)

    @property
    def location_ids(self) -> tuple[str, ...]:
        return tuple(location.location_id for location in self.locations)

    @property
    def action_types(self) -> tuple[str, ...]:
        return tuple(action.action_type for action in self.actions)

    def to_dict(self) -> dict[str, Any]:
        return {
            "scenario_id": self.scenario_id,
            "title": self.title,
            "description": self.description,
            "agents": [agent.to_dict() for agent in self.agents],
            "locations": [location.to_dict() for location in self.locations],
            "actions": [action.to_dict() for action in self.actions],
            "initial_events": [
                event.to_dict() for event in self.initial_events
            ],
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class SimulationConfig:
    """Runtime choices kept separate from the scenario definition."""

    scenario_id: str
    max_rounds: int
    seed: int
    condition: str = "baseline"
    model_name: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _require_text(self.scenario_id, "scenario_id")
        _require_text(self.condition, "condition")
        if self.max_rounds < 1:
            raise ValueError("max_rounds must be at least 1.")

    def to_dict(self) -> dict[str, Any]:
        return {
            "scenario_id": self.scenario_id,
            "max_rounds": self.max_rounds,
            "seed": self.seed,
            "condition": self.condition,
            "model_name": self.model_name,
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class ActionRequest:
    """A proposed action; it cannot change the world until GM validation."""

    actor_id: str
    action_type: str
    parameters: Mapping[str, Any]
    round_index: int

    def __post_init__(self) -> None:
        _require_text(self.actor_id, "actor_id")
        _require_text(self.action_type, "action_type")
        if self.round_index < 0:
            raise ValueError("round_index must be non-negative.")

    def to_dict(self) -> dict[str, Any]:
        return {
            "actor_id": self.actor_id,
            "action_type": self.action_type,
            "parameters": dict(self.parameters),
            "round_index": self.round_index,
        }


@dataclass(frozen=True)
class ActionResult:
    """The Game Master's grounded decision about a requested action."""

    request: ActionRequest
    accepted: bool
    reason: str
    events: tuple[WorldEvent, ...] = ()
    state_changes: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _require_text(self.reason, "reason")

    def to_dict(self) -> dict[str, Any]:
        return {
            "request": self.request.to_dict(),
            "accepted": self.accepted,
            "reason": self.reason,
            "events": [event.to_dict() for event in self.events],
            "state_changes": dict(self.state_changes),
        }


@dataclass
class WorldState:
    """Mutable grounded state owned by the Game Master, never by the LLM."""

    scenario_id: str
    round_index: int
    agent_locations: dict[str, str]
    variables: dict[str, Any] = field(default_factory=dict)
    relationships: dict[str, dict[str, float]] = field(default_factory=dict)
    events: list[WorldEvent] = field(default_factory=list)

    @classmethod
    def from_scenario(cls, scenario: ScenarioSpec) -> WorldState:
        return cls(
            scenario_id=scenario.scenario_id,
            round_index=0,
            agent_locations={
                agent.agent_id: agent.initial_location
                for agent in scenario.agents
            },
            relationships={
                agent.agent_id: {} for agent in scenario.agents
            },
            events=list(scenario.initial_events),
        )

    def advance_round(self) -> int:
        self.round_index += 1
        return self.round_index

    def move_agent(
        self,
        *,
        agent_id: str,
        destination: str,
        scenario: ScenarioSpec,
    ) -> None:
        if agent_id not in scenario.agent_ids:
            raise ValueError(f"Unknown agent: {agent_id!r}.")
        if destination not in scenario.location_ids:
            raise ValueError(f"Unknown destination: {destination!r}.")
        self.agent_locations[agent_id] = destination

    def record_event(self, event: WorldEvent) -> None:
        if any(existing.event_id == event.event_id for existing in self.events):
            raise ValueError(f"Duplicate event ID: {event.event_id!r}.")
        if event.round_index > self.round_index:
            raise ValueError(
                "Cannot record an event from a future simulation round."
            )
        self.events.append(event)

    def set_relationship(
        self,
        *,
        source_agent_id: str,
        target_agent_id: str,
        value: float,
    ) -> None:
        if source_agent_id not in self.agent_locations:
            raise ValueError(f"Unknown source agent: {source_agent_id!r}.")
        if target_agent_id not in self.agent_locations:
            raise ValueError(f"Unknown target agent: {target_agent_id!r}.")
        if source_agent_id == target_agent_id:
            raise ValueError("An agent cannot have a relationship with itself.")
        if not -1.0 <= value <= 1.0:
            raise ValueError("Relationship values must be between -1 and 1.")
        self.relationships.setdefault(source_agent_id, {})[
            target_agent_id
        ] = value

    def adjust_relationship(
        self,
        *,
        source_agent_id: str,
        target_agent_id: str,
        delta: float,
    ) -> float:
        current = self.relationships.get(source_agent_id, {}).get(
            target_agent_id,
            0.0,
        )
        updated = max(-1.0, min(1.0, current + delta))
        self.set_relationship(
            source_agent_id=source_agent_id,
            target_agent_id=target_agent_id,
            value=updated,
        )
        return updated

    def to_dict(self) -> dict[str, Any]:
        return {
            "scenario_id": self.scenario_id,
            "round_index": self.round_index,
            "agent_locations": dict(self.agent_locations),
            "variables": dict(self.variables),
            "relationships": {
                source: dict(targets)
                for source, targets in self.relationships.items()
            },
            "events": [event.to_dict() for event in self.events],
        }
