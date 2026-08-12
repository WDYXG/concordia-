from __future__ import annotations

from collections.abc import Collection, Sequence
import unittest

from concordia.language_model import language_model

from concordia_riverbend.experiments.election import run_election
from concordia_riverbend.scenarios.riverbend_election import (
    ELECTION_OBSERVATION,
)
from concordia_riverbend.scenarios.riverbend_election import RIVERBEND_VOTERS


class ProfileSensitiveModel(language_model.LanguageModel):
    """A deterministic stand-in that reacts to the assembled agent context."""

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
        if "Summarize the statements above" in prompt:
            return (
                "Riverbend river parks health factory jobs business taxes "
                "schools clinic"
            )
        if "Luis Ortiz" in prompt or "Evelyn Brooks" in prompt:
            return "Economic stability and reliable local jobs matter most."
        return "Public health and long-term town services matter most."

    def sample_choice(
        self,
        prompt: str,
        responses: Sequence[str],
        *,
        seed: int | None = None,
    ) -> tuple[int, str, dict[str, float]]:
        del seed
        self.choice_calls += 1
        choose_bob = "Luis Ortiz" in prompt or "Evelyn Brooks" in prompt
        index = 1 if choose_bob else 0
        return index, responses[index], {}


class ElectionExperimentTest(unittest.TestCase):
    def test_runs_five_independent_voters_and_tallies_results(self) -> None:
        model = ProfileSensitiveModel()

        result = run_election(
            model=model,
            profiles=RIVERBEND_VOTERS,
            election_observation=ELECTION_OBSERVATION,
        )

        self.assertEqual(len(result.outcomes), 5)
        self.assertEqual(result.tally, {"Alice": 3, "Bob": 2})
        self.assertEqual(model.choice_calls, 5)
        self.assertEqual(model.text_calls, 15)
        self.assertEqual(
            [outcome.voter for outcome in result.outcomes],
            [profile.name for profile in RIVERBEND_VOTERS],
        )
        self.assertTrue(all(outcome.reason for outcome in result.outcomes))

    def test_serializes_observable_results(self) -> None:
        model = ProfileSensitiveModel()
        result = run_election(
            model=model,
            profiles=RIVERBEND_VOTERS[:1],
            election_observation=ELECTION_OBSERVATION,
        )

        payload = result.to_dict()

        self.assertEqual(payload["tally"], {"Alice": 1, "Bob": 0})
        self.assertEqual(payload["outcomes"][0]["voter"], "Maya Chen")


if __name__ == "__main__":
    unittest.main()
