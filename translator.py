"""Chain-of-reasoning parser that emits FOL-style relations."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List, Optional


@dataclass
class Step:
    label: str
    detail: str


@dataclass
class ChainSegment:
    title: str
    steps: List[Step]


def _to_constant(text: str) -> str:
    tokens = re.findall(r"[A-Za-z0-9]+", text)
    return "".join(token.capitalize() for token in tokens) or "Unknown"


class ChainReasoningParser:
    SECTION_PATTERN = re.compile(r"^\s*(\d+)\.\s*(.+)$", re.M)
    STEP_PATTERN = re.compile(r'^\s*([A-Za-z0-9 &\'"/-]+):\s*(.+)$')
    BULLET_PATTERN = re.compile(r"^\s*[-•]\s*(.+)$")

    def parse(self, text: str) -> List[ChainSegment]:
        text = text.strip()
        if not text:
            return []
        matches = list(self.SECTION_PATTERN.finditer(text))
        if matches:
            segments: List[ChainSegment] = []
            for idx, match in enumerate(matches):
                start = match.end()
                end = matches[idx + 1].start() if idx + 1 < len(matches) else len(text)
                title = match.group(2).strip() or f"Chain{idx + 1}"
                body = text[start:end].strip()
                steps = self._extract_steps(body)
                if steps:
                    segments.append(ChainSegment(title=title, steps=steps))
            return segments
        return [ChainSegment(title="ReasoningChain", steps=self._extract_steps(text))]

    def _extract_steps(self, body: str) -> List[Step]:
        steps: List[Step] = []
        for raw in body.splitlines():
            line = raw.strip()
            if not line:
                continue
            match = self.STEP_PATTERN.match(line)
            if match:
                steps.append(Step(match.group(1).strip(), match.group(2).strip()))
                continue
            match = self.BULLET_PATTERN.match(line)
            if match:
                detail = match.group(1).strip()
                label = " ".join(detail.split()[:3]) or "Step"
                steps.append(Step(label, detail))
                continue
        if steps:
            return steps
        sentences = [s.strip() for s in re.split(r"[.!?]\s+", body) if s.strip()]
        if not sentences:
            sentences = [body.strip()]
        return [Step(f"Step{idx + 1}", sentence) for idx, sentence in enumerate(sentences)]


def _segments_to_fol(segments: List[ChainSegment]) -> str:
    lines: List[str] = []
    for idx, segment in enumerate(segments, start=1):
        chain_const = _to_constant(segment.title or f"Chain{idx}")
        lines.append(f"Chain({chain_const})")
        for order, step in enumerate(segment.steps, start=1):
            label_const = _to_constant(step.label or f"Step{order}")
            detail_const = _to_constant(step.detail)
            lines.append(f"Step({chain_const}, {order}, {label_const})")
            lines.append(f"Supports({label_const}, {detail_const})")
    return "\n".join(lines)


PARSER = ChainReasoningParser()


def translate(text: str) -> Optional[str]:
    segments = PARSER.parse(text)
    if not segments:
        return None
    return _segments_to_fol(segments)
