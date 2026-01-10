"""Family clustering and robustness analysis for tasks."""

from __future__ import annotations

import difflib
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class FamilyResult:
    family_id: str
    rep_run_id: str
    run_ids: List[str]


def _cosine_similarity(vec_a: List[float], vec_b: List[float]) -> float:
    if not vec_a or not vec_b:
        return 0.0
    dot = sum(a * b for a, b in zip(vec_a, vec_b))
    norm_a = sum(a * a for a in vec_a) ** 0.5
    norm_b = sum(b * b for b in vec_b) ** 0.5
    denom = (norm_a * norm_b) or 1.0
    return dot / denom


def _text_similarity(text_a: str, text_b: str) -> float:
    return difflib.SequenceMatcher(None, text_a, text_b).ratio()


def _build_signature_text(run: Dict[str, Any]) -> str:
    final_answer = (run.get("final_answer") or "").strip()
    plan_steps = run.get("plan_steps") or []
    assumptions = run.get("assumptions") or []
    fallbacks = _fallbacks_from_run(run)
    parts = [
        final_answer,
        "\n".join(plan_steps),
        "\n".join(assumptions),
        "\n".join(fallbacks),
    ]
    return "\n".join(part for part in parts if part)


def _fallbacks_from_run(run: Dict[str, Any]) -> List[str]:
    raw_json = run.get("raw_json") or {}
    summary = raw_json.get("reasoning_summary") or {}
    fallbacks = summary.get("fallbacks")
    return fallbacks if isinstance(fallbacks, list) else []


def compute_families_and_robustness(
    runs: List[Dict[str, Any]],
    embedding_threshold: float = 0.85,
    text_threshold: float = 0.65,
) -> Tuple[List[FamilyResult], str, Optional[str], Dict[str, Any]]:
    """Cluster runs into families and return robustness status."""
    valid_runs = [run for run in runs if run.get("is_valid")]
    if len(valid_runs) < 2:
        return [], "INSUFFICIENT_DATA", None, {"valid_runs": len(valid_runs)}

    families: List[FamilyResult] = []
    signature_cache: Dict[str, str] = {}
    mode_counts = {"embedding": 0, "text": 0}

    for run in valid_runs:
        run_id = run.get("_id") or run.get("run_id")
        if not run_id:
            continue

        signature_cache[run_id] = _build_signature_text(run)
        assigned = False

        for family in families:
            rep_id = family.rep_run_id
            rep_run = _find_run_by_id(valid_runs, rep_id)
            if not rep_run:
                continue

            sim, mode = _similarity(run, rep_run, signature_cache)
            mode_counts[mode] += 1
            threshold = embedding_threshold if mode == "embedding" else text_threshold
            if sim >= threshold:
                family.run_ids.append(run_id)
                assigned = True
                break

        if not assigned:
            family_id = f"family_{len(families) + 1}"
            families.append(
                FamilyResult(
                    family_id=family_id,
                    rep_run_id=run_id,
                    run_ids=[run_id],
                )
            )

    robustness = "FRAGILE" if len(families) == 1 else "ROBUST"
    return families, robustness, None, {
        "valid_runs": len(valid_runs),
        "mode_counts": mode_counts,
        "num_families": len(families),
        "robustness_status": robustness,
    }


def _find_run_by_id(runs: List[Dict[str, Any]], run_id: str) -> Optional[Dict[str, Any]]:
    for run in runs:
        if run.get("_id") == run_id or run.get("run_id") == run_id:
            return run
    return None


def _similarity(
    run_a: Dict[str, Any],
    run_b: Dict[str, Any],
    signature_cache: Dict[str, str],
) -> Tuple[float, str]:
    emb_a = _embedding_from_run(run_a)
    emb_b = _embedding_from_run(run_b)
    if emb_a and emb_b:
        return _cosine_similarity(emb_a, emb_b), "embedding"
    id_a = run_a.get("_id") or run_a.get("run_id")
    id_b = run_b.get("_id") or run_b.get("run_id")
    text_a = signature_cache.get(id_a, "")
    text_b = signature_cache.get(id_b, "")
    return _text_similarity(text_a, text_b), "text"


def _embedding_from_run(run: Dict[str, Any]) -> List[float]:
    raw_json = run.get("raw_json") or {}
    embedding = raw_json.get("embedding_vector")
    return embedding if isinstance(embedding, list) and embedding else []
