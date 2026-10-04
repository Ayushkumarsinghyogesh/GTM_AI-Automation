"""Supabase data access. Saara DB-touching code sirf yahan (baaki modules pure/testable)."""
from datetime import datetime, timezone
from functools import lru_cache
from typing import Any

from supabase import Client, create_client

from .config import get_settings

OPEN_MSG_STATUSES = ["draft", "approved", "queued", "pushed", "rejected"]


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


@lru_cache
def sb() -> Client:
    s = get_settings()
    return create_client(s.supabase_url, s.supabase_service_role_key)


def _clean(d: dict) -> dict:
    return {k: v for k, v in d.items() if v is not None}


# ---------- raw events ----------
def insert_raw_event(source: str, payload: Any, payload_hash: str) -> bool:
    """True = naya, False = duplicate (ignore)."""
    res = (
        sb().table("raw_events")
        .upsert({"source": source, "payload": payload, "payload_hash": payload_hash},
                on_conflict="payload_hash", ignore_duplicates=True)
        .execute()
    )
    return bool(res.data)


def fetch_pending_events(limit: int, max_attempts: int) -> list[dict]:
    return (
        sb().table("raw_events").select("*")
        .in_("status", ["pending", "failed"]).lt("attempts", max_attempts)
        .order("received_at").limit(limit).execute().data
    )


def mark_event(event_id: str, status: str, error: str | None = None, attempts: int | None = None) -> None:
    row: dict = {"status": status, "error": error, "processed_at": now() if status != "failed" else None}
    if attempts is not None:
        row["attempts"] = attempts
    sb().table("raw_events").update(row).eq("id", event_id).execute()


# ---------- core entities ----------
def upsert_company(ev) -> str | None:
    if not ev.company_key:
        return None
    row = _clean({"company_key": ev.company_key, "name": ev.company_name, "domain": ev.domain,
                  "employees": ev.employees, "industry": ev.industry, "linkedin_url": ev.company_linkedin})
    return sb().table("companies").upsert(row, on_conflict="company_key").execute().data[0]["id"]


def upsert_contact(ev, company_id: str | None) -> str:
    row = _clean({"contact_key": ev.contact_key, "linkedin_url": ev.linkedin_url, "first_name": ev.first_name,
                  "last_name": ev.last_name, "full_name": ev.full_name, "title": ev.title,
                  "email": ev.email, "company_id": company_id})
    return sb().table("contacts").upsert(row, on_conflict="contact_key").execute().data[0]["id"]


def insert_signal(ev, contact_id: str, company_id: str | None, raw_event_id: str, source: str) -> bool:
    row = _clean({"contact_id": contact_id, "company_id": company_id, "raw_event_id": raw_event_id,
                  "source": source, "signal_type": ev.signal_type, "text": ev.signal_text,
                  "url": ev.signal_url, "occurred_at": ev.occurred_at, "signal_hash": ev.signal_hash})
    res = sb().table("signals").upsert(row, on_conflict="signal_hash", ignore_duplicates=True).execute()
    return bool(res.data)


def recent_signals(contact_id: str, n: int = 15) -> list[dict]:
    return (sb().table("signals").select("signal_hash,signal_type,text,url,occurred_at")
            .eq("contact_id", contact_id).order("created_at", desc=True).limit(n).execute().data)


def get_contact(contact_id: str) -> dict:
    return (sb().table("contacts").select("*, companies(*)").eq("id", contact_id).single().execute().data)


def latest_score(contact_id: str) -> dict | None:
    r = (sb().table("scores").select("*").eq("contact_id", contact_id)
         .order("created_at", desc=True).limit(1).execute().data)
    return r[0] if r else None


def insert_score(row: dict) -> str:
    return sb().table("scores").insert(row).execute().data[0]["id"]


def is_suppressed(contact_key: str, company_key: str | None) -> bool:
    keys = [k for k in (contact_key, company_key) if k]
    return bool(sb().table("suppressions").select("id").in_("key", keys).limit(1).execute().data)


# ---------- messages ----------
def has_open_message(contact_id: str) -> bool:
    return bool(sb().table("messages").select("id").eq("contact_id", contact_id)
                .in_("status", OPEN_MSG_STATUSES).limit(1).execute().data)


def insert_message(row: dict) -> str:
    return sb().table("messages").insert(row).execute().data[0]["id"]


EMBED = ("*, contacts(full_name, first_name, last_name, title, email, linkedin_url, contact_key, "
         "companies(name, domain, employees, company_key)), scores(total_score, tier, breakdown)")


def list_messages(status: str, limit: int) -> list[dict]:
    return (sb().table("messages").select(EMBED).eq("status", status)
            .order("created_at").limit(limit).execute().data)


def get_message(message_id: str) -> dict | None:
    r = sb().table("messages").select(EMBED).eq("id", message_id).limit(1).execute().data
    return r[0] if r else None


def update_message(message_id: str, fields: dict, only_if_status: str | None = None) -> bool:
    q = sb().table("messages").update(fields).eq("id", message_id)
    if only_if_status:
        q = q.eq("status", only_if_status)
    return bool(q.execute().data)


def claim_message(message_id: str) -> bool:
    """Atomic: approved -> queued. Do launches ek hi message push nahi kar sakte."""
    return update_message(message_id, {"status": "queued"}, only_if_status="approved")


def audit(event: str, entity: str | None = None, entity_id: str | None = None, detail: dict | None = None) -> None:
    sb().table("audit_log").insert(_clean({"event": event, "entity": entity, "entity_id": entity_id, "detail": detail})).execute()


# ---------- reporting ----------
def count(table: str, since_iso: str | None = None, **eq) -> int:
    q = sb().table(table).select("id", count="exact")
    for k, v in eq.items():
        q = q.eq(k, v)
    if since_iso:
        q = q.gte("created_at", since_iso)
    return q.limit(1).execute().count or 0


def tier_counts() -> dict[str, int]:
    rows = sb().table("v_latest_scores").select("tier").execute().data
    out: dict[str, int] = {}
    for r in rows:
        out[r["tier"]] = out.get(r["tier"], 0) + 1
    return out
