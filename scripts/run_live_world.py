"""Run the multi-round Riverbend world with DeepSeek Agent controllers."""

from __future__ import annotations

import argparse
import datetime
import json
from pathlib import Path
import random

from concordia_riverbend.agents import LLMWorldController
from concordia_riverbend.core import SimulationConfig
from concordia_riverbend.core import SimulationRunner
from concordia_riverbend.experiments.world_design import analyze_world_run
from concordia_riverbend.language_models.deepseek_model import (
    DeepSeekLanguageModel,
)
from concordia_riverbend.memory import WorldMemory
from concordia_riverbend.memory import FastEmbedTextEmbedder
from concordia_riverbend.memory import HashingTextEmbedder
from concordia_riverbend.memory import semantic_model_cache
from concordia_riverbend.scenarios.election_conditions import (
    ELECTION_CONDITIONS,
)
from concordia_riverbend.scenarios.riverbend_world import (
    build_riverbend_world,
)
from concordia_riverbend.scenarios.riverbend_schedule import (
    RiverbendDayScheduler,
)
from concordia_riverbend.scenarios.riverbend_schedule import (
    build_daily_event_schedule,
)


def resolve_candidate_order(
    mode: str,
    seed: int,
) -> tuple[str, str]:
    """Resolve an explicit order or alternate it reproducibly by seed."""
    if mode == "alice-first":
        return ("Alice", "Bob")
    if mode == "bob-first":
        return ("Bob", "Alice")
    if mode == "auto":
        return (
            ("Alice", "Bob")
            if seed % 2
            else ("Bob", "Alice")
        )
    raise ValueError(f"Unknown candidate-order mode: {mode!r}.")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run a live multi-round Riverbend Agent world."
    )
    parser.add_argument(
        "--condition",
        choices=tuple(condition.name for condition in ELECTION_CONDITIONS),
        default="baseline",
    )
    parser.add_argument(
        "--life-days",
        "--rounds",
        dest="life_days",
        type=int,
        default=10,
        help=(
            "Number of normal-life days before the election. --rounds is "
            "retained as a compatibility alias."
        ),
    )
    parser.add_argument("--seed", type=int, default=20260727)
    parser.add_argument(
        "--candidate-order",
        choices=("auto", "alice-first", "bob-first"),
        default="auto",
        help=(
            "Auto alternates the first candidate by seed parity. Explicit "
            "orders remain available for planned counterbalancing."
        ),
    )
    parser.add_argument(
        "--confirm-live-api",
        action="store_true",
        help="Required acknowledgement that this command spends API credit.",
    )
    parser.add_argument(
        "--memory-backend",
        choices=("semantic", "hash"),
        default="semantic",
        help=(
            "Semantic uses the downloaded local ONNX model. Hash is the "
            "lightweight lexical fallback."
        ),
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    if not args.confirm_live_api:
        raise SystemExit(
            "No API call was made. Re-run with --confirm-live-api after "
            "reviewing the estimated call count."
        )
    if args.life_days < 1:
        raise SystemExit("--life-days must be at least 1.")

    project_root = Path(__file__).resolve().parents[1]
    condition = next(
        item
        for item in ELECTION_CONDITIONS
        if item.name == args.condition
    )
    candidate_order = resolve_candidate_order(
        args.candidate_order,
        args.seed,
    )
    election_day = args.life_days + 1
    event_schedule = build_daily_event_schedule(
        args.seed,
        life_days=args.life_days,
    )
    scenario = build_riverbend_world(
        condition,
        candidate_order=candidate_order,
        life_simulation=True,
        election_day=election_day,
    )
    if args.memory_backend == "semantic":
        memory_embedder = FastEmbedTextEmbedder(
            cache_dir=semantic_model_cache(project_root),
            local_files_only=True,
        )
    else:
        memory_embedder = HashingTextEmbedder()
    memory = WorldMemory(
        scenario,
        embedder=memory_embedder,
    )
    agent_order = list(scenario.agent_ids)
    random.Random(args.seed).shuffle(agent_order)
    model = DeepSeekLanguageModel(env_file=project_root / ".env")
    controllers = {
        agent.agent_id: LLMWorldController(
            model=model,
            agent=agent,
            scenario=scenario,
        )
        for agent in scenario.agents
    }
    total_days = election_day
    minimum_calls = total_days * len(scenario.agents)
    maximum_calls = minimum_calls * 2
    print(
        f"Live run: {args.life_days} life days + day {election_day} "
        f"election x {len(scenario.agents)} Agents. "
        f"Expected {minimum_calls}-{maximum_calls} model calls, depending "
        "on JSON retries."
    )
    print(
        "Election protocol: residents begin at their normal locations, "
        f"the treatment is broadcast on day {args.life_days}, and all "
        f"voters enter town_hall on day {election_day}; "
        f"candidate order is {' then '.join(candidate_order)} "
        f"({args.candidate_order})."
    )
    scheduler = RiverbendDayScheduler(
        schedule=event_schedule,
        condition=condition,
        candidate_order=candidate_order,
        election_day=election_day,
    )
    run = SimulationRunner(
        scenario=scenario,
        config=SimulationConfig(
            scenario_id=scenario.scenario_id,
            max_rounds=total_days,
            seed=args.seed,
            condition=condition.name,
            model_name=model.model_name,
            metadata={
                "candidate_order": candidate_order,
                "candidate_order_mode": args.candidate_order,
                "agent_order": agent_order,
                "live_api": True,
                "time_unit": "day",
                "life_days": args.life_days,
                "election_day": election_day,
                "treatment_day": args.life_days,
                "event_schedule": [
                    event.to_dict() for event in event_schedule
                ],
                "start_at_voting_location": False,
                "memory_embedder": memory_embedder.name,
            },
        ),
        controllers=controllers,
        agent_order=agent_order,
        memory_system=memory,
        round_scheduler=scheduler,
    ).run()

    run_at = datetime.datetime.now(datetime.timezone.utc)
    run_id = run_at.strftime("%Y%m%dT%H%M%S_%fZ")
    payload = {
        "run_id": run_id,
        "run_at": run_at.isoformat(),
        "run": run.to_dict(),
        "metrics": analyze_world_run(run),
        "controller_traces": {
            agent_id: controller.trace()
            for agent_id, controller in controllers.items()
        },
        "model_usage": model.usage_summary(),
    }
    output_dir = project_root / "outputs" / "world_runs"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{run_id}.json"
    output_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"Saved: {output_path}")


if __name__ == "__main__":
    main()
