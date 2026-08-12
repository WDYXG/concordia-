from __future__ import annotations

import unittest

from concordia.agents import entity_agent_with_logging

from concordia_riverbend.experiments.gm_condition_experiment import (
    run_gm_condition_experiment,
)
from concordia_riverbend.game_master.election import VoteLedger
from concordia_riverbend.game_master.election import run_gm_election
from concordia_riverbend.scenarios.election_conditions import BASELINE
from concordia_riverbend.scenarios.election_conditions import (
    ELECTION_CONDITIONS,
)
from concordia_riverbend.scenarios.election_conditions import (
    EMPLOYMENT_EVIDENCE,
)
from concordia_riverbend.scenarios.riverbend_election import (
    ELECTION_OBSERVATION,
)
from concordia_riverbend.scenarios.riverbend_election import RIVERBEND_VOTERS
from test_condition_experiment import ConditionSensitiveModel


class VoteLedgerTest(unittest.TestCase):
    def test_rejects_invalid_and_duplicate_ballots(self) -> None:
        ledger = VoteLedger(
            voter_names=("Maya", "Luis"),
            candidates=("Alice", "Bob"),
        )

        ledger.record("Maya", "Alice")

        with self.assertRaisesRegex(ValueError, "already voted"):
            ledger.record("Maya", "Bob")
        with self.assertRaisesRegex(ValueError, "Unknown voter"):
            ledger.record("Unknown", "Alice")
        with self.assertRaisesRegex(ValueError, "Invalid candidate"):
            ledger.record("Luis", "Carol")
        self.assertEqual(ledger.votes, {"Maya": "Alice"})
        self.assertEqual(ledger.tally, {"Alice": 1, "Bob": 0})


class DeterministicGameMasterTest(unittest.TestCase):
    def test_broadcasts_events_and_maintains_grounded_ledger(self) -> None:
        model = ConditionSensitiveModel()
        profiles = RIVERBEND_VOTERS[:2]

        run = run_gm_election(
            model=model,
            profiles=profiles,
            base_observation=ELECTION_OBSERVATION,
            condition=EMPLOYMENT_EVIDENCE,
        )

        self.assertIsInstance(
            run.game_master.agent,
            entity_agent_with_logging.EntityAgentWithLogging,
        )
        self.assertEqual(
            run.game_master.broadcasts,
            (ELECTION_OBSERVATION, EMPLOYMENT_EVIDENCE.event),
        )
        self.assertEqual(
            run.game_master.ledger.votes,
            {"Maya Chen": "Bob", "Luis Ortiz": "Bob"},
        )
        self.assertEqual(run.game_master.ledger.tally, {"Alice": 0, "Bob": 2})
        self.assertTrue(run.game_master.ledger.is_complete)
        self.assertEqual(run.election.tally, {"Alice": 0, "Bob": 2})
        self.assertEqual(model.text_calls, 2)
        self.assertEqual(model.choice_calls, 2)

    def test_baseline_broadcasts_no_second_event(self) -> None:
        run = run_gm_election(
            model=ConditionSensitiveModel(),
            profiles=RIVERBEND_VOTERS[:1],
            base_observation=ELECTION_OBSERVATION,
            condition=BASELINE,
        )

        self.assertEqual(
            run.game_master.broadcasts,
            (ELECTION_OBSERVATION,),
        )

    def test_runs_all_four_conditions_through_fresh_game_masters(self) -> None:
        model = ConditionSensitiveModel()

        result = run_gm_condition_experiment(
            model=model,
            profiles=RIVERBEND_VOTERS[:2],
            base_observation=ELECTION_OBSERVATION,
            conditions=ELECTION_CONDITIONS,
            num_runs_per_condition=1,
        )

        self.assertEqual(
            result.candidate_contrasts("Bob"),
            {
                "announcement_effect": 0.0,
                "employment_information_effect": 1.0,
                "pollution_information_effect": 0.0,
            },
        )
        self.assertEqual(model.text_calls, 8)
        self.assertEqual(model.choice_calls, 8)
        for outcome in result.outcomes:
            self.assertEqual(len(outcome.game_master_runs), 1)
            gm_record = outcome.game_master_runs[0]
            self.assertTrue(gm_record["deterministic"])
            self.assertEqual(
                set(gm_record["ledger"]),
                {"Maya Chen", "Luis Ortiz"},
            )


if __name__ == "__main__":
    unittest.main()
