"""Family clustering and robustness analysis for tasks."""

from __future__ import annotations

import difflib
import math
import random
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple


SIM_THRESHOLD_DEFAULT = 0.80
TEXT_THRESHOLD_DEFAULT = 0.65
MIN_CLUSTER_SIZE_DEFAULT = 2


@dataclass
class FamilyResult:
    family_id: str
    rep_run_id: str
    run_ids: List[str]
    centroid: List[float]
    rep_signature: str


def compute_families_and_robustness(
    runs: List[Dict[str, Any]],
    sim_threshold: float = SIM_THRESHOLD_DEFAULT,
    text_threshold: float = TEXT_THRESHOLD_DEFAULT,
    min_cluster_size: int = MIN_CLUSTER_SIZE_DEFAULT,
) -> Tuple[List[FamilyResult], str, Optional[str], Dict[str, Any]]:
    """Cluster runs into families using embedding centroids."""
    valid_runs = [run for run in runs if run.get("is_valid")]
    if len(valid_runs) < 2:
        return [], "INSUFFICIENT_DATA", None, {"valid_runs": len(valid_runs)}

    families: List[FamilyResult] = []
    similarity_stats: List[float] = []
    mode_counts = {"embedding": 0, "text": 0}
    signature_cache: Dict[str, str] = {}

    for run in valid_runs:
        run_id = _run_id(run)
        if not run_id:
            continue
        embedding = _embedding_from_run(run)
        signature_cache[run_id] = _build_signature_text(run)

        assigned = False
        best_family = None
        best_similarity = -1.0
        best_mode = "embedding"
        for family in families:
            sim, mode = _similarity_to_family(
                run, family, signature_cache, text_threshold
            )
            if sim > best_similarity:
                best_similarity = sim
                best_family = family
                best_mode = mode

        threshold = sim_threshold if best_mode == "embedding" else text_threshold
        if best_family and best_similarity >= threshold:
            best_family.run_ids.append(run_id)
            if best_mode == "embedding":
                best_family.centroid = _update_centroid(best_family.centroid, embedding)
            similarity_stats.append(best_similarity)
            mode_counts[best_mode] += 1
            assigned = True

        if not assigned:
            family_id = f"family_{len(families) + 1}"
            families.append(
                FamilyResult(
                    family_id=family_id,
                    rep_run_id=run_id,
                    run_ids=[run_id],
                    centroid=_normalize(embedding) if embedding else [],
                    rep_signature=signature_cache.get(run_id, ""),
                )
            )

    families_before_merge = len(families)

    families = _merge_singletons(
        families,
        valid_runs,
        signature_cache,
        sim_threshold - 0.05,
        text_threshold - 0.05,
        min_cluster_size,
    )

    families = _apply_numeric_answer_rule(families, valid_runs)

    if len(families) == 0:
        robustness = "INSUFFICIENT_DATA"
    elif len(families) == 1:
        robustness = "FRAGILE"
    else:
        robustness = "ROBUST"
    debug = _debug_stats(families, valid_runs, similarity_stats)
    debug.update(
        {
            "families_before_merge": families_before_merge,
            "families_after_merge": len(families),
            "threshold_used": sim_threshold,
            "min_cluster_size": min_cluster_size,
            "clustering_method": "embedding_centroid_with_text_fallback",
            "mode_counts": mode_counts,
            "valid_runs": len(valid_runs),
        }
    )
    return families, robustness, None, debug


def _find_run_by_id(runs: List[Dict[str, Any]], run_id: str) -> Optional[Dict[str, Any]]:
    for run in runs:
        if run.get("_id") == run_id or run.get("run_id") == run_id:
            return run
    return None


def _embedding_from_run(run: Dict[str, Any]) -> List[float]:
    raw_json = run.get("raw_json") or {}
    embedding = raw_json.get("embedding_vector")
    return embedding if isinstance(embedding, list) and embedding else []


def _run_id(run: Dict[str, Any]) -> Optional[str]:
    return run.get("_id") or run.get("run_id")


def _cosine_similarity(vec_a: List[float], vec_b: List[float]) -> float:
    if not vec_a or not vec_b:
        return 0.0
    dot = sum(a * b for a, b in zip(vec_a, vec_b))
    norm_a = sum(a * a for a in vec_a) ** 0.5
    norm_b = sum(b * b for b in vec_b) ** 0.5
    denom = (norm_a * norm_b) or 1.0
    return dot / denom


def _normalize(vec: List[float]) -> List[float]:
    norm = math.sqrt(sum(v * v for v in vec)) or 1.0
    return [v / norm for v in vec]


def _update_centroid(current: List[float], new_vec: List[float]) -> List[float]:
    combined = [a + b for a, b in zip(current, _normalize(new_vec))]
    return _normalize(combined)


def _merge_singletons(
    families: List[FamilyResult],
    runs: List[Dict[str, Any]],
    signature_cache: Dict[str, str],
    reassignment_threshold: float,
    text_threshold: float,
    min_cluster_size: int,
) -> List[FamilyResult]:
    if not families:
        return families

    large_families = [f for f in families if len(f.run_ids) >= min_cluster_size]
    singletons = [f for f in families if len(f.run_ids) == 1]
    if not large_families or not singletons:
        return families

    for family in singletons:
        run_id = family.run_ids[0]
        run = _find_run_by_id(runs, run_id)
        if not run:
            continue
        best = None
        best_sim = -1.0
        best_mode = "embedding"
        for target in large_families:
            sim, mode = _similarity_to_family(
                run, target, signature_cache, text_threshold
            )
            if sim > best_sim:
                best_sim = sim
                best = target
                best_mode = mode
        threshold = reassignment_threshold if best_mode == "embedding" else text_threshold
        if best and best_sim >= threshold:
            best.run_ids.append(run_id)
            if best_mode == "embedding":
                embedding = _embedding_from_run(run)
                if embedding:
                    best.centroid = _update_centroid(best.centroid, embedding)
            family.run_ids = []

    return [f for f in families if f.run_ids]


def _apply_numeric_answer_rule(
    families: List[FamilyResult], runs: List[Dict[str, Any]]
) -> List[FamilyResult]:
    numeric_map: Dict[str, List[str]] = {}
    for run in runs:
        answer = (run.get("final_answer") or "").strip()
        normalized = _normalize_answer(answer)
        if _is_simple_numeric(normalized):
            run_id = _run_id(run)
            if run_id:
                numeric_map.setdefault(normalized, []).append(run_id)

    if not numeric_map:
        return families

    run_to_family = {}
    for family in families:
        for run_id in family.run_ids:
            run_to_family[run_id] = family

    for run_ids in numeric_map.values():
        if len(run_ids) < 2:
            continue
        primary_family = None
        for run_id in run_ids:
            family = run_to_family.get(run_id)
            if family:
                primary_family = family
                break
        if not primary_family:
            continue
        for run_id in run_ids:
            family = run_to_family.get(run_id)
            if family and family is primary_family:
                continue
            if family:
                family.run_ids = [rid for rid in family.run_ids if rid != run_id]
            primary_family.run_ids.append(run_id)
            run_to_family[run_id] = primary_family

    return [f for f in families if f.run_ids]


def _normalize_answer(text: str) -> str:
    return re.sub(r"[^\w\.]+", "", text.casefold())


def _is_simple_numeric(text: str) -> bool:
    return bool(re.fullmatch(r"\d+(\.\d+)?", text))


def _debug_stats(
    families: List[FamilyResult],
    runs: List[Dict[str, Any]],
    similarity_stats: List[float],
) -> Dict[str, Any]:
    if similarity_stats:
        min_sim = min(similarity_stats)
        max_sim = max(similarity_stats)
        avg_sim = sum(similarity_stats) / len(similarity_stats)
    else:
        min_sim = max_sim = avg_sim = 0.0

    sample_run = random.choice(runs) if runs else None
    top5 = []
    if sample_run:
        sample_emb = _embedding_from_run(sample_run)
        for run in runs:
            if run is sample_run:
                continue
            emb = _embedding_from_run(run)
            if emb:
                top5.append(_cosine_similarity(sample_emb, emb))
        top5 = sorted(top5, reverse=True)[:5]

    return {
        "min_similarity": min_sim,
        "avg_similarity": avg_sim,
        "max_similarity": max_sim,
        "sample_top5_similarities": top5,
    }


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


def _similarity_to_family(
    run: Dict[str, Any],
    family: FamilyResult,
    signature_cache: Dict[str, str],
    text_threshold: float,
) -> Tuple[float, str]:
    embedding = _embedding_from_run(run)
    if embedding and family.centroid:
        return _cosine_similarity(embedding, family.centroid), "embedding"
    run_id = _run_id(run)
    signature = signature_cache.get(run_id, _build_signature_text(run))
    rep_signature = family.rep_signature
    if not rep_signature:
        rep_signature = signature_cache.get(family.rep_run_id, "")
    return _text_similarity(signature, rep_signature, text_threshold), "text"


def _text_similarity(text_a: str, text_b: str, _: float) -> float:
    if not text_a or not text_b:
        return 0.0
    return difflib.SequenceMatcher(None, text_a, text_b).ratio()
