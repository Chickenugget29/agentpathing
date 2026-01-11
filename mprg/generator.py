"""Reasoning Guard Generator module for MPRG.

Runs diverse LLM agents in parallel and returns a TaskBundle JSON.
No chain-of-thought is requested or stored.
"""

from __future__ import annotations

import json
import os
import time
import uuid
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
import re
from concurrent.futures import ThreadPoolExecutor

import requests

try:
    import voyageai
except ImportError:  # Optional dependency for embeddings
    voyageai = None

try:
    from anthropic import Anthropic
except ImportError:  # Optional dependency for Anthropic provider
    Anthropic = None


REASONING_KEYS = [
    "agent_role",
    "task_id",
    "final_answer",
    "plan_steps",
    "assumptions",
    "tools",
    "risks",
    "fallbacks",
]


AGENT_ROLES = [
    {
        "role": "planner",
        "constraint": "Optimize for clarity and actionable steps.",
    },
    {
        "role": "skeptic",
        "constraint": "Challenge assumptions and propose a safer alternative.",
    },
    {
        "role": "ops_reliability",
        "constraint": "Assume frequent failures and prioritize recovery paths.",
    },
    {
        "role": "cost_optimizer",
        "constraint": "Minimize tool calls and operational cost.",
    },
    {
        "role": "alternative_strategy",
        "constraint": "Avoid batching and offer a different approach.",
    },
    {
        "role": "security_focus",
        "constraint": "Prioritize security, least privilege, and data protection.",
    },
    {
        "role": "compliance_guard",
        "constraint": "Assume strict compliance requirements and auditability.",
    },
    {
        "role": "performance_engineer",
        "constraint": "Optimize for latency and throughput under load.",
    },
    {
        "role": "data_quality",
        "constraint": "Prioritize validation, deduplication, and correctness checks.",
    },
    {
        "role": "observability",
        "constraint": "Maximize logging, tracing, and alerting for visibility.",
    },
    {
        "role": "resilience_tester",
        "constraint": "Design for chaos testing and graceful degradation.",
    },
    {
        "role": "integration_architect",
        "constraint": "Emphasize integration contracts and schema versioning.",
    },
    {
        "role": "minimalist",
        "constraint": "Reduce steps and dependencies to the smallest viable plan.",
    },
    {
        "role": "batching_critic",
        "constraint": "Avoid batching; prefer incremental or streaming sync.",
    },
    {
        "role": "human_in_loop",
        "constraint": "Include manual checkpoints and approvals where risky.",
    },
    {
        "role": "rollback_specialist",
        "constraint": "Plan explicit rollback and recovery procedures.",
    },
    {
        "role": "scalability",
        "constraint": "Assume rapid growth; design for horizontal scaling.",
    },
    {
        "role": "edge_case_hunter",
        "constraint": "Focus on rare edge cases and failure modes.",
    },
    {
        "role": "timeboxer",
        "constraint": "Keep the workflow within strict time constraints.",
    },
    {
        "role": "api_rate_limiter",
        "constraint": "Optimize for rate limits and backoff strategies.",
    },
]


@dataclass
class ReasoningSummary:
    agent_role: str
    task_id: str
    final_answer: str
    plan_steps: List[str]
    assumptions: List[str]
    tools: List[str]
    risks: List[str]
    fallbacks: List[str]


@dataclass
class TaskRun:
    agent_role: str
    is_valid: bool
    reasoning_summary: Optional[ReasoningSummary]
    error: Optional[str]
    embedding_vector: Optional[List[float]]
    embedding_error: Optional[str]


@dataclass
class TaskMeta:
    started_at: str
    finished_at: str
    total_runs: int
    valid_runs: int
    invalid_runs: int
    embeddings_enabled: bool


@dataclass
class TaskBundle:
    task_id: str
    user_prompt: str
    runs: List[TaskRun]
    meta: TaskMeta


def _is_list_of_strings(value: Any) -> bool:
    return isinstance(value, list) and all(isinstance(item, str) for item in value)


def validate_reasoning_summary(
    data: Dict[str, Any], task_id: str
) -> Tuple[bool, Optional[str]]:
    if not isinstance(data, dict):
        return False, "Output is not a JSON object."
    keys = list(data.keys())
    if set(keys) != set(REASONING_KEYS):
        missing = [k for k in REASONING_KEYS if k not in data]
        extra = [k for k in keys if k not in REASONING_KEYS]
        if missing:
            return False, f"Missing keys: {', '.join(missing)}"
        return False, f"Extra keys not allowed: {', '.join(extra)}"
    if not isinstance(data.get("agent_role"), str) or not data["agent_role"].strip():
        return False, "agent_role must be a non-empty string."
    if data.get("task_id") != task_id:
        return False, "task_id must match the requested task_id."
    if not isinstance(data.get("final_answer"), str) or not data["final_answer"].strip():
        return False, "final_answer must be a non-empty string."
    for field in ["plan_steps", "assumptions", "tools", "risks", "fallbacks"]:
        if not _is_list_of_strings(data.get(field)):
            return False, f"{field} must be a list of strings."
    for step in data.get("plan_steps", []):
        if _has_numbering_prefix(step):
            return False, "plan_steps must not include numbering prefixes."
    return True, None


def _has_numbering_prefix(text: str) -> bool:
    normalized = text.strip().lower()
    if normalized.startswith(("step ", "step-", "step:", "step")):
        return True
    if normalized[:2] in {"1.", "2.", "3.", "4.", "5.", "6.", "7.", "8.", "9."}:
        return True
    if re.match(r"^\s*[\-\*\u2022]\s+", text):
        return True
    if re.match(r"^\s*\d+[\.\)\:\-]\s+", text):
        return True
    return False


def _clean_plan_step(text: str) -> str:
    cleaned = re.sub(r"^\s*(step\s*\d+[:\.\)\-]?\s*)", "", text, flags=re.I)
    cleaned = re.sub(r"^\s*[\-\*\u2022]\s+", "", cleaned)
    cleaned = re.sub(r"^\s*\d+[\.\)\:\-]\s+", "", cleaned)
    return cleaned.strip()


def _extract_json(response: str) -> Optional[Dict[str, Any]]:
    cleaned = response.strip()
    cleaned = re.sub(r"^```(?:json)?", "", cleaned, flags=re.I).strip()
    cleaned = re.sub(r"```$", "", cleaned).strip()
    for candidate in (cleaned, _slice_json(cleaned)):
        if not candidate:
            continue
        parsed = _try_parse_json(candidate)
        if parsed is not None:
            return parsed
        repaired = _sanitize_json(candidate)
        parsed = _try_parse_json(repaired)
        if parsed is not None:
            return parsed
    return None


def _slice_json(text: str) -> Optional[str]:
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return None
    return text[start : end + 1]


def _try_parse_json(text: str) -> Optional[Dict[str, Any]]:
    try:
        data = json.loads(text)
        return data if isinstance(data, dict) else None
    except json.JSONDecodeError:
        return None


def _sanitize_json(text: str) -> str:
    fixed = text.replace("“", '"').replace("”", '"').replace("’", "'")
    fixed = re.sub(r",\s*([}\]])", r"\1", fixed)
    return fixed


def _deterministic_embed_input(summary: ReasoningSummary) -> str:
    plan = "\n".join(f"{idx + 1}. {step}" for idx, step in enumerate(summary.plan_steps))
    assumptions = "\n".join(f"- {item}" for item in summary.assumptions)
    fallbacks = "\n".join(f"- {item}" for item in summary.fallbacks)
    return f"PLAN:\n{plan}\nASSUMPTIONS:\n{assumptions}\nFALLBACKS:\n{fallbacks}"


class ReasoningGuardGenerator:
    """Run diverse agents and return a TaskBundle JSON-ready dict."""

    def __init__(
        self,
        provider: str = "openai",
        openai_key: Optional[str] = None,
        openai_model: str = "gpt-4o-mini",
        anthropic_key: Optional[str] = None,
        anthropic_model: str = "claude-3-5-sonnet-20240620",
        anthropic_base_url: Optional[str] = None,
        num_agents: int = 5,
        enable_embeddings: bool = False,
        voyage_key: Optional[str] = None,
    ) -> None:
        self.provider = provider
        self.openai_key = openai_key or os.getenv("OPENAI_API_KEY")
        self.anthropic_key = anthropic_key or os.getenv("ANTHROPIC_API_KEY")
        if self.provider == "openai" and not self.openai_key:
            raise ValueError("OPENAI_API_KEY is required for OpenAI provider.")
        if self.provider == "anthropic" and not self.anthropic_key:
            raise ValueError("ANTHROPIC_API_KEY is required for Anthropic provider.")
        if self.provider == "anthropic" and Anthropic is None:
            raise ValueError("Install the anthropic package to use the Anthropic provider.")
        self.openai_model = openai_model
        self.anthropic_model = anthropic_model
        base_url = (
            anthropic_base_url
            or os.getenv("ANTHROPIC_API_BASE")
            or "https://api.anthropic.com"
        ).rstrip("/")
        if base_url.endswith("/v1"):
            base_url = base_url[:-3]
        self.anthropic_base_url = base_url
        self._anthropic = self._try_init_anthropic()
        self.num_agents = max(3, min(num_agents, len(AGENT_ROLES)))
        self.enable_embeddings = enable_embeddings
        self.voyage_key = voyage_key or os.getenv("VOYAGE_API_KEY")

    def _try_init_anthropic(self):
        if self.provider != "anthropic":
            return None
        if not self.anthropic_key or Anthropic is None:
            return None
        try:
            if self.anthropic_base_url:
                return Anthropic(api_key=self.anthropic_key, base_url=self.anthropic_base_url)
            return Anthropic(api_key=self.anthropic_key)
        except Exception:
            return None

    def generate(self, user_prompt: str) -> Dict[str, Any]:
        task_id = f"task_{uuid.uuid4().hex[:12]}"
        started = datetime.now(timezone.utc).isoformat()

        roles = AGENT_ROLES[: self.num_agents]
        with ThreadPoolExecutor(max_workers=len(roles)) as executor:
            futures = [
                executor.submit(self._run_agent, task_id, user_prompt, role)
                for role in roles
            ]
            runs = [future.result() for future in futures]

        if self.enable_embeddings and self.voyage_key:
            self._attach_embeddings(runs)

        finished = datetime.now(timezone.utc).isoformat()
        valid_runs = sum(1 for run in runs if run.is_valid)
        invalid_runs = len(runs) - valid_runs
        if invalid_runs:
            for run in runs:
                if not run.is_valid:
                    print(f"[generator] invalid run {run.agent_role}: {run.error}")

        bundle = TaskBundle(
            task_id=task_id,
            user_prompt=user_prompt,
            runs=runs,
            meta=TaskMeta(
                started_at=started,
                finished_at=finished,
                total_runs=len(runs),
                valid_runs=valid_runs,
                invalid_runs=invalid_runs,
                embeddings_enabled=bool(self.enable_embeddings and self.voyage_key),
            ),
        )
        return _serialize_task_bundle(bundle)

    def _run_agent(
        self, task_id: str, user_prompt: str, role_info: Dict[str, str]
    ) -> TaskRun:
        role = role_info["role"]
        constraint = role_info["constraint"]

        response = self._call_llm(task_id, user_prompt, role, constraint, strict=False)
        parsed = _extract_json(response)
        summary, error = self._validate_or_error(parsed, task_id, role)
        if summary:
            return TaskRun(
                agent_role=role,
                is_valid=True,
                reasoning_summary=summary,
                error=None,
                embedding_vector=None,
                embedding_error=None,
            )

        retry = self._call_llm(task_id, user_prompt, role, constraint, strict=True)
        parsed_retry = _extract_json(retry)
        summary_retry, error_retry = self._validate_or_error(parsed_retry, task_id, role)
        if summary_retry:
            return TaskRun(
                agent_role=role,
                is_valid=True,
                reasoning_summary=summary_retry,
                error=None,
                embedding_vector=None,
                embedding_error=None,
            )

        numbering_error = "plan_steps must not include numbering prefixes"
        if (error_retry and numbering_error in error_retry) or (
            error and numbering_error in error
        ):
            repair = self._call_llm(task_id, user_prompt, role, constraint, strict=True, repair=True)
            parsed_repair = _extract_json(repair)
            summary_repair, error_repair = self._validate_or_error(parsed_repair, task_id, role)
            if summary_repair:
                return TaskRun(
                    agent_role=role,
                    is_valid=True,
                    reasoning_summary=summary_repair,
                    error=None,
                    embedding_vector=None,
                    embedding_error=None,
                )
            error_retry = error_repair or error_retry

        return TaskRun(
            agent_role=role,
            is_valid=False,
            reasoning_summary=None,
            error=error_retry or error or "Invalid JSON or schema.",
            embedding_vector=None,
            embedding_error=None,
        )

    def _validate_or_error(
        self, parsed: Optional[Dict[str, Any]], task_id: str, agent_role: str
    ) -> Tuple[Optional[ReasoningSummary], Optional[str]]:
        if parsed is None:
            return None, "Output is not valid JSON."
        if "task_id" not in parsed:
            parsed["task_id"] = task_id
        if "agent_role" not in parsed:
            parsed["agent_role"] = agent_role
        is_valid, error = validate_reasoning_summary(parsed, task_id)
        if not is_valid:
            if error and "plan_steps must not include numbering prefixes" in error:
                cleaned = dict(parsed)
                cleaned_steps = [_clean_plan_step(step) for step in cleaned.get("plan_steps", [])]
                cleaned["plan_steps"] = [step for step in cleaned_steps if step]
                is_clean, clean_error = validate_reasoning_summary(cleaned, task_id)
                if is_clean:
                    return ReasoningSummary(**cleaned), None
                return None, clean_error or error
            return None, error
        return ReasoningSummary(**parsed), None

    def _call_openai(
        self,
        task_id: str,
        user_prompt: str,
        role: str,
        constraint: str,
        strict: bool,
        repair: bool = False,
    ) -> str:
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
            "Return ONLY valid JSON matching the schema, no extra keys. "
            "Use double quotes for all strings. No trailing commas. "
            "Do not wrap in code fences or add commentary."
            if strict
            else "Return JSON only; do not include chain-of-thought. "
                 "Use double quotes and no code fences."
        )
        step_rules = (
            "plan_steps must be plain strings with no numbering or prefixes. "
            "Do not include '1.', 'Step 1', '-', or '•'. "
            "If you include numbering, output will be rejected."
        )
        if repair:
            step_rules = (
                "Rewrite plan_steps with no numbering or prefixes. "
                "Return JSON only."
            )
        prompt = (
            f"You are the {role}. {constraint}\n"
            f"Task ID: {task_id}\n"
            f"Task: {user_prompt}\n"
            f"{rules}\n"
            f"{step_rules}\n"
            f"Schema example (types only): {json.dumps(schema)}"
        )
        headers = {
            "Authorization": f"Bearer {self.openai_key}",
            "Content-Type": "application/json",
        }
        temperature = 0.2 if strict or repair else 0.7
        body = {
            "model": self.openai_model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": temperature,
        }
        if strict or repair:
            body["response_format"] = {"type": "json_object"}
        response = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers=headers,
            json=body,
            timeout=60,
        )
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"].strip()

    def _call_anthropic(
        self,
        task_id: str,
        user_prompt: str,
        role: str,
        constraint: str,
        strict: bool,
        repair: bool = False,
    ) -> str:
        if not self._anthropic:
            raise ValueError("Anthropic client is not configured.")
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
            "Return ONLY valid JSON matching the schema, no extra keys. "
            "Use double quotes for all strings. No trailing commas. "
            "Do not wrap in code fences or add commentary."
            if strict
            else "Return JSON only; do not include chain-of-thought. "
                 "Use double quotes and no code fences."
        )
        step_rules = (
            "plan_steps must be plain strings with no numbering or prefixes. "
            "Do not include '1.', 'Step 1', '-', or '•'. "
            "If you include numbering, output will be rejected."
        )
        if repair:
            step_rules = (
                "Rewrite plan_steps with no numbering or prefixes. "
                "Return JSON only."
            )
        prompt = (
            f"You are the {role}. {constraint}\n"
            f"Task ID: {task_id}\n"
            f"Task: {user_prompt}\n"
            f"{rules}\n"
            f"{step_rules}\n"
            f"Schema example (types only): {json.dumps(schema)}"
        )
        temperature = 0.2 if strict or repair else 0.7
        response = self._anthropic.messages.create(
            model=self.anthropic_model,
            max_tokens=800,
            temperature=temperature,
            system="Return a single JSON object only. Do not include code fences or commentary.",
            messages=[{"role": "user", "content": prompt}],
        )
        parts = []
        for item in response.content:
            if getattr(item, "type", None) == "text":
                parts.append(item.text)
        return "\n".join(parts).strip()

    def _call_llm(
        self,
        task_id: str,
        user_prompt: str,
        role: str,
        constraint: str,
        strict: bool,
        repair: bool = False,
    ) -> str:
        if self.provider == "anthropic":
            return self._call_anthropic(task_id, user_prompt, role, constraint, strict, repair)
        return self._call_openai(task_id, user_prompt, role, constraint, strict, repair)

    def _attach_embeddings(self, runs: List[TaskRun]) -> None:
        if not self.voyage_key or voyageai is None:
            for run in runs:
                if run.is_valid:
                    run.embedding_error = "Voyage client unavailable."
            return

        client = voyageai.Client(api_key=self.voyage_key)
        for run in runs:
            if not run.is_valid or not run.reasoning_summary:
                continue
            input_text = _deterministic_embed_input(run.reasoning_summary)
            try:
                result = client.embed([input_text], model="voyage-3")
                run.embedding_vector = result.embeddings[0]
            except Exception as exc:
                run.embedding_error = str(exc)
                run.embedding_vector = None


def _serialize_task_bundle(bundle: TaskBundle) -> Dict[str, Any]:
    def run_to_dict(run: TaskRun) -> Dict[str, Any]:
        summary = asdict(run.reasoning_summary) if run.reasoning_summary else None
        return {
            "agent_role": run.agent_role,
            "is_valid": run.is_valid,
            "reasoning_summary": summary,
            "error": run.error,
            "embedding_vector": run.embedding_vector,
            "embedding_error": run.embedding_error,
        }

    return {
        "task_id": bundle.task_id,
        "user_prompt": bundle.user_prompt,
        "runs": [run_to_dict(run) for run in bundle.runs],
        "meta": asdict(bundle.meta),
    }
