"""Data models and validation for MPRG ReasoningSummary."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Tuple


REQUIRED_KEYS = [
    "agent_role",
    "task_id",
    "final_answer",
    "plan_steps",
    "assumptions",
    "tools",
    "risks",
    "fallbacks",
]


@dataclass
class ReasoningSummary:
    """Strict JSON schema for agent outputs."""

    agent_role: str
    task_id: str
    final_answer: str
    plan_steps: List[str]
    assumptions: List[str]
    tools: List[str]
    risks: List[str]
    fallbacks: List[str]

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ReasoningSummary":
        return cls(
            agent_role=data["agent_role"],
            task_id=data["task_id"],
            final_answer=data["final_answer"],
            plan_steps=data["plan_steps"],
            assumptions=data["assumptions"],
            tools=data["tools"],
            risks=data["risks"],
            fallbacks=data["fallbacks"],
        )


def _is_list_of_strings(value: Any) -> bool:
    return isinstance(value, list) and all(isinstance(item, str) for item in value)


def validate_summary(
    data: Dict[str, Any],
    task_id: str,
) -> Tuple[bool, str, ReasoningSummary | None]:
    """Validate JSON output against the ReasoningSummary schema."""
    if not isinstance(data, dict):
        return False, "Output is not a JSON object.", None

    missing = [key for key in REQUIRED_KEYS if key not in data]
    if missing:
        return False, f"Missing keys: {', '.join(missing)}", None

    if not isinstance(data.get("agent_role"), str) or not data["agent_role"].strip():
        return False, "agent_role must be a non-empty string.", None
    if not isinstance(data.get("task_id"), str) or data["task_id"] != task_id:
        return False, "task_id must match the requested task_id.", None
    if not isinstance(data.get("final_answer"), str) or not data["final_answer"].strip():
        return False, "final_answer must be a non-empty string.", None

    list_fields = ["plan_steps", "assumptions", "tools", "risks", "fallbacks"]
    for field in list_fields:
        if not _is_list_of_strings(data.get(field)):
            return False, f"{field} must be a list of strings.", None

    return True, "", ReasoningSummary.from_dict(data)
