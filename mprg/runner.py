"""Multi-agent runner for parallel reasoning capture.

Runs multiple agents on the same task with varied prompts
to capture diverse reasoning approaches.
"""

from __future__ import annotations

import asyncio
import os
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import List, Optional

# Import existing planner infrastructure
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from planner import PlanningClient


@dataclass
class AgentResponse:
    """Response from a single agent run."""
    agent_id: str
    prompt_variant: str
    plan: str
    explanation: str
    raw_response: str
    elapsed_ms: int


# Prompt variants to get diverse reasoning
PROMPT_VARIANTS = [
    {
        "id": "systematic",
        "system": (
            "You are a systematic planning specialist. Break down tasks into "
            "clear, sequential steps. Focus on dependencies and prerequisites."
        ),
        "suffix": "Think step-by-step and explain your reasoning."
    },
    {
        "id": "pragmatic", 
        "system": (
            "You are a pragmatic solutions architect. Focus on the fastest path "
            "to results. Prioritize efficiency over completeness."
        ),
        "suffix": "Explain why this is the most efficient approach."
    },
    {
        "id": "risk_aware",
        "system": (
            "You are a risk-aware analyst. Identify potential failure points "
            "and build in safeguards. Consider edge cases."
        ),
        "suffix": "Explain the risks you're mitigating and why."
    },
    {
        "id": "innovative",
        "system": (
            "You are an innovative problem solver. Think of unconventional "
            "approaches that might be more elegant or effective."
        ),
        "suffix": "Explain what makes this approach unique or better."
    },
    {
        "id": "conservative",
        "system": (
            "You are a conservative planner. Stick to proven patterns and "
            "well-established practices. Minimize novelty."
        ),
        "suffix": "Explain why this tried-and-true approach is reliable."
    },
]


class MultiAgentRunner:
    """Runs multiple agents in parallel on the same task.
    
    Each agent uses a different prompt variant to encourage
    diverse reasoning approaches.
    """
    
    def __init__(
        self,
        voyage_key: Optional[str] = None,
        openai_key: Optional[str] = None,
        anthropic_key: Optional[str] = None,
        num_agents: int = 5
    ):
        """Initialize the multi-agent runner.
        
        Args:
            voyage_key: Voyage AI API key
            openai_key: OpenAI API key (fallback)
            num_agents: Number of parallel agents (default: 5)
        """
        self.voyage_key = voyage_key or os.getenv("VOYAGE_API_KEY")
        self.openai_key = openai_key or os.getenv("OPENAI_API_KEY")
        self.anthropic_key = anthropic_key or os.getenv("ANTHROPIC_API_KEY")
        self.num_agents = min(num_agents, len(PROMPT_VARIANTS))
            
    def run(self, task: str, num_agents: Optional[int] = None) -> List[AgentResponse]:
        """Run multiple agents on the same task.
        
        Args:
            task: The task prompt to analyze
            
        Returns:
            List of AgentResponse objects with plans and explanations
        """
        count = num_agents or self.num_agents
        count = max(1, min(count, len(PROMPT_VARIANTS)))
        variants = PROMPT_VARIANTS[:count]
        
        # Run agents in parallel using ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=count) as executor:
            futures = [
                executor.submit(self._run_single_agent, task, variant)
                for variant in variants
            ]
            responses = [f.result() for f in futures]
            
        return responses
    
    def _run_single_agent(self, task: str, variant: dict) -> AgentResponse:
        """Run a single agent with a specific prompt variant."""
        start_time = time.time()
        agent_id = f"agent_{variant['id']}_{uuid.uuid4().hex[:8]}"
        
        # Build the prompt
        full_prompt = f"{task}\n\n{variant['suffix']}"
        
        try:
            # Use existing PlanningClient
            client = PlanningClient(
                voyage_key=self.voyage_key,
                openai_key=self.openai_key,
                anthropic_key=self.anthropic_key
            )
            
            # Override system prompt for this variant
            response = self._call_with_variant(client, full_prompt, variant)
            
            elapsed_ms = int((time.time() - start_time) * 1000)
            
            # Parse response into plan and explanation
            plan, explanation = self._parse_response(response)
            
            return AgentResponse(
                agent_id=agent_id,
                prompt_variant=variant['id'],
                plan=plan,
                explanation=explanation,
                raw_response=response,
                elapsed_ms=elapsed_ms
            )
            
        except Exception as e:
            elapsed_ms = int((time.time() - start_time) * 1000)
            return AgentResponse(
                agent_id=agent_id,
                prompt_variant=variant['id'],
                plan=f"Error: {str(e)}",
                explanation=f"Agent failed: {str(e)}",
                raw_response=str(e),
                elapsed_ms=elapsed_ms
            )
    
    def _call_with_variant(
        self, 
        client: PlanningClient, 
        prompt: str, 
        variant: dict
    ) -> str:
        """Call LLM with custom system prompt variant."""
        import requests
        
        if client.provider == "openai":
            headers = {
                "Authorization": f"Bearer {self.openai_key}",
                "Content-Type": "application/json",
            }
            body = {
                "model": "gpt-4o-mini",
                "messages": [
                    {"role": "system", "content": variant["system"]},
                    {"role": "user", "content": prompt},
                ],
                "temperature": 0.7,  # Higher temp for diversity
            }
            response = requests.post(
                "https://api.openai.com/v1/chat/completions",
                headers=headers,
                json=body,
                timeout=60
            )
            response.raise_for_status()
            return response.json()["choices"][0]["message"]["content"]
            
        else:
            # Voyage AI path
            # Note: Voyage may need different API structure
            return client.generate_plan(prompt)
    
    def _parse_response(self, response: str) -> tuple[str, str]:
        """Parse response into plan and explanation sections."""
        # Try to find explicit sections
        response_lower = response.lower()
        
        # Look for plan markers
        plan_markers = ["## plan", "### plan", "plan:", "steps:"]
        explain_markers = [
            "## explanation", "### explanation", "explanation:",
            "## reasoning", "### reasoning", "reasoning:",
            "because", "the reason", "this approach"
        ]
        
        plan_start = -1
        explain_start = -1
        
        for marker in plan_markers:
            idx = response_lower.find(marker)
            if idx != -1 and (plan_start == -1 or idx < plan_start):
                plan_start = idx
                
        for marker in explain_markers:
            idx = response_lower.find(marker)
            if idx != -1 and (explain_start == -1 or idx < explain_start):
                explain_start = idx
        
        # If we found sections, split them
        if plan_start != -1 and explain_start != -1:
            if plan_start < explain_start:
                plan = response[plan_start:explain_start].strip()
                explanation = response[explain_start:].strip()
            else:
                explanation = response[explain_start:plan_start].strip()
                plan = response[plan_start:].strip()
        else:
            # No clear sections - use heuristics
            lines = response.strip().split('\n')
            mid = len(lines) // 2
            plan = '\n'.join(lines[:mid])
            explanation = '\n'.join(lines[mid:])
            
        return plan.strip(), explanation.strip()


# CLI for testing
if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python -m mprg.runner 'Your task here'")
        sys.exit(1)
        
    task = " ".join(sys.argv[1:])
    print(f"Running {len(PROMPT_VARIANTS)} agents on task: {task}\n")
    
    runner = MultiAgentRunner()
    responses = runner.run(task)
    
    for i, resp in enumerate(responses, 1):
        print(f"\n{'='*60}")
        print(f"Agent {i} ({resp.prompt_variant}) - {resp.elapsed_ms}ms")
        print(f"{'='*60}")
        print(f"\nPLAN:\n{resp.plan[:500]}...")
        print(f"\nEXPLANATION:\n{resp.explanation[:500]}...")
