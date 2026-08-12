"""Tests that live world runs cannot spend credit accidentally."""

from __future__ import annotations

from pathlib import Path
import subprocess
import sys
import unittest

from scripts.run_live_world import resolve_candidate_order


class LiveWorldGuardTest(unittest.TestCase):
    def test_command_requires_explicit_live_api_confirmation(self) -> None:
        project_root = Path(__file__).resolve().parents[1]
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "scripts.run_live_world",
                "--rounds",
                "1",
            ],
            cwd=project_root,
            capture_output=True,
            text=True,
            check=False,
            timeout=30,
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("No API call was made", result.stderr)

    def test_auto_candidate_order_alternates_reproducibly(self) -> None:
        self.assertEqual(
            resolve_candidate_order("auto", 20260727),
            ("Alice", "Bob"),
        )
        self.assertEqual(
            resolve_candidate_order("auto", 20260728),
            ("Bob", "Alice"),
        )
        self.assertEqual(
            resolve_candidate_order("bob-first", 20260727),
            ("Bob", "Alice"),
        )
