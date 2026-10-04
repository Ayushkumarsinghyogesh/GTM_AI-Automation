-- GTM Engine schema. Supabase SQL Editor me run karo (ya `supabase db push`).
-- Rule: applied migration ko edit mat karo. Naya change = naya file (0002_...).

-- ============ RAW LAYER (jo aaya wahi, bina chhede) ============
create table if not exists raw_events (
  id            uuid primary key default gen_random_uuid(),
  source        text not null,
  payload       jsonb not null,
  payload_hash  text not null unique,           -- idempotency: same webhook 2 baar aaye to ek hi row
  status        text not null default 'pending'
                check (status in ('pending','processed','skipped','failed')),
  attempts      int  not null default 0,
  error         text,
  received_at   timestamptz not null default now(),
  processed_at  timestamptz
);
create index if not exists raw_events_status_idx on raw_events (status, received_at);

-- ============ CORE LAYER ============
create table if not exists companies (
  id           uuid primary key default gen_random_uuid(),
  company_key  text not null unique,            -- domain ya lowercase name
  name         text,
  domain       text,
  employees    int,
  industry     text,
  linkedin_url text,
  created_at   timestamptz not null default now(),
  updated_at   timestamptz not null default now()
);

create table if not exists contacts (
  id           uuid primary key default gen_random_uuid(),
  contact_key  text not null unique,            -- normalized linkedin url ya email
  linkedin_url text,
  first_name   text,
  last_name    text,
  full_name    text,
  title        text,
  email        text,
  company_id   uuid references companies(id) on delete set null,
  created_at   timestamptz not null default now(),
  updated_at   timestamptz not null default now()
);
create index if not exists contacts_company_idx on contacts (company_id);

create table if not exists signals (
  id           uuid primary key default gen_random_uuid(),
  contact_id   uuid not null references contacts(id) on delete cascade,
  company_id   uuid references companies(id) on delete set null,
  raw_event_id uuid references raw_events(id) on delete set null,
  source       text not null,
  signal_type  text,
  text         text,
  url          text,
  occurred_at  timestamptz,
  signal_hash  text not null unique,
  created_at   timestamptz not null default now()
);
create index if not exists signals_contact_idx on signals (contact_id, created_at desc);

create table if not exists scores (
  id               uuid primary key default gen_random_uuid(),
  contact_id       uuid not null references contacts(id) on delete cascade,
  thesis_score     int not null,
  pain_score       int not null,
  attendance_score int not null,
  total_score      int not null,
  tier             text not null check (tier in ('priority','standard','luma_only','drop')),
  breakdown        jsonb not null,               -- {"title_leadership": 4, ...}
  evidence         jsonb not null default '{}',  -- {"thesis_ai_post": "quote..."}
  notes            text[] not null default '{}',
  input_hash       text,                         -- same input pe Claude dobara call nahi
  model            text,
  created_at       timestamptz not null default now()
);
create index if not exists scores_contact_idx on scores (contact_id, created_at desc);

create table if not exists messages (
  id              uuid primary key default gen_random_uuid(),
  contact_id      uuid not null references contacts(id) on delete cascade,
  score_id        uuid references scores(id) on delete set null,
  status          text not null default 'draft'
                  check (status in ('draft','approved','rejected','queued','pushed','failed')),
  hook            text not null,
  evidence_quote  text not null,
  connection_note text not null,
  message         text not null,
  model           text,
  prompt_version  text,
  reviewer        text,
  reviewed_at     timestamptz,
  reject_reason   text,
  campaign_id     bigint,
  pushed_at       timestamptz,
  push_error      text,
  created_at      timestamptz not null default now(),
  updated_at      timestamptz not null default now()
);
-- ek contact ka ek hi "active" message ho sakta hai (double-send se bachav)
create unique index if not exists one_open_message_per_contact
  on messages (contact_id) where status in ('draft','approved','queued','pushed');
create index if not exists messages_status_idx on messages (status, created_at);

create table if not exists suppressions (         -- inhe kabhi contact mat karo
  id         uuid primary key default gen_random_uuid(),
  kind       text not null check (kind in ('contact','company')),
  key        text not null unique,                -- contact_key ya company_key
  reason     text,
  created_at timestamptz not null default now()
);

create table if not exists audit_log (
  id         bigserial primary key,
  event      text not null,
  entity     text,
  entity_id  text,
  detail     jsonb,
  created_at timestamptz not null default now()
);

-- ============ updated_at trigger ============
create or replace function set_updated_at() returns trigger as $$
begin new.updated_at = now(); return new; end;
$$ language plpgsql;

do $$
declare t text;
begin
  foreach t in array array['companies','contacts','messages'] loop
    execute format('drop trigger if exists trg_%1$s_updated on %1$s', t);
    execute format('create trigger trg_%1$s_updated before update on %1$s
                    for each row execute function set_updated_at()', t);
  end loop;
end $$;

-- ============ VIEWS (Metabase / Supabase Studio / Claude MCP ke liye) ============
create or replace view v_latest_scores as
  select distinct on (contact_id) *
  from scores order by contact_id, created_at desc;

create or replace view v_review_queue as
  select m.id as message_id, m.status, c.full_name, c.title, co.name as company,
         co.employees, s.total_score, s.tier, m.hook, m.connection_note, m.message, m.created_at
  from messages m
  join contacts c on c.id = m.contact_id
  left join companies co on co.id = c.company_id
  left join scores s on s.id = m.score_id
  where m.status = 'draft'
  order by s.total_score desc nulls last, m.created_at;

-- ============ SECURITY ============
-- Engine service_role key use karta hai (RLS bypass). anon/authenticated ko kuch nahi milega.
alter table raw_events   enable row level security;
alter table companies    enable row level security;
alter table contacts     enable row level security;
alter table signals      enable row level security;
alter table scores       enable row level security;
alter table messages     enable row level security;
alter table suppressions enable row level security;
alter table audit_log    enable row level security;
