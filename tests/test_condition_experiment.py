from __future__ import annotations

from collections.abc import Collection, Sequence
import unittest

from concordia.language_model import language_model

from concordia_riverbend.experiments.condition_experiment import (
    run_condition_experiment,
)
from concordia_riverbend.scenarios.election_conditions import (
    ELECTION_CONDITIONS,
)
from concordia_riverbend.scenarios.riverbend_election import (
    ELECTION_OBSERVATION,
)
from concordia_riverbend.scenarios.riverbend_election import RIVERBEND_VOTERS


class ConditionSensitiveModel(language_model.LanguageModel):
    def __init__(self) -> None:
        self.text_calls = 0
        self.choice_calls = 0

    def sample_text(
        self,
        prompt: str,
        *,
        max_tokens: int = language_model.DEFAULT_MAX_TOKENS,
        terminators: Collection[str] = language_model.DEFAULT_TERMINATORS,
        temperature: float = language_model.DEFAULT_TEMPERATURE,
        top_p: float = language_model.DEFAULT_TOP_P,
        top_k: int = language_model.DEFAULT_TOP_K,
        timeout: float = language_model.DEFAULT_TIMEOUT_SECONDS,
        seed: int | None = None,
    ) -> str:
        del max_tokens, terminators, temperature, top_p, top_k, timeout, seed
        self.text_calls += 1
        if "audited contracts and staffing plans" in prompt:
            return "independent evidence confirms 300 net local factory jobs"
        if "water and soil assessments" in prompt:
            return "independent evidence confirms increased river pollution risk"
        return "no new evidence changes the candidate platform assessment"

    def sample_choice(
        self,
        prompt: str,
        responses: Sequence[str],
        *,
        seed: int | None = None,
    ) -> tuple[int, str, dict[str, float]]:
        del seed
        self.choice_calls += 1
        choose_bob = "300 net local jobs" in prompt
        index = 1 if choose_bob else 0
        return index, responses[index], {}


class ConditionExperimentTest(unittest.TestCase):
    def test_changes_only_information_and_reports_share_deltas(self) -> None:
        model = ConditionSensitiveModel()

        result = run_condition_experiment(
            model=model,
            profiles=RIVERBEND_VOTERS,
            base_observation=ELECTION_OBSERVATION,
            conditions=ELECTION_CONDITIONS,
            num_runs_per_condition=1,
        )

        self.assertEqual(
            [outcome.condition.name for outcome in result.outcomes],
            [
                "baseline",
                "placebo",
                "employment_evidence",
                "pollution_evidence",
            ],
        )
        self.assertEqual(
            result.candidate_share_deltas("Bob"),
            {
                "baseline": 0.0,
                "placebo": 0.0,
                "employment_evidence": 1.0,
                "pollution_evidence": 0.0,
            },
        )
        self.assertEqual(
            result.candidate_contrasts("Bob"),
            {
                "announcement_effect": 0.0,
                "employment_information_effect": 1.0,
                "pollution_information_effect": 0.0,
            },
        )
        self.assertEqual(model.choice_calls, 20)
        self.assertEqual(model.text_calls, 20)

    def test_requires_named_baseline_condition(self) -> None:
        with self.assertRaisesRegex(ValueError, "Control condition"):
            run_condition_experiment(
                model=ConditionSensitiveModel(),
                profiles=RIVERBEND_VOTERS,
                base_observation=ELECTION_OBSERVATION,
                conditions=ELECTION_CONDITIONS[1:],
                num_runs_per_condition=1,
            )


if __name__ == "__main__":
    unittest.main()
