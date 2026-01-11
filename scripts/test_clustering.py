"""Basic clustering tests for reasoning families."""

from __future__ import annotations

import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from mprg.task_analysis import compute_families_and_robustness


def test_numeric_answer_single_family() -> None:
    runs = [
        {
            "_id": "r1",
            "is_valid": True,
            "final_answer": "12",
            "plan_steps": ["add 7 and 5"],
            "assumptions": [],
            "canonical_text": "answer: 12\nintent: math\nsteps: add 7 and 5",
            "raw_json": {"embedding_vector": [1.0, 0.0]},
        },
        {
            "_id": "r2",
            "is_valid": True,
            "final_answer": "12",
            "plan_steps": ["sum numbers"],
            "assumptions": [],
            "canonical_text": "answer: 12\nintent: math\nsteps: sum numbers",
            "raw_json": {"embedding_vector": [0.0, 1.0]},
        },
    ]
    families, robustness, _, metrics = compute_families_and_robustness(runs)
    assert metrics["num_families"] == 1
    assert robustness == "FRAGILE"


def test_open_ended_multiple_families() -> None:
    runs = []
    for idx in range(6):
        runs.append(
            {
                "_id": f"a{idx}",
                "is_valid": True,
                "final_answer": "migrate to microservices",
                "plan_steps": ["split services", "deploy independently"],
                "assumptions": [],
                "canonical_text": "answer: migrate to microservices\nintent: planning\nsteps: split services; deploy independently",
                "raw_json": {"embedding_vector": [1.0, 0.1]},
            }
        )
    for idx in range(6):
        runs.append(
            {
                "_id": f"b{idx}",
                "is_valid": True,
                "final_answer": "incremental strangler pattern",
                "plan_steps": ["strangle legacy", "route traffic"],
                "assumptions": [],
                "canonical_text": "answer: incremental strangler pattern\nintent: planning\nsteps: strangle legacy; route traffic",
                "raw_json": {"embedding_vector": [0.0, 1.0]},
            }
        )
    families, robustness, _, metrics = compute_families_and_robustness(runs)
    assert metrics["num_families"] >= 2
    assert all(size > 1 for size in metrics.get("family_sizes", [2, 2]))
    assert robustness == "ROBUST"


if __name__ == "__main__":
    test_numeric_answer_single_family()
    test_open_ended_multiple_families()
    print("OK - clustering tests passed.")
