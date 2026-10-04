"""Chhote helpers: grounding check (anti-hallucination), hashing."""
import hashlib
import json
import re
from typing import Any


def grounded(evidence: str, corpus: str, threshold: float = 0.6) -> bool:
    """True agar evidence ke >= threshold words source text me milte hain.
    LLM ne kuch invent kiya ho to ye pakad leta hai."""
    ev = re.findall(r"\w+", (evidence or "").lower())
    if not ev:
        return False
    cs = set(re.findall(r"\w+", (corpus or "").lower()))
    return sum(w in cs for w in ev) / len(ev) >= threshold


def stable_hash(obj: Any) -> str:
    raw = json.dumps(obj, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(raw.encode()).hexdigest()
