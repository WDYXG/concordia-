from __future__ import annotations

from collections.abc import Collection, Sequence
import unittest

from concordia.language_model import language_model

from concordia_riverbend.agents.voter import VoterProfile
from concordia_riverbend.agents.voter import build_voter_agent
from concordia_riverbend.agents.voter import run_vote


class RecordingModel(language_model.LanguageModel):
    def __init__(self) -> None:
        self.text_prompts: list[str] = []
        self.choice_prompts: list[str] = []

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
        self.text_prompts.append(prompt)
        if "Summarize the statements above" in prompt:
            return "river pollution, public parks, and clean water"
        return "Clean water and the park matter most to me."

    def sample_choice(
        self,
        prompt: str,
        responses: Sequence[str],
        *,
        seed: int | None = None,
    ) -> tuple[int, str, dict[str, float]]:
        del seed
        self.choice_prompts.append(prompt)
        # Concordia presents candidate names in the prompt, then asks the
        # language model to choose the corresponding letter label.
        return 0, responses[0], {}


class VoterAgentTest(unittest.TestCase):
    def setUp(self) -> None:
        self.model = RecordingModel()
        self.profile = VoterProfile(
            name="Maya Chen",
            background=(
                "Maya is a teacher who lives near Riverbend's public park."
            ),
            goal=(
                "Vote for the candidate most likely to protect Maya's family "
                "and improve Riverbend."
            ),
            memories=(
                "Maya's child became ill after pollution reached the river.",
                "Alice promised to clean the river and fund public parks.",
                "Bob proposed a factory expansion and lower business taxes.",
            ),
        )

    def test_builds_official_agent_and_loads_formative_memories(self) -> None:
        voter = build_voter_agent(model=self.model, profile=self.profile)

        self.assertEqual(voter.agent.name, "Maya Chen")
        stored = voter.memory_bank.get_data_frame()["text"].tolist()
        self.assertEqual(len(stored), 4)
        self.assertTrue(any("Alice promised" in text for text in stored))

    def test_vote_uses_recalled_memory_and_returns_reason(self) -> None:
        voter = build_voter_agent(model=self.model, profile=self.profile)

        decision = run_vote(
            voter,
            election_observation=(
                "Election day has arrived. Alice prioritizes river cleanup "
                "and parks. Bob prioritizes factory growth and tax cuts."
            ),
        )

        self.assertEqual(decision.candidate, "Alice")
        self.assertEqual(
            decision.reason, "Clean water and the park matter most to me."
        )
        self.assertEqual(len(self.model.choice_prompts), 1)
        choice_prompt = self.model.choice_prompts[0]
        self.assertIn("Alice promised to clean the river", choice_prompt)
        self.assertIn("which candidate do you vote for", choice_prompt)

    def test_rejects_duplicate_candidates_before_model_call(self) -> None:
        voter = build_voter_agent(model=self.model, profile=self.profile)

        with self.assertRaisesRegex(ValueError, "unique"):
            run_vote(
                voter,
                election_observation="Election day.",
                candidates=("Alice", "Alice"),
            )

        self.assertEqual(self.model.choice_prompts, [])


if __name__ == "__main__":
    unittest.main()
