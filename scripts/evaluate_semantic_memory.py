"""Compare lexical Hash retrieval with the local neural embedder."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import numpy as np

from concordia_riverbend.memory import FastEmbedTextEmbedder
from concordia_riverbend.memory import HashingTextEmbedder
from concordia_riverbend.memory import semantic_model_cache


MEMORIES = (
    {
        "id": "pollution_child",
        "text": "Maya's child became ill after pollution reached the river.",
    },
    {
        "id": "school_program",
        "text": (
            "Maya's school lost an after-school program during a budget cut."
        ),
    },
    {
        "id": "factory_jobs",
        "text": (
            "The factory expansion is expected to create local employment."
        ),
    },
    {
        "id": "clinic_funding",
        "text": "The community clinic needs stable financial support.",
    },
    {
        "id": "shop_permits",
        "text": "Evelyn wants faster permits for small local businesses.",
    },
)

QUERIES = (
    {
        "query": "Water contamination harmed her kid.",
        "expected_id": "pollution_child",
    },
    {
        "query": "Industrial growth may offer more jobs.",
        "expected_id": "factory_jobs",
    },
    {
        "query": "The medical center requires reliable funding.",
        "expected_id": "clinic_funding",
    },
    {
        "query": "河水污染让她的孩子生病了。",
        "expected_id": "pollution_child",
    },
    {
        "query": "削减预算导致学校课后项目被取消。",
        "expected_id": "school_program",
    },
    {
        "query": "店主希望更快获得营业审批。",
        "expected_id": "shop_permits",
    },
)


def evaluate_embedder(
    embedder: Any,
) -> dict[str, Any]:
    memory_vectors = {
        item["id"]: embedder(item["text"])
        for item in MEMORIES
    }
    cases: list[dict[str, Any]] = []
    for item in QUERIES:
        query_vector = embedder(item["query"])
        scores = {
            memory_id: float(np.dot(query_vector, vector))
            for memory_id, vector in memory_vectors.items()
        }
        ranked = sorted(
            scores,
            key=lambda memory_id: scores[memory_id],
            reverse=True,
        )
        cases.append(
            {
                "query": item["query"],
                "expected_id": item["expected_id"],
                "retrieved_id": ranked[0],
                "correct": ranked[0] == item["expected_id"],
                "top_score": round(scores[ranked[0]], 4),
                "expected_score": round(
                    scores[item["expected_id"]],
                    4,
                ),
            }
        )
    correct = sum(1 for case in cases if case["correct"])
    return {
        "embedder": embedder.name,
        "top_1_accuracy": correct / len(cases),
        "correct": correct,
        "total": len(cases),
        "cases": cases,
    }


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Evaluate semantic recall on paraphrase cases."
    )
    parser.add_argument(
        "--cache-dir",
        type=Path,
        help="Defaults to models/fastembed under the project root.",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    project_root = Path(__file__).resolve().parents[1]
    cache_dir = args.cache_dir or semantic_model_cache(project_root)
    hash_result = evaluate_embedder(HashingTextEmbedder())
    semantic_result = evaluate_embedder(
        FastEmbedTextEmbedder(
            cache_dir=cache_dir,
            local_files_only=True,
        )
    )
    payload = {
        "benchmark": "riverbend_synonym_recall_v1",
        "hash": hash_result,
        "semantic": semantic_result,
        "accuracy_delta": (
            semantic_result["top_1_accuracy"]
            - hash_result["top_1_accuracy"]
        ),
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    if semantic_result["top_1_accuracy"] < 0.8:
        raise SystemExit("Semantic top-1 accuracy is below 0.8.")
    if (
        semantic_result["top_1_accuracy"]
        <= hash_result["top_1_accuracy"]
    ):
        raise SystemExit("Semantic retrieval did not improve over Hash.")


if __name__ == "__main__":
    main()
