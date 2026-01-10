"""Dynamic FOL translator for natural language sentences.

Translates single sentences into First-Order Logic predicates.
Handles commands, questions, statements, and reasoning chains.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List, Optional, Tuple


# Common action verbs and their FOL predicates
ACTION_VERBS = {
    # Computation/Process verbs
    "do": "Execute",
    "perform": "Execute",
    "run": "Execute",
    "execute": "Execute",
    "apply": "Apply",
    "compute": "Compute",
    "calculate": "Compute",
    "solve": "Solve",
    "find": "Find",
    "determine": "Determine",
    "derive": "Derive",
    
    # Transformation verbs
    "transform": "Transform",
    "convert": "Transform",
    "change": "Transform",
    "orthogonalize": "Orthogonalize",
    "normalize": "Normalize",
    "simplify": "Simplify",
    "reduce": "Reduce",
    "factor": "Factor",
    "decompose": "Decompose",
    
    # Analysis verbs
    "analyze": "Analyze",
    "check": "Check",
    "verify": "Verify",
    "prove": "Prove",
    "show": "Show",
    "demonstrate": "Show",
    "explain": "Explain",
    
    # Creation verbs
    "create": "Create",
    "make": "Create",
    "build": "Create",
    "generate": "Generate",
    "construct": "Construct",
    
    # Query verbs
    "get": "Retrieve",
    "fetch": "Retrieve",
    "retrieve": "Retrieve",
    "look up": "Retrieve",
    "search": "Search",
    "query": "Query",
}

# Known mathematical/technical concepts
KNOWN_CONCEPTS = {
    "gram-schmidt": "GramSchmidt",
    "gram schmidt": "GramSchmidt",
    "gaussian elimination": "GaussianElimination",
    "lu decomposition": "LUDecomposition",
    "qr factorization": "QRFactorization",
    "eigenvalue": "Eigenvalue",
    "eigenvector": "Eigenvector",
    "matrix": "Matrix",
    "vector": "Vector",
    "orthogonal": "Orthogonal",
    "orthonormal": "Orthonormal",
    "basis": "Basis",
    "linear combination": "LinearCombination",
    "dot product": "DotProduct",
    "cross product": "CrossProduct",
    "determinant": "Determinant",
    "inverse": "Inverse",
    "transpose": "Transpose",
}


@dataclass
class ParsedSentence:
    """Parsed components of a sentence."""
    action: Optional[str]
    subject: Optional[str]
    object_: Optional[str]
    modifiers: List[str]
    raw: str


def _to_constant(text: str) -> str:
    """Convert text to a FOL constant (CamelCase identifier)."""
    if not text:
        return "Unknown"
    
    # Check for known concepts first
    lower = text.lower().strip()
    for pattern, constant in KNOWN_CONCEPTS.items():
        if pattern in lower:
            return constant
    
    # Convert to CamelCase
    tokens = re.findall(r"[A-Za-z0-9]+", text)
    return "".join(token.capitalize() for token in tokens) or "Unknown"


def _extract_action(text: str) -> Tuple[Optional[str], str]:
    """Extract action verb from sentence, return (action, remaining_text)."""
    lower = text.lower().strip()
    
    # Handle imperative sentences (commands)
    for verb, predicate in ACTION_VERBS.items():
        if lower.startswith(verb + " "):
            remaining = text[len(verb):].strip()
            return predicate, remaining
        # Also check "verb the X"
        pattern = rf"^{verb}\s+(?:the\s+)?(.+)$"
        match = re.match(pattern, lower, re.IGNORECASE)
        if match:
            remaining = match.group(1)
            return predicate, remaining
    
    return None, text


def _extract_concepts(text: str) -> List[str]:
    """Extract concepts/objects from text."""
    concepts = []
    lower = text.lower()
    
    # Check for known concepts
    for pattern, constant in KNOWN_CONCEPTS.items():
        if pattern in lower:
            concepts.append(constant)
    
    # If no known concepts, extract noun phrases
    if not concepts:
        # Simple extraction: get words after "the" or at key positions
        # Remove common articles and prepositions
        cleaned = re.sub(r'\b(the|a|an|of|for|to|with|on|in|by)\b', ' ', text, flags=re.IGNORECASE)
        tokens = [t.strip() for t in cleaned.split() if t.strip()]
        if tokens:
            concepts.append(_to_constant(" ".join(tokens)))
    
    return concepts


def _parse_sentence(text: str) -> ParsedSentence:
    """Parse a single sentence into its components."""
    text = text.strip()
    
    # Extract action
    action, remaining = _extract_action(text)
    
    # Extract concepts from remaining text
    concepts = _extract_concepts(remaining)
    
    return ParsedSentence(
        action=action,
        subject=concepts[0] if concepts else None,
        object_=concepts[1] if len(concepts) > 1 else None,
        modifiers=concepts[2:] if len(concepts) > 2 else [],
        raw=text
    )


def _sentence_to_fol(parsed: ParsedSentence) -> str:
    """Convert parsed sentence to FOL predicates."""
    lines = []
    
    if parsed.action and parsed.subject:
        # Action on subject: Execute(GramSchmidt)
        lines.append(f"{parsed.action}({parsed.subject})")
        
        # If there's an object, add relationship
        if parsed.object_:
            lines.append(f"Target({parsed.action}, {parsed.object_})")
            
        # Add modifiers as properties
        for mod in parsed.modifiers:
            lines.append(f"With({parsed.subject}, {mod})")
            
    elif parsed.subject:
        # Just a concept mentioned
        lines.append(f"Concept({parsed.subject})")
        
    else:
        # Fallback: treat whole sentence as a task
        const = _to_constant(parsed.raw)
        lines.append(f"Task({const})")
    
    return "\n".join(lines)


def translate(text: str) -> Optional[str]:
    """Translate natural language text into FOL.
    
    Handles:
    - Single commands: "Do the Gram-Schmidt process"
    - Questions: "What is the determinant?"
    - Statements: "The matrix is orthogonal"
    - Multi-step reasoning (original behavior)
    
    Args:
        text: Input text (single sentence or multi-step reasoning)
        
    Returns:
        FOL predicates as a string, or None if parsing failed
    """
    text = text.strip()
    if not text:
        return None
    
    # Check if it's multi-step reasoning (has numbered sections or bullets)
    has_numbers = bool(re.search(r"^\s*\d+\.", text, re.MULTILINE))
    has_bullets = bool(re.search(r"^\s*[-•]", text, re.MULTILINE))
    has_multiple_lines = len(text.splitlines()) > 2
    
    if has_numbers or has_bullets or has_multiple_lines:
        # Use chain reasoning parser for complex input
        return _translate_chain(text)
    
    # Single sentence - use dynamic parser
    parsed = _parse_sentence(text)
    return _sentence_to_fol(parsed)


def _translate_chain(text: str) -> Optional[str]:
    """Translate multi-step reasoning chains (original behavior)."""
    from dataclasses import dataclass as dc
    
    @dc
    class Step:
        label: str
        detail: str

    @dc
    class ChainSegment:
        title: str
        steps: List[Step]
    
    SECTION_PATTERN = re.compile(r"^\s*(\d+)\.\s*(.+)$", re.M)
    STEP_PATTERN = re.compile(r"^\s*([A-Za-z0-9 &'\"/-]+):\s*(.+)$")
    BULLET_PATTERN = re.compile(r"^\s*[-•]\s*(.+)$")
    
    def extract_steps(body: str) -> List[Step]:
        steps = []
        for raw in body.splitlines():
            line = raw.strip()
            if not line:
                continue
            match = STEP_PATTERN.match(line)
            if match:
                steps.append(Step(match.group(1).strip(), match.group(2).strip()))
                continue
            match = BULLET_PATTERN.match(line)
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
        return [Step(f"Step{i+1}", s) for i, s in enumerate(sentences)]
    
    matches = list(SECTION_PATTERN.finditer(text))
    
    if matches:
        segments = []
        for idx, match in enumerate(matches):
            start = match.end()
            end = matches[idx + 1].start() if idx + 1 < len(matches) else len(text)
            title = match.group(2).strip() or f"Chain{idx + 1}"
            body = text[start:end].strip()
            steps = extract_steps(body)
            if steps:
                segments.append(ChainSegment(title=title, steps=steps))
    else:
        segments = [ChainSegment(title="ReasoningChain", steps=extract_steps(text))]
    
    if not segments:
        return None
    
    # Convert to FOL
    lines = []
    for idx, segment in enumerate(segments, start=1):
        chain_const = _to_constant(segment.title or f"Chain{idx}")
        lines.append(f"Chain({chain_const})")
        for order, step in enumerate(segment.steps, start=1):
            label_const = _to_constant(step.label or f"Step{order}")
            detail_const = _to_constant(step.detail)
            lines.append(f"Step({chain_const}, {order}, {label_const})")
            lines.append(f"Supports({label_const}, {detail_const})")
    
    return "\n".join(lines)


# Convenience function for testing
def test_examples():
    """Test the translator with example sentences."""
    examples = [
        "Do the Gram-Schmidt process",
        "Compute the determinant",
        "Apply Gaussian elimination",
        "Find the eigenvalues",
        "Orthogonalize the basis vectors",
        "Perform QR factorization on the matrix",
    ]
    
    for ex in examples:
        print(f"\nInput: {ex}")
        print(f"FOL:\n{translate(ex)}")


if __name__ == "__main__":
    test_examples()
