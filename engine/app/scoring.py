"""Deterministic scoring (Black Hat rubric). Koi LLM nahi, pure functions => testable.
Claude sirf 'kya ye signal fire hua' decide karta hai (classify.py). Points yahan lagte hain."""
import re
from dataclasses import dataclass, field

from .gtm_config import cfg, signal_defs


@dataclass
class ScoreResult:
    thesis: int
    pain: int
    attendance: int
    total: int
    tier: str
    breakdown: dict[str, int]
    notes: list[str] = field(default_factory=list)


def title_key(title: str | None) -> str | None:
    """Return: rule key, '__drop__', ya None."""
    t = (title or "").lower()
    if not t:
        return None
    rules = cfg()["title_rules"]
    if any(re.search(p, t) for p in rules["drop_patterns"]):
        return "__drop__"
    for rule in rules["ordered"]:
        if any(re.search(p, t) for p in rule["patterns"]):
            return rule["key"]
    return None


def company_fit(employees: int | None, industry: str | None) -> bool:
    c = cfg()["company_fit"]
    if employees is None or not (c["min_employees"] <= employees <= c["max_employees"]):
        return False
    if not industry:
        return True  # size fit, industry unknown -> benefit of doubt
    return any(k in industry.lower() for k in c["industry_keywords"])


def tier_for(total: int) -> str:
    for t in sorted(cfg()["tiers"], key=lambda x: -x["min"]):
        if total >= t["min"]:
            return t["name"]
    return "drop"


def score_contact(
    title: str | None,
    employees: int | None,
    industry: str | None,
    hits: dict[str, bool],
) -> ScoreResult:
    defs = signal_defs()
    notes: list[str] = []
    fired: dict[str, int] = {}

    tk = title_key(title)
    if tk == "__drop__":
        return ScoreResult(0, 0, 0, 0, "drop", {}, [f"title excluded by drop rule: {title!r}"])
    if tk:
        fired[tk] = defs[tk]["points"]
    if company_fit(employees, industry):
        fired["company_fit"] = defs["company_fit"]["points"]
    for key, on in hits.items():
        if on and key in defs and defs[key].get("classifiable"):
            fired[key] = defs[key]["points"]

    by_cat = {"thesis": 0, "pain": 0, "attendance": 0}
    for k, pts in fired.items():
        by_cat[defs[k]["category"]] += pts
    total = sum(by_cat.values())
    tier = tier_for(total)

    if cfg().get("attendance_only_drop") and fired and set(
        defs[k]["category"] for k in fired
    ) == {"attendance"}:
        tier = "drop"
        notes.append("only attendance signals: dropped per rubric")

    return ScoreResult(by_cat["thesis"], by_cat["pain"], by_cat["attendance"], total, tier, fired, notes)
