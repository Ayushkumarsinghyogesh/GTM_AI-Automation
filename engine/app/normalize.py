"""ClearCue webhook payload -> hamara standard format.

IMPORTANT: ClearCue ka exact payload schema yahan verify nahi hua. Isliye ye tolerant hai:
FIELD_MAP me multiple possible key names hain. Pehla REAL webhook aane ke baad
raw_events table me payload dekho aur FIELD_MAP ko uske hisaab se tight karo
(Claude Code me /fix-normalizer command isi ke liye hai).
"""
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from urllib.parse import urlparse

from .textutil import stable_hash

FIELD_MAP = {
    "person_obj": ["person", "contact", "lead", "profile", "prospect"],
    "company_obj": ["company", "organization", "organisation", "account"],
    "signal_obj": ["signal", "event", "trigger"],
    "signal_list": ["signals", "events"],
    "first_name": ["first_name", "firstName", "firstname"],
    "last_name": ["last_name", "lastName", "lastname"],
    "full_name": ["full_name", "fullName", "name"],
    "title": ["title", "job_title", "jobTitle", "position", "headline"],
    "email": ["email", "email_address", "emailAddress"],
    "linkedin_url": ["linkedin_url", "linkedinUrl", "linkedin", "profile_url", "profileUrl", "url"],
    "company_name": ["name", "company_name", "companyName"],
    "domain": ["domain", "website", "company_domain", "url"],
    "employees": ["employees", "employee_count", "employeeCount", "size", "headcount", "company_size"],
    "industry": ["industry", "sector"],
    "company_linkedin": ["linkedin_url", "linkedinUrl", "linkedin"],
    "signal_type": ["type", "signal_type", "signalType", "name", "category"],
    "signal_text": ["text", "content", "description", "summary", "evidence", "post_text", "body"],
    "signal_url": ["url", "link", "post_url", "source_url"],
    "occurred_at": ["detected_at", "detectedAt", "occurred_at", "created_at", "createdAt", "date", "timestamp"],
}


@dataclass
class NormalizedEvent:
    contact_key: str
    linkedin_url: str | None
    first_name: str | None
    last_name: str | None
    full_name: str | None
    title: str | None
    email: str | None
    company_key: str | None
    company_name: str | None
    domain: str | None
    employees: int | None
    industry: str | None
    company_linkedin: str | None
    signal_type: str | None
    signal_text: str | None
    signal_url: str | None
    occurred_at: str | None
    signal_hash: str = field(default="")


def _sub(d: dict, names: list[str]) -> dict:
    for n in names:
        v = d.get(n)
        if isinstance(v, dict):
            return v
    return {}


def _pick(primary: dict, keys: list[str], fallback: dict | None = None) -> Any:
    for src in (primary, fallback or {}):
        for k in keys:
            v = src.get(k)
            if v not in (None, "", [], {}):
                return v
    return None


def norm_linkedin(url: str | None) -> str | None:
    if not url or "linkedin.com" not in str(url).lower():
        return None
    p = urlparse(str(url).strip())
    path = re.sub(r"/+$", "", p.path).lower()
    if not path:
        return None
    return f"https://www.linkedin.com{path}"


def norm_domain(v: str | None) -> str | None:
    if not v:
        return None
    s = str(v).strip().lower()
    if "linkedin.com" in s:
        return None
    s = re.sub(r"^https?://", "", s)
    s = re.sub(r"^www\.", "", s)
    s = s.split("/")[0]
    return s or None


def parse_employees(v: Any) -> int | None:
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return int(v)
    nums = [int(n) for n in re.findall(r"\d+", str(v).replace(",", ""))]
    if not nums:
        return None
    return nums[0] if len(nums) == 1 else (nums[0] + nums[1]) // 2


def parse_ts(v: Any) -> str | None:
    if not v:
        return None
    try:
        return datetime.fromisoformat(str(v).replace("Z", "+00:00")).isoformat()
    except ValueError:
        return None


def normalize(payload: dict) -> list[NormalizedEvent]:
    """Ek payload me multiple signals ho sakte hain -> multiple events."""
    if not isinstance(payload, dict):
        return []
    person = _sub(payload, FIELD_MAP["person_obj"])
    company = _sub(payload, FIELD_MAP["company_obj"])

    first = _pick(person, FIELD_MAP["first_name"])
    last = _pick(person, FIELD_MAP["last_name"])
    full = _pick(person, FIELD_MAP["full_name"]) or " ".join(x for x in [first, last] if x) or None
    if full and not (first or last):
        parts = str(full).split(" ", 1)
        first, last = parts[0], (parts[1] if len(parts) > 1 else None)

    li = norm_linkedin(_pick(person, FIELD_MAP["linkedin_url"]))
    email = _pick(person, FIELD_MAP["email"])
    email = str(email).strip().lower() if email else None
    contact_key = li or email
    if not contact_key:
        return []

    cname = _pick(company, FIELD_MAP["company_name"])
    domain = norm_domain(_pick(company, FIELD_MAP["domain"]))
    company_key = domain or (str(cname).strip().lower() if cname else None)

    raw_signals: list[dict] = []
    for k in FIELD_MAP["signal_list"]:
        if isinstance(payload.get(k), list):
            raw_signals = [s for s in payload[k] if isinstance(s, dict)]
            break
    if not raw_signals:
        one = _sub(payload, FIELD_MAP["signal_obj"])
        raw_signals = [one or payload]

    out: list[NormalizedEvent] = []
    for s in raw_signals:
        ev = NormalizedEvent(
            contact_key=contact_key,
            linkedin_url=li,
            first_name=first,
            last_name=last,
            full_name=full,
            title=_pick(person, FIELD_MAP["title"]),
            email=email,
            company_key=company_key,
            company_name=cname,
            domain=domain,
            employees=parse_employees(_pick(company, FIELD_MAP["employees"])),
            industry=_pick(company, FIELD_MAP["industry"]),
            company_linkedin=norm_linkedin(_pick(company, FIELD_MAP["company_linkedin"])),
            signal_type=_pick(s, FIELD_MAP["signal_type"]),
            signal_text=_pick(s, FIELD_MAP["signal_text"]),
            signal_url=_pick(s, FIELD_MAP["signal_url"]),
            occurred_at=parse_ts(_pick(s, FIELD_MAP["occurred_at"])),
        )
        ev.signal_hash = stable_hash([contact_key, ev.signal_type, ev.signal_text, ev.signal_url])[:40]
        out.append(ev)
    return out
