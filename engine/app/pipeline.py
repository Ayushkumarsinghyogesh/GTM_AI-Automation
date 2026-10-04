"""Raw event -> contact -> signals -> classify -> score -> (draft message)."""
import logging

from . import db
from .classify import classify_keywords, classify_with_claude, corpus_of
from .config import get_settings
from .gtm_config import cfg
from .normalize import normalize
from .personalize import PROMPT_VERSION, generate_draft
from .scoring import score_contact
from .textutil import stable_hash

log = logging.getLogger("pipeline")


def _ctx(contact: dict, signals: list[dict]) -> dict:
    co = contact.get("companies") or {}
    return {
        "person": {"name": contact.get("full_name"), "title": contact.get("title")},
        "title": contact.get("title"),
        "company": {"name": co.get("name"), "domain": co.get("domain"),
                    "employees": co.get("employees"), "industry": co.get("industry")},
        "signals": [{"type": s.get("signal_type"), "text": s.get("text"),
                     "url": s.get("url"), "date": s.get("occurred_at")} for s in signals],
    }


def process_event(ev_row: dict) -> dict:
    s = get_settings()
    events = normalize(ev_row["payload"])
    if not events:
        db.mark_event(ev_row["id"], "skipped", error="no linkedin url or email in payload")
        return {"status": "skipped"}

    contact_id = None
    company_id = None
    for ev in events:
        company_id = db.upsert_company(ev)
        contact_id = db.upsert_contact(ev, company_id)
        db.insert_signal(ev, contact_id, company_id, ev_row["id"], ev_row["source"])

    contact = db.get_contact(contact_id)
    signals = db.recent_signals(contact_id)
    ctx = _ctx(contact, signals)

    # Same input pe dobara Claude call nahi (cost + stability)
    input_hash = stable_hash([contact.get("title"), ctx["company"], sorted(x["signal_hash"] for x in signals)])
    prev = db.latest_score(contact_id)
    if prev and prev.get("input_hash") == input_hash:
        db.mark_event(ev_row["id"], "processed")
        return {"status": "processed", "contact_id": contact_id, "tier": prev["tier"], "note": "unchanged"}

    # 1) classify
    model_used = "keywords"
    try:
        if s.anthropic_api_key:
            hits_raw = classify_with_claude(s.anthropic_api_key, s.claude_model_classify, ctx)
            model_used = s.claude_model_classify
        else:
            hits_raw = classify_keywords(ctx)
    except Exception as e:  # Claude down => keyword fallback, pipeline rukti nahi
        log.warning("claude classify failed, fallback to keywords: %s", e)
        hits_raw = classify_keywords(ctx)
    hits = {k: v["fires"] for k, v in hits_raw.items()}
    evidence = {k: v["evidence"] for k, v in hits_raw.items() if v["fires"]}

    # 2) score
    res = score_contact(contact.get("title"), (contact.get("companies") or {}).get("employees"),
                        (contact.get("companies") or {}).get("industry"), hits)
    tier, notes = res.tier, list(res.notes)

    # 3) draft (sirf outreach tiers, suppression/duplicate check ke baad)
    draft = None
    if tier in cfg()["outreach_tiers"]:
        co = contact.get("companies") or {}
        if db.is_suppressed(contact["contact_key"], co.get("company_key")):
            tier = "drop"; notes.append("suppressed")
        elif db.has_open_message(contact_id):
            notes.append("open message already exists")
        elif not s.anthropic_api_key:
            tier = "luma_only"; notes.append("no ANTHROPIC_API_KEY: cannot draft")
        else:
            draft = generate_draft(s.anthropic_api_key, s.claude_model_write, ctx, corpus_of(ctx))
            if draft is None:
                tier = "luma_only"; notes.append("no grounded hook: downgraded (rubric rule)")

    score_id = db.insert_score({
        "contact_id": contact_id, "thesis_score": res.thesis, "pain_score": res.pain,
        "attendance_score": res.attendance, "total_score": res.total, "tier": tier,
        "breakdown": res.breakdown, "evidence": evidence, "notes": notes,
        "input_hash": input_hash, "model": model_used,
    })
    msg_id = None
    if draft:
        msg_id = db.insert_message({
            "contact_id": contact_id, "score_id": score_id, "status": "draft",
            "hook": draft.hook, "evidence_quote": draft.evidence_quote,
            "connection_note": draft.connection_note, "message": draft.message,
            "model": draft.model, "prompt_version": PROMPT_VERSION,
        })
    db.mark_event(ev_row["id"], "processed")
    return {"status": "processed", "contact_id": contact_id, "tier": tier,
            "total": res.total, "draft_id": msg_id}


def process_pending(limit: int = 20) -> dict:
    s = get_settings()
    rows = db.fetch_pending_events(limit, s.max_event_attempts)
    out = {"picked": len(rows), "processed": 0, "skipped": 0, "failed": 0, "drafts_created": 0, "results": []}
    for r in rows:
        try:
            res = process_event(r)
        except Exception as e:
            log.exception("event %s failed", r["id"])
            db.mark_event(r["id"], "failed", error=str(e)[:500], attempts=(r.get("attempts") or 0) + 1)
            out["failed"] += 1
            continue
        out[res["status"]] = out.get(res["status"], 0) + 1
        out["drafts_created"] += 1 if res.get("draft_id") else 0
        out["results"].append(res)
    return out
