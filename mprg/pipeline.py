"""Main MPRG pipeline - ties all components together.

This is the end-to-end flow:
1. Task → Multi-Agent Runner → 5 responses
2. Responses → Analyzer → Dual-layer traces
3. Traces → Grouper → Families
4. Families → Scorer → Robustness
5. Robustness → Gate → Decision
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, asdict
from typing import Optional, Dict, Any, List

from .runner import MultiAgentRunner, AgentResponse
from .analyzer import ReasoningAnalyzer, AnalyzedReasoning
from .grouper import FamilyGrouper, ReasoningFamily
from .scorer import RobustnessScorer, RobustnessScore
from .gate import ExecutionGate, GateResult, gate_result_to_dict
from .vectors import VectorStore
from .db import ReasoningLedger, AgentOutput, ReasoningTrace, RobustnessResult


@dataclass
class MPRGResult:
    """Complete MPRG analysis result with full visibility."""
    task_id: str
    task_prompt: str
    
    # Timing
    total_time_ms: int
    
    # All layers of analysis (for demo visibility)
    agent_responses: List[Dict]
    analyzed_reasoning: List[Dict]
    families: List[Dict]
    robustness: Dict
    gate_decision: Dict
    
    # Quick summary
    summary: str


class MPRGPipeline:
    """Complete MPRG pipeline with full reasoning visibility.
    
    Designed to make every step of reasoning analysis visible
    for hackathon demo.
    """
    
    def __init__(
        self,
        voyage_key: Optional[str] = None,
        openai_key: Optional[str] = None,
        anthropic_key: Optional[str] = None,
        mongodb_uri: Optional[str] = None,
        num_agents: int = 5
    ):
        """Initialize pipeline.
        
        Args:
            voyage_key: Voyage AI API key (unused until Voyage offers chat)
            openai_key: OpenAI API key
            anthropic_key: Anthropic API key
            mongodb_uri: MongoDB Atlas connection string
            num_agents: Number of parallel agents
        """
        # Initialize components
        self.vectors = VectorStore()
        self.runner = MultiAgentRunner(
            voyage_key=voyage_key,
            openai_key=openai_key,
            anthropic_key=anthropic_key,
            num_agents=num_agents
        )
        self.analyzer = ReasoningAnalyzer(vector_store=self.vectors)
        self.grouper = FamilyGrouper(vector_store=self.vectors)
        self.scorer = RobustnessScorer()
        self.gate = ExecutionGate()
        
        # MongoDB ledger (optional)
        try:
            self.ledger = ReasoningLedger(mongodb_uri)
        except Exception:
            self.ledger = None
            
    def analyze(self, task: str) -> MPRGResult:
        """Run full MPRG analysis on a task.
        
        Args:
            task: The task prompt to analyze
            
        Returns:
            MPRGResult with complete visibility into all layers
        """
        start_time = time.time()
        task_id = f"task_{uuid.uuid4().hex[:12]}"
        
        # Step 1: Run multiple agents
        responses = self.runner.run(task)
        
        # Step 2: Analyze each response
        analyzed = self.analyzer.analyze_batch(responses, task_id)
        
        # Step 3: Group into families
        families = self.grouper.group(analyzed, task_id)
        
        # Step 4: Calculate robustness
        robustness = self.scorer.score(families)
        
        # Step 5: Gate decision
        gate_result = self.gate.evaluate(robustness)
        
        total_time_ms = int((time.time() - start_time) * 1000)
        
        # Store in MongoDB if available
        if self.ledger:
            self._store_analysis(
                task_id, task, responses, analyzed,
                families, robustness, gate_result, total_time_ms
            )
        
        # Create summary
        summary = self._create_summary(robustness, gate_result)
        
        return MPRGResult(
            task_id=task_id,
            task_prompt=task,
            total_time_ms=total_time_ms,
            agent_responses=[self._response_to_dict(r) for r in responses],
            analyzed_reasoning=[self._analyzed_to_dict(a) for a in analyzed],
            families=[self._family_to_dict(f) for f in families],
            robustness=self._robustness_to_dict(robustness),
            gate_decision=gate_result_to_dict(gate_result),
            summary=summary
        )
    
    def _store_analysis(
        self,
        task_id: str,
        task: str,
        responses: List[AgentResponse],
        analyzed: List[AnalyzedReasoning],
        families: List[ReasoningFamily],
        robustness: RobustnessScore,
        gate_result: GateResult,
        total_time_ms: int
    ):
        """Store complete analysis in MongoDB."""
        if not self.ledger:
            return
            
        # Store agent outputs
        for resp in responses:
            self.ledger.store_agent_output(AgentOutput(
                task_id=task_id,
                agent_id=resp.agent_id,
                prompt_variant=resp.prompt_variant,
                raw_response=resp.raw_response,
                plan=resp.plan,
                explanation=resp.explanation
            ))
            
        # Store reasoning traces
        for a in analyzed:
            self.ledger.store_reasoning_trace(ReasoningTrace(
                agent_output_id=a.agent_id,
                fol_translation=a.fol_translation,
                fol_predicates=a.fol_predicates,
                fol_variables=a.fol_variables,
                fol_structure_hash=a.fol_structure_hash,
                original_text=a.original_explanation,
                embedding_vector=[],  # Stored in ChromaDB
                key_concepts=a.key_concepts,
                assumptions=a.assumptions,
                steps=a.steps,
                dependencies=a.dependencies,
                key_idea=a.key_idea
            ))
            
        # Store final result
        self.ledger.store_result(RobustnessResult(
            task_id=task_id,
            task_prompt=task,
            total_agents=robustness.total_agents,
            agent_outputs=[r.agent_id for r in responses],
            distinct_families=robustness.distinct_families,
            family_breakdown=robustness.family_breakdown,
            robustness_score=robustness.score,
            confidence=robustness.confidence,
            gate_decision=gate_result.decision.value,
            gate_reason=gate_result.reason,
            processing_time_ms=total_time_ms
        ))
    
    def _create_summary(
        self,
        robustness: RobustnessScore,
        gate_result: GateResult
    ) -> str:
        """Create human-readable summary."""
        return (
            f"{gate_result.icon} {robustness.score}: "
            f"{robustness.distinct_families} reasoning families from "
            f"{robustness.total_agents} agents. "
            f"Decision: {gate_result.decision.value}"
        )
    
    # =========================================================================
    # Serialization helpers
    # =========================================================================
    
    def _response_to_dict(self, r: AgentResponse) -> Dict:
        return {
            "agent_id": r.agent_id,
            "prompt_variant": r.prompt_variant,
            "plan": r.plan[:500],
            "explanation": r.explanation[:500],
            "elapsed_ms": r.elapsed_ms
        }
    
    def _analyzed_to_dict(self, a: AnalyzedReasoning) -> Dict:
        return {
            "agent_id": a.agent_id,
            "fol_translation": a.fol_translation,
            "fol_predicates": a.fol_predicates,
            "fol_structure_hash": a.fol_structure_hash,
            "assumptions": a.assumptions,
            "steps": a.steps,
            "dependencies": a.dependencies,
            "key_idea": a.key_idea,
            "key_concepts": a.key_concepts
        }
    
    def _family_to_dict(self, f: ReasoningFamily) -> Dict:
        return {
            "family_id": f.family_id,
            "member_ids": f.member_ids,
            "member_count": len(f.member_ids),
            "shared_key_idea": f.shared_key_idea,
            "shared_fol_pattern": f.shared_fol_pattern[:150],
            "shared_assumptions": f.shared_assumptions,
            "fol_similarity": f.fol_similarity,
            "semantic_similarity": f.semantic_similarity,
            "combined_score": f.combined_score
        }
    
    def _robustness_to_dict(self, r: RobustnessScore) -> Dict:
        return {
            "total_agents": r.total_agents,
            "distinct_families": r.distinct_families,
            "score": r.score,
            "confidence": r.confidence,
            "explanation": r.explanation,
            "recommendation": r.recommendation,
            "family_breakdown": r.family_breakdown
        }


def result_to_dict(result: MPRGResult) -> Dict[str, Any]:
    """Convert MPRGResult to JSON-serializable dict."""
    return asdict(result)


# CLI for testing
if __name__ == "__main__":
    import sys
    import json
    
    if len(sys.argv) < 2:
        print("Usage: python -m mprg.pipeline 'Your task here'")
        sys.exit(1)
        
    task = " ".join(sys.argv[1:])
    print(f"\n🔍 Analyzing task: {task}\n")
    
    pipeline = MPRGPipeline()
    result = pipeline.analyze(task)
    
    print(f"\n{result.summary}")
    print(f"\n📊 Full results:")
    print(json.dumps(result_to_dict(result), indent=2, default=str))
