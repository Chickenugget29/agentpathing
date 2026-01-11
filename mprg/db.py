"""MongoDB Atlas integration for the OmniPath reasoning ledger.

This module provides durable storage for all reasoning traces,
enabling crash recovery, historical analysis, and demo replay.
MongoDB Atlas is essential for:
1. Storing raw agent outputs with full reasoning traces
2. Persisting parsed FOL translations
3. Tracking reasoning families over time
4. Recording robustness scores and gate decisions
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, asdict

from pymongo import MongoClient
from pymongo.collection import Collection
from bson import ObjectId


@dataclass
class AgentOutput:
    """Raw output from a single agent run."""
    task_id: str
    agent_id: str
    prompt_variant: str
    raw_response: str
    plan: str
    explanation: str
    created_at: datetime = None
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now(timezone.utc)


@dataclass
class ReasoningTrace:
    """Detailed trace of reasoning analysis - THE KEY VISIBILITY FEATURE.
    
    This captures every step of reasoning analysis so judges can see
    exactly how the system detected robust vs fragile reasoning.
    """
    agent_output_id: str
    
    # Layer 1: Symbolic Logic (FOL)
    fol_translation: str              # e.g., "exists d (Document(d) & Policy(d))"
    fol_predicates: List[str]         # ["Document(d)", "Policy(d)", "Topic(d, X)"]
    fol_variables: List[str]          # ["d", "p"]
    fol_structure_hash: str           # Hash for quick structural comparison
    
    # Layer 2: Semantic Embeddings
    original_text: str
    embedding_vector: List[float]
    key_concepts: List[str]           # Extracted key ideas
    
    # Extracted reasoning components
    assumptions: List[str]
    steps: List[str]
    dependencies: List[str]
    key_idea: str
    
    created_at: datetime = None
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now(timezone.utc)


@dataclass
class ReasoningFamily:
    """A group of reasoning traces that represent the same underlying idea."""
    task_id: str
    family_id: str
    member_ids: List[str]             # AgentOutput IDs in this family
    
    # Why these are grouped together
    shared_fol_structure: str         # Common FOL pattern
    shared_assumptions: List[str]
    representative_key_idea: str
    
    # Grouping confidence
    fol_similarity: float             # 0-1 structural match
    semantic_similarity: float        # 0-1 embedding similarity
    combined_confidence: float        # Overall grouping confidence
    
    created_at: datetime = None


@dataclass 
class RobustnessResult:
    """Final analysis result with full transparency."""
    task_id: str
    task_prompt: str
    
    # Agent analysis
    total_agents: int
    agent_outputs: List[str]          # IDs for reference
    
    # Family analysis
    distinct_families: int
    family_breakdown: List[Dict]      # Detailed family info
    
    # Final verdict
    robustness_score: str             # FRAGILE | MODERATE | ROBUST
    confidence: float
    
    # Gate decision
    gate_decision: str                # BLOCK | WARN | ALLOW
    gate_reason: str
    
    # Timestamps for replay
    created_at: datetime = None
    processing_time_ms: int = 0


class ReasoningLedger:
    """MongoDB Atlas-backed reasoning storage with full trace visibility.
    
    This is the core infrastructure that makes the system valuable:
    - Durable storage for reasoning traces
    - Historical analysis of fragile patterns
    - Crash recovery and replay
    - Demo-friendly querying
    """
    
    def __init__(self, connection_uri: Optional[str] = None):
        """Initialize MongoDB connection.
        
        Args:
            connection_uri: MongoDB Atlas URI. Falls back to env var.
        """
        uri = connection_uri or os.getenv("MONGODB_URI")
        if not uri:
            # For local dev, use local MongoDB
            uri = "mongodb://localhost:27017"
            
        self.client = MongoClient(uri)
        self.db = self.client.mprg
        
        # Collections
        self.agent_outputs: Collection = self.db.agent_outputs
        self.reasoning_traces: Collection = self.db.reasoning_traces
        self.reasoning_families: Collection = self.db.reasoning_families
        self.robustness_results: Collection = self.db.robustness_results
        
        # Create indexes for efficient queries
        self._ensure_indexes()
    
    def _ensure_indexes(self):
        """Create MongoDB indexes for performance."""
        self.agent_outputs.create_index("task_id")
        self.agent_outputs.create_index("created_at")
        self.reasoning_traces.create_index("agent_output_id")
        self.reasoning_traces.create_index("fol_structure_hash")
        self.reasoning_families.create_index("task_id")
        self.robustness_results.create_index("task_id")
        self.robustness_results.create_index("created_at")
    
    # =========================================================================
    # STORE OPERATIONS
    # =========================================================================
    
    def store_agent_output(self, output: AgentOutput) -> str:
        """Store raw agent output, return ID."""
        doc = asdict(output)
        result = self.agent_outputs.insert_one(doc)
        return str(result.inserted_id)
    
    def store_reasoning_trace(self, trace: ReasoningTrace) -> str:
        """Store detailed reasoning trace, return ID."""
        doc = asdict(trace)
        result = self.reasoning_traces.insert_one(doc)
        return str(result.inserted_id)
    
    def store_family(self, family: ReasoningFamily) -> str:
        """Store reasoning family, return ID."""
        doc = asdict(family)
        if family.created_at is None:
            doc["created_at"] = datetime.now(timezone.utc)
        result = self.reasoning_families.insert_one(doc)
        return str(result.inserted_id)
    
    def store_result(self, result: RobustnessResult) -> str:
        """Store final robustness result, return ID."""
        doc = asdict(result)
        if result.created_at is None:
            doc["created_at"] = datetime.now(timezone.utc)
        res = self.robustness_results.insert_one(doc)
        return str(res.inserted_id)
    
    # =========================================================================
    # QUERY OPERATIONS - For demo and debugging
    # =========================================================================
    
    def get_task_analysis(self, task_id: str) -> Dict[str, Any]:
        """Get complete analysis for a task - perfect for demo visualization."""
        result = self.robustness_results.find_one({"task_id": task_id})
        if not result:
            return None
            
        # Get all agent outputs
        outputs = list(self.agent_outputs.find({"task_id": task_id}))
        
        # Get all reasoning traces
        output_ids = [str(o["_id"]) for o in outputs]
        traces = list(self.reasoning_traces.find({
            "agent_output_id": {"$in": output_ids}
        }))
        
        # Get families
        families = list(self.reasoning_families.find({"task_id": task_id}))
        
        return {
            "result": _serialize_doc(result),
            "agent_outputs": [_serialize_doc(o) for o in outputs],
            "reasoning_traces": [_serialize_doc(t) for t in traces],
            "families": [_serialize_doc(f) for f in families],
        }
    
    def get_recent_analyses(self, limit: int = 10) -> List[Dict]:
        """Get recent analyses for dashboard."""
        results = self.robustness_results.find().sort(
            "created_at", -1
        ).limit(limit)
        return [_serialize_doc(r) for r in results]
    
    def get_fragile_patterns(self) -> List[Dict]:
        """Get historical fragile patterns - shows system learning over time."""
        pipeline = [
            {"$match": {"robustness_score": "FRAGILE"}},
            {"$group": {
                "_id": "$task_prompt",
                "count": {"$sum": 1},
                "last_seen": {"$max": "$created_at"}
            }},
            {"$sort": {"count": -1}},
            {"$limit": 20}
        ]
        return list(self.robustness_results.aggregate(pipeline))
    
    # =========================================================================
    # RECOVERY OPERATIONS - Crash recovery for long-running agents
    # =========================================================================
    
    def recover_task_state(self, task_id: str) -> Optional[Dict]:
        """Recover task state after crash - key for Statement One."""
        analysis = self.get_task_analysis(task_id)
        if analysis:
            return {
                "recovered": True,
                "task_id": task_id,
                "state": analysis,
                "message": "Recovered reasoning state from MongoDB"
            }
        return None


def _serialize_doc(doc: Dict) -> Dict:
    """Convert MongoDB doc to JSON-serializable dict."""
    if doc is None:
        return None
    result = {}
    for k, v in doc.items():
        if isinstance(v, ObjectId):
            result[k] = str(v)
        elif isinstance(v, datetime):
            result[k] = v.isoformat()
        else:
            result[k] = v
    return result
