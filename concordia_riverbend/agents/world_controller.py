"""LLM-backed controller that can only propose grounded world actions."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
import json
from typing import Any

from concordia.language_model import language_model

from concordia_riverbend.core import ActionRequest
from concordia_riverbend.core import ActionResult
from concordia_riverbend.core import AgentSpec
from concordia_riverbend.core import AgentTurnContext
from concordia_riverbend.core import ScenarioSpec


@dataclass(frozen=True)
class ControllerCall:
    """One auditable model response used to propose a world action."""

    round_index: int
    prompt: str
    raw_response: str
    parsed_action: Mapping[str, Any] | None
    error: str | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "round_index": self.round_index,
            "prompt": self.prompt,
            "raw_response": self.raw_response,
            "parsed_action": (
                dict(self.parsed_action)
                if self.parsed_action is not None
                else None
            ),
            "error": self.error,
        }


class LLMWorldController:
    """Uses a Concordia LanguageModel to propose, never apply, actions."""

    def __init__(
        self,
        *,
        model: language_model.LanguageModel,
        agent: AgentSpec,
        scenario: ScenarioSpec,
        max_attempts: int = 2,
    ) -> None:
        if agent.agent_id not in scenario.agent_ids:
            raise ValueError("The controller agent is not in the scenario.")
        if max_attempts < 1:
            raise ValueError("max_attempts must be at least 1.")
        self.model = model
        self.agent = agent
        self.scenario = scenario
        self.max_attempts = max_attempts
        self.calls: list[ControllerCall] = []
        self.results: list[ActionResult] = []

    def _prompt(self, context: AgentTurnContext) -> str:
        phase_actions = context.public_variables.get("allowed_actions")
        phase_action_set = (
            set(phase_actions)
            if isinstance(phase_actions, (list, tuple, set))
            else None
        )
        action_specs = [
            {
                "action_type": action.action_type,
                "description": action.description,
                "required_parameters": list(action.parameter_names),
                "optional_parameters": list(
                    action.optional_parameter_names
                ),
            }
            for action in self.scenario.actions
            if action.action_type in self.agent.allowed_actions
            and (
                phase_action_set is None
                or action.action_type in phase_action_set
            )
        ]
        events = [
            {
                "event_id": event.event_id,
                "event_type": event.event_type,
                "content": event.content,
                "source_agent_id": event.actor_id,
            }
            for event in context.new_events
        ]
        memories = [
            {
                "memory_id": memory.get("memory_id"),
                "memory_type": memory.get("memory_type"),
                "content": memory.get("content"),
                "source_event_id": memory.get("source_event_id"),
            }
            for memory in context.recalled_memories
        ]
        previous_action_result = (
            self.results[-1].to_dict() if self.results else None
        )
        world_context = {
            "identity": {
                "name": self.agent.name,
                "role": self.agent.role,
                "goal": self.agent.goal,
                "background": self.agent.attributes.get(
                    "background",
                    "",
                ),
            },
            "round_index": context.round_index,
            "current_location": context.location_id,
            "new_events": events,
            "recalled_memories": memories,
            "relationships": dict(context.own_relationships),
            "public_world_variables": dict(context.public_variables),
            "previous_action_result": previous_action_result,
            "scenario_metadata": dict(self.scenario.metadata),
            "available_actions": action_specs,
        }
        return (
            "You are an Agent inside a fictional social simulation. "
            "Stay in character and choose at most one available action. "
            "You may propose an action, but the Game Master will independently "
            "validate permissions and world rules. Do not invent a Skill or "
            "claim that the world already changed. Treat "
            "previous_action_result as authoritative feedback; when it was "
            "rejected, use its reason to correct the next action.\n\n"
            f"World context:\n{json.dumps(world_context, ensure_ascii=False)}"
            "\n\nReturn JSON only. To act, return "
            '{"action_type":"<available action>","parameters":{...}}. '
            'For a vote, include both "candidate" and a concise, '
            'first-person "reason" in parameters; do not make a separate '
            'reasoning call. To wait, return '
            '{"action_type":"wait","parameters":{}}.'
        )

    def choose_action(
        self,
        context: AgentTurnContext,
    ) -> ActionRequest | None:
        prompt = self._prompt(context)
        last_error = ""
        for _ in range(self.max_attempts):
            raw = self.model.sample_text(
                prompt,
                max_tokens=350,
                temperature=0.4,
                top_p=0.95,
            ).strip()
            parsed: Mapping[str, Any] | None = None
            error: str | None = None
            try:
                value = json.loads(raw)
                if not isinstance(value, dict):
                    raise ValueError("The response must be a JSON object.")
                action_type = str(value["action_type"]).strip()
                parameters = value.get("parameters", {})
                if not isinstance(parameters, dict):
                    raise ValueError("parameters must be a JSON object.")
                if action_type == "vote":
                    reason = parameters.get("reason")
                    if not isinstance(reason, str) or not reason.strip():
                        raise ValueError(
                            "A vote action requires a concise reason."
                        )
                    parameters = {
                        **parameters,
                        "reason": reason.strip(),
                    }
                parsed = {
                    "action_type": action_type,
                    "parameters": parameters,
                }
            except (json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
                error = str(exc)
                last_error = error
            self.calls.append(
                ControllerCall(
                    round_index=context.round_index,
                    prompt=prompt,
                    raw_response=raw,
                    parsed_action=parsed,
                    error=error,
                )
            )
            if parsed is None:
                continue
            if parsed["action_type"] == "wait":
                return None
            return ActionRequest(
                actor_id=self.agent.agent_id,
                action_type=str(parsed["action_type"]),
                parameters=dict(parsed["parameters"]),
                round_index=context.round_index,
            )
        raise language_model.InvalidResponseError(
            "The Agent did not return a valid action JSON after "
            f"{self.max_attempts} attempts. Last error: {last_error}"
        )

    def receive_result(self, result: ActionResult) -> None:
        self.results.append(result)

    def trace(self) -> dict[str, Any]:
        return {
            "agent_id": self.agent.agent_id,
            "calls": [call.to_dict() for call in self.calls],
            "results": [result.to_dict() for result in self.results],
        }
