"""Run the three-condition Riverbend information experiment."""

from __future__ import annotations

import argparse
import datetime
import json
from pathlib import Path

from concordia_riverbend.experiments.gm_condition_experiment import (
    run_gm_condition_experiment,
)
from concordia_riverbend.language_models.deepseek_model import (
    DeepSeekLanguageModel,
)
from concordia_riverbend.scenarios.election_conditions import (
    ELECTION_CONDITIONS,
)
from concordia_riverbend.scenarios.riverbend_election import (
    ELECTION_OBSERVATION,
)
from concordia_riverbend.scenarios.riverbend_election import RIVERBEND_VOTERS


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Compare three Riverbend election information conditions."
    )
    parser.add_argument(
        "--runs-per-condition",
        type=int,
        default=1,
        help="Fresh elections per condition (default: 1).",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    if args.runs_per_condition < 1:
        raise SystemExit("--runs-per-condition must be at least 1.")

    project_root = Path(__file__).resolve().parents[1]
    model = DeepSeekLanguageModel(env_file=project_root / ".env")
    calls_per_voter = 2
    expected_calls = (
        len(ELECTION_CONDITIONS)
        * args.runs_per_condition
        * len(RIVERBEND_VOTERS)
        * calls_per_voter
    )
    print(
        f"Running {len(ELECTION_CONDITIONS)} conditions x "
        f"{args.runs_per_condition} run(s), approximately "
        f"{expected_calls} model calls."
    )

    experiment = run_gm_condition_experiment(
        model=model,
        profiles=RIVERBEND_VOTERS,
        base_observation=ELECTION_OBSERVATION,
        conditions=ELECTION_CONDITIONS,
        num_runs_per_condition=args.runs_per_condition,
    )

    bob_deltas = experiment.candidate_share_deltas("Bob")
    bob_contrasts = experiment.candidate_contrasts("Bob")
    for outcome in experiment.outcomes:
        result = outcome.result
        print(f"\n{outcome.condition.name}")
        for candidate in result.candidates:
            print(
                f"  {candidate}: {result.total_tally[candidate]} "
                f"({result.vote_shares[candidate]:.1%})"
            )
        print(
            "  Bob share change vs baseline: "
            f"{bob_deltas[outcome.condition.name]:+.1%}"
        )
        for voter, counts in result.choices_by_voter.items():
            choices = ", ".join(
                f"{candidate}={counts[candidate]}"
                for candidate in result.candidates
            )
            print(f"  {voter}: {choices}")

    print("\nPre-specified Bob-share contrasts")
    for contrast, value in bob_contrasts.items():
        print(f"  {contrast}: {value:+.1%}")

    run_at = datetime.datetime.now(datetime.timezone.utc)
    run_id = run_at.strftime("%Y%m%dT%H%M%S_%fZ")
    payload = experiment.to_dict()
    payload.update(
        {
            "run_id": run_id,
            "run_at": run_at.isoformat(),
            "model": model.model_name,
            "runs_per_condition": args.runs_per_condition,
            "include_reasons": False,
            "game_master": "deterministic_concordia_game_master",
            "base_observation": ELECTION_OBSERVATION,
            "voters": [profile.name for profile in RIVERBEND_VOTERS],
        }
    )
    output_dir = project_root / "outputs" / "condition_experiments"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{run_id}.json"
    output_path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print(f"\nSaved: {output_path}")


if __name__ == "__main__":
    main()
