"""Tests for the no-side-effect LLM world action boundary."""

from __future__ import annotations

import json
import unittest

from concordia_riverbend.agents import LLMWorldController
from concordia_riverbend.core import AgentTurnContext
from concordia_riverbend.core import ScriptedAgentController
from concordia_riverbend.core import SimulationConfig
from concordia_riverbend.core import SimulationRunner
from concordia_riverbend.memory import WorldMemory
from concordia_riverbend.scenarios.riverbend_world import (
    build_riverbend_world,
)


class FakeTextModel:
    def __init__(self, responses: list[str]) -> None:
        self.responses = responses
        self.prompts: list[str] = []

    def sample_text(self, prompt: str, **_: object) -> str:
        self.prompts.append(prompt)
        return self.responses.pop(0)


class FeedbackAwareFakeModel:
    def __init__(self) -> None:
        self.prompts: list[str] = []

    def sample_text(self, prompt: str, **_: object) -> str:
        self.prompts.append(prompt)
        if "The agent must be at town_hall to vote." in prompt:
            return (
                '{"action_type":"move","parameters":'
                '{"destination":"town_hall"}}'
            )
        return (
            '{"action_type":"vote","parameters":{"candidate":"Alice",'
            '"reason":"I prioritize clean water and stable schools."}}'
        )


class LLMWorldControllerTest(unittest.TestCase):
    def test_retries_invalid_json_and_proposes_grounded_request(self) -> None:
        scenario = build_riverbend_world()
        agent = scenario.agents[0]
        model = FakeTextModel(
            [
                "not-json",
                (
                    '{"action_type":"move","parameters":'
                    '{"destination":"town_hall"}}'
                ),
            ]
        )
        controller = LLMWorldController(
            model=model,  # type: ignore[arg-type]
            agent=agent,
            scenario=scenario,
        )
        context = AgentTurnContext(
            agent=agent,
            round_index=1,
            location_id=agent.initial_location,
            new_events=scenario.initial_events,
            recalled_memories=(),
            own_relationships={},
            public_variables={},
        )

        request = controller.choose_action(context)

        self.assertIsNotNone(request)
        assert request is not None
        self.assertEqual(request.actor_id, agent.agent_id)
        self.assertEqual(request.action_type, "move")
        self.assertEqual(request.parameters["destination"], "town_hall")
        self.assertEqual(len(controller.calls), 2)
        self.assertIn("available_actions", model.prompts[-1])

    def test_invalid_skill_is_rejected_by_gm_not_applied_by_model(self) -> None:
        scenario = build_riverbend_world()
        llm_agent = scenario.agents[0]
        controller = LLMWorldController(
            model=FakeTextModel(
                [
                    (
                        '{"action_type":"teleport","parameters":'
                        '{"destination":"town_hall"}}'
                    )
                ]
            ),  # type: ignore[arg-type]
            agent=llm_agent,
            scenario=scenario,
        )
        controllers = {
            agent.agent_id: (
                controller
                if agent.agent_id == llm_agent.agent_id
                else ScriptedAgentController(())
            )
            for agent in scenario.agents
        }
        run = SimulationRunner(
            scenario=scenario,
            config=SimulationConfig(
                scenario_id=scenario.scenario_id,
                max_rounds=1,
                seed=3,
            ),
            controllers=controllers,
            memory_system=WorldMemory(scenario),
        ).run()

        first_result = run.turns[0].result
        self.assertIsNotNone(first_result)
        assert first_result is not None
        self.assertFalse(first_result.accepted)
        self.assertEqual(
            run.final_state.agent_locations[llm_agent.agent_id],
            llm_agent.initial_location,
        )

    def test_wait_produces_no_action_request(self) -> None:
        scenario = build_riverbend_world()
        agent = scenario.agents[0]
        controller = LLMWorldController(
            model=FakeTextModel(
                ['{"action_type":"wait","parameters":{}}']
            ),  # type: ignore[arg-type]
            agent=agent,
            scenario=scenario,
        )
        context = AgentTurnContext(
            agent=agent,
            round_index=1,
            location_id=agent.initial_location,
            new_events=(),
            recalled_memories=(),
            own_relationships={},
            public_variables={},
        )

        self.assertIsNone(controller.choose_action(context))

    def test_vote_reason_is_required_in_the_same_action_response(
        self,
    ) -> None:
        scenario = build_riverbend_world(
            start_at_voting_location=True
        )
        agent = scenario.agents[0]
        model = FakeTextModel(
            [
                (
                    '{"action_type":"vote","parameters":'
                    '{"candidate":"Alice"}}'
                ),
                (
                    '{"action_type":"vote","parameters":'
                    '{"candidate":"Alice","reason":'
                    '"I prioritize clean water and stable schools."}}'
                ),
            ]
        )
        controller = LLMWorldController(
            model=model,  # type: ignore[arg-type]
            agent=agent,
            scenario=scenario,
        )
        context = AgentTurnContext(
            agent=agent,
            round_index=1,
            location_id="town_hall",
            new_events=scenario.initial_events,
            recalled_memories=(),
            own_relationships={},
            public_variables={"allowed_actions": ["vote"]},
        )

        request = controller.choose_action(context)

        self.assertIsNotNone(request)
        assert request is not None
        self.assertEqual(request.action_type, "vote")
        self.assertEqual(
            request.parameters["reason"],
            "I prioritize clean water and stable schools.",
        )
        self.assertEqual(len(controller.calls), 2)
        self.assertIn(
            "requires a concise reason",
            controller.calls[0].error or "",
        )
        self.assertIn(
            'include both "candidate"',
            model.prompts[-1],
        )

    def test_prompt_shows_only_actions_allowed_in_the_current_phase(
        self,
    ) -> None:
        scenario = build_riverbend_world()
        agent = scenario.agents[0]
        controller = LLMWorldController(
            model=FakeTextModel([]),  # type: ignore[arg-type]
            agent=agent,
            scenario=scenario,
        )
        context = AgentTurnContext(
            agent=agent,
            round_index=11,
            location_id="town_hall",
            new_events=(),
            recalled_memories=(),
            own_relationships={},
            public_variables={
                "phase": "election_day",
                "allowed_actions": ["vote"],
            },
        )

        prompt = controller._prompt(context)
        world_json = prompt.split("World context:\n", 1)[1].split(
            "\n\nReturn JSON only.",
            1,
        )[0]
        world_context = json.loads(world_json)

        self.assertEqual(
            [
                action["action_type"]
                for action in world_context["available_actions"]
            ],
            ["vote"],
        )

    def test_rejected_action_feedback_corrects_the_next_turn(self) -> None:
        scenario = build_riverbend_world()
        llm_agent = scenario.agents[0]
        model = FeedbackAwareFakeModel()
        controller = LLMWorldController(
            model=model,  # type: ignore[arg-type]
            agent=llm_agent,
            scenario=scenario,
        )
        controllers = {
            agent.agent_id: (
                controller
                if agent.agent_id == llm_agent.agent_id
                else ScriptedAgentController(())
            )
            for agent in scenario.agents
        }

        run = SimulationRunner(
            scenario=scenario,
            config=SimulationConfig(
                scenario_id=scenario.scenario_id,
                max_rounds=2,
                seed=17,
            ),
            controllers=controllers,
        ).run()

        agent_turns = [
            turn
            for turn in run.turns
            if turn.agent_id == llm_agent.agent_id
        ]
        first_result = agent_turns[0].result
        second_result = agent_turns[1].result
        assert first_result is not None
        assert second_result is not None
        self.assertFalse(first_result.accepted)
        self.assertEqual(first_result.request.action_type, "vote")
        self.assertTrue(second_result.accepted)
        self.assertEqual(second_result.request.action_type, "move")
        self.assertIn("previous_action_result", model.prompts[1])
        self.assertIn(first_result.reason, model.prompts[1])
        self.assertEqual(
            run.final_state.agent_locations[llm_agent.agent_id],
            "town_hall",
        )
