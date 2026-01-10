"""Reasoning family grouper using dual-layer analysis.

Groups agent reasoning by:
1. Structural similarity (FOL topology)
2. Semantic similarity (embeddings)

Only considers reasoning "the same family" if BOTH layers match.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Dict, Set
import uuid

from .analyzer import AnalyzedReasoning
from .vectors import VectorStore


@dataclass
class ReasoningFamily:
    """A group of reasoning traces that share the same underlying approach."""
    family_id: str
    member_ids: List[str]
    
    # Why grouped together
    shared_fol_pattern: str
    shared_key_idea: str
    shared_assumptions: List[str]
    
    # Similarity metrics
    fol_similarity: float        # 0-1
    semantic_similarity: float   # 0-1
    combined_score: float        # 0-1
    
    # For display
    representative_explanation: str
    
    def __post_init__(self):
        if not self.family_id:
            self.family_id = f"family_{uuid.uuid4().hex[:8]}"


class FamilyGrouper:
    """Groups reasoning by dual-layer similarity.
    
    The key insight: We only group reasoning together if BOTH:
    1. They have similar FOL structure (same logical topology)
    2. They have similar embeddings (same semantic meaning)
    
    This catches "fake agreement" where agents use different words
    but the same underlying reasoning.
    """
    
    def __init__(
        self,
        vector_store: VectorStore,
        fol_threshold: float = 0.7,
        semantic_threshold: float = 0.8
    ):
        """Initialize grouper.
        
        Args:
            vector_store: VectorStore for semantic similarity
            fol_threshold: Min similarity for FOL match (0-1)
            semantic_threshold: Min similarity for semantic match (0-1)
        """
        self.vectors = vector_store
        self.fol_threshold = fol_threshold
        self.semantic_threshold = semantic_threshold
        
    def group(
        self,
        analyzed: List[AnalyzedReasoning],
        task_id: str
    ) -> List[ReasoningFamily]:
        """Group analyzed reasoning into families.
        
        Args:
            analyzed: List of AnalyzedReasoning from analyzer
            task_id: Task ID for this analysis
            
        Returns:
            List of ReasoningFamily groups
        """
        if not analyzed:
            return []
            
        if len(analyzed) == 1:
            # Single agent = single family
            return [self._create_single_family(analyzed[0])]
        
        # Step 1: Compute FOL similarity matrix
        fol_matrix = self._compute_fol_similarity(analyzed)
        
        # Step 2: Compute semantic similarity matrix
        semantic_matrix = self._compute_semantic_similarity(analyzed, task_id)
        
        # Step 3: Combined clustering using both matrices
        families = self._cluster_dual_layer(
            analyzed, fol_matrix, semantic_matrix
        )
        
        return families
    
    def _compute_fol_similarity(
        self,
        analyzed: List[AnalyzedReasoning]
    ) -> List[List[float]]:
        """Compute pairwise FOL structural similarity."""
        n = len(analyzed)
        matrix = [[0.0] * n for _ in range(n)]
        
        for i in range(n):
            for j in range(n):
                if i == j:
                    matrix[i][j] = 1.0
                else:
                    sim = self._fol_similarity(analyzed[i], analyzed[j])
                    matrix[i][j] = sim
                    matrix[j][i] = sim
                    
        return matrix
    
    def _fol_similarity(
        self,
        a: AnalyzedReasoning,
        b: AnalyzedReasoning
    ) -> float:
        """Compute FOL structural similarity between two reasoning traces.
        
        Uses:
        1. Structure hash match (exact structure)
        2. Predicate overlap (shared predicates)
        3. Variable pattern similarity
        """
        score = 0.0
        
        # Hash match = perfect structural match
        if a.fol_structure_hash == b.fol_structure_hash:
            return 1.0
            
        # Predicate overlap
        pred_a = set(self._normalize_predicates(a.fol_predicates))
        pred_b = set(self._normalize_predicates(b.fol_predicates))
        
        if pred_a and pred_b:
            intersection = pred_a & pred_b
            union = pred_a | pred_b
            pred_overlap = len(intersection) / len(union) if union else 0
            score += pred_overlap * 0.6
            
        # Assumption overlap
        assume_a = set(a.assumptions)
        assume_b = set(b.assumptions)
        
        if assume_a and assume_b:
            intersection = assume_a & assume_b
            union = assume_a | assume_b
            assume_overlap = len(intersection) / len(union) if union else 0
            score += assume_overlap * 0.4
            
        return min(score, 1.0)
    
    def _normalize_predicates(self, predicates: List[str]) -> List[str]:
        """Normalize predicates for comparison (remove specific constants)."""
        import re
        normalized = []
        for pred in predicates:
            # Replace specific constants with placeholder
            norm = re.sub(r',\s*[A-Z][a-z]+\)', ', X)', pred)
            normalized.append(norm)
        return normalized
    
    def _compute_semantic_similarity(
        self,
        analyzed: List[AnalyzedReasoning],
        task_id: str
    ) -> List[List[float]]:
        """Compute pairwise semantic similarity using embeddings."""
        texts = [a.original_explanation for a in analyzed]
        ids = [a.agent_id for a in analyzed]
        
        return self.vectors.compute_similarity_matrix(texts, ids)
    
    def _cluster_dual_layer(
        self,
        analyzed: List[AnalyzedReasoning],
        fol_matrix: List[List[float]],
        semantic_matrix: List[List[float]]
    ) -> List[ReasoningFamily]:
        """Cluster using both similarity matrices.
        
        Two items are in the same family only if:
        - FOL similarity >= fol_threshold AND
        - Semantic similarity >= semantic_threshold
        """
        n = len(analyzed)
        assigned = [False] * n
        families = []
        
        for i in range(n):
            if assigned[i]:
                continue
                
            # Start new family with this item
            family_members = [i]
            assigned[i] = True
            
            # Find all items similar to this one
            for j in range(i + 1, n):
                if assigned[j]:
                    continue
                    
                fol_sim = fol_matrix[i][j]
                semantic_sim = semantic_matrix[i][j]
                
                # Must meet BOTH thresholds
                if (fol_sim >= self.fol_threshold and 
                    semantic_sim >= self.semantic_threshold):
                    family_members.append(j)
                    assigned[j] = True
            
            # Create family from members
            family = self._create_family(
                analyzed,
                family_members,
                fol_matrix,
                semantic_matrix
            )
            families.append(family)
            
        return families
    
    def _create_family(
        self,
        analyzed: List[AnalyzedReasoning],
        member_indices: List[int],
        fol_matrix: List[List[float]],
        semantic_matrix: List[List[float]]
    ) -> ReasoningFamily:
        """Create a ReasoningFamily from member indices."""
        members = [analyzed[i] for i in member_indices]
        member_ids = [m.agent_id for m in members]
        
        # Find shared attributes
        all_assumptions = []
        for m in members:
            all_assumptions.extend(m.assumptions)
        shared_assumptions = self._find_common(all_assumptions)
        
        # Representative = first member
        representative = members[0]
        
        # Compute average similarities
        avg_fol = 0.0
        avg_semantic = 0.0
        count = 0
        
        for i in range(len(member_indices)):
            for j in range(i + 1, len(member_indices)):
                idx_i = member_indices[i]
                idx_j = member_indices[j]
                avg_fol += fol_matrix[idx_i][idx_j]
                avg_semantic += semantic_matrix[idx_i][idx_j]
                count += 1
                
        if count > 0:
            avg_fol /= count
            avg_semantic /= count
        else:
            avg_fol = 1.0
            avg_semantic = 1.0
            
        return ReasoningFamily(
            family_id=f"family_{uuid.uuid4().hex[:8]}",
            member_ids=member_ids,
            shared_fol_pattern=representative.fol_translation[:200],
            shared_key_idea=representative.key_idea,
            shared_assumptions=shared_assumptions,
            fol_similarity=avg_fol,
            semantic_similarity=avg_semantic,
            combined_score=(avg_fol + avg_semantic) / 2,
            representative_explanation=representative.original_explanation[:300]
        )
    
    def _create_single_family(
        self,
        analyzed: AnalyzedReasoning
    ) -> ReasoningFamily:
        """Create a family with a single member."""
        return ReasoningFamily(
            family_id=f"family_{uuid.uuid4().hex[:8]}",
            member_ids=[analyzed.agent_id],
            shared_fol_pattern=analyzed.fol_translation[:200],
            shared_key_idea=analyzed.key_idea,
            shared_assumptions=analyzed.assumptions,
            fol_similarity=1.0,
            semantic_similarity=1.0,
            combined_score=1.0,
            representative_explanation=analyzed.original_explanation[:300]
        )
    
    def _find_common(self, items: List[str], min_count: int = 2) -> List[str]:
        """Find items that appear multiple times."""
        from collections import Counter
        counts = Counter(items)
        return [item for item, count in counts.items() if count >= min_count]
