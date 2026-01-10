"""Robustness scoring based on reasoning family diversity.

Simple, intuitive scoring:
- 1 family = FRAGILE (all agents used same reasoning)
- 2 families = MODERATE (some diversity)
- 3+ families = ROBUST (genuine diversity)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Dict, Any

from .grouper import ReasoningFamily


@dataclass
class RobustnessScore:
    """Complete robustness analysis with full transparency."""
    
    # Core metrics
    total_agents: int
    distinct_families: int
    
    # Classification
    score: str                    # FRAGILE | MODERATE | ROBUST
    confidence: float             # 0-1
    
    # Detailed breakdown for demo
    family_breakdown: List[Dict[str, Any]]
    
    # Human-readable explanation
    explanation: str
    
    # Recommendation
    recommendation: str


class RobustnessScorer:
    """Calculates robustness score from reasoning families.
    
    The key metric: Number of DISTINCT reasoning families.
    - This is NOT the same as number of agents
    - Catches "fake agreement" where 5 agents all use the same idea
    """
    
    def score(self, families: List[ReasoningFamily]) -> RobustnessScore:
        """Calculate robustness score.
        
        Args:
            families: List of reasoning families from grouper
            
        Returns:
            RobustnessScore with full analysis
        """
        num_families = len(families)
        total_agents = sum(len(f.member_ids) for f in families)
        
        # Determine classification
        if num_families == 1:
            classification = "FRAGILE"
            confidence = 0.9  # High confidence it's fragile
            explanation = (
                f"All {total_agents} agents used the same underlying reasoning. "
                f"Agreement is shallow - they're saying the same thing in different words."
            )
            recommendation = (
                "Consider revising the task or explicitly requesting alternative approaches. "
                "Current plan relies on a single reasoning path."
            )
        elif num_families == 2:
            classification = "MODERATE"
            confidence = 0.7
            explanation = (
                f"Found {num_families} distinct reasoning approaches among {total_agents} agents. "
                f"Some diversity exists, but limited validation."
            )
            recommendation = (
                "Plan has moderate support. Consider whether both approaches lead to same outcome. "
                "Proceed with awareness of the alternative perspective."
            )
        else:
            classification = "ROBUST"
            confidence = 0.85
            explanation = (
                f"Found {num_families} distinct reasoning approaches among {total_agents} agents. "
                f"Multiple independent paths support the conclusion."
            )
            recommendation = (
                "Plan is well-validated by diverse reasoning. "
                "Proceed with confidence."
            )
            
        # Create detailed breakdown
        breakdown = []
        for i, family in enumerate(families):
            breakdown.append({
                "family_id": family.family_id,
                "family_number": i + 1,
                "member_count": len(family.member_ids),
                "members": family.member_ids,
                "key_idea": family.shared_key_idea,
                "fol_pattern": family.shared_fol_pattern[:100],
                "assumptions": family.shared_assumptions[:3],
                "internal_similarity": {
                    "fol": family.fol_similarity,
                    "semantic": family.semantic_similarity,
                    "combined": family.combined_score
                }
            })
            
        return RobustnessScore(
            total_agents=total_agents,
            distinct_families=num_families,
            score=classification,
            confidence=confidence,
            family_breakdown=breakdown,
            explanation=explanation,
            recommendation=recommendation
        )
    
    def get_diversity_matrix(
        self,
        families: List[ReasoningFamily]
    ) -> Dict[str, Any]:
        """Get diversity analysis for visualization.
        
        Shows how different the families are from each other.
        """
        if len(families) < 2:
            return {
                "has_diversity": False,
                "message": "Only one reasoning family found"
            }
            
        # Compare key ideas
        key_ideas = [f.shared_key_idea for f in families]
        
        # Compare assumptions
        all_assumptions = []
        for f in families:
            all_assumptions.extend(f.shared_assumptions)
            
        unique_assumptions = list(set(all_assumptions))
        
        return {
            "has_diversity": True,
            "families_count": len(families),
            "key_ideas": key_ideas,
            "total_assumptions": len(all_assumptions),
            "unique_assumptions": len(unique_assumptions),
            "assumption_overlap": 1 - (len(unique_assumptions) / max(len(all_assumptions), 1))
        }
