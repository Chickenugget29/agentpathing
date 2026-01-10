"""Execution gate - the payoff feature.

Makes actual decisions based on robustness:
- FRAGILE → Block or require revision
- MODERATE → Warn but allow override
- ROBUST → Allow execution
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Dict, Any
from enum import Enum

from .scorer import RobustnessScore


class GateDecision(Enum):
    """Gate decision types."""
    BLOCK = "BLOCK"
    WARN = "WARN"
    ALLOW = "ALLOW"


@dataclass
class GateResult:
    """Result of gate evaluation with full reasoning trace."""
    
    decision: GateDecision
    
    # Why this decision
    reason: str
    
    # What to do next
    action: str
    suggestion: Optional[str]
    
    # For UI display
    color: str              # red, yellow, green
    icon: str               # 🛑, ⚠️, ✅
    
    # Original analysis
    robustness: RobustnessScore
    
    # Override capability
    can_override: bool
    override_warning: Optional[str]


class ExecutionGate:
    """Gate that decides whether to allow agent execution.
    
    This is where MPRG turns insight into action:
    - Before a long-running agent acts, check reasoning robustness
    - Block fragile plans before they waste resources
    - Allow robust plans to proceed confidently
    """
    
    def __init__(
        self,
        strict_mode: bool = False,
        require_minimum_families: int = 2
    ):
        """Initialize gate.
        
        Args:
            strict_mode: If True, MODERATE also blocks (not just FRAGILE)
            require_minimum_families: Minimum families to allow without warning
        """
        self.strict_mode = strict_mode
        self.require_minimum_families = require_minimum_families
        
    def evaluate(self, robustness: RobustnessScore) -> GateResult:
        """Evaluate whether to allow execution.
        
        Args:
            robustness: RobustnessScore from scorer
            
        Returns:
            GateResult with decision and reasoning
        """
        score = robustness.score
        
        if score == "FRAGILE":
            return self._block_decision(robustness)
        elif score == "MODERATE":
            if self.strict_mode:
                return self._block_decision(robustness, is_moderate=True)
            return self._warn_decision(robustness)
        else:  # ROBUST
            return self._allow_decision(robustness)
            
    def _block_decision(
        self,
        robustness: RobustnessScore,
        is_moderate: bool = False
    ) -> GateResult:
        """Create a BLOCK decision."""
        return GateResult(
            decision=GateDecision.BLOCK,
            reason=(
                f"Only {robustness.distinct_families} reasoning family detected. "
                f"Agreement among {robustness.total_agents} agents is shallow."
            ),
            action="Execution blocked. Please revise the plan.",
            suggestion=(
                "Try rephrasing the task to encourage diverse approaches, "
                "or explicitly ask for alternative solutions."
            ),
            color="red",
            icon="🛑",
            robustness=robustness,
            can_override=True,  # Allow override with explicit confirmation
            override_warning=(
                "Proceeding with fragile reasoning is risky. "
                "The plan relies on a single untested approach."
            )
        )
    
    def _warn_decision(self, robustness: RobustnessScore) -> GateResult:
        """Create a WARN decision."""
        return GateResult(
            decision=GateDecision.WARN,
            reason=(
                f"{robustness.distinct_families} reasoning families detected. "
                f"Moderate diversity among {robustness.total_agents} agents."
            ),
            action="Proceed with caution. Consider the alternatives.",
            suggestion=(
                "Review the different approaches before executing. "
                "Ensure you understand why they differ."
            ),
            color="yellow",
            icon="⚠️",
            robustness=robustness,
            can_override=False,  # No override needed, just proceed
            override_warning=None
        )
    
    def _allow_decision(self, robustness: RobustnessScore) -> GateResult:
        """Create an ALLOW decision."""
        return GateResult(
            decision=GateDecision.ALLOW,
            reason=(
                f"{robustness.distinct_families} distinct reasoning approaches found. "
                f"Plan is validated by diverse logic."
            ),
            action="Execution allowed. Proceed with confidence.",
            suggestion=None,
            color="green",
            icon="✅",
            robustness=robustness,
            can_override=False,
            override_warning=None
        )
    
    def override(
        self,
        result: GateResult,
        confirmation: str
    ) -> GateResult:
        """Override a BLOCK decision (with confirmation).
        
        Args:
            result: Original GateResult with BLOCK decision
            confirmation: User's confirmation message
            
        Returns:
            New GateResult allowing execution
        """
        if not result.can_override:
            return result
            
        return GateResult(
            decision=GateDecision.ALLOW,
            reason=f"User override: {confirmation}",
            action="Execution allowed by user override.",
            suggestion="Proceeding despite fragile reasoning - monitor carefully.",
            color="yellow",
            icon="⚠️✅",
            robustness=result.robustness,
            can_override=False,
            override_warning="This execution was forced despite low robustness."
        )


# Helper for JSON serialization
def gate_result_to_dict(result: GateResult) -> Dict[str, Any]:
    """Convert GateResult to JSON-serializable dict."""
    return {
        "decision": result.decision.value,
        "reason": result.reason,
        "action": result.action,
        "suggestion": result.suggestion,
        "color": result.color,
        "icon": result.icon,
        "can_override": result.can_override,
        "override_warning": result.override_warning,
        "robustness": {
            "score": result.robustness.score,
            "confidence": result.robustness.confidence,
            "total_agents": result.robustness.total_agents,
            "distinct_families": result.robustness.distinct_families,
            "explanation": result.robustness.explanation,
            "recommendation": result.robustness.recommendation,
            "family_breakdown": result.robustness.family_breakdown
        }
    }
