"""GTM Engine API. n8n / Claude Code / curl sab isi ko call karte hain."""
import logging
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Body, Depends, FastAPI, Header, HTTPException
from pydantic import BaseModel

from . import campaigns, db, pipeline
from .config import get_settings
from .heyreach import HeyReachClient
from .textutil import stable_hash

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
app = FastAPI(title="GTM Engine", version="0.1.0")


def require_key(x_api_key: str = Header(default="")) -> None:
    if not secrets.compare_digest(x_api_key, get_settings().engine_api_key):
        raise HTTPException(status_code=401, detail="invalid api key")


router = APIRouter(dependencies=[Depends(require_key)])


@app.get("/healthz")
def healthz() -> dict:
    return {"ok": True}


@router.get("/health/deps")
def health_deps() -> dict:
    s = get_settings()
    out: dict[str, Any] = {"anthropic_key_set": bool(s.anthropic_api_key),
                           "heyreach_key_set": bool(s.heyreach_api_key)}
    try:
        db.sb().table("raw_events").select("id").limit(1).execute()
        out["supabase"] = "ok"
    except Exception as e:
        out["supabase"] = f"error: {str(e)[:120]}"
    if s.heyreach_api_key:
        out["heyreach"] = "ok" if HeyReachClient(s.heyreach_api_key, s.heyreach_base_url).check_api_key() else "invalid key"
    return out


# ---------- ingest ----------
@router.post("/webhooks/clearcue", status_code=202)
def clearcue_webhook(payload: Any = Body(...)) -> dict:
    """Fast: sirf raw store. Processing alag (/process/pending). Duplicate webhook safe."""
    items = payload if isinstance(payload, list) else [payload]
    stored = dup = 0
    for item in items:
        if db.insert_raw_event("clearcue", item, stable_hash(item)):
            stored += 1
        else:
            dup += 1
    return {"stored": stored, "duplicates": dup}


@router.post("/process/pending")
def process_pending(limit: int = 20) -> dict:
    return pipeline.process_pending(limit=min(max(limit, 1), 100))


# ---------- human review ----------
def _flat(m: dict) -> dict:
    c = m.get("contacts") or {}
    co = c.get("companies") or {}
    sc = m.get("scores") or {}
    return {"message_id": m["id"], "status": m["status"], "name": c.get("full_name"), "title": c.get("title"),
            "company": co.get("name"), "employees": co.get("employees"), "linkedin_url": c.get("linkedin_url"),
            "score": sc.get("total_score"), "tier": sc.get("tier"), "breakdown": sc.get("breakdown"),
            "hook": m["hook"], "connection_note": m["connection_note"], "message": m["message"]}


@router.get("/queue")
def queue(status: str = "draft", limit: int = 20) -> dict:
    rows = [_flat(m) for m in db.list_messages(status, min(limit, 100))]
    rows.sort(key=lambda r: -(r["score"] or 0))
    return {"count": len(rows), "items": rows}


class Review(BaseModel):
    reviewer: str
    edited_message: str | None = None
    edited_connection_note: str | None = None
    reason: str | None = None


@router.post("/messages/{message_id}/approve")
def approve(message_id: str, body: Review) -> dict:
    fields: dict = {"status": "approved", "reviewer": body.reviewer, "reviewed_at": db.now()}
    if body.edited_message:
        fields["message"] = body.edited_message
    if body.edited_connection_note:
        fields["connection_note"] = body.edited_connection_note
    if not db.update_message(message_id, fields, only_if_status="draft"):
        raise HTTPException(409, "message not found or not in draft status")
    db.audit("message.approved", "message", message_id, {"by": body.reviewer, "edited": bool(body.edited_message)})
    return {"ok": True, "status": "approved"}


@router.post("/messages/{message_id}/reject")
def reject(message_id: str, body: Review) -> dict:
    fields = {"status": "rejected", "reviewer": body.reviewer, "reviewed_at": db.now(), "reject_reason": body.reason}
    if not db.update_message(message_id, fields, only_if_status="draft"):
        raise HTTPException(409, "message not found or not in draft status")
    db.audit("message.rejected", "message", message_id, {"by": body.reviewer, "reason": body.reason})
    return {"ok": True, "status": "rejected"}


# ---------- launch ----------
class Launch(BaseModel):
    campaign_id: int | None = None
    limit: int | None = None
    dry_run: bool = True   # default SAFE


@router.post("/campaigns/launch")
def launch(body: Launch) -> dict:
    try:
        return campaigns.launch(body.campaign_id, body.limit, body.dry_run)
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        raise HTTPException(502, f"heyreach push failed: {str(e)[:200]}")


# ---------- reporting ----------
@router.get("/report/summary")
def report(days: int = 7) -> dict:
    since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    return {
        "window_days": days,
        "raw_events": {st: db.count("raw_events", since, status=st)
                       for st in ("pending", "processed", "skipped", "failed")},
        "contacts_total": db.count("contacts"),
        "signals_in_window": db.count("signals", since),
        "contacts_by_tier": db.tier_counts(),
        "messages": {st: db.count("messages", since, status=st)
                     for st in ("draft", "approved", "rejected", "queued", "pushed", "failed")},
    }


app.include_router(router)
