# 02. Setup Guide: zero se live tak (Hinglish, step by step)

Time: ~2-3 ghante pehli baar. Har step ke baad "✅ check" karo, tab aage badho.

## Step 0: Kya chahiye
- Python 3.12+, Docker, Git, **Claude Code** (terminal)
- Accounts: Supabase, Anthropic API key, ClearCue, HeyReach (API key), (optional) Railway
- ClearCue me kam se kam **1 signal** ban chuka ho (jaise "VM tool se frustration wali LinkedIn posts")
- HeyReach me **1 campaign** bana ho (connect request + message). Campaign ke message me ye variables use karo:
  - connection note: `{connection_note}`
  - first message: `{ai_message}`
  (HeyReach me custom variable ka exact syntax apne editor me dekh lo: Add variable → custom fields. Naam wahi rakhna: `connection_note`, `ai_message`, `ai_hook`.)
- Campaign ko **empty list** ke saath launch/paused rakho; hum leads API se daalenge.

## Step 1: Project khol ke Claude Code start karo
```bash
cd gtm-engine
cp .env.example .env        # .env bharo (neeche step 2-4 me)
claude                      # Claude Code start
```
Claude Code `CLAUDE.md` khud padh leta hai. Ab tum bol sakte ho: "/setup-check", "/review", "/launch 12345" (commands `.claude/commands/` me hain).

## Step 2: Supabase
1. New project banao → **SQL Editor** → `supabase/migrations/0001_init.sql` ka content paste → Run.
2. Project Settings → API se `URL` aur **service_role key** copy → `.env` me `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`.
   ⚠️ service_role key sirf server pe; frontend/git me kabhi nahi.
✅ check: Table Editor me `raw_events, contacts, signals, scores, messages...` dikhne chahiye.

## Step 3: Claude + Engine keys
- `.env`: `ANTHROPIC_API_KEY=...`
- `ENGINE_API_KEY` = koi lambi random string (`openssl rand -hex 32`)
- `config/gtm.yaml` me `luma_url` apna Luma link daalo.

## Step 4: HeyReach
- HeyReach → Settings → Integrations → Public API → **New API key** → `.env` me `HEYREACH_API_KEY`.
- Campaign ID: campaign URL/API se nikalo → `.env` me `HEYREACH_DEFAULT_CAMPAIGN_ID` (uncomment karo).
- Optional: specific sender account ID → `HEYREACH_SENDER_ACCOUNT_ID`.

## Step 5: Local run + tests
```bash
make install
make test          # 16 tests pass hone chahiye
make run           # http://localhost:8000
./scripts/gtm.sh health
```
✅ check: `health` me `supabase: ok`, `heyreach: ok`, `anthropic_key_set: true`.

## Step 6: End-to-end demo (sample data se)
```bash
./scripts/gtm.sh ingest-sample     # fake ClearCue webhook
./scripts/gtm.sh process           # score + Claude draft
./scripts/gtm.sh queue draft       # draft dekho
```
Ya Claude Code me sirf bolo: `/ingest-sample`. Output ka example `docs/03_SAMPLE_OUTPUT.md` me hai.
✅ check: 1 contact, tier `priority`, ek draft message jisme hook aur Luma link ho.

## Step 7: n8n + ClearCue webhook
```bash
make up            # engine + n8n docker me
```
1. `http://localhost:5678` kholo → owner account.
2. **Credentials** → New → *Header Auth* → Name: `Engine API Key`; Header name: `X-API-Key`; Value: tumhara `ENGINE_API_KEY`.
3. **Import** teeno workflow (`n8n/workflows/*.json`). Har HTTP node me credential `Engine API Key` select karo.
4. Workflow 01 me webhook `path` ko random banao (jaise `clearcue-9f83kd72`). Workflow **Activate** karo.
5. **Production webhook URL** copy karo (`https://<tumhara-n8n>/webhook/clearcue-9f83kd72`).
   ⚠️ Local pe ClearCue ye URL reach nahi karega. Iske liye n8n ko Railway/VPS pe deploy karo (ya temporary tunnel: `cloudflared`/`ngrok`).
6. ClearCue → Integrations → **Webhook** → ye URL daalo.
7. Workflow 02 (process pending) Activate. Workflow 03 abhi **inactive** rakho.
✅ check: ClearCue se test event bhejo → n8n Executions me green → `raw_events` me row.

## Step 8: Pehla REAL payload fix (bahut zaroori)
Real webhook aane ke baad Claude Code me: `/fix-normalizer`.
Ye `raw_events.payload` dekh ke `normalize.py` ka `FIELD_MAP` tight kar dega, aur test update karega.
Jab tak ye nahi hota, `skipped` events aa sakte hain ("no linkedin url or email").

## Step 9: Review → approve → launch
```
/review                  # Claude Code drafts dikhata hai, tum IDs batao
/launch 12345            # pehle DRY RUN preview
/launch 12345 --live     # confirmation ke baad hi
```
- Approval ka asli maalik **Ashish** (rubric ka rule). Reviewer name `.env` me `GTM_REVIEWER`.
- Pehle **sirf 3-5 leads** live bhejo, HeyReach dashboard me check karo (variables sahi bhare?), phir badhao.
- Workflow 03 me `campaign_id: 0` ko apne ID se badlo; jab confident ho tab `dry_run` ko `false` karo.

## Step 10: Deploy (production)
- **Railway** (ya Fly/Render): 2 services: `engine` (Dockerfile) + `n8n`. Env vars dashboard me daalo.
- n8n ko persistent volume do; `N8N_ENCRYPTION_KEY` kabhi mat badlo (credentials decrypt nahi honge).
- Engine URL n8n me internal hostname se (docker-compose me `http://engine:8000`; Railway me private networking URL).
- Scale par n8n ko Postgres pe chalao (SQLite chhod ke).

## Roz ka routine (5 minute)
1. `/report` → kal ka summary
2. `/review` → naye drafts approve/reject
3. `/launch <id>` → dry-run → live (chhote batch)

## Kaise customize karein (code chhue bina)
| Kya badalna hai | Kahan |
|---|---|
| Points / tiers | `config/gtm.yaml` → `signals`, `tiers` |
| Kis title ko drop/keep | `title_rules` |
| Company size/industry | `company_fit` |
| Message ka tone/rules | `brand.message_rules` (phir `PROMPT_VERSION` bump) |
| Max sends per run | `.env` `MAX_LAUNCH_PER_RUN` |
| Kisi ko kabhi contact na karo | Supabase `suppressions` table (`kind='contact'|'company'`, `key=contact_key/company_key`) |

## Troubleshooting
| Problem | Reason / fix |
|---|---|
| `401 invalid api key` | n8n credential ya `.env` ka `ENGINE_API_KEY` mismatch |
| Events `skipped` | payload me linkedin/email nahi mila → `/fix-normalizer` |
| Events `failed` | `raw_events.error` padho; 3 attempts ke baad ruk jata hai |
| Sab `luma_only` | Claude key nahi, ya hook grounded nahi bana → `scores.notes` dekho |
| HeyReach 400 | `build_lead` ke field names Postman docs se match karo |
| HeyReach 429 | Rate limit (300/min); client auto-retry karta hai |
| Duplicate contact | `contact_key` = normalized LinkedIn URL; alag URL format ho to `norm_linkedin` check |

## Seekhne ka plan (tumhare Data/ML goal ke liye)
1. **Week 1:** ye pipeline chalao, code padho (`normalize → scoring → pipeline`). Idempotency, retries, upsert samjho.
2. **Week 2:** 50 contacts ka golden set label karo; script likho jo tier vs label ka precision/recall nikale.
3. **Week 3:** outcomes (reply/signup) `messages` se jodo; pandas me analysis; Metabase dashboard.
4. **Week 4+:** 🤖 logistic regression lead-score (scikit-learn), phir prompt A/B, phir dbt + warehouse (Architecture D).
