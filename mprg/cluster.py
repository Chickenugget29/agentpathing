"""Reasoning family clustering for MPRG."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Tuple

from .embeddings import cosine_similarity


@dataclass
class FamilyResult:
    family_id: str
    run_ids: List[str]
    representative_run_id: str
    family_signature: str


def normalize_assumption(text: str) -> str:
    cleaned = "".join(ch.lower() if ch.isalnum() or ch.isspace() else " " for ch in text)
    return " ".join(cleaned.split())


def jaccard_similarity(set_a: set[str], set_b: set[str]) -> float:
    if not set_a and not set_b:
        return 1.0
    union = set_a | set_b
    if not union:
        return 0.0
    return len(set_a & set_b) / len(union)


class UnionFind:
    def __init__(self, size: int) -> None:
        self.parent = list(range(size))

    def find(self, idx: int) -> int:
        while self.parent[idx] != idx:
            self.parent[idx] = self.parent[self.parent[idx]]
            idx = self.parent[idx]
        return idx

    def union(self, a: int, b: int) -> None:
        root_a = self.find(a)
        root_b = self.find(b)
        if root_a != root_b:
            self.parent[root_b] = root_a


def cluster_runs(
    run_records: List[Dict],
    plan_threshold: float,
    assumption_threshold: float,
) -> List[FamilyResult]:
    """Cluster runs into reasoning families using plan + assumption similarity."""
    if not run_records:
        return []

    uf = UnionFind(len(run_records))
    assumption_sets = [r["assumption_set"] for r in run_records]
    embeddings = [r["plan_embedding"] for r in run_records]

    for i in range(len(run_records)):
        for j in range(i + 1, len(run_records)):
            cosine = cosine_similarity(embeddings[i], embeddings[j])
            jaccard = jaccard_similarity(assumption_sets[i], assumption_sets[j])
            if cosine >= plan_threshold or jaccard >= assumption_threshold:
                uf.union(i, j)

    clusters: Dict[int, List[int]] = {}
    for idx in range(len(run_records)):
        root = uf.find(idx)
        clusters.setdefault(root, []).append(idx)

    families = []
    for family_idx, indices in enumerate(clusters.values(), start=1):
        members = [run_records[i] for i in indices]
        run_ids = [m["run_id"] for m in members]
        representative = members[0]
        signature = build_family_signature(members, representative)
        families.append(
            FamilyResult(
                family_id=f"family_{family_idx}",
                run_ids=run_ids,
                representative_run_id=representative["run_id"],
                family_signature=signature,
            )
        )

    return families


def build_family_signature(members: List[Dict], representative: Dict) -> str:
    """Create a concise signature: top assumptions + condensed steps."""
    assumption_counts: Dict[str, int] = {}
    assumption_labels: Dict[str, str] = {}
    for member in members:
        for raw in member["assumptions_raw"]:
            normalized = normalize_assumption(raw)
            if not normalized:
                continue
            assumption_counts[normalized] = assumption_counts.get(normalized, 0) + 1
            assumption_labels.setdefault(normalized, raw)

    top_assumptions = sorted(
        assumption_counts.items(),
        key=lambda item: item[1],
        reverse=True,
    )[:3]
    assumption_text = ", ".join(
        assumption_labels[key] for key, _ in top_assumptions
    )

    steps = representative.get("plan_steps", [])[:3]
    steps_text = " | ".join(steps)
    return f"Assumptions: {assumption_text or 'None'} | Steps: {steps_text or 'N/A'}"
