"""
Compound multi-task planning agent powered by Voyage AI.

The agent focuses exclusively on the planning stage: it generates detailed
execution steps plus the intended end result, but never runs the plan.
"""

from __future__ import annotations

import os
import textwrap
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Optional

import requests


VOYAGE_DEFAULT_MODEL = "voyage-code-2"
OPENAI_DEFAULT_MODEL = "gpt-4o-mini"
VOYAGE_CHAT_URL = "https://api.voyageai.com/v1/chat/completions"


@dataclass(frozen=True)
class CompoundTask:
    """Represents a higher-level goal that should be planned but not executed."""

    name: str
    objective: str
    context: str
    deliverable: str


@dataclass(frozen=True)
class PlanResult:
    """Holds the generated plan and the expected end result."""

    task: CompoundTask
    plan_markdown: str


class PlanningClient:
    """Minimal chat wrapper that can target Voyage or OpenAI."""

    def __init__(
        self,
        voyage_key: Optional[str],
        openai_key: Optional[str],
        voyage_model: str = VOYAGE_DEFAULT_MODEL,
        openai_model: str = OPENAI_DEFAULT_MODEL,
    ) -> None:
        if openai_key:
            self.provider = "openai"
            self._openai_key = openai_key
            self._openai_model = openai_model
            self._voyage_key = None
            self._voyage_model = None
        elif voyage_key:
            self.provider = "voyage"
            self._openai_key = None
            self._openai_model = None
            self._voyage_key = voyage_key
            self._voyage_model = voyage_model
        else:
            raise ValueError("Set OPENAI_API_KEY or VOYAGE_API_KEY before running the planner.")

    def generate_plan(self, prompt: str, task: Optional["CompoundTask"] = None) -> str:
        """Call the configured provider with a deterministic planning prompt."""
        payload = self._build_payload(prompt)
        if self.provider == "openai":
            return self._call_openai(payload)
        return self._call_voyage(payload)

    @staticmethod
    def _build_payload(prompt: str) -> dict:
        return {
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are a planning specialist. Your job is to design "
                        "step-by-step execution plans and describe the intended end "
                        "result. DO NOT execute the plan. Always stop after outlining "
                        "the plan and the expected outcome."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.1,
        }

    def _call_voyage(self, payload: dict) -> str:
        assert self._voyage_key and self._voyage_model
        headers = {
            "Authorization": f"Bearer {self._voyage_key}",
            "Content-Type": "application/json",
        }
        body = {"model": self._voyage_model, **payload}
        response = requests.post(VOYAGE_CHAT_URL, headers=headers, json=body, timeout=60)
        response.raise_for_status()
        data = response.json()
        return data["choices"][0]["message"]["content"].strip()

    def _call_openai(self, payload: dict) -> str:
        headers = {
            "Authorization": f"Bearer {self._openai_key}",
            "Content-Type": "application/json",
        }
        body = {"model": self._openai_model or OPENAI_DEFAULT_MODEL, **payload}
        response = requests.post(
            "https://api.openai.com/v1/chat/completions", headers=headers, json=body, timeout=60
        )
        response.raise_for_status()
        data = response.json()
        return data["choices"][0]["message"]["content"].strip()


class CompoundMultiTaskAgent:
    """Agent that batches multiple planning-only requests to the chosen LLM."""

    def __init__(self, voyage: PlanningClient) -> None:
        self.voyage = voyage

    def plan(self, tasks: Iterable[CompoundTask]) -> List[PlanResult]:
        plans: List[PlanResult] = []
        for task in tasks:
            prompt = self._build_prompt(task)
            plan_text = self.voyage.generate_plan(prompt, task)
            plans.append(PlanResult(task=task, plan_markdown=plan_text))
        return plans

    @staticmethod
    def _build_prompt(task: CompoundTask) -> str:
        """Template telling Voyage to output only the plan and expected outcome."""
        return textwrap.dedent(
            f"""
            Goal: {task.objective}
            Task Name: {task.name}
            Context: {task.context}
            Required Deliverable: {task.deliverable}

            Instructions:
            - Produce a numbered execution plan with 4-6 steps.
            - After the steps, add a section titled "EXPECTED RESULT" describing the
              final artifact or state as if it has been achieved.
            - Do not actually execute the plan; only describe it.
            - Keep the response in Markdown.
            """
        ).strip()


PRESET_TASKS: List[CompoundTask] = [
    CompoundTask(
        name="Improve-Security-KB",
        objective="Refresh the security knowledge base with the latest badge policies.",
        context=(
            "The physical security handbook is outdated after the new badge firmware "
            "rollout. We need a plan for updating the documentation and notifying "
            "facility owners."
        ),
        deliverable="Revised handbook + communication brief summarizing changes.",
    ),
    CompoundTask(
        name="Prototype-RAG-Evaluator",
        objective="Design evaluation coverage for the Atlas RAG semantic parser.",
        context=(
            "The parser now supports richer FOL templates but lacks regression tests. "
            "Plan how to create evaluation datasets, scoring harnesses, and reporting."
        ),
        deliverable="Detailed plan for dataset creation, scoring pipeline, and metrics dashboard.",
    ),
    CompoundTask(
        name="Launch-Developer-Enablement",
        objective="Roll out a developer enablement session for Voyage-powered planning.",
        context=(
            "Engineers need guidance on how to use the new planning agent responsibly. "
            "Plan internal training, office hours, and success tracking."
        ),
        deliverable="Launch kit that includes the session agenda, demo scripts, and adoption KPIs.",
    ),
]


def _load_env_keys() -> tuple[Optional[str], Optional[str]]:
    voyage_key = os.getenv("VOYAGE_API_KEY")
    openai_key = os.getenv("OPENAI_API_KEY")
    env_path = Path(__file__).with_name(".env")
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#") or "=" not in stripped:
                continue
            key, value = stripped.split("=", 1)
            normalized = key.strip()
            val = value.strip().strip('"').strip("'")
            if normalized == "VOYAGE_API_KEY" and not voyage_key and val:
                voyage_key = val
                os.environ["VOYAGE_API_KEY"] = val
            if normalized == "OPENAI_API_KEY" and not openai_key and val:
                openai_key = val
                os.environ["OPENAI_API_KEY"] = val
    return voyage_key, openai_key


def run_cli() -> None:
    """Entry point that prints plans for the preset compound tasks."""
    voyage_key, openai_key = _load_env_keys()
    client = PlanningClient(voyage_key=voyage_key, openai_key=openai_key)
    agent = CompoundMultiTaskAgent(client)

    print(f"Using provider: {client.provider}")
    print("Generating plan-only outputs for preset compound tasks...\n")
    for result in agent.plan(PRESET_TASKS):
        print(f"# Task: {result.task.name}")
        print(result.plan_markdown)
        print("\n---\n")


if __name__ == "__main__":
    run_cli()
