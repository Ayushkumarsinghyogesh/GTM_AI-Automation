"""Claude se personalised LinkedIn message. Code guardrails: grounding, length, banned phrases.
Link (Luma) code append karta hai, LLM nahi (LLM link bigaad sakta hai)."""
import json
from dataclasses import dataclass
from functools import lru_cache

import anthropic

from .gtm_config import cfg
from .textutil import grounded

PROMPT_VERSION = "v1"
TOOL_NAME = "write_outreach"

TOOL = {
    "name": TOOL_NAME,
    "description": "Write a grounded, personalised LinkedIn outreach draft.",
    "input_schema": {
        "type": "object",
        "properties": {
            "hook": {"type": "string", "description": "ONE sentence: the specific thing this person said/did (internal note)."},
            "evidence_quote": {"type": "string", "description": "Text copied from a provided signal that supports the hook (max 25 words)."},
            "connection_note": {"type": "string", "description": "LinkedIn connection note. No pitch, no links."},
            "message": {"type": "string", "description": "First message after connecting. No links."},
        },
        "required": ["hook", "evidence_quote", "connection_note", "message"],
    },
}


@dataclass
class Draft:
    hook: str
    evidence_quote: str
    connection_note: str
    message: str  # CTA line ke saath (final)
    model: str
    prompt_version: str = PROMPT_VERSION


def system_prompt() -> str:
    b = cfg()["brand"]
    rules = "\n".join(f"- {r}" for r in b["message_rules"])
    qs = "\n".join(f"- {q}" for q in b["three_questions"])
    lim = cfg()["limits"]
    return (
        f"You write outreach on behalf of {b['sender_name']}, founder of {b['company']}.\n\n"
        f"COMPANY THESIS (context only, do not paste):\n{b['thesis']}\n\n"
        f"The three questions the product answers:\n{qs}\n\n"
        f"RULES:\n{rules}\n"
        f"- connection_note <= {lim['connection_note_max_chars']} characters.\n"
        f"- message <= {lim['message_max_chars']} characters.\n"
        "Everything you state about the person must come from the SIGNALS provided."
    )


def validate_draft(d: dict, corpus: str) -> list[str]:
    lim = cfg()["limits"]
    errs: list[str] = []
    for k in ("hook", "evidence_quote", "connection_note", "message"):
        if not (d.get(k) or "").strip():
            errs.append(f"{k} is empty")
    if errs:
        return errs
    if not grounded(d["evidence_quote"], corpus):
        errs.append("evidence_quote is not found in the provided signals (hallucination risk)")
    if len(d["connection_note"]) > lim["connection_note_max_chars"]:
        errs.append(f"connection_note too long ({len(d['connection_note'])})")
    if len(d["message"]) > lim["message_max_chars"]:
        errs.append(f"message too long ({len(d['message'])})")
    blob = f"{d['connection_note']} {d['message']}".lower()
    for p in cfg()["banned_phrases"]:
        if p in blob:
            errs.append(f"banned phrase: {p!r}")
    if "http://" in blob or "https://" in blob or "www." in blob:
        errs.append("draft must not contain links")
    return errs


def final_message(body: str) -> str:
    b = cfg()["brand"]
    return f"{body.strip()}\n\n{b['cta_line'].format(luma_url=b['luma_url'])}"


@lru_cache
def _client(api_key: str) -> anthropic.Anthropic:
    return anthropic.Anthropic(api_key=api_key, max_retries=3, timeout=60)


def generate_draft(api_key: str, model: str, ctx: dict, corpus: str) -> Draft | None:
    """Max 2 attempts; dusri baar errors feedback me. Fail => None (caller tier downgrade karega)."""
    feedback = ""
    for _ in range(2):
        content = json.dumps(ctx, ensure_ascii=False) + (f"\n\nFIX THESE PROBLEMS FROM LAST ATTEMPT: {feedback}" if feedback else "")
        resp = _client(api_key).messages.create(
            model=model,
            max_tokens=900,
            system=system_prompt(),
            tools=[TOOL],
            tool_choice={"type": "tool", "name": TOOL_NAME},
            messages=[{"role": "user", "content": content}],
        )
        block = next((b for b in resp.content if b.type == "tool_use"), None)
        if not block:
            feedback = "no tool output"
            continue
        d = dict(block.input)
        errs = validate_draft(d, corpus)
        if not errs:
            return Draft(
                hook=d["hook"].strip(),
                evidence_quote=d["evidence_quote"].strip(),
                connection_note=d["connection_note"].strip(),
                message=final_message(d["message"]),
                model=model,
            )
        feedback = "; ".join(errs)
    return None
