"""Run multiple fresh Riverbend elections and save an aggregate report."""

from __future__ import annotations

import argparse
import datetime
import json
from pathlib import Path

from concordia_riverbend.experiments.repeated_election import (
    run_repeated_election,
)
from concordia_riverbend.language_models.deepseek_model import (
    DeepSeekLanguageModel,
)
from concordia_riverbend.scenarios.riverbend_election import (
    ELECTION_OBSERVATION,
)
from concordia_riverbend.scenarios.riverbend_election import RIVERBEND_VOTERS


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Repeat the five-voter Riverbend election."
    )
    parser.add_argument(
        "--runs",
        type=int,
        default=3,
        help="Number of fresh election runs (default: 3).",
    )
    parser.add_argument(
        "--include-reasons",
        action="store_true",
        help="Generate a reason after every vote; roughly doubles API calls.",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    if args.runs < 1:
        raise SystemExit("--runs must be at least 1.")

    project_root = Path(__file__).resolve().parents[1]
    model = DeepSeekLanguageModel(env_file=project_root / ".env")
    calls_per_voter = 4 if args.include_reasons else 2
    expected_calls = args.runs * len(RIVERBEND_VOTERS) * calls_per_voter
    print(
        f"Running {args.runs} fresh elections with approximately "
        f"{expected_calls} model calls."
    )

    result = run_repeated_election(
        model=model,
        profiles=RIVERBEND_VOTERS,
        election_observation=ELECTION_OBSERVATION,
        num_runs=args.runs,
        include_reasons=args.include_reasons,
    )

    for run_number, run in enumerate(result.runs, start=1):
        votes = ", ".join(
            f"{outcome.voter}={outcome.candidate}"
            for outcome in run.outcomes
        )
        print(f"Run {run_number}: {votes}")

    print("\nAggregate tally")
    for candidate in result.candidates:
        count = result.total_tally[candidate]
        share = result.vote_shares[candidate]
        print(f"{candidate}: {count} ({share:.1%})")

    print("\nChoices by voter")
    for voter, counts in result.choices_by_voter.items():
        display = ", ".join(
            f"{candidate}={counts[candidate]}"
            for candidate in result.candidates
        )
        print(f"{voter}: {display}")

    run_at = datetime.datetime.now(datetime.timezone.utc)
    run_id = run_at.strftime("%Y%m%dT%H%M%S_%fZ")
    payload = result.to_dict()
    payload.update(
        {
            "run_id": run_id,
            "run_at": run_at.isoformat(),
            "model": model.model_name,
            "include_reasons": args.include_reasons,
            "scenario": {
                "name": "riverbend_election",
                "observation": ELECTION_OBSERVATION,
                "voters": [profile.name for profile in RIVERBEND_VOTERS],
            },
        }
    )
    output_dir = project_root / "outputs" / "repeated_elections"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{run_id}.json"
    output_path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print(f"\nSaved: {output_path}")


if __name__ == "__main__":
    main()
