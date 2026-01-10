"""Multi-agent runner that enforces ReasoningSummary JSON output."""

from __future__ import annotations

import json
import os
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import requests

from .models import ReasoningSummary, validate_summary


DEFAULT_AGENT_ROLES = [
    "Systematic Planner",
    "Risk Analyst",
    "Pragmatic Engineer",
    "Skeptical Reviewer",
    "Creative Strategist",
]


@dataclass
class AgentRun:
    """Result of a single agent run (valid or invalid)."""

    run_id: str
    task_id: str
    agent_role: str
    raw_response: str
    summary: Optional[ReasoningSummary]
    valid: bool
    error: Optional[str]
    elapsed_ms: int
    attempt_count: int


class MultiAgentRunner:
    """Runs multiple LLM agents in parallel with strict JSON enforcement."""

    def __init__(
        self,
        openai_key: Optional[str] = None,
        model: str = "gpt-4o-mini",
        num_agents: int = 4,
        temperature: float = 0.6,
        timeout_s: int = 60,
    ) -> None:
        self.openai_key = openai_key or os.getenv("OPENAI_API_KEY")
        if not self.openai_key:
            raise ValueError("Set OPENAI_API_KEY to run agents.")
        self.model = model
        self.num_agents = max(3, min(num_agents, 5))
        self.temperature = temperature
        self.timeout_s = timeout_s

    def run(self, task_id: str, task: str) -> List[AgentRun]:
        roles = DEFAULT_AGENT_ROLES[: self.num_agents]
        with ThreadPoolExecutor(max_workers=len(roles)) as executor:
            futures = [
                executor.submit(self._run_single_agent, task_id, task, role)
                for role in roles
            ]
            return [f.result() for f in futures]

    def _run_single_agent(self, task_id: str, task: str, role: str) -> AgentRun:
        start = time.time()
        run_id = f"run_{uuid.uuid4().hex[:12]}"

        summary, raw_response, error, attempts = self._generate_summary(
            task_id, task, role
        )

        elapsed_ms = int((time.time() - start) * 1000)
        return AgentRun(
            run_id=run_id,
            task_id=task_id,
            agent_role=role,
            raw_response=raw_response,
            summary=summary,
            valid=summary is not None,
            error=error,
            elapsed_ms=elapsed_ms,
            attempt_count=attempts,
        )

    def _generate_summary(
        self, task_id: str, task: str, role: str
    ) -> Tuple[Optional[ReasoningSummary], str, Optional[str], int]:
        """Generate a ReasoningSummary with one retry on invalid JSON."""
        prompt = self._build_prompt(task_id, task, role, strict=False)
        raw = self._call_openai(prompt)
        summary, error = self._parse_and_validate(raw, task_id)
        if summary:
            return summary, raw, None, 1

        strict_prompt = self._build_prompt(task_id, task, role, strict=True)
        raw_retry = self._call_openai(strict_prompt)
        summary_retry, error_retry = self._parse_and_validate(raw_retry, task_id)
        if summary_retry:
            return summary_retry, raw_retry, None, 2
        return None, raw_retry, error_retry or error, 2

    def _call_openai(self, prompt: str) -> str:
        headers = {
            "Authorization": f"Bearer {self.openai_key}",
            "Content-Type": "application/json",
        }
        body = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": self.temperature,
        }
        response = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers=headers,
            json=body,
            timeout=self.timeout_s,
        )
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"].strip()

    def _parse_and_validate(
        self, response: str, task_id: str
    ) -> Tuple[Optional[ReasoningSummary], Optional[str]]:
        data = self._extract_json(response)
        if data is None:
            return None, "Response was not valid JSON."
        is_valid, error, summary = validate_summary(data, task_id)
        if not is_valid:
            return None, error
        return summary, None

    def _extract_json(self, response: str) -> Optional[Dict]:
        try:
            return json.loads(response)
        except json.JSONDecodeError:
            start = response.find("{")
            end = response.rfind("}")
            if start == -1 or end == -1 or end <= start:
                return None
            try:
                return json.loads(response[start : end + 1])
            except json.JSONDecodeError:
                return None

    def _build_prompt(self, task_id: str, task: str, role: str, strict: bool) -> str:
        schema = {
            "agent_role": role,
            "task_id": task_id,
            "final_answer": "string",
            "plan_steps": ["string"],
            "assumptions": ["string"],
            "tools": ["string"],
            "risks": ["string"],
            "fallbacks": ["string"],
        }
        rules = (
            "Return ONLY valid JSON that matches the schema. No markdown."
            if strict
            else "Return JSON only. Do not include chain-of-thought."
        )
        return (
            f"You are a {role}. Analyze the task and respond as JSON.\n"
            f"Task ID: {task_id}\n"
            f"Task: {task}\n"
            f"{rules}\n"
            f"Schema example (types only): {json.dumps(schema)}"
        )
