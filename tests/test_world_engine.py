"""Tests for multi-round orchestration, Skills, and permission boundaries."""

from __future__ import annotations

import unittest

from concordia_riverbend.core import ActionRequest
from concordia_riverbend.core import ScriptedAgentController
from concordia_riverbend.core import SimulationConfig
from concordia_riverbend.core import SimulationRunner
from concordia_riverbend.core import WorldGameMaster
from concordia_riverbend.scenarios.riverbend_world import (
    build_riverbend_world,
)


class WorldEngineTest(unittest.TestCase):
    def test_runs_three_rounds_and_applies_grounded_skills(self) -> None:
        scenario = build_riverbend_world()
        controllers = {
            agent.agent_id: ScriptedAgentController(
                (
                    (
                        "inspect",
                        {"target": agent.initial_location},
                    ),
                    (
                        "move",
                        {"destination": "town_hall"},
                    ),
                    (
                        "vote",
                        {
                            "candidate": (
                                "Alice"
                                if index % 2 == 0
                                else "Bob"
                            )
                        },
                    ),
                )
            )
            for index, agent in enumerate(scenario.agents)
        }
        run = SimulationRunner(
            scenario=scenario,
            config=SimulationConfig(
                scenario_id=scenario.scenario_id,
                max_rounds=3,
                seed=7,
            ),
            controllers=controllers,
        ).run()

        self.assertEqual(run.final_state.round_index, 3)
        self.assertEqual(
            set(run.final_state.agent_locations.values()),
            {"town_hall"},
        )
        self.assertEqual(len(run.final_state.variables["ballots"]), 5)
        self.assertEqual(len(run.turns), 15)
        self.assertTrue(
            all(
                turn.result is None or turn.result.accepted
                for turn in run.turns
            )
        )

    def test_rejected_action_does_not_change_world_state(self) -> None:
        scenario = build_riverbend_world()
        game_master = WorldGameMaster(scenario=scenario)
        state_before = game_master.state.to_dict()
        game_master.state.advance_round()
        request = ActionRequest(
            actor_id="maya_chen",
            action_type="move",
            parameters={"destination": "unknown_place"},
            round_index=1,
        )
        result = game_master.resolve(request)

        self.assertFalse(result.accepted)
        self.assertEqual(
            game_master.state.agent_locations,
            state_before["agent_locations"],
        )
        self.assertEqual(len(game_master.state.events), 1)

    def test_private_messages_are_visible_only_to_participants(self) -> None:
        scenario = build_riverbend_world()
        maya = ScriptedAgentController(
            (
                (
                    "speak",
                    {
                        "message": "Please verify the river report.",
                        "channel": "private",
                        "recipients": ["noah_williams"],
                    },
                ),
            )
        )
        controllers = {
            agent.agent_id: (
                maya
                if agent.agent_id == "maya_chen"
                else ScriptedAgentController(())
            )
            for agent in scenario.agents
        }
        run = SimulationRunner(
            scenario=scenario,
            config=SimulationConfig(
                scenario_id=scenario.scenario_id,
                max_rounds=2,
                seed=11,
            ),
            controllers=controllers,
        ).run()

        noah_contexts = controllers["noah_williams"].contexts
        luis_contexts = controllers["luis_ortiz"].contexts
        noah_private = {
            event.content
            for context in noah_contexts
            for event in context.new_events
            if event.event_type == "private_message"
        }
        luis_private = {
            event.content
            for context in luis_contexts
            for event in context.new_events
            if event.event_type == "private_message"
        }
        self.assertEqual(
            noah_private,
            {"Please verify the river report."},
        )
        self.assertEqual(luis_private, set())
        self.assertEqual(run.final_state.round_index, 2)

    def test_vote_requires_town_hall_and_allows_only_one_ballot(self) -> None:
        scenario = build_riverbend_world()
        game_master = WorldGameMaster(scenario=scenario)
        game_master.state.advance_round()

        early_vote = game_master.resolve(
            ActionRequest(
                actor_id="maya_chen",
                action_type="vote",
                parameters={"candidate": "Alice"},
                round_index=1,
            )
        )
        self.assertFalse(early_vote.accepted)
        self.assertNotIn("ballots", game_master.state.variables)

        move = game_master.resolve(
            ActionRequest(
                actor_id="maya_chen",
                action_type="move",
                parameters={"destination": "town_hall"},
                round_index=1,
            )
        )
        first_vote = game_master.resolve(
            ActionRequest(
                actor_id="maya_chen",
                action_type="vote",
                parameters={
                    "candidate": "Alice",
                    "reason": (
                        "I prioritize clean water and stable schools."
                    ),
                },
                round_index=1,
            )
        )
        second_vote = game_master.resolve(
            ActionRequest(
                actor_id="maya_chen",
                action_type="vote",
                parameters={"candidate": "Bob"},
                round_index=1,
            )
        )

        self.assertTrue(move.accepted)
        self.assertTrue(first_vote.accepted)
        self.assertFalse(second_vote.accepted)
        self.assertEqual(
            game_master.state.variables["ballots"]["maya_chen"],
            "Alice",
        )
        self.assertEqual(
            game_master.state.variables["vote_reasons"]["maya_chen"],
            "I prioritize clean water and stable schools.",
        )
        self.assertEqual(
            first_vote.events[0].metadata["reason"],
            "I prioritize clean water and stable schools.",
        )
