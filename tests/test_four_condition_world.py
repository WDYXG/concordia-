"""Tests for the guarded four-condition Live Run batch."""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from scripts.run_four_condition_world import ADDITIONAL_CONDITIONS
from scripts.run_four_condition_world import build_live_command
from scripts.run_four_condition_world import build_manifest
from scripts.run_four_condition_world import validate_baseline


def _payload(
    condition: str,
    *,
    candidate: str = "Alice",
) -> dict[str, object]:
    ballots = {
        "maya_chen": candidate,
        "luis_ortiz": candidate,
    }
    return {
        "run_id": f"run_{condition}",
        "run_at": "2026-07-30T00:00:00+00:00",
        "run": {
            "scenario": {
                "agents": [
                    {"agent_id": "maya_chen"},
                    {"agent_id": "luis_ortiz"},
                ]
            },
            "config": {
                "condition": condition,
                "seed": 20260729,
                "max_rounds": 11,
                "model_name": "deepseek-chat",
                "metadata": {
                    "candidate_order": ["Bob", "Alice"],
                    "life_days": 10,
                    "election_day": 11,
                    "event_schedule": [
                        {"day": day, "event_type": "neutral"}
                        for day in range(1, 11)
                    ],
                    "agent_order": [
                        "luis_ortiz",
                        "maya_chen",
                    ],
                    "memory_embedder": "test-embedder",
                },
            },
        },
        "metrics": {
            "condition": condition,
            "ballots": ballots,
            "candidate_tally": {
                "Alice": (
                    len(ballots) if candidate == "Alice" else 0
                ),
                "Bob": (
                    len(ballots) if candidate == "Bob" else 0
                ),
            },
            "vote_reasons": {},
            "manipulation_check_passed": True,
        },
        "model_usage": {
            "request_count": 22,
            "total_tokens": 2000,
        },
    }


class FourConditionWorldTest(unittest.TestCase):
    def test_command_requires_explicit_live_api_confirmation(self) -> None:
        project_root = Path(__file__).resolve().parents[1]
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "scripts.run_four_condition_world",
                "--baseline-run",
                "unused.json",
            ],
            cwd=project_root,
            capture_output=True,
            text=True,
            check=False,
            timeout=30,
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("No API call was made", result.stderr)

    def test_builds_only_the_three_non_baseline_commands(self) -> None:
        commands = [
            build_live_command(
                project_root=Path("project"),
                condition=condition,
                seed=20260729,
                candidate_order_mode="bob-first",
                life_days=10,
                memory_backend="semantic",
            )
            for condition in ADDITIONAL_CONDITIONS
        ]

        self.assertEqual(
            ADDITIONAL_CONDITIONS,
            (
                "placebo",
                "employment_evidence",
                "pollution_evidence",
            ),
        )
        self.assertTrue(
            all("baseline" not in command for command in commands)
        )
        self.assertTrue(
            all("--confirm-live-api" in command for command in commands)
        )

    def test_validate_only_checks_a_realistic_baseline_without_api(
        self,
    ) -> None:
        project_root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as temporary:
            baseline_path = Path(temporary) / "baseline.json"
            baseline_path.write_text(
                json.dumps(_payload("baseline")),
                encoding="utf-8",
            )
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "scripts.run_four_condition_world",
                    "--baseline-run",
                    str(baseline_path),
                    "--validate-only",
                ],
                cwd=project_root,
                capture_output=True,
                text=True,
                check=False,
                timeout=30,
            )

        self.assertEqual(result.returncode, 0)
        self.assertIn("Validation passed", result.stdout)
        self.assertIn("No API call was made", result.stdout)

    def test_rejects_a_mismatched_baseline(self) -> None:
        baseline = _payload("baseline")
        baseline["run"]["config"]["metadata"][
            "candidate_order"
        ] = ["Alice", "Bob"]

        with self.assertRaisesRegex(
            ValueError,
            "Baseline configuration mismatch",
        ):
            validate_baseline(
                baseline,
                seed=20260729,
                candidate_order=("Bob", "Alice"),
                life_days=10,
            )

    def test_manifest_reports_vote_changes_and_usage(self) -> None:
        baseline = _payload("baseline", candidate="Alice")
        placebo = _payload("placebo", candidate="Bob")
        payloads = {
            "baseline": baseline,
            "placebo": placebo,
        }
        paths = {
            "baseline": Path("baseline.json"),
            "placebo": Path("placebo.json"),
        }
        invariants = validate_baseline(
            baseline,
            seed=20260729,
            candidate_order=("Bob", "Alice"),
            life_days=10,
        )

        manifest = build_manifest(
            batch_id="batch",
            status="running",
            project_root=Path.cwd(),
            payloads=payloads,
            paths=paths,
            invariants=invariants,
        )

        self.assertEqual(
            manifest["completed_conditions"],
            ["baseline", "placebo"],
        )
        self.assertEqual(
            len(manifest["vote_changes_vs_baseline"]["placebo"]),
            2,
        )
        self.assertEqual(
            manifest["combined_model_usage"]["request_count"],
            44,
        )


if __name__ == "__main__":
    unittest.main()
