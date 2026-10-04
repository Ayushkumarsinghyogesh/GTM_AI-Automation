# GTM Engine: Claude Code project guide

Owner ko **Hinglish** me simple words me jawab do. Code/comments English ya Hinglish, dono theek.

## Kya hai ye project
Signal-to-outreach engine. Flow:
ClearCue (signals) -> n8n webhook -> Engine API (FastAPI) -> Supabase (data) -> Claude (classify + message)
-> human approval -> HeyReach (LinkedIn campaign).

n8n = sirf pipes/scheduler. Saara logic `engine/app/` me (testable). Supabase = single source of truth.

## Folder map
- `config/gtm.yaml`: rubric, tiers, brand, message rules. Behaviour badalna ho to pehle yahin dekho.
- `engine/app/normalize.py`: ClearCue payload -> standard format (`FIELD_MAP`)
- `engine/app/classify.py`: Claude signal classification (+ keyword fallback)
- `engine/app/scoring.py`: deterministic points/tier (no LLM)
- `engine/app/personalize.py`: Claude message + guardrails (grounding, length, banned phrases)
- `engine/app/heyreach.py`: HeyReach client + payload builder (`build_lead`)
- `engine/app/pipeline.py`, `campaigns.py`, `db.py`, `main.py`
- `supabase/migrations/`: SQL (naye change = naya numbered file, purani file edit mat karo)
- `n8n/workflows/`: importable workflow JSONs
- `scripts/gtm.sh`: CLI wrapper (health/process/queue/approve/launch/report)

## Hard rules (kabhi todna nahi)
1. HeyReach pe live push tabhi jab user ne **explicitly "live" bola**. Default hamesha `dry_run=true`.
2. Sirf `approved` messages push hote hain. Kabhi status manually `approved` mat karo user ke bina.
3. Secrets (`.env`, API keys) kabhi print/log/commit mat karo.
4. Message me links LLM se mat likhwao; CTA link code append karta hai.
5. Code badalne ke baad `make test` chalao. Tests fail ho to aage mat badho.
6. Claude ke output ko trust mat karo: grounding check (`textutil.grounded`) hatana nahi.
7. DB schema change = naya migration file + user ko batao ki Supabase me run karna hai.

## Common tasks
- Naya signal type / points badalna: `config/gtm.yaml` (+ agar classifiable hai to `classify.KEYWORDS` fallback).
- ClearCue ka real payload aaya: `/fix-normalizer`.
- Message style badalna: `brand.message_rules` in gtm.yaml, phir `personalize.PROMPT_VERSION` bump karo.
- Daily ops: `/process`, `/review`, `/launch`, `/report`.

## Known unknowns (verify karo, guess mat karo)
- ClearCue webhook ka exact JSON schema (sample sirf illustrative hai).
- HeyReach `AddLeadsToCampaignV2` ke exact field names: Postman docs se match karo (`heyreach.build_lead`).
- HeyReach response me `failedLeadsCount` jaisa kuch aaye to audit_log check karo.
