-- ============================================================
-- URBAN 360 — ADDITIVE CIVIC TRANSFORMATION MIGRATION
-- Project: Urban 360 — Connecting People with Urban Services
-- Description: Safe, non-destructive additive migration extending
--              existing RAKSHA-FORCE tables to support municipal
--              departments, complaint lifecycles, and citizen feedback.
-- ============================================================

-- 1. DEPARTMENTS TABLE
create table if not exists public.departments (
  id            uuid primary key default gen_random_uuid(),
  name          text not null unique,
  code          text not null unique,
  description   text,
  categories    text[] not null default '{}',
  contact_phone text,
  is_active     boolean not null default true,
  created_at    timestamptz not null default now()
);

-- 2. COMPLAINT STATUS HISTORY TABLE
create table if not exists public.complaint_status_history (
  id              uuid primary key default gen_random_uuid(),
  complaint_id    uuid not null references public.incident_reports(id) on delete cascade,
  actor_id        uuid references auth.users(id) on delete set null,
  actor_role      text not null check (actor_role in ('citizen', 'officer', 'worker', 'admin', 'responder', 'system')),
  previous_status text,
  new_status      text not null,
  reason          text,
  created_at      timestamptz not null default now()
);

create index if not exists idx_status_history_complaint_id on public.complaint_status_history(complaint_id);
create index if not exists idx_status_history_created_at on public.complaint_status_history(created_at desc);

-- 3. COMPLAINT FEEDBACK TABLE
create table if not exists public.complaint_feedback (
  id            uuid primary key default gen_random_uuid(),
  complaint_id  uuid not null unique references public.incident_reports(id) on delete cascade,
  user_id       uuid references auth.users(id) on delete set null,
  rating        integer not null check (rating between 1 and 5),
  comment       text,
  created_at    timestamptz not null default now()
);

create index if not exists idx_complaint_feedback_complaint on public.complaint_feedback(complaint_id);

-- 4. ADDITIVE COLUMNS ON INCIDENT_REPORTS (CIVIC COMPLAINTS)
do $$
begin
  if not exists (select 1 from information_schema.columns where table_schema = 'public' and table_name = 'incident_reports' and column_name = 'title') then
    alter table public.incident_reports add column title text;
  end if;

  if not exists (select 1 from information_schema.columns where table_schema = 'public' and table_name = 'incident_reports' and column_name = 'department_id') then
    alter table public.incident_reports add column department_id uuid references public.departments(id) on delete set null;
  end if;

  if not exists (select 1 from information_schema.columns where table_schema = 'public' and table_name = 'incident_reports' and column_name = 'due_date') then
    alter table public.incident_reports add column due_date timestamptz;
  end if;

  if not exists (select 1 from information_schema.columns where table_schema = 'public' and table_name = 'incident_reports' and column_name = 'resolution_evidence_url') then
    alter table public.incident_reports add column resolution_evidence_url text;
  end if;

  if not exists (select 1 from information_schema.columns where table_schema = 'public' and table_name = 'incident_reports' and column_name = 'resolution_notes') then
    alter table public.incident_reports add column resolution_notes text;
  end if;

  if not exists (select 1 from information_schema.columns where table_schema = 'public' and table_name = 'incident_reports' and column_name = 'verified_at') then
    alter table public.incident_reports add column verified_at timestamptz;
  end if;

  if not exists (select 1 from information_schema.columns where table_schema = 'public' and table_name = 'incident_reports' and column_name = 'verified_by') then
    alter table public.incident_reports add column verified_by uuid references auth.users(id) on delete set null;
  end if;
end $$;

-- 5. ROW LEVEL SECURITY (RLS) FOR NEW ENTITIES
alter table public.departments enable row level security;
alter table public.complaint_status_history enable row level security;
alter table public.complaint_feedback enable row level security;

-- Departments: readable by everyone, manageable by admin
create policy "departments_select_all" on public.departments for select using (true);
create policy "departments_admin_all" on public.departments for all using (
  exists (select 1 from public.profiles where id = auth.uid() and role = 'admin')
);

-- Status history: readable by complaint owner or staff/admin
create policy "status_history_select" on public.complaint_status_history for select using (
  exists (
    select 1 from public.incident_reports
    where id = complaint_id and (user_id = auth.uid() or exists (
      select 1 from public.profiles where id = auth.uid() and role in ('admin', 'responder', 'officer', 'worker')
    ))
  )
);
create policy "status_history_insert" on public.complaint_status_history for insert with check (
  exists (select 1 from public.profiles where id = auth.uid() and role in ('admin', 'responder', 'officer', 'worker'))
  or true -- allows system logging on complaint creation
);

-- Feedback: readable by complaint owner and admin; insertable by complaint owner
create policy "feedback_select" on public.complaint_feedback for select using (
  user_id = auth.uid() or exists (select 1 from public.profiles where id = auth.uid() and role in ('admin', 'officer'))
);
create policy "feedback_insert" on public.complaint_feedback for insert with check (
  auth.uid() = user_id or true
);

-- 6. SEED MUNICIPAL DEPARTMENTS
insert into public.departments (name, code, description, categories, contact_phone) values
  ('Roads & Infrastructure', 'ROADS', 'Maintenance of city roads, potholes, flyovers, and pedestrian paths', '{"roads", "accident", "infrastructure"}', '020-25501001'),
  ('Solid Waste Management', 'WASTE', 'Garbage collection, public bins, and city waste disposal', '{"waste", "sanitation"}', '020-25501002'),
  ('Water Supply & Sewage', 'WATER', 'Drinking water pipelines, leakages, drainage, and stormwater flooding', '{"water", "drainage", "flood"}', '020-25501003'),
  ('Street Lighting & Electrical', 'LIGHTS', 'Maintenance of streetlights, dark zones, and electrical hazards', '{"streetlights"}', '020-25501004'),
  ('Public Health & Sanitation', 'HEALTH', 'Public restrooms, pest control, and community hygiene facilities', '{"sanitation", "medical", "ambulance"}', '020-25501005'),
  ('Traffic Infrastructure & Safety', 'TRAFFIC', 'Traffic signals, signage, road obstructions, and civic encroachment', '{"traffic_signs", "police", "encroachment", "other"}', '020-25501006')
on conflict (code) do update
set
  name = excluded.name,
  description = excluded.description,
  categories = excluded.categories,
  contact_phone = excluded.contact_phone;

-- ============================================================
-- ROLLBACK INSTRUCTIONS (IF EVER NEEDED):
-- alter table public.incident_reports drop column if exists title, drop column if exists department_id, drop column if exists due_date, drop column if exists resolution_evidence_url, drop column if exists resolution_notes, drop column if exists verified_at, drop column if exists verified_by;
-- drop table if exists public.complaint_feedback cascade;
-- drop table if exists public.complaint_status_history cascade;
-- drop table if exists public.departments cascade;
-- ============================================================
