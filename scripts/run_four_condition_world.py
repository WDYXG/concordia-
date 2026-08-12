"""Run three paid Riverbend conditions beside one validated baseline."""

from __future__ import annotations

import argparse
from collections.abc import Mapping
import datetime
import json
from pathlib import Path
import subprocess
import sys
from typing import Any


ADDITIONAL_CONDITIONS = (
    "placebo",
    "employment_evidence",
    "pollution_evidence",
)


def resolve_candidate_order(mode: str) -> tuple[str, str]:
    if mode == "alice-first":
        return ("Alice", "Bob")
    if mode == "bob-first":
        return ("Bob", "Alice")
    raise ValueError(
        "Batch runs require an explicit candidate order."
    )


def _read_payload(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} does not contain a JSON object.")
    return value


def run_invariants(payload: Mapping[str, Any]) -> dict[str, Any]:
    run = payload["run"]
    config = run["config"]
    metadata = config["metadata"]
    return {
        "seed": config["seed"],
        "candidate_order": list(metadata["candidate_order"]),
        "life_days": metadata["life_days"],
        "election_day": metadata["election_day"],
        "event_schedule": metadata["event_schedule"],
        "agent_order": list(metadata["agent_order"]),
        "memory_embedder": metadata["memory_embedder"],
        "max_rounds": config["max_rounds"],
        "model_name": config["model_name"],
    }


def validate_baseline(
    payload: Mapping[str, Any],
    *,
    seed: int,
    candidate_order: tuple[str, str],
    life_days: int,
) -> dict[str, Any]:
    run = payload.get("run")
    metrics = payload.get("metrics")
    if not isinstance(run, Mapping) or not isinstance(
        metrics,
        Mapping,
    ):
        raise ValueError("The baseline lacks run or metrics data.")
    config = run.get("config")
    if not isinstance(config, Mapping):
        raise ValueError("The baseline lacks run configuration.")
    if config.get("condition") != "baseline":
        raise ValueError("The supplied source is not a baseline run.")
    invariants = run_invariants(payload)
    expected = {
        "seed": seed,
        "candidate_order": list(candidate_order),
        "life_days": life_days,
        "election_day": life_days + 1,
        "max_rounds": life_days + 1,
    }
    mismatches = {
        key: {"expected": value, "actual": invariants.get(key)}
        for key, value in expected.items()
        if invariants.get(key) != value
    }
    if mismatches:
        raise ValueError(
            "Baseline configuration mismatch: "
            + json.dumps(mismatches, ensure_ascii=False)
        )
    if not metrics.get("manipulation_check_passed"):
        raise ValueError(
            "The baseline manipulation check did not pass."
        )
    return invariants


def assert_matching_invariants(
    payload: Mapping[str, Any],
    expected: Mapping[str, Any],
) -> None:
    actual = run_invariants(payload)
    mismatches = {
        key: {"expected": value, "actual": actual.get(key)}
        for key, value in expected.items()
        if actual.get(key) != value
    }
    if mismatches:
        raise ValueError(
            "Run invariants differ from baseline: "
            + json.dumps(mismatches, ensure_ascii=False)
        )


def build_live_command(
    *,
    project_root: Path,
    condition: str,
    seed: int,
    candidate_order_mode: str,
    life_days: int,
    memory_backend: str,
) -> list[str]:
    if condition not in ADDITIONAL_CONDITIONS:
        raise ValueError(f"Unsupported batch condition: {condition}.")
    return [
        sys.executable,
        "-m",
        "scripts.run_live_world",
        "--condition",
        condition,
        "--life-days",
        str(life_days),
        "--seed",
        str(seed),
        "--candidate-order",
        candidate_order_mode,
        "--memory-backend",
        memory_backend,
        "--confirm-live-api",
    ]


def _saved_path(stdout: str) -> Path:
    saved_lines = [
        line.removeprefix("Saved: ").strip()
        for line in stdout.splitlines()
        if line.startswith("Saved: ")
    ]
    if len(saved_lines) != 1:
        raise ValueError(
            "The child run did not report exactly one saved path."
        )
    return Path(saved_lines[0])


def _relative_path(path: Path, project_root: Path) -> str:
    try:
        return str(path.resolve().relative_to(project_root.resolve()))
    except ValueError:
        return str(path.resolve())


def build_manifest(
    *,
    batch_id: str,
    status: str,
    project_root: Path,
    payloads: Mapping[str, Mapping[str, Any]],
    paths: Mapping[str, Path],
    invariants: Mapping[str, Any],
    error: str | None = None,
) -> dict[str, Any]:
    baseline_ballots = dict(
        payloads["baseline"]["metrics"].get("ballots", {})
    )
    summaries: dict[str, Any] = {}
    vote_changes: dict[str, list[dict[str, str]]] = {}
    total_requests = 0
    total_tokens = 0
    for condition, payload in payloads.items():
        metrics = payload["metrics"]
        usage = payload["model_usage"]
        ballots = dict(metrics.get("ballots", {}))
        total_requests += int(usage.get("request_count", 0))
        total_tokens += int(usage.get("total_tokens", 0))
        summaries[condition] = {
            "source_file": _relative_path(
                paths[condition],
                project_root,
            ),
            "run_id": payload["run_id"],
            "run_at": payload["run_at"],
            "candidate_tally": metrics["candidate_tally"],
            "ballots": ballots,
            "vote_reasons": metrics.get("vote_reasons", {}),
            "manipulation_check_passed": metrics[
                "manipulation_check_passed"
            ],
            "model_usage": usage,
        }
        if condition != "baseline":
            vote_changes[condition] = [
                {
                    "agent_id": agent_id,
                    "baseline": baseline_candidate,
                    "condition": ballots.get(agent_id, "unvoted"),
                }
                for agent_id, baseline_candidate
                in baseline_ballots.items()
                if ballots.get(agent_id) != baseline_candidate
            ]
    return {
        "batch_id": batch_id,
        "status": status,
        "error": error,
        "condition_order": [
            "baseline",
            *ADDITIONAL_CONDITIONS,
        ],
        "configuration": dict(invariants),
        "completed_conditions": list(payloads),
        "import_files": [
            _relative_path(paths[condition], project_root)
            for condition in payloads
        ],
        "summaries": summaries,
        "vote_changes_vs_baseline": vote_changes,
        "combined_model_usage": {
            "request_count": total_requests,
            "total_tokens": total_tokens,
        },
    }


def _write_manifest(path: Path, payload: Mapping[str, Any]) -> None:
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run the three non-baseline Riverbend conditions and build "
            "one four-condition manifest."
        )
    )
    parser.add_argument(
        "--baseline-run",
        type=Path,
        required=True,
    )
    parser.add_argument("--seed", type=int, default=20260729)
    parser.add_argument("--life-days", type=int, default=10)
    parser.add_argument(
        "--candidate-order",
        choices=("alice-first", "bob-first"),
        default="bob-first",
    )
    parser.add_argument(
        "--memory-backend",
        choices=("semantic", "hash"),
        default="semantic",
    )
    parser.add_argument(
        "--confirm-live-api",
        action="store_true",
        help="Required acknowledgement that three paid runs will start.",
    )
    parser.add_argument(
        "--validate-only",
        action="store_true",
        help="Validate the baseline and batch configuration without API calls.",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    if not args.confirm_live_api and not args.validate_only:
        raise SystemExit(
            "No API call was made. Re-run with --confirm-live-api after "
            "reviewing the estimated 165-330 model calls."
        )
    if args.life_days < 1:
        raise SystemExit("--life-days must be at least 1.")

    project_root = Path(__file__).resolve().parents[1]
    baseline_path = args.baseline_run.resolve()
    baseline_payload = _read_payload(baseline_path)
    candidate_order = resolve_candidate_order(args.candidate_order)
    invariants = validate_baseline(
        baseline_payload,
        seed=args.seed,
        candidate_order=candidate_order,
        life_days=args.life_days,
    )
    if args.validate_only:
        print(
            "Validation passed. No API call was made. "
            f"Conditions: {', '.join(ADDITIONAL_CONDITIONS)}."
        )
        print(
            "Matched invariants: "
            + json.dumps(invariants, ensure_ascii=False)
        )
        return

    run_at = datetime.datetime.now(datetime.timezone.utc)
    batch_id = run_at.strftime("%Y%m%dT%H%M%S_%fZ")
    output_dir = project_root / "outputs" / "world_batches"
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = output_dir / f"{batch_id}.json"
    payloads: dict[str, Mapping[str, Any]] = {
        "baseline": baseline_payload
    }
    paths = {"baseline": baseline_path}
    _write_manifest(
        manifest_path,
        build_manifest(
            batch_id=batch_id,
            status="running",
            project_root=project_root,
            payloads=payloads,
            paths=paths,
            invariants=invariants,
        ),
    )

    minimum_calls = (
        len(ADDITIONAL_CONDITIONS)
        * (args.life_days + 1)
        * len(baseline_payload["run"]["scenario"]["agents"])
    )
    print(
        "Four-condition batch: reusing baseline and running "
        f"{', '.join(ADDITIONAL_CONDITIONS)}."
    )
    print(
        f"Expected additional calls: {minimum_calls}-{minimum_calls * 2}."
    )
    print(f"Progress manifest: {manifest_path}")

    try:
        for condition in ADDITIONAL_CONDITIONS:
            print(f"Starting condition: {condition}")
            command = build_live_command(
                project_root=project_root,
                condition=condition,
                seed=args.seed,
                candidate_order_mode=args.candidate_order,
                life_days=args.life_days,
                memory_backend=args.memory_backend,
            )
            result = subprocess.run(
                command,
                cwd=project_root,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                check=False,
            )
            if result.stdout:
                print(result.stdout, end="")
            if result.stderr:
                print(result.stderr, file=sys.stderr, end="")
            if result.returncode != 0:
                raise RuntimeError(
                    f"Condition {condition} failed with exit code "
                    f"{result.returncode}."
                )
            saved_path = _saved_path(result.stdout)
            condition_payload = _read_payload(saved_path)
            if condition_payload["run"]["config"]["condition"] != condition:
                raise ValueError(
                    f"Saved run condition is not {condition}."
                )
            assert_matching_invariants(
                condition_payload,
                invariants,
            )
            if not condition_payload["metrics"][
                "manipulation_check_passed"
            ]:
                raise ValueError(
                    f"Manipulation check failed for {condition}."
                )
            payloads[condition] = condition_payload
            paths[condition] = saved_path
            _write_manifest(
                manifest_path,
                build_manifest(
                    batch_id=batch_id,
                    status="running",
                    project_root=project_root,
                    payloads=payloads,
                    paths=paths,
                    invariants=invariants,
                ),
            )
    except Exception as exc:
        _write_manifest(
            manifest_path,
            build_manifest(
                batch_id=batch_id,
                status="failed",
                project_root=project_root,
                payloads=payloads,
                paths=paths,
                invariants=invariants,
                error=str(exc),
            ),
        )
        raise

    _write_manifest(
        manifest_path,
        build_manifest(
            batch_id=batch_id,
            status="completed",
            project_root=project_root,
            payloads=payloads,
            paths=paths,
            invariants=invariants,
        ),
    )
    print(f"Completed four-condition manifest: {manifest_path}")


if __name__ == "__main__":
    main()
