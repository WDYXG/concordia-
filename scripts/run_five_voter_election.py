"""Run and save the live five-voter Riverbend election."""

from __future__ import annotations

import datetime
import json
from pathlib import Path

from concordia_riverbend.experiments.election import run_election
from concordia_riverbend.language_models.deepseek_model import (
    DeepSeekLanguageModel,
)
from concordia_riverbend.scenarios.riverbend_election import (
    ELECTION_OBSERVATION,
)
from concordia_riverbend.scenarios.riverbend_election import RIVERBEND_VOTERS


def main() -> None:
    project_root = Path(__file__).resolve().parents[1]
    model = DeepSeekLanguageModel(env_file=project_root / ".env")
    result = run_election(
        model=model,
        profiles=RIVERBEND_VOTERS,
        election_observation=ELECTION_OBSERVATION,
    )

    print("Riverbend election")
    print("-------------------")
    for outcome in result.outcomes:
        print(f"{outcome.voter}: {outcome.candidate}")
        print(f"  {outcome.reason}")
    print("-------------------")
    for candidate, votes in result.tally.items():
        print(f"{candidate}: {votes}")

    payload = result.to_dict()
    payload["run_at"] = datetime.datetime.now(
        datetime.timezone.utc
    ).isoformat()
    output_dir = project_root / "outputs"
    output_dir.mkdir(exist_ok=True)
    timestamp = datetime.datetime.now(
        datetime.timezone.utc
    ).strftime("%Y%m%dT%H%M%S_%fZ")
    output_path = output_dir / f"five_voter_election_{timestamp}.json"
    output_path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print(f"Saved: {output_path}")


if __name__ == "__main__":
    main()
