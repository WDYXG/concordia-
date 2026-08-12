"""Tests for Riverbend's seeded ten-day life and election protocol."""

from __future__ import annotations

import unittest

from concordia_riverbend.core import ScriptedAgentController
from concordia_riverbend.core import SimulationConfig
from concordia_riverbend.core import SimulationRunner
from concordia_riverbend.scenarios.election_conditions import (
    EMPLOYMENT_EVIDENCE,
)
from concordia_riverbend.scenarios.riverbend_schedule import (
    RiverbendDayScheduler,
)
from concordia_riverbend.scenarios.riverbend_schedule import (
    build_daily_event_schedule,
)
from concordia_riverbend.scenarios.riverbend_world import (
    build_riverbend_world,
)


class RiverbendScheduleTest(unittest.TestCase):
    def test_seeded_schedule_is_reproducible_and_has_one_event_per_day(
        self,
    ) -> None:
        first = build_daily_event_schedule(20260729)
        repeated = build_daily_event_schedule(20260729)
        different = build_daily_event_schedule(20260730)

        self.assertEqual(first, repeated)
        self.assertNotEqual(first, different)
        self.assertEqual(tuple(event.day for event in first), tuple(range(1, 11)))
        self.assertEqual(len({event.event_id for event in first}), 10)

    def test_life_protocol_rejects_early_votes_and_opens_day_eleven(
        self,
    ) -> None:
        condition = EMPLOYMENT_EVIDENCE
        candidate_order = ("Bob", "Alice")
        schedule = build_daily_event_schedule(31)
        scenario = build_riverbend_world(
            condition,
            candidate_order=candidate_order,
            life_simulation=True,
            election_day=11,
        )
        controllers = {
            agent.agent_id: ScriptedAgentController(
                tuple(
                    (
                        "vote",
                        {
                            "candidate": (
                                "Alice"
                                if index % 2 == 0
                                else "Bob"
                            )
                        },
                    )
                    for _ in range(11)
                )
            )
            for index, agent in enumerate(scenario.agents)
        }
        run = SimulationRunner(
            scenario=scenario,
            config=SimulationConfig(
                scenario_id=scenario.scenario_id,
                max_rounds=11,
                seed=31,
                condition=condition.name,
                metadata={"time_unit": "day"},
            ),
            controllers=controllers,
            round_scheduler=RiverbendDayScheduler(
                schedule=schedule,
                condition=condition,
                candidate_order=candidate_order,
                election_day=11,
            ),
        ).run()

        life_turns = [
            turn for turn in run.turns if turn.round_index <= 10
        ]
        election_turns = [
            turn for turn in run.turns if turn.round_index == 11
        ]
        self.assertEqual(len(life_turns), 50)
        self.assertTrue(
            all(
                turn.result is not None and not turn.result.accepted
                for turn in life_turns
            )
        )
        self.assertNotIn("ballots", run.snapshots[10]["variables"])
        self.assertEqual(len(election_turns), 5)
        self.assertTrue(
            all(
                turn.result is not None and turn.result.accepted
                for turn in election_turns
            )
        )
        self.assertEqual(len(run.final_state.variables["ballots"]), 5)
        self.assertEqual(
            set(run.final_state.agent_locations.values()),
            {"town_hall"},
        )
        treatment = next(
            event
            for event in run.final_state.events
            if event.event_id == "condition_employment_evidence"
        )
        self.assertEqual(treatment.round_index, 10)
        briefing = next(
            event
            for event in run.final_state.events
            if event.event_id == "election_briefing"
        )
        self.assertEqual(briefing.round_index, 11)
        self.assertLess(
            briefing.content.index("Bob proposes"),
            briefing.content.index("Alice proposes"),
        )
        for controller in controllers.values():
            observed_on_day_ten = {
                event.event_id
                for event in controller.contexts[9].new_events
            }
            self.assertIn(
                "condition_employment_evidence",
                observed_on_day_ten,
            )

    def test_life_scenario_delays_treatment_until_scheduler_runs(self) -> None:
        scenario = build_riverbend_world(
            EMPLOYMENT_EVIDENCE,
            life_simulation=True,
            election_day=11,
        )

        self.assertEqual(len(scenario.initial_events), 1)
        self.assertEqual(
            scenario.initial_events[0].event_id,
            "election_announcement",
        )
        self.assertNotIn(
            "condition_employment_evidence",
            {event.event_id for event in scenario.initial_events},
        )
