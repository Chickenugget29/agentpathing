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
ANTHROPIC_DEFAULT_MODEL = "claude-3-5-sonnet-20240620"
VOYAGE_CHAT_URL = "https://api.voyageai.com/v1/chat/completions"
ANTHROPIC_CHAT_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_VERSION = "2023-06-01"


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
        anthropic_key: Optional[str] = None,
        voyage_model: str = VOYAGE_DEFAULT_MODEL,
        openai_model: str = OPENAI_DEFAULT_MODEL,
        anthropic_model: str = ANTHROPIC_DEFAULT_MODEL,
        provider: Optional[str] = None,
    ) -> None:
        requested_provider = (
            provider or os.getenv("PLANNER_PROVIDER") or os.getenv("LLM_PROVIDER") or ""
        ).strip().lower()
        if not requested_provider:
            if openai_key:
                requested_provider = "openai"
            elif anthropic_key:
                requested_provider = "anthropic"
            elif voyage_key:
                requested_provider = "voyage"

        if requested_provider == "openai":
            if not openai_key:
                raise ValueError("Set OPENAI_API_KEY to use the OpenAI planner provider.")
            self.provider = "openai"
            self._openai_key = openai_key
            self._openai_model = openai_model
            self._anthropic_key = None
            self._anthropic_model = None
            self._voyage_key = None
            self._voyage_model = None
        elif requested_provider == "anthropic":
            if not anthropic_key:
                raise ValueError("Set ANTHROPIC_API_KEY to use the Anthropic planner provider.")
            self.provider = "anthropic"
            self._anthropic_key = anthropic_key
            self._anthropic_model = anthropic_model
            self._openai_key = None
            self._openai_model = None
            self._voyage_key = None
            self._voyage_model = None
        elif requested_provider == "voyage":
            raise ValueError(
                "Voyage AI does not provide chat completions; set PLANNER_PROVIDER=openai "
                "or anthropic and provide the corresponding API key."
            )
        else:
            raise ValueError(
                "Specify PLANNER_PROVIDER as 'openai' or 'anthropic' and provide the matching API key."
            )

    def generate_plan(self, prompt: str, task: Optional["CompoundTask"] = None) -> str:
        """Call the configured provider with a deterministic planning prompt."""
        payload = self._build_payload(prompt)
        if self.provider == "openai":
            return self._call_openai(payload)
        if self.provider == "anthropic":
            return self._call_anthropic(payload)
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
        raise RuntimeError(
            "Voyage AI chat completions are not supported. Please set OPENAI_API_KEY or "
            "ANTHROPIC_API_KEY and select the appropriate provider."
        )

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

    def _call_anthropic(self, payload: dict) -> str:
        assert self._anthropic_key and self._anthropic_model
        system_prompt = ""
        user_chunks: List[str] = []
        for msg in payload.get("messages", []):
            role = msg.get("role")
            content = msg.get("content", "")
            if role == "system":
                system_prompt = content
            else:
                user_chunks.append(content)
        body = {
            "model": self._anthropic_model,
            "max_tokens": 800,
            "temperature": payload.get("temperature", 0.1),
            "messages": [{"role": "user", "content": "\n\n".join(user_chunks)}],
        }
        if system_prompt:
            body["system"] = system_prompt
        headers = {
            "x-api-key": self._anthropic_key,
            "anthropic-version": ANTHROPIC_VERSION,
            "content-type": "application/json",
        }
        response = requests.post(ANTHROPIC_CHAT_URL, headers=headers, json=body, timeout=60)
        response.raise_for_status()
        data = response.json()
        content = data.get("content", [])
        if content and isinstance(content, list):
            first = content[0]
            text = first.get("text") if isinstance(first, dict) else first
            if text:
                return text.strip()
        return data.get("output", "").strip()


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


def _load_env_keys() -> tuple[Optional[str], Optional[str], Optional[str]]:
    voyage_key = os.getenv("VOYAGE_API_KEY")
    openai_key = os.getenv("OPENAI_API_KEY")
    anthropic_key = os.getenv("ANTHROPIC_API_KEY")
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
            if normalized == "ANTHROPIC_API_KEY" and not anthropic_key and val:
                anthropic_key = val
                os.environ["ANTHROPIC_API_KEY"] = val
    return voyage_key, openai_key, anthropic_key


def run_cli() -> None:
    """Entry point that prints plans for the preset compound tasks."""
    voyage_key, openai_key, anthropic_key = _load_env_keys()
    client = PlanningClient(
        voyage_key=voyage_key,
        openai_key=openai_key,
        anthropic_key=anthropic_key,
    )
    agent = CompoundMultiTaskAgent(client)

    print(f"Using provider: {client.provider}")
    print("Generating plan-only outputs for preset compound tasks...\n")
    for result in agent.plan(PRESET_TASKS):
        print(f"# Task: {result.task.name}")
        print(result.plan_markdown)
        print("\n---\n")


if __name__ == "__main__":
    run_cli()
