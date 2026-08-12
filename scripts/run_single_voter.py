"""Run one live Riverbend voter through Concordia and DeepSeek."""

from __future__ import annotations

from pathlib import Path

from concordia_riverbend.agents.voter import VoterProfile
from concordia_riverbend.agents.voter import build_voter_agent
from concordia_riverbend.agents.voter import run_vote
from concordia_riverbend.language_models.deepseek_model import (
    DeepSeekLanguageModel,
)


def main() -> None:
    project_root = Path(__file__).resolve().parents[1]
    model = DeepSeekLanguageModel(env_file=project_root / ".env")
    profile = VoterProfile(
        name="Maya Chen",
        background=(
            "Maya is a 38-year-old public-school teacher. She lives with her "
            "family near Riverbend's riverfront park."
        ),
        goal=(
            "Vote for the candidate Maya believes will best protect her "
            "family's health and improve Riverbend."
        ),
        memories=(
            "Last summer, Maya's child became ill after pollution reached "
            "the river near their neighborhood.",
            "Alice told residents she would strengthen river cleanup and "
            "restore funding for public parks.",
            "Bob told business owners he would approve a factory expansion "
            "and reduce local business taxes.",
            "Maya values stable school funding, safe drinking water, and "
            "accessible parks.",
        ),
    )
    voter = build_voter_agent(model=model, profile=profile)
    decision = run_vote(
        voter,
        election_observation=(
            "It is election day in Riverbend. Alice's platform emphasizes "
            "river cleanup, parks, and public services. Bob's platform "
            "emphasizes factory expansion, jobs, and lower business taxes. "
            "Maya must now cast one vote."
        ),
    )

    print(f"Voter: {profile.name}")
    print(f"Vote: {decision.candidate}")
    print(f"Reason: {decision.reason}")


if __name__ == "__main__":
    main()
