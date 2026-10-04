"""Approved messages -> HeyReach campaign. Safety: dry-run default, per-run cap, atomic claim, suppression."""
from . import db
from .config import get_settings
from .heyreach import HeyReachClient, build_lead


def launch(campaign_id: int | None, limit: int | None, dry_run: bool = True) -> dict:
    s = get_settings()
    campaign_id = campaign_id or s.heyreach_default_campaign_id
    if not campaign_id:
        raise ValueError("campaign_id required (or set HEYREACH_DEFAULT_CAMPAIGN_ID)")
    if not dry_run and not s.heyreach_api_key:
        raise ValueError("HEYREACH_API_KEY missing")

    cap = min(limit or s.max_launch_per_run, s.max_launch_per_run)
    rows = db.list_messages("approved", cap)

    pairs, ids, skipped = [], [], []
    for m in rows:
        c = m["contacts"]
        co = c.get("companies") or {}
        if not c.get("linkedin_url"):
            skipped.append({"id": m["id"], "reason": "no linkedin_url"}); continue
        if db.is_suppressed(c["contact_key"], co.get("company_key")):
            skipped.append({"id": m["id"], "reason": "suppressed"}); continue
        if not dry_run and not db.claim_message(m["id"]):
            skipped.append({"id": m["id"], "reason": "already claimed"}); continue
        pairs.append(build_lead(c, m, s.heyreach_sender_account_id))
        ids.append(m["id"])

    summary = {"campaign_id": campaign_id, "dry_run": dry_run, "cap": cap,
               "eligible": len(pairs), "skipped": skipped}
    if dry_run:
        summary["preview"] = pairs[:3]
        return summary
    if not pairs:
        return summary

    try:
        resp = HeyReachClient(s.heyreach_api_key, s.heyreach_base_url).add_leads(campaign_id, pairs)
    except Exception as e:
        for mid in ids:
            db.update_message(mid, {"status": "failed", "push_error": str(e)[:300]})
        db.audit("campaign.push_failed", "campaign", str(campaign_id), {"error": str(e)[:300], "count": len(ids)})
        raise
    for mid in ids:
        db.update_message(mid, {"status": "pushed", "pushed_at": db.now(), "campaign_id": campaign_id})
    db.audit("campaign.pushed", "campaign", str(campaign_id), {"count": len(ids), "heyreach_response": resp})
    summary["pushed"] = len(ids)
    summary["heyreach_response"] = resp
    return summary
