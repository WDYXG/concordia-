"""Tests for reproducible experiment planning and world metrics."""

from __future__ import annotations

from collections import Counter
import unittest

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
from concordia_riverbend.core import ScriptedAgentController
from concordia_riverbend.core import SimulationConfig
from concordia_riverbend.core import SimulationRunner
from concordia_riverbend.scenarios.election_conditions import (
    ELECTION_CONDITIONS,
)
from concordia_riverbend.scenarios.riverbend_world import (
    build_riverbend_world,
)


class ExperimentPlanTest(unittest.TestCase):
    def test_same_seed_reproduces_complete_plan(self) -> None:
        scenario = build_riverbend_world()
        kwargs = {
            "conditions": [
                condition.name for condition in ELECTION_CONDITIONS
            ],
            "repetitions_per_condition": 4,
            "agent_ids": scenario.agent_ids,
            "candidates": ("Alice", "Bob"),
            "base_seed": 42,
        }
        first = build_experiment_plan(**kwargs)
        second = build_experiment_plan(**kwargs)

        self.assertEqual(first.to_dict(), second.to_dict())
        self.assertEqual(len(first.runs), 16)

    def test_candidate_order_is_balanced_within_each_condition(self) -> None:
        scenario = build_riverbend_world()
        plan = build_experiment_plan(
            conditions=[
                condition.name for condition in ELECTION_CONDITIONS
            ],
            repetitions_per_condition=4,
            agent_ids=scenario.agent_ids,
            candidates=("Alice", "Bob"),
            base_seed=9,
        )

        for condition in {
            run.condition for run in plan.runs
        }:
            first_candidates = Counter(
                run.candidate_order[0]
                for run in plan.runs
                if run.condition == condition
            )
            self.assertEqual(first_candidates, {"Alice": 2, "Bob": 2})

    def test_scripted_execution_uses_each_planned_order_and_seed(self) -> None:
        scenario = build_riverbend_world()
        plan = build_experiment_plan(
            conditions=[
                condition.name for condition in ELECTION_CONDITIONS
            ],
            repetitions_per_condition=2,
            agent_ids=scenario.agent_ids,
            candidates=("Alice", "Bob"),
            base_seed=17,
        )
        runs = run_scripted_experiment_plan(
            plan=plan,
            conditions=ELECTION_CONDITIONS,
        )

        self.assertEqual(len(runs), len(plan.runs))
        for run, run_plan in zip(runs, plan.runs):
            self.assertEqual(run.config.seed, run_plan.seed)
            self.assertEqual(
                tuple(run.config.metadata["candidate_order"]),
                run_plan.candidate_order,
            )
            self.assertEqual(
                tuple(
                    turn.agent_id
                    for turn in run.turns[: len(scenario.agents)]
                ),
                run_plan.agent_order,
            )


class WorldMetricsTest(unittest.TestCase):
    def test_scripted_run_passes_delivery_check_and_records_metrics(self) -> None:
        condition = next(
            item
            for item in ELECTION_CONDITIONS
            if item.name == "employment_evidence"
        )
        run = run_scripted_riverbend_world(condition=condition)
        metrics = analyze_world_run(run)

        self.assertTrue(metrics["manipulation_check_passed"])
        self.assertEqual(metrics["accepted_actions"], 15)
        self.assertEqual(metrics["rejected_actions"], 0)
        self.assertEqual(sum(metrics["candidate_tally"].values()), 5)
        self.assertEqual(len(metrics["vote_reasons"]), 5)
        self.assertGreater(metrics["relationship_edges"], 0)
        self.assertGreater(metrics["memory_type_counts"]["semantic"], 0)

    def test_summary_states_the_synthetic_unit_limit(self) -> None:
        runs = [
            run_scripted_riverbend_world(condition=condition)
            for condition in ELECTION_CONDITIONS
        ]
        summary = summarize_world_runs(runs)

        self.assertIn("not independent human", summary["unit_note"])
        self.assertEqual(set(summary["conditions"]), {
            condition.name for condition in ELECTION_CONDITIONS
        })

    def test_metrics_report_every_agent_without_a_ballot(self) -> None:
        scenario = build_riverbend_world(
            start_at_voting_location=True
        )
        run = SimulationRunner(
            scenario=scenario,
            config=SimulationConfig(
                scenario_id=scenario.scenario_id,
                max_rounds=1,
                seed=31,
            ),
            controllers={
                agent.agent_id: ScriptedAgentController(())
                for agent in scenario.agents
            },
        ).run()

        metrics = analyze_world_run(run)

        self.assertEqual(metrics["eligible_voters"], 5)
        self.assertEqual(metrics["ballots_cast"], 0)
        self.assertEqual(metrics["unvoted_count"], 5)
        self.assertEqual(
            set(metrics["unvoted_agent_ids"]),
            set(scenario.agent_ids),
        )
