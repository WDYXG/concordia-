"""Grounded Skill execution and permission checks for world actions."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any
from typing import Protocol

from concordia_riverbend.core.models import ActionRequest
from concordia_riverbend.core.models import ActionResult
from concordia_riverbend.core.models import AgentSpec
from concordia_riverbend.core.models import ScenarioSpec
from concordia_riverbend.core.models import WorldEvent
from concordia_riverbend.core.models import WorldState


@dataclass(frozen=True)
class PermissionDecision:
    """Result of checking whether an agent may request an action."""

    allowed: bool
    reason: str


class PermissionPolicy:
    """Validates identity, role, declared capability, and action parameters."""

    def check(
        self,
        request: ActionRequest,
        *,
        scenario: ScenarioSpec,
        state: WorldState,
    ) -> PermissionDecision:
        agents = {agent.agent_id: agent for agent in scenario.agents}
        actions = {
            action.action_type: action for action in scenario.actions
        }
        agent = agents.get(request.actor_id)
        if agent is None:
            return PermissionDecision(False, "Unknown agent.")
        action = actions.get(request.action_type)
        if action is None:
            return PermissionDecision(False, "Unknown action type.")
        if request.round_index != state.round_index:
            return PermissionDecision(
                False,
                "The request does not belong to the current simulation round.",
            )
        if request.action_type not in agent.allowed_actions:
            return PermissionDecision(
                False,
                "This action is not in the agent's capability list.",
            )
        if action.allowed_roles and agent.role not in action.allowed_roles:
            return PermissionDecision(
                False,
                "The agent's role is not permitted to use this action.",
            )
        missing = set(action.parameter_names) - set(request.parameters)
        if missing:
            return PermissionDecision(
                False,
                "Missing required parameters: " + ", ".join(sorted(missing)),
            )
        known_parameters = set(action.parameter_names) | set(
            action.optional_parameter_names
        )
        unknown = set(request.parameters) - known_parameters
        if unknown:
            return PermissionDecision(
                False,
                "Unknown parameters: " + ", ".join(sorted(unknown)),
            )
        return PermissionDecision(True, "The request passed general policy.")


class SkillHandler(Protocol):
    """One deterministic implementation of an ActionSpec."""

    def execute(
        self,
        request: ActionRequest,
        *,
        agent: AgentSpec,
        scenario: ScenarioSpec,
        state: WorldState,
        event_id: str,
    ) -> ActionResult:
        """Validate domain rules and return the grounded outcome."""


def _rejected(request: ActionRequest, reason: str) -> ActionResult:
    return ActionResult(request=request, accepted=False, reason=reason)


def _accepted(
    request: ActionRequest,
    *,
    reason: str,
    event: WorldEvent,
    state_changes: Mapping[str, Any],
) -> ActionResult:
    return ActionResult(
        request=request,
        accepted=True,
        reason=reason,
        events=(event,),
        state_changes=state_changes,
    )


class MoveSkill:
    """Move an agent between declared scenario locations."""

    def execute(
        self,
        request: ActionRequest,
        *,
        agent: AgentSpec,
        scenario: ScenarioSpec,
        state: WorldState,
        event_id: str,
    ) -> ActionResult:
        destination = str(request.parameters["destination"])
        if destination not in scenario.location_ids:
            return _rejected(request, "The destination does not exist.")
        previous = state.agent_locations[agent.agent_id]
        if destination == previous:
            return _rejected(request, "The agent is already at that location.")
        state.move_agent(
            agent_id=agent.agent_id,
            destination=destination,
            scenario=scenario,
        )
        event = WorldEvent(
            event_id=event_id,
            round_index=state.round_index,
            event_type="movement",
            actor_id=agent.agent_id,
            location_id=destination,
            content=f"{agent.name} moved from {previous} to {destination}.",
            metadata={"origin": previous, "destination": destination},
        )
        return _accepted(
            request,
            reason="The destination is accessible.",
            event=event,
            state_changes={
                f"agent_locations.{agent.agent_id}": destination
            },
        )


class SpeakSkill:
    """Emit a public statement or a private message with provenance."""

    def execute(
        self,
        request: ActionRequest,
        *,
        agent: AgentSpec,
        scenario: ScenarioSpec,
        state: WorldState,
        event_id: str,
    ) -> ActionResult:
        message = str(request.parameters["message"]).strip()
        channel = str(request.parameters["channel"]).strip().lower()
        raw_recipients = request.parameters["recipients"]
        if not message:
            return _rejected(request, "A message cannot be empty.")
        if channel not in {"public", "private"}:
            return _rejected(
                request,
                "The channel must be either public or private.",
            )
        if not isinstance(raw_recipients, (list, tuple)):
            return _rejected(request, "Recipients must be a list.")
        recipients = tuple(str(item) for item in raw_recipients)
        if len(set(recipients)) != len(recipients):
            return _rejected(request, "Recipients must be unique.")
        unknown = set(recipients) - set(scenario.agent_ids)
        if unknown:
            return _rejected(
                request,
                "Unknown recipients: " + ", ".join(sorted(unknown)),
            )
        if channel == "private" and not recipients:
            return _rejected(
                request,
                "A private message requires at least one recipient.",
            )

        source_event_id = request.parameters.get("source_event_id")
        if source_event_id is not None:
            visible_ids = {
                event.event_id
                for event in visible_events_for(
                    agent.agent_id,
                    state.events,
                )
            }
            if str(source_event_id) not in visible_ids:
                return _rejected(
                    request,
                    "The agent cannot relay an event it has not observed.",
                )

        if channel == "public":
            audience: tuple[str, ...] = ()
            is_public = True
        else:
            audience = tuple(
                dict.fromkeys((agent.agent_id,) + recipients)
            )
            is_public = False
        event = WorldEvent(
            event_id=event_id,
            round_index=state.round_index,
            event_type=(
                "public_statement"
                if channel == "public"
                else "private_message"
            ),
            actor_id=agent.agent_id,
            location_id=state.agent_locations[agent.agent_id],
            content=message,
            audience=audience,
            is_public=is_public,
            metadata={
                "channel": channel,
                "recipients": list(recipients),
                "source_event_id": source_event_id,
            },
        )
        relationship_changes: dict[str, Any] = {}
        if channel == "private":
            for recipient in recipients:
                if recipient == agent.agent_id:
                    continue
                outward = state.adjust_relationship(
                    source_agent_id=agent.agent_id,
                    target_agent_id=recipient,
                    delta=0.05,
                )
                inward = state.adjust_relationship(
                    source_agent_id=recipient,
                    target_agent_id=agent.agent_id,
                    delta=0.05,
                )
                relationship_changes[
                    f"relationships.{agent.agent_id}.{recipient}"
                ] = outward
                relationship_changes[
                    f"relationships.{recipient}.{agent.agent_id}"
                ] = inward
        return _accepted(
            request,
            reason=f"The {channel} message was delivered.",
            event=event,
            state_changes=relationship_changes,
        )


class InspectSkill:
    """Inspect the agent's current location without leaking other state."""

    def execute(
        self,
        request: ActionRequest,
        *,
        agent: AgentSpec,
        scenario: ScenarioSpec,
        state: WorldState,
        event_id: str,
    ) -> ActionResult:
        target = str(request.parameters["target"])
        current_location = state.agent_locations[agent.agent_id]
        if target != current_location:
            return _rejected(
                request,
                "An agent may inspect only its current location.",
            )
        location = next(
            item
            for item in scenario.locations
            if item.location_id == current_location
        )
        event = WorldEvent(
            event_id=event_id,
            round_index=state.round_index,
            event_type="inspection",
            actor_id=agent.agent_id,
            location_id=current_location,
            content=f"{location.name}: {location.description}",
            audience=(agent.agent_id,),
            is_public=False,
            metadata={"target": target},
        )
        return _accepted(
            request,
            reason="The location is available to inspect.",
            event=event,
            state_changes={},
        )


class VoteSkill:
    """Record one secret ballot per agent at the configured voting place."""

    def execute(
        self,
        request: ActionRequest,
        *,
        agent: AgentSpec,
        scenario: ScenarioSpec,
        state: WorldState,
        event_id: str,
    ) -> ActionResult:
        candidate = str(request.parameters["candidate"])
        reason = str(request.parameters.get("reason", "")).strip()
        candidates = tuple(
            str(item) for item in scenario.metadata.get("candidates", ())
        )
        if candidate not in candidates:
            return _rejected(request, "The candidate is not eligible.")
        voting_location = str(
            scenario.metadata.get("voting_location", "town_hall")
        )
        if state.agent_locations[agent.agent_id] != voting_location:
            return _rejected(
                request,
                f"The agent must be at {voting_location} to vote.",
            )
        ballots = state.variables.setdefault("ballots", {})
        if agent.agent_id in ballots:
            return _rejected(request, "The agent has already voted.")
        ballots[agent.agent_id] = candidate
        state_changes: dict[str, Any] = {
            f"ballots.{agent.agent_id}": candidate
        }
        if reason:
            vote_reasons = state.variables.setdefault(
                "vote_reasons",
                {},
            )
            vote_reasons[agent.agent_id] = reason
            state_changes[
                f"vote_reasons.{agent.agent_id}"
            ] = reason
        event = WorldEvent(
            event_id=event_id,
            round_index=state.round_index,
            event_type="secret_ballot",
            actor_id=agent.agent_id,
            location_id=voting_location,
            content=f"{agent.name} cast a secret ballot.",
            audience=(agent.agent_id,),
            is_public=False,
            metadata={"candidate": candidate, "reason": reason},
        )
        return _accepted(
            request,
            reason="The secret ballot was recorded.",
            event=event,
            state_changes=state_changes,
        )


def visible_events_for(
    agent_id: str,
    events: list[WorldEvent] | tuple[WorldEvent, ...],
) -> tuple[WorldEvent, ...]:
    """Return public events plus private events addressed to one agent."""
    return tuple(
        event
        for event in events
        if event.is_public
        or agent_id in event.audience
        or event.actor_id == agent_id
    )


class SkillRegistry:
    """Routes permitted action requests to deterministic Skill handlers."""

    def __init__(
        self,
        *,
        handlers: Mapping[str, SkillHandler] | None = None,
        permission_policy: PermissionPolicy | None = None,
    ) -> None:
        self._handlers: dict[str, SkillHandler] = dict(
            handlers
            or {
                "move": MoveSkill(),
                "speak": SpeakSkill(),
                "inspect": InspectSkill(),
                "vote": VoteSkill(),
            }
        )
        self._permission_policy = permission_policy or PermissionPolicy()

    def execute(
        self,
        request: ActionRequest,
        *,
        scenario: ScenarioSpec,
        state: WorldState,
        event_id_factory: Callable[[], str],
    ) -> ActionResult:
        permission = self._permission_policy.check(
            request,
            scenario=scenario,
            state=state,
        )
        if not permission.allowed:
            return _rejected(request, permission.reason)
        handler = self._handlers.get(request.action_type)
        if handler is None:
            return _rejected(
                request,
                "No deterministic handler is registered for this action.",
            )
        agent = next(
            agent
            for agent in scenario.agents
            if agent.agent_id == request.actor_id
        )
        result = handler.execute(
            request,
            agent=agent,
            scenario=scenario,
            state=state,
            event_id=event_id_factory(),
        )
        if result.accepted:
            for event in result.events:
                state.record_event(event)
        return result
