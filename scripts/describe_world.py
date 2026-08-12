"""Print Riverbend's generic world definition without calling an LLM."""

from __future__ import annotations

import argparse
import json

from concordia_riverbend.scenarios.election_conditions import (
    ELECTION_CONDITIONS,
)
from concordia_riverbend.scenarios.riverbend_world import (
    build_initial_riverbend_state,
)
from concordia_riverbend.scenarios.riverbend_world import (
    build_riverbend_world,
)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Inspect Riverbend's generic scenario and initial state."
    )
    parser.add_argument(
        "--condition",
        choices=tuple(condition.name for condition in ELECTION_CONDITIONS),
        default="baseline",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print the complete frontend-ready JSON record.",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    condition = next(
        condition
        for condition in ELECTION_CONDITIONS
        if condition.name == args.condition
    )
    scenario = build_riverbend_world(condition)
    state = build_initial_riverbend_state(condition)

    if args.json:
        print(
            json.dumps(
                {
                    "scenario": scenario.to_dict(),
                    "world_state": state.to_dict(),
                },
                indent=2,
                ensure_ascii=False,
            )
        )
        return

    print(scenario.title)
    print("-" * len(scenario.title))
    print(f"Condition: {condition.name}")
    print(f"Agents: {len(scenario.agents)}")
    print(f"Locations: {len(scenario.locations)}")
    print(f"Actions: {', '.join(scenario.action_types)}")
    print(f"Initial events: {len(state.events)}")
    for agent in scenario.agents:
        print(
            f"- {agent.name}: {agent.role} at "
            f"{agent.initial_location}"
        )
    print("\nNo language model was called.")


if __name__ == "__main__":
    main()
