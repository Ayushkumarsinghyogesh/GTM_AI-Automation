# 03. Sample Output (kaisa data milega)

⚠️ Input payload **illustrative** hai (ClearCue ka real schema verify karna baaki). Neeche ke outputs wahi hain jo engine ka logic in inputs par banata hai (score tests me verify hai).

## 1. ClearCue webhook (input)
```json
{
  "event_id": "cc_evt_8f3a1",
  "person":  {"first_name": "Priya", "last_name": "Nair", "title": "VP Security",
              "linkedin_url": "https://www.linkedin.com/in/Priya-Nair-Sec/?utm_source=x"},
  "company": {"name": "Northwind Cloud", "website": "https://www.northwindcloud.io",
              "employees": "501-1000", "industry": "Computer Software"},
  "signal":  {"type": "post_keyword",
              "text": "Our Tenable backlog hit 14,000 findings again. Exploitation windows are shrinking to days and we are still triaging by hand.",
              "detected_at": "2026-07-09T08:14:22Z"}
}
```

## 2. `POST /webhooks/clearcue` response
```json
{"stored": 1, "duplicates": 0}
```
(Same payload dobara → `{"stored": 0, "duplicates": 1}`: double-processing nahi.)

## 3. Normalized (contacts / companies / signals)
```json
{
  "contact_key": "https://www.linkedin.com/in/priya-nair-sec",
  "full_name": "Priya Nair", "title": "VP Security",
  "company_key": "northwindcloud.io", "employees": 750, "industry": "Computer Software",
  "signal_type": "post_keyword", "signal_hash": "3c1f...(40 chars)"
}
```

## 4. Score (`scores` table)
```json
{
  "thesis_score": 4, "pain_score": 11, "attendance_score": 0, "total_score": 15,
  "tier": "priority",
  "breakdown": {"title_leadership": 4, "company_fit": 2, "thesis_ai_post": 4,
                "vm_tool_frustration": 3, "uses_scanner": 2},
  "evidence": {
    "thesis_ai_post": "Exploitation windows are shrinking to days and we are still triaging by hand",
    "vm_tool_frustration": "Tenable backlog hit 14,000 findings again",
    "uses_scanner": "Tenable"
  },
  "notes": [], "model": "claude-haiku-4-5-20251001"
}
```
Tier 14+ = **priority** (Ashish khud message kare, fast-track).

## 5. Draft message (`messages`, status = `draft`)
Ye ek **example** hai; actual text Claude likhega aur guardrails pass karne padenge.
```json
{
  "hook": "Priya posted that her Tenable backlog hit 14,000 findings while exploitation windows shrink to days.",
  "evidence_quote": "Tenable backlog hit 14,000 findings again",
  "connection_note": "Priya, your post on the Tenable backlog vs shrinking exploitation windows stuck with me. I'm hosting small private sessions on exactly this at Black Hat. Worth connecting?",
  "message": "Thanks for connecting. Your point about triaging by hand while exploitation windows collapse is the gap I keep hearing about. We're hosting a few private suite sessions in Vegas on it.\n\nIf it's useful, you can grab a slot here: https://lu.ma/your-page"
}
```

## 6. Review queue (`GET /queue?status=draft`)
```json
{"count": 1, "items": [{
  "message_id": "b1c2...", "status": "draft",
  "name": "Priya Nair", "title": "VP Security", "company": "Northwind Cloud", "employees": 750,
  "score": 15, "tier": "priority", "hook": "...", "connection_note": "...", "message": "..."
}]}
```

## 7. Approve → Launch (dry-run)
`POST /messages/{id}/approve` → `{"ok": true, "status": "approved"}`

`POST /campaigns/launch {"campaign_id": 12345, "dry_run": true}`:
```json
{
  "campaign_id": 12345, "dry_run": true, "cap": 25, "eligible": 1, "skipped": [],
  "preview": [{
    "lead": {
      "firstName": "Priya", "lastName": "Nair",
      "profileUrl": "https://www.linkedin.com/in/priya-nair-sec",
      "position": "VP Security", "companyName": "Northwind Cloud", "emailAddress": "",
      "customUserFields": [
        {"name": "ai_hook", "value": "Priya posted that her Tenable backlog..."},
        {"name": "connection_note", "value": "Priya, your post on..."},
        {"name": "ai_message", "value": "Thanks for connecting..."}
      ]
    }
  }]
}
```
Live (`dry_run: false`) me `messages.status` → `queued` → `pushed`, `audit_log` me HeyReach response save.

## 8. Report (`GET /report/summary?days=7`)
```json
{
  "window_days": 7,
  "raw_events": {"pending": 0, "processed": 41, "skipped": 3, "failed": 1},
  "contacts_total": 38, "signals_in_window": 44,
  "contacts_by_tier": {"priority": 6, "standard": 11, "luma_only": 14, "drop": 7},
  "messages": {"draft": 9, "approved": 5, "rejected": 2, "queued": 0, "pushed": 8, "failed": 0}
}
```
(Numbers illustrative.)
