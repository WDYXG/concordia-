"""Tests for the reusable simulation data contracts."""

from __future__ import annotations

import unittest

from concordia_riverbend.core import ActionRequest
from concordia_riverbend.core import ActionResult
from concordia_riverbend.core import ActionSpec
from concordia_riverbend.core import AgentSpec
from concordia_riverbend.core import LocationSpec
from concordia_riverbend.core import ScenarioSpec
from concordia_riverbend.core import WorldEvent
from concordia_riverbend.core import WorldState


def _scenario() -> ScenarioSpec:
    return ScenarioSpec(
        scenario_id="test_world",
        title="Test World",
        description="A small deterministic test scenario.",
        agents=(
            AgentSpec(
                agent_id="alex",
                name="Alex",
                role="resident",
                goal="Learn what is happening.",
                initial_location="square",
                allowed_actions=("move",),
            ),
        ),
        locations=(
            LocationSpec(
                location_id="square",
                name="Town Square",
                description="A public meeting place.",
            ),
            LocationSpec(
                location_id="library",
                name="Library",
                description="A place to inspect public records.",
            ),
        ),
        actions=(
            ActionSpec(
                action_type="move",
                description="Move between public locations.",
                parameter_names=("destination",),
            ),
        ),
    )


class ScenarioSpecTest(unittest.TestCase):
    def test_rejects_unknown_agent_action(self) -> None:
        with self.assertRaisesRegex(ValueError, "unknown actions"):
            ScenarioSpec(
                scenario_id="invalid",
                title="Invalid",
                description="Invalid action reference.",
                agents=(
                    AgentSpec(
                        agent_id="alex",
                        name="Alex",
                        role="resident",
                        goal="Act.",
                        initial_location="square",
                        allowed_actions=("missing",),
                    ),
                ),
                locations=(
                    LocationSpec(
                        location_id="square",
                        name="Square",
                        description="A square.",
                    ),
                ),
                actions=(),
            )

    def test_rejects_duplicate_agent_ids(self) -> None:
        scenario = _scenario()
        with self.assertRaisesRegex(ValueError, "agent IDs"):
            ScenarioSpec(
                scenario_id="duplicate",
                title="Duplicate",
                description="Duplicate IDs.",
                agents=(scenario.agents[0], scenario.agents[0]),
                locations=scenario.locations,
                actions=scenario.actions,
            )


class WorldStateTest(unittest.TestCase):
    def test_initializes_and_moves_agents_with_grounded_validation(self) -> None:
        scenario = _scenario()
        state = WorldState.from_scenario(scenario)

        self.assertEqual(state.agent_locations, {"alex": "square"})
        state.move_agent(
            agent_id="alex",
            destination="library",
            scenario=scenario,
        )
        self.assertEqual(state.agent_locations["alex"], "library")

        with self.assertRaisesRegex(ValueError, "Unknown destination"):
            state.move_agent(
                agent_id="alex",
                destination="nowhere",
                scenario=scenario,
            )

    def test_records_action_contract_without_applying_it_implicitly(self) -> None:
        request = ActionRequest(
            actor_id="alex",
            action_type="move",
            parameters={"destination": "library"},
            round_index=0,
        )
        event = WorldEvent(
            event_id="alex_moves",
            round_index=0,
            event_type="movement",
            actor_id="alex",
            location_id="library",
            content="Alex moved to the library.",
        )
        result = ActionResult(
            request=request,
            accepted=True,
            reason="The destination is public.",
            events=(event,),
            state_changes={"agent_locations.alex": "library"},
        )

        serialized = result.to_dict()
        self.assertTrue(serialized["accepted"])
        self.assertEqual(
            serialized["request"]["parameters"]["destination"],
            "library",
        )
        self.assertEqual(serialized["events"][0]["event_id"], "alex_moves")

    def test_private_events_require_an_audience(self) -> None:
        with self.assertRaisesRegex(ValueError, "private event"):
            WorldEvent(
                event_id="secret",
                round_index=0,
                event_type="private_message",
                content="A private message.",
                is_public=False,
            )
