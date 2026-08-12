"""Tests for Riverbend's generic scenario representation."""

from __future__ import annotations

import unittest

from concordia_riverbend.scenarios.election_conditions import (
    EMPLOYMENT_EVIDENCE,
)
from concordia_riverbend.scenarios.riverbend_election import RIVERBEND_VOTERS
from concordia_riverbend.scenarios.riverbend_world import (
    build_initial_riverbend_state,
)
from concordia_riverbend.scenarios.riverbend_world import (
    build_riverbend_world,
)


class RiverbendWorldTest(unittest.TestCase):
    def test_maps_existing_voters_into_one_generic_scenario(self) -> None:
        scenario = build_riverbend_world()

        self.assertEqual(len(scenario.agents), len(RIVERBEND_VOTERS))
        self.assertEqual(
            {agent.name for agent in scenario.agents},
            {profile.name for profile in RIVERBEND_VOTERS},
        )
        self.assertEqual(
            set(scenario.action_types),
            {"move", "speak", "inspect", "vote"},
        )
        self.assertEqual(scenario.metadata["condition"], "baseline")
        self.assertEqual(len(scenario.initial_events), 1)

    def test_adds_condition_as_a_grounded_initial_event(self) -> None:
        scenario = build_riverbend_world(EMPLOYMENT_EVIDENCE)

        self.assertEqual(len(scenario.initial_events), 2)
        self.assertEqual(
            scenario.initial_events[-1].event_type,
            "information_treatment",
        )
        self.assertEqual(
            scenario.initial_events[-1].metadata["condition"],
            "employment_evidence",
        )

    def test_builds_serializable_initial_world_state(self) -> None:
        state = build_initial_riverbend_state()
        payload = state.to_dict()

        self.assertEqual(payload["scenario_id"], "riverbend_election")
        self.assertEqual(len(payload["agent_locations"]), 5)
        self.assertEqual(payload["round_index"], 0)
        self.assertEqual(len(payload["events"]), 1)

    def test_election_ready_start_does_not_change_general_world(self) -> None:
        general = build_riverbend_world()
        election_ready = build_riverbend_world(
            start_at_voting_location=True
        )

        self.assertGreater(
            len({agent.initial_location for agent in general.agents}),
            1,
        )
        self.assertEqual(
            {
                agent.initial_location
                for agent in election_ready.agents
            },
            {"town_hall"},
        )
        self.assertEqual(
            election_ready.metadata["starting_location_policy"],
            "voting_location",
        )

    def test_candidate_order_changes_the_actual_briefing_text(self) -> None:
        bob_first = build_riverbend_world(
            candidate_order=("Bob", "Alice")
        )
        briefing = bob_first.initial_events[0].content

        self.assertLess(
            briefing.index("Bob proposes"),
            briefing.index("Alice proposes"),
        )
        self.assertIn("vote for Bob or Alice", briefing)
