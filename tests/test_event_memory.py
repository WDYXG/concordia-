"""Tests for isolated event memory and information provenance."""

from __future__ import annotations

import unittest

from concordia_riverbend.core import ScriptedAgentController
from concordia_riverbend.core import SimulationConfig
from concordia_riverbend.core import SimulationRunner
from concordia_riverbend.memory import AgentEventMemory
from concordia_riverbend.memory import WorldMemory
from concordia_riverbend.scenarios.riverbend_world import (
    build_riverbend_world,
)


class AgentEventMemoryTest(unittest.TestCase):
    def test_classifies_events_and_preserves_source_fields(self) -> None:
        scenario = build_riverbend_world()
        maya = next(
            agent
            for agent in scenario.agents
            if agent.agent_id == "maya_chen"
        )
        memory = AgentEventMemory(agent=maya)
        memory.observe(scenario.initial_events)

        record = memory.records[-1]
        self.assertEqual(record.memory_type, "semantic")
        self.assertEqual(record.event_id, "election_briefing")
        self.assertIsNone(record.source_event_id)

    def test_retrieval_uses_content_recency_and_importance(self) -> None:
        scenario = build_riverbend_world()
        maya = next(
            agent
            for agent in scenario.agents
            if agent.agent_id == "maya_chen"
        )
        memory = AgentEventMemory(agent=maya)
        memory.observe(scenario.initial_events)

        recalled = memory.retrieve(
            "river pollution enforcement",
            current_round=2,
            limit=2,
        )
        self.assertEqual(len(recalled), 2)
        self.assertTrue(
            any("river" in record.content.lower() for record in recalled)
        )


class WorldMemoryIntegrationTest(unittest.TestCase):
    def test_runner_records_visible_events_without_private_leakage(self) -> None:
        scenario = build_riverbend_world()
        controllers = {
            agent.agent_id: ScriptedAgentController(())
            for agent in scenario.agents
        }
        controllers["maya_chen"] = ScriptedAgentController(
            (
                (
                    "speak",
                    {
                        "message": "Private clinic question.",
                        "channel": "private",
                        "recipients": ["noah_williams"],
                        "source_event_id": "election_briefing",
                    },
                ),
            )
        )
        memory = WorldMemory(scenario)
        run = SimulationRunner(
            scenario=scenario,
            config=SimulationConfig(
                scenario_id=scenario.scenario_id,
                max_rounds=2,
                seed=19,
            ),
            controllers=controllers,
            memory_system=memory,
        ).run()

        noah_messages = [
            record
            for record in memory.records_for("noah_williams")
            if record.content == "Private clinic question."
        ]
        luis_messages = [
            record
            for record in memory.records_for("luis_ortiz")
            if record.content == "Private clinic question."
        ]
        self.assertEqual(len(noah_messages), 1)
        self.assertEqual(
            noah_messages[0].source_event_id,
            "election_briefing",
        )
        self.assertEqual(luis_messages, [])
        self.assertEqual(
            run.final_state.relationships["maya_chen"][
                "noah_williams"
            ],
            0.05,
        )
        self.assertEqual(
            run.final_state.relationships["noah_williams"][
                "maya_chen"
            ],
            0.05,
        )
        self.assertIn("maya_chen", run.memory_state)
