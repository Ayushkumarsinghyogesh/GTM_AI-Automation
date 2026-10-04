"""Signals -> rubric hits. Claude tool-use se STRUCTURED output (JSON parse ka tension nahi).
Guardrail: fires=true tabhi maana jayega jab evidence source text me grounded ho."""
import json
import re
from functools import lru_cache

import anthropic

from .gtm_config import classifiable_keys, signal_defs
from .textutil import grounded

TOOL_NAME = "record_signal_hits"

SYSTEM = """You classify B2B buying signals for a cybersecurity GTM team.
You get one person's title, company, and a list of SIGNALS (things they posted, engaged with, or events about their company).
For EACH rubric key decide if it fires. Rules:
- Use ONLY the provided SIGNALS/context. Never use outside knowledge or guess.
- fires=true requires a short evidence string copied or closely quoted from the provided text.
- If evidence is missing or ambiguous, fires=false and evidence="".
- Be conservative: a false positive wastes a founder's time.
Rubric keys:
{rubric}"""


def build_tool() -> dict:
    props = {
        k: {
            "type": "object",
            "properties": {
                "fires": {"type": "boolean"},
                "evidence": {"type": "string", "description": "quote from provided text; empty if fires=false"},
            },
            "required": ["fires", "evidence"],
        }
        for k in classifiable_keys()
    }
    return {
        "name": TOOL_NAME,
        "description": "Record which rubric signals fire, with evidence.",
        "input_schema": {"type": "object", "properties": props, "required": classifiable_keys()},
    }


def corpus_of(ctx: dict) -> str:
    parts = [ctx.get("title") or "", ctx.get("company", {}).get("name") or ""]
    for s in ctx.get("signals", []):
        parts += [s.get("type") or "", s.get("text") or ""]
    return " \n".join(parts)


@lru_cache
def _client(api_key: str) -> anthropic.Anthropic:
    return anthropic.Anthropic(api_key=api_key, max_retries=3, timeout=60)


def classify_with_claude(api_key: str, model: str, ctx: dict) -> dict[str, dict]:
    defs = signal_defs()
    rubric = "\n".join(f"- {k}: {defs[k]['description']}" for k in classifiable_keys())
    resp = _client(api_key).messages.create(
        model=model,
        max_tokens=1500,
        system=SYSTEM.format(rubric=rubric),
        tools=[build_tool()],
        tool_choice={"type": "tool", "name": TOOL_NAME},
        messages=[{"role": "user", "content": json.dumps(ctx, ensure_ascii=False)}],
    )
    block = next((b for b in resp.content if b.type == "tool_use"), None)
    raw = dict(block.input) if block else {}
    corpus = corpus_of(ctx)
    out: dict[str, dict] = {}
    for k in classifiable_keys():
        item = raw.get(k) or {}
        ev = (item.get("evidence") or "").strip()
        fires = bool(item.get("fires")) and grounded(ev, corpus)
        out[k] = {"fires": fires, "evidence": ev if fires else ""}
    return out


# ---------- Fallback: API key nahi hai / tests / Claude down ----------
KEYWORDS = {
    "thesis_ai_post": r"ai[- ]?(paced|driven|powered)|autonomous (exploit|attack)|exploitation window|cve velocity|manual triage",
    "thesis_competitor_engagement": r"tuskira|cogent security|\bwiz\b|\borca\b",
    "thesis_wrote_vm_inadequacy": r"(vm|vulnerability management).{0,40}(broken|obsolete|not enough|fails)",
    "vm_tool_frustration": r"patch backlog|too many findings|scanner noise|findings again",
    "uses_scanner": r"tenable|qualys|rapid7|nessus",
    "hiring_vm_roles": r"hiring.{0,40}(vulnerab|exposure)|(vulnerab|exposure).{0,40}(job|opening|hiring)",
    "recent_breach": r"\bbreach\b|\bransomware\b|incident disclosed",
    "spoke_vm_conf": r"(speaker|speaking|talk).{0,60}(vulnerab|exposure|attack surface)",
    "bh_speaker": r"black ?hat.{0,40}(speaker|arsenal|briefing)",
    "bh_2026_post": r"black ?hat ?2026|#blackhat2026",
}


def classify_keywords(ctx: dict) -> dict[str, dict]:
    corpus = corpus_of(ctx)
    out = {}
    for k in classifiable_keys():
        m = re.search(KEYWORDS[k], corpus, re.I) if k in KEYWORDS else None
        out[k] = {"fires": bool(m), "evidence": m.group(0) if m else ""}
    return out
