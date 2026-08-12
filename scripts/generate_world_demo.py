"""Generate no-API Riverbend runs consumed by the browser frontend."""

from __future__ import annotations

import argparse
import datetime
import json
from pathlib import Path

from concordia_riverbend.experiments.scripted_world import (
    run_scripted_experiment_plan,
)
from concordia_riverbend.experiments.scripted_world import (
    run_scripted_riverbend_world,
)
from concordia_riverbend.experiments.world_design import analyze_world_run
from concordia_riverbend.experiments.world_design import (
    build_experiment_plan,
)
from concordia_riverbend.experiments.world_design import summarize_world_runs
from concordia_riverbend.scenarios.election_conditions import (
    ELECTION_CONDITIONS,
)
from concordia_riverbend.scenarios.riverbend_world import (
    build_riverbend_world,
)


_CONDITION_LABELS = {
    "baseline": "基线组",
    "placebo": "安慰剂组",
    "employment_evidence": "就业证据组",
    "pollution_evidence": "污染证据组",
}


def _parse_args() -> argparse.Namespace:
    project_root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(
        description="Generate deterministic frontend demo data."
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=project_root / "web" / "data" / "demo_bundle.json",
    )
    parser.add_argument("--seed", type=int, default=20260727)
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    scenario = build_riverbend_world()
    plan = build_experiment_plan(
        conditions=[
            condition.name for condition in ELECTION_CONDITIONS
        ],
        repetitions_per_condition=4,
        agent_ids=scenario.agent_ids,
        candidates=("Alice", "Bob"),
        base_seed=args.seed,
    )
    demo_runs = [
        run_scripted_riverbend_world(
            condition=condition,
            seed=args.seed + index,
        )
        for index, condition in enumerate(ELECTION_CONDITIONS)
    ]
    planned_runs = run_scripted_experiment_plan(
        plan=plan,
        conditions=ELECTION_CONDITIONS,
    )
    payload = {
        "generated_at": datetime.datetime.now(
            datetime.timezone.utc
        ).isoformat(),
        "mode": "scripted_no_api_demo",
        "disclaimer": (
            "这是确定性脚本演示，用于验证框架和网页，不是 LLM "
            "实验结果，也不能代表真实人类行为。"
        ),
        "conditions": [
            {
                "name": condition.name,
                "label": _CONDITION_LABELS[condition.name],
                "run": run.to_dict(),
                "metrics": analyze_world_run(run),
            }
            for condition, run in zip(ELECTION_CONDITIONS, demo_runs)
        ],
        "experiment_plan": plan.to_dict(),
        "experiment_summary": summarize_world_runs(planned_runs),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"Saved no-API demo data: {args.output.resolve()}")


if __name__ == "__main__":
    main()
