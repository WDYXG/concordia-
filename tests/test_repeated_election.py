from __future__ import annotations

import unittest

from concordia_riverbend.experiments.repeated_election import (
    run_repeated_election,
)
from concordia_riverbend.scenarios.riverbend_election import (
    ELECTION_OBSERVATION,
)
from concordia_riverbend.scenarios.riverbend_election import RIVERBEND_VOTERS
from test_election_experiment import ProfileSensitiveModel


class RepeatedElectionTest(unittest.TestCase):
    def test_aggregates_three_fresh_runs_without_reasons(self) -> None:
        model = ProfileSensitiveModel()

        result = run_repeated_election(
            model=model,
            profiles=RIVERBEND_VOTERS,
            election_observation=ELECTION_OBSERVATION,
            num_runs=3,
        )

        self.assertEqual(len(result.runs), 3)
        self.assertEqual(result.total_tally, {"Alice": 9, "Bob": 6})
        self.assertEqual(result.vote_shares, {"Alice": 0.6, "Bob": 0.4})
        self.assertEqual(
            result.choices_by_voter["Luis Ortiz"],
            {"Alice": 0, "Bob": 3},
        )
        self.assertEqual(model.choice_calls, 15)
        self.assertEqual(model.text_calls, 15)
        self.assertTrue(
            all(
                not outcome.reason
                for run in result.runs
                for outcome in run.outcomes
            )
        )

    def test_rejects_non_positive_run_count(self) -> None:
        with self.assertRaisesRegex(ValueError, "at least 1"):
            run_repeated_election(
                model=ProfileSensitiveModel(),
                profiles=RIVERBEND_VOTERS,
                election_observation=ELECTION_OBSERVATION,
                num_runs=0,
            )


if __name__ == "__main__":
    unittest.main()
