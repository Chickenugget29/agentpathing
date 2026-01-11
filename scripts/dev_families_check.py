"""Dev helper to seed a task with fake runs and verify family analysis."""

from __future__ import annotations

from mprg.task_store import TaskStore
from mprg.task_analysis import compute_families_and_robustness


def main() -> None:
    store = TaskStore()
    task_id = store.create_task("DEV: family analysis smoke test")
    store.update_task(task_id, {"status": "RUNNING"})

    runs = [
        {
            "agent_role": "planner",
            "plan_steps": ["Fetch data", "Transform data", "Store results"],
            "assumptions": ["API returns JSON"],
            "final_answer": "Use batch ETL",
            "is_valid": True,
            "canonical_text": "answer: use batch etl\nintent: planning\nsteps: fetch data; transform data; store results",
            "raw_json": {"reasoning_summary": {"fallbacks": ["Retry on failure"]}},
        },
        {
            "agent_role": "skeptic",
            "plan_steps": ["Fetch data", "Transform data", "Store results"],
            "assumptions": ["API returns JSON"],
            "final_answer": "Use batch ETL",
            "is_valid": True,
            "canonical_text": "answer: use batch etl\nintent: planning\nsteps: fetch data; transform data; store results",
            "raw_json": {"reasoning_summary": {"fallbacks": ["Retry on failure"]}},
        },
        {
            "agent_role": "alternative_strategy",
            "plan_steps": ["Stream events", "Validate schema", "Update sink"],
            "assumptions": ["Events arrive continuously"],
            "final_answer": "Use streaming",
            "is_valid": True,
            "canonical_text": "answer: use streaming\nintent: planning\nsteps: stream events; validate schema; update sink",
            "raw_json": {"reasoning_summary": {"fallbacks": ["Buffer and replay"]}},
        },
    ]

    for run in runs:
        store.insert_run(task_id, run)

    stored_runs = store.get_runs(task_id)
    families, robustness, _, metrics = compute_families_and_robustness(stored_runs)

    assert metrics["num_families"] == 2, "Expected 2 families"
    assert robustness == "ROBUST", "Expected ROBUST status"

    family_payload = [
        {"family_id": f.family_id, "rep_run_id": f.rep_run_id, "run_ids": f.run_ids}
        for f in families
    ]
    store.update_task_analysis(
        task_id,
        families=family_payload,
        num_families=metrics["num_families"],
        robustness_status=robustness,
    )
    store.update_task(task_id, {"status": "DONE"})

    print("OK - families:", metrics["num_families"], "robustness:", robustness)


if __name__ == "__main__":
    main()
