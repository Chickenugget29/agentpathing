"""Dual-layer reasoning analyzer.

Combines symbolic FOL analysis (Layer 1) with semantic embeddings (Layer 2)
to provide full visibility into agent reasoning structure.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from typing import List, Optional, Tuple

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from translator import translate as fol_translate
from .runner import AgentResponse
from .vectors import VectorStore, compute_text_hash


@dataclass
class AnalyzedReasoning:
    """Complete analysis of a single agent's reasoning.
    
    This provides FULL VISIBILITY into how reasoning was analyzed,
    which is key for the demo.
    """
    agent_id: str
    
    # Original content
    original_explanation: str
    original_plan: str
    
    # Layer 1: Symbolic Logic (FOL)
    fol_translation: str              # Full FOL string
    fol_predicates: List[str]         # Extracted predicates
    fol_variables: List[str]          # Extracted variables
    fol_structure_hash: str           # Hash for quick comparison
    
    # Layer 2: Semantic
    key_concepts: List[str]           # Extracted concepts
    
    # Extracted reasoning structure
    assumptions: List[str]
    steps: List[str]
    dependencies: List[str]
    key_idea: str


class ReasoningAnalyzer:
    """Analyzes agent reasoning using dual-layer approach.
    
    Layer 1: Symbolic FOL translation (uses translator.py)
    Layer 2: Semantic embedding (uses ChromaDB)
    """
    
    def __init__(self, vector_store: Optional[VectorStore] = None):
        """Initialize analyzer.
        
        Args:
            vector_store: Optional VectorStore instance
        """
        self.vectors = vector_store or VectorStore()
        
    def analyze(self, response: AgentResponse) -> AnalyzedReasoning:
        """Analyze a single agent response.
        
        Args:
            response: AgentResponse from multi-agent runner
            
        Returns:
            AnalyzedReasoning with full trace
        """
        explanation = response.explanation
        plan = response.plan
        
        # Layer 1: FOL Translation (plan + explanation to capture full chain)
        fol_result = self._translate_to_fol(f"{plan}\n\n{explanation}")
        predicates = self._extract_predicates(fol_result)
        variables = self._extract_variables(fol_result)
        structure_hash = self._compute_structure_hash(fol_result)
        
        # Extract reasoning structure
        assumptions = self._extract_assumptions(explanation)
        steps = self._extract_steps(plan)
        dependencies = self._extract_dependencies(explanation)
        key_idea = self._extract_key_idea(explanation)
        
        # Layer 2: Key concepts for semantic comparison
        key_concepts = self._extract_key_concepts(explanation)
        
        return AnalyzedReasoning(
            agent_id=response.agent_id,
            original_explanation=explanation,
            original_plan=plan,
            fol_translation=fol_result,
            fol_predicates=predicates,
            fol_variables=variables,
            fol_structure_hash=structure_hash,
            key_concepts=key_concepts,
            assumptions=assumptions,
            steps=steps,
            dependencies=dependencies,
            key_idea=key_idea
        )
    
    def analyze_batch(
        self, 
        responses: List[AgentResponse],
        task_id: str
    ) -> List[AnalyzedReasoning]:
        """Analyze multiple agent responses.
        
        Also stores embeddings in vector store for similarity computation.
        """
        results = []
        
        for response in responses:
            analyzed = self.analyze(response)
            results.append(analyzed)
            
            # Store in vector DB for similarity
            self.vectors.add_reasoning(
                id=response.agent_id,
                text=analyzed.fol_translation,
                metadata={
                    "task_id": task_id,
                    "agent_id": response.agent_id,
                    "prompt_variant": response.prompt_variant,
                    "key_idea": analyzed.key_idea
                }
            )
            
        return results
    
    # =========================================================================
    # Layer 1: Symbolic FOL Analysis
    # =========================================================================
    
    def _translate_to_fol(self, text: str) -> str:
        """Create structural FOL representation of reasoning.
        
        Instead of using the generic chain translator, we extract:
        - Actions (verbs)
        - Objects (nouns)  
        - Conditions (if/when clauses)
        - Sequence (before/after/then)
        
        This creates FOL that can be meaningfully compared.
        """
        predicates = []
        
        # Extract action-object pairs
        actions = self._extract_actions(text)
        for action, obj in actions:
            predicates.append(f"Action({action}, {obj})")
        
        # Extract conditions
        conditions = self._extract_conditions(text)
        for cond, result in conditions:
            predicates.append(f"Implies({cond}, {result})")
        
        # Extract sequence relationships
        sequences = self._extract_sequences(text)
        for first, second in sequences:
            predicates.append(f"Before({first}, {second})")
        
        # Extract method/approach
        methods = self._extract_methods(text)
        for method in methods:
            predicates.append(f"Method({method})")
        
        if predicates:
            return " & ".join(predicates)
        
        # Fallback
        return self._create_fallback_fol(text)
    
    def _extract_actions(self, text: str) -> List[Tuple[str, str]]:
        """Extract action-object pairs from text."""
        patterns = [
            r'\b(fetch|get|retrieve|load|read)\s+(?:the\s+)?(\w+)',
            r'\b(store|save|write|persist|cache)\s+(?:the\s+)?(\w+)',
            r'\b(transform|convert|process|parse|format)\s+(?:the\s+)?(\w+)',
            r'\b(validate|verify|check|test|ensure)\s+(?:the\s+)?(\w+)',
            r'\b(send|transmit|post|push)\s+(?:the\s+)?(\w+)',
            r'\b(create|generate|build|construct)\s+(?:the\s+)?(\w+)',
            r'\b(delete|remove|clear|purge)\s+(?:the\s+)?(\w+)',
            r'\b(update|modify|change|edit)\s+(?:the\s+)?(\w+)',
            r'\b(connect|link|join|merge)\s+(?:the\s+)?(\w+)',
            r'\b(authenticate|authorize|login)\s+(?:to\s+)?(\w+)',
        ]
        
        actions = []
        text_lower = text.lower()
        for pattern in patterns:
            matches = re.findall(pattern, text_lower)
            for verb, noun in matches:
                actions.append((verb.capitalize(), noun.capitalize()))
        
        return actions[:5]
    
    def _extract_conditions(self, text: str) -> List[Tuple[str, str]]:
        """Extract if-then conditions."""
        patterns = [
            r'if\s+([^,]+),\s*(?:then\s+)?([^.]+)',
            r'when\s+([^,]+),\s*([^.]+)',
            r'once\s+([^,]+),\s*([^.]+)',
        ]
        
        conditions = []
        text_lower = text.lower()
        for pattern in patterns:
            matches = re.findall(pattern, text_lower)
            for cond, result in matches:
                cond_const = self._to_constant(cond)
                result_const = self._to_constant(result)
                conditions.append((cond_const, result_const))
        
        return conditions[:3]
    
    def _extract_sequences(self, text: str) -> List[Tuple[str, str]]:
        """Extract sequential relationships."""
        patterns = [
            r'first\s+([^,]+),?\s*then\s+([^.]+)',
            r'after\s+([^,]+),?\s*([^.]+)',
            r'before\s+([^,]+),?\s*([^.]+)',
            r'([^.]+)\s+followed by\s+([^.]+)',
        ]
        
        sequences = []
        text_lower = text.lower()
        for pattern in patterns:
            matches = re.findall(pattern, text_lower)
            for first, second in matches:
                first_const = self._to_constant(first)
                second_const = self._to_constant(second)
                sequences.append((first_const, second_const))
        
        return sequences[:3]
    
    def _extract_methods(self, text: str) -> List[str]:
        """Extract methodology/approach mentions."""
        patterns = [
            r'using\s+(?:a\s+)?(\w+(?:\s+\w+)?)\s+(?:approach|method|pattern|strategy)',
            r'(?:approach|method|pattern|strategy)\s+(?:is|:)\s+(\w+(?:\s+\w+)?)',
            r'via\s+(\w+(?:\s+\w+)?)',
            r'through\s+(\w+(?:\s+\w+)?)',
            r'\b(batch|stream|parallel|sequential|async|sync)\s+processing',
            r'\b(polling|webhook|push|pull)\s+(?:model|pattern)?',
        ]
        
        methods = []
        text_lower = text.lower()
        for pattern in patterns:
            matches = re.findall(pattern, text_lower)
            for match in matches:
                methods.append(self._to_constant(match))
        
        return methods[:3]
    
    def _to_constant(self, text: str) -> str:
        """Convert text to FOL constant."""
        words = re.findall(r'[a-zA-Z]+', text)
        return ''.join(w.capitalize() for w in words[:3]) or 'Unknown'
    
    def _create_fallback_fol(self, text: str) -> str:
        """Create fallback FOL for text that doesn't match rules."""
        # Extract key nouns as topics
        words = re.findall(r'\b[A-Z][a-z]+\b', text)
        if not words:
            words = re.findall(r'\b\w{4,}\b', text)[:3]
            
        topics = [w.capitalize() for w in words[:3]]
        
        if topics:
            predicates = [f"Topic({t})" for t in topics]
            return " & ".join(predicates)
        
        return "GeneralReasoning()"
    
    def _extract_predicates(self, fol: str) -> List[str]:
        """Extract predicates from FOL string."""
        # Match patterns like Name(args)
        predicates = re.findall(r'([A-Z][a-zA-Z]*\([^)]+\))', fol)
        return list(set(predicates))
    
    def _extract_variables(self, fol: str) -> List[str]:
        """Extract variables from FOL string."""
        # Look for single letters used as variables
        # Usually after quantifiers or as arguments
        vars_after_quantifier = re.findall(r'(?:exists|forall)\s+(\w+)', fol)
        vars_in_predicates = re.findall(r'\(([a-z][a-z0-9]*)', fol)
        
        all_vars = set(vars_after_quantifier + vars_in_predicates)
        # Filter out likely constants (capitalized)
        return [v for v in all_vars if v[0].islower()]
    
    def _compute_structure_hash(self, fol: str) -> str:
        """Compute hash of FOL structure for quick comparison.
        
        Normalizes variable names to detect structural equivalence.
        """
        # Normalize: replace specific variable names with placeholders
        normalized = re.sub(r'\b([a-z])\d*\b', 'VAR', fol)
        # Remove specific constant values
        normalized = re.sub(r',\s*[A-Z][a-z]+\)', ', CONST)', normalized)
        
        return hashlib.sha256(normalized.encode()).hexdigest()[:12]
    
    # =========================================================================
    # Reasoning Structure Extraction
    # =========================================================================
    
    def _extract_assumptions(self, text: str) -> List[str]:
        """Extract assumptions from reasoning text."""
        assumptions = []
        
        # Look for assumption indicators
        patterns = [
            r'assum[a-z]+\s+(?:that\s+)?([^.]+)',
            r'given\s+(?:that\s+)?([^.]+)',
            r'if\s+([^,]+),',
            r'presum[a-z]+\s+(?:that\s+)?([^.]+)',
            r'expect[a-z]*\s+(?:that\s+)?([^.]+)',
        ]
        
        text_lower = text.lower()
        for pattern in patterns:
            matches = re.findall(pattern, text_lower)
            assumptions.extend(matches)
            
        # Deduplicate and clean
        return list(set(a.strip() for a in assumptions if len(a.strip()) > 10))[:5]
    
    def _extract_steps(self, plan: str) -> List[str]:
        """Extract steps from plan."""
        steps = []
        
        # Look for numbered or bulleted items
        lines = plan.split('\n')
        for line in lines:
            line = line.strip()
            # Match: 1. Step, - Step, * Step, Step 1:
            if re.match(r'^[\d]+[.)\s]|^[-*•]\s|^Step\s+\d', line, re.I):
                # Clean the line
                step = re.sub(r'^[\d]+[.)\s]|^[-*•]\s|^Step\s+\d+[.:]\s*', '', line)
                if step and len(step) > 5:
                    steps.append(step.strip())
                    
        return steps[:10]  # Max 10 steps
    
    def _extract_dependencies(self, text: str) -> List[str]:
        """Extract dependencies from reasoning."""
        dependencies = []
        
        patterns = [
            r'depends?\s+on\s+([^.]+)',
            r'requires?\s+([^.]+)',
            r'needs?\s+([^.]+)',
            r'before\s+([^,]+)',
            r'after\s+([^,]+)',
        ]
        
        text_lower = text.lower()
        for pattern in patterns:
            matches = re.findall(pattern, text_lower)
            dependencies.extend(matches)
            
        return list(set(d.strip() for d in dependencies if len(d.strip()) > 5))[:5]
    
    def _extract_key_idea(self, text: str) -> str:
        """Extract the core key idea from reasoning.
        
        This is what makes the reasoning distinct.
        """
        # Look for explicit key idea markers
        markers = [
            r'the (?:key|main|core) (?:idea|concept|approach) is ([^.]+)',
            r'fundamentally,?\s*([^.]+)',
            r'essentially,?\s*([^.]+)',
            r'the approach is to ([^.]+)',
            r'this works because ([^.]+)',
        ]
        
        text_lower = text.lower()
        for pattern in markers:
            match = re.search(pattern, text_lower)
            if match:
                return match.group(1).strip()
                
        # Fallback: use first sentence as key idea
        sentences = re.split(r'[.!?]+', text)
        if sentences:
            return sentences[0].strip()[:100]
            
        return "general approach"
    
    def _extract_key_concepts(self, text: str) -> List[str]:
        """Extract key concepts for semantic grouping."""
        # Extract capitalized phrases (likely important concepts)
        concepts = re.findall(r'\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\b', text)
        
        # Also extract quoted phrases
        quoted = re.findall(r'"([^"]+)"', text)
        quoted.extend(re.findall(r"'([^']+)'", text))
        
        all_concepts = concepts + quoted
        
        # Deduplicate and filter
        seen = set()
        result = []
        for c in all_concepts:
            c_lower = c.lower()
            if c_lower not in seen and len(c) > 3:
                seen.add(c_lower)
                result.append(c)
                
        return result[:10]
