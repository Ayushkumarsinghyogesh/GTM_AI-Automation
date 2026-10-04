# 01. Architecture + Meri Soch (Hinglish)

## 1. Idea ek line me
> **ClearCue** bolta hai "ye banda abhi interested lag raha hai" → **n8n** us khabar ko pakadta hai →
> **Engine** (Python) sochta hai (score + Claude se message) → **Supabase** sab yaad rakhta hai →
> **Insaan (Ashish/tum) approve** karta hai → **HeyReach** LinkedIn pe bhejta hai.

Golden rule: **n8n = pipes (naliyan). Python engine = brain (dimaag). Supabase = memory (yaaddasht).**
Isse n8n me spaghetti nahi banta, aur logic ko Claude Code se edit + test kar sakte ho.

## 2. Recommended architecture (jo code me bana hai)

```
                        ┌──────────────┐
   LinkedIn/News/Jobs → │   ClearCue   │  signals dhundta hai (AI qualification + signal stacking)
                        └──────┬───────┘
                               │ webhook (POST JSON)
                        ┌──────▼───────┐
                        │  n8n  #1     │  receive → retry(3x) → forward → "ok" reply
                        └──────┬───────┘
                               │
                 ┌─────────────▼──────────────┐
                 │  ENGINE (FastAPI)           │
                 │  /webhooks/clearcue         │──► raw_events   (jo aaya wahi store, dedupe)
                 └─────────────┬──────────────┘
      n8n #2 (har 2 min) ─────►│ /process/pending
                 ┌─────────────▼──────────────┐
                 │ normalize → upsert →        │──► companies / contacts / signals
                 │ Claude classify (Haiku)     │
                 │ score (rubric, no LLM)      │──► scores  (tier: priority/standard/luma_only/drop)
                 │ Claude write (Sonnet)       │
                 │ guardrails (grounding etc.) │──► messages (status = draft)
                 └─────────────┬──────────────┘
                               │
                 ┌─────────────▼──────────────┐
                 │  HUMAN REVIEW (approve)     │  Claude Code /review  ya  Supabase Studio
                 └─────────────┬──────────────┘
      n8n #3 (weekday 10:00) ─►│ /campaigns/launch  (dry-run default, cap 25/run)
                 ┌─────────────▼──────────────┐
                 │  HeyReach campaign          │  LinkedIn connect + message (custom variables)
                 └─────────────────────────────┘
        Claude Code (terminal) = tumhara remote control: /process /review /launch /report
```

## 3. Har layer: kya karta hai, kyu ye tool, alternatives

| Layer | Hamara choice | Kyu | Alternatives (kab lena) |
|---|---|---|---|
| Signals | **ClearCue** | Natural language me signal batao, AI qualify karta hai, webhook + MCP + CSV deta hai | **Trigify** (LinkedIn engagement me strong), **Clay** (flexible waterfall, technical team), **Common Room** (community/product signals), **Bombora/6sense** (enterprise intent, mehnga) |
| Automation glue | **n8n** | Self-host, webhook + schedule + retry visual, cheap | **Make/Zapier** (easy par mehnge at volume), **Temporal / Prefect / Dagster / Airflow** (code-first, scale ke liye), **Inngest / Trigger.dev** (serverless jobs) |
| Brain | **FastAPI (Python)** | Testable, versioned, Claude Code se edit easy, ML libraries same language me | Node/TypeScript same kaam karega; agar sirf low-code chahiye to n8n Code node (par test mushkil) |
| Database | **Supabase (Postgres)** | Postgres + REST + Studio UI + MCP, free tier, pgvector later | **Neon / RDS / Cloud SQL** (plain Postgres), **BigQuery/Snowflake** (analytics scale), **ClickHouse** (heavy event analytics) |
| LLM | **Claude** (Haiku classify, Sonnet write) | Tool-use se structured JSON, instruction following strong, cheap+fast split | Same pattern OpenAI/Gemini par bhi chalta; **fine-tuned small model** baad me classification ke liye |
| Outreach (LinkedIn) | **HeyReach** | Multi-account sender rotation, API se leads add, custom variables | **Expandi, Lemlist, Dripify, Waalaxy** (UI-first), **Unipile** (API-level LinkedIn, zyada control par zyada kaam) |
| Email (Phase 2) | (abhi nahi) | | **Smartlead / Instantly** + ZeroBounce verify |
| Hosting | Docker (Railway/Fly/Render) | Simple deploy | **AWS ECS/Fargate, GCP Cloud Run** production scale |
| Observability | audit_log + n8n executions | Phase 1 kaafi | **Sentry, Langfuse (LLM traces), Metabase (dashboards), promptfoo (prompt evals)** |

## 4. Multiple architectures: tum kaunsa choose karo?

### A. Low-code lean (sabse jaldi, fragile)
`ClearCue → n8n (Claude node + Supabase node + HeyReach HTTP) → done`
- ✅ 1 din me chal jata hai, prototype/demo ke liye best.
- ❌ Logic n8n canvas me bikhra, testing/versioning weak, debugging mushkil, Claude Code se edit karna painful.
- Kab: Sirf proof-of-concept ya client ko demo dikhana ho.

### B. **Hybrid: n8n thin + Python engine + Supabase** ✅ (RECOMMENDED, yehi bana hai)
- ✅ Production-grade balance: visual scheduling/retries + real code + tests.
- ✅ Claude Code se poora repo operate hota hai. Naya channel (email) add karna easy.
- ❌ 2 services maintain karni padti hain (engine + n8n).
- Kab: Phase 1 se lekar ~10k signals/day tak.

### C. Code-first + real queue (no n8n)
`ClearCue → FastAPI → Postgres queue (pgmq/SKIP LOCKED) ya Redis+Celery/Arq → workers → HeyReach` ; orchestration: **Temporal / Prefect**
- ✅ Strong retries, backpressure, exactly-once jaisi guarantees, high throughput.
- ❌ Non-technical teammates flow nahi dekh paate; ops overhead.
- Kab: Volume badhe, multi-client agency, ya n8n bottleneck bane.

### D. Data-platform / ML-first (learning ke liye best)
`ClearCue → webhook → Supabase (raw) → dbt → warehouse (BigQuery/Snowflake) → features → ML model (lead score) → reverse-ETL (Hightouch/Census) → HubSpot/HeyReach`
- ✅ Outcome data (reply, sandbox signup, cloud-connect) se **learned scoring**, cohort analysis, A/B test messages.
- ❌ Heavy; data kam ho to over-engineering.
- Kab: 3-6 mahine ka outcome data jama ho jaye (Gate 2 ke baad).

### E. Agentic (Claude as operator)
Claude Code + MCP tools (ClearCue MCP, Supabase MCP, HeyReach MCP) — "batao is hafte ke best 20 leads aur draft karo".
- ✅ Exploration, ad-hoc research, ops ke liye zabardast (ye bhi humne Claude Code commands se rakha hai).
- ❌ Non-deterministic: **bhejne wale critical step ko agent ke bharose mat chhodo.**
- Kab: B ke **upar** operator layer ki tarah, replacement ki tarah nahi.

> **Meri salah:** B se shuru karo → data jama hone par D ke parts (dbt + ML scoring) jodo → volume badhe to C ke parts (queue/Temporal). E hamesha operator layer rahe.

## 5. Accuracy kaise badhti hai ("perfect users" tak kaise pahunchein)
Ek tool pe bharosa nahi, **5 layers** lagti hain:
1. **ClearCue AI qualification + signal stacking**: pehle hi kachra kam.
2. **Deterministic rubric** (`config/gtm.yaml`): Black Hat file ke points as-is. Explainable: "kyu 15 mile" har row me `breakdown` + `evidence`.
3. **Claude classify with evidence**: `fires=true` tabhi jab quote source text me milta ho (`grounded()` check).
4. **Guardrails on messages**: quote grounded, length, banned phrases, no links; fail → tier `luma_only` (rubric ka "no genuine hook = Luma only" rule).
5. **Human approval**: Ashish ka sign-off (non-negotiable) + suppression list + per-run cap + dry-run default.

Aur **measure** karo: 50-100 contacts ka **golden set** manually label karo (sahi fit / galat fit) → precision/recall by tier nikalo → rubric/prompt tune karo. Bina measurement ke "accuracy" sirf feeling hai.

## 6. Scale roadmap + improvements

**Phase 1 (ab):** jo code me hai.
**Phase 1.5 (1-2 hafte):**
- Reply loop: HeyReach webhooks → Supabase → reply classify → Slack alert.
- n8n Error Workflow → Slack; Metabase on `v_latest_scores`, `v_review_queue`.
- Enrichment waterfall (Apify/Serper/Firecrawl/ZeroBounce jaisa Planned Deliverables D2 me hai).
- `workspace_id` column har table me (agar OneGTM multiple clients chalaye).
**Phase 2:**
- Email channel (Smartlead) + channel router (LinkedIn vs email by data quality).
- HubSpot sync: **sirf scoring decisions** (signal_score, tier_flag), raw data nahi (spec ke mutabik).
- Queue (pgmq/Temporal) replace cron polling.
**Phase 3 (AI/ML, flagged):**
- 🤖 **ML lead scoring**: outcomes (reply/MQL/SQL) se logistic regression → gradient boosting; rubric ko baseline rakho, model ko calibrate karo (AUC, precision@k).
- 🤖 **Reply intent classifier** (interested / not now / wrong person / unsubscribe) + auto-suppression.
- 🤖 **Message A/B + bandit**: prompt versions ko reply-rate se compare.
- 🤖 **pgvector**: "mere best customers jaise similar accounts" embeddings search.
- 🤖 **LLM eval harness** (promptfoo/Langfuse): har prompt change pe regression check.

## 7. Risks (seedhi baat)
- **LinkedIn automation ToS risk**: account restriction ho sakta hai. Volume low rakho, sender accounts rotate, HeyReach limits follow karo. Ye engineering se poori tarah hat nahi sakta.
- **Privacy/consent**: EU contacts (GDPR) aur email (CAN-SPAM) ke rules; suppression list use karo, opt-out fast honour karo. Legal review Ashish/OneGTM ka zimma.
- **Unverified integrations**: ClearCue payload schema aur HeyReach payload field names maine docs se pura verify nahi kiye (sirf auth/limits/endpoint confirmed). Pehle real webhook + 1-lead dry test karo.
- **LLM galti**: isliye grounding + human approval. Kabhi auto-send mat karo.
