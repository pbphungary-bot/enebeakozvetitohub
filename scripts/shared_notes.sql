-- Optional PUBLIC shared notes. No login; everyone with the public site can read/write.
-- Do NOT use for confidential information. Use only Supabase publishable/anon key.
create table if not exists public.nba_commentator_notes (
  matchup_key text primary key check (matchup_key ~ '^nba-notes:[0-9]+:[0-9]+$'),
  notes jsonb not null default '{}'::jsonb check (jsonb_typeof(notes) = 'object' and pg_column_size(notes) < 200000),
  updated_at timestamptz not null default now()
);
alter table public.nba_commentator_notes enable row level security;
revoke all on public.nba_commentator_notes from public;
grant select, insert, update on public.nba_commentator_notes to anon;
create policy "Public commentator notes read" on public.nba_commentator_notes for select to anon using (true);
create policy "Public commentator notes insert" on public.nba_commentator_notes for insert to anon with check (true);
create policy "Public commentator notes update" on public.nba_commentator_notes for update to anon using (true) with check (true);
