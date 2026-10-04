# GTM Engine (Phase 1)
ClearCue → n8n → Engine (FastAPI) → Supabase → Claude → human approval → HeyReach.
Claude Code se operate hota hai (`CLAUDE.md` + `.claude/commands/`).

**Padhne ka order:** `docs/01_ARCHITECTURE.md` → `docs/02_GUIDE.md` → `docs/03_SAMPLE_OUTPUT.md`

Quick start:
```bash
cp .env.example .env   # keys bharo
make install && make test
make run         cla      # engine :8000
./scripts/gtm.sh health
./scripts/gtm.sh ingest-sample && ./scripts/gtm.sh process && ./scripts/gtm.sh queue
```
Safety: live push default OFF (dry-run), sirf approved messages, per-run cap, suppression list.
Verify pending: ClearCue real payload schema, HeyReach `AddLeadsToCampaignV2` field names (guide Step 8, Troubleshooting).
