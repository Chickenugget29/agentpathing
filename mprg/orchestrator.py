"""Orchestrator for running MPRG tasks end-to-end."""

from __future__ import annotations

from dataclasses import asdict
from typing import Dict, List, Tuple

from .agent_runner import AgentRun, MultiAgentRunner
from .cluster import cluster_runs, normalize_assumption
from .embeddings import EmbeddingModel
from .store import MongoStore


class MPRGOrchestrator:
    """Coordinates agent runs, clustering, and persistence."""

    def __init__(
        self,
        store: MongoStore,
        runner: MultiAgentRunner,
        plan_threshold: float = 0.85,
        assumption_threshold: float = 0.70,
        embedding_model: EmbeddingModel | None = None,
    ) -> None:
        self.store = store
        self.runner = runner
        self.plan_threshold = plan_threshold
        self.assumption_threshold = assumption_threshold
        self.embedding_model = embedding_model or EmbeddingModel()

    def create_and_run(self, prompt: str) -> Dict[str, str]:
        task_id = self.store.create_task(prompt)
        self.run_task(task_id, prompt)
        return {"task_id": task_id}

    def run_task(self, task_id: str, prompt: str) -> None:
        runs = self.runner.run(task_id, prompt)
        run_docs = [self._run_to_doc(run) for run in runs]
        self._attach_embeddings(run_docs)
        self.store.add_runs(task_id, run_docs)
        self._cluster_and_update(task_id)

    def resume_task(self, task_id: str) -> None:
        """Restart-safe: recompute families and update task status."""
        self._cluster_and_update(task_id)

    def _cluster_and_update(self, task_id: str) -> None:
        runs = self.store.get_runs(task_id)
        valid_runs = [r for r in runs if r.get("valid")]
        families_payload, family_count, answers_agree = self._cluster_valid_runs(
            task_id, valid_runs
        )
        self.store.clear_families(task_id)
        self.store.add_families(task_id, families_payload)
        robustness_status = "FRAGILE" if family_count == 1 else "ROBUST"
        self.store.update_task(
            task_id,
            {
                "status": "COMPLETED",
                "total_runs": len(runs),
                "valid_runs": len(valid_runs),
                "family_count": family_count,
                "robustness_status": robustness_status,
                "answers_agree": answers_agree,
            },
        )

    def _cluster_valid_runs(
        self, task_id: str, runs: List[Dict]
    ) -> Tuple[List[Dict], int, bool]:
        if not runs:
            return [], 0, False

        run_records = []
        for run in runs:
            embedding = run.get("plan_embedding") or []
            assumptions_raw = run["summary"]["assumptions"]
            assumption_set = {
                normalize_assumption(a) for a in assumptions_raw if normalize_assumption(a)
            }
            run_records.append(
                {
                    "run_id": run["run_id"],
                    "plan_embedding": embedding,
                    "assumption_set": assumption_set,
                    "assumptions_raw": assumptions_raw,
                    "plan_steps": run["summary"]["plan_steps"],
                }
            )

        families = cluster_runs(
            run_records,
            plan_threshold=self.plan_threshold,
            assumption_threshold=self.assumption_threshold,
        )

        answers_agree = self._check_answer_agreement(runs)
        family_docs = [
            {
                "family_id": family.family_id,
                "run_ids": family.run_ids,
                "representative_run_id": family.representative_run_id,
                "family_signature": family.family_signature,
                "metrics": {
                    "family_count": len(families),
                    "robustness_status": "FRAGILE" if len(families) == 1 else "ROBUST",
                    "answers_agree": answers_agree,
                },
            }
            for family in families
        ]

        return family_docs, len(families), answers_agree

    def _check_answer_agreement(self, runs: List[Dict]) -> bool:
        normalized = []
        for run in runs:
            answer = run["summary"]["final_answer"].strip().lower()
            normalized.append(answer)
        return len(set(normalized)) == 1

    def _run_to_doc(self, run: AgentRun) -> Dict:
        summary = asdict(run.summary) if run.summary else None
        return {
            "run_id": run.run_id,
            "agent_role": run.agent_role,
            "raw_response": run.raw_response,
            "summary": summary,
            "valid": run.valid,
            "error": run.error,
            "elapsed_ms": run.elapsed_ms,
            "attempt_count": run.attempt_count,
            "plan_embedding": [],
        }

    def _attach_embeddings(self, run_docs: List[Dict]) -> None:
        valid_runs = [run for run in run_docs if run["valid"] and run["summary"]]
        if not valid_runs:
            return
        plan_texts = ["\n".join(run["summary"]["plan_steps"]) for run in valid_runs]
        embeddings = self.embedding_model.embed_texts(plan_texts)
        for run, embedding in zip(valid_runs, embeddings):
            run["plan_embedding"] = embedding
