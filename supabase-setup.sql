-- =============================================================================
-- YOU vs 166,691 — Supabase setup
-- =============================================================================
-- Paste this whole file into: Supabase dashboard → SQL Editor → New query → Run.
-- It is idempotent: running it twice is safe.
--
-- Before running, enable anonymous sign-ins:
--   Dashboard → Authentication → Sign In / Providers → Anonymous Sign-Ins → ON
--
-- Security model in one paragraph:
--   Players sign in anonymously, so they hold the `authenticated` role with a
--   real auth.uid(). Profiles and runs are world-readable (the leaderboard is
--   public by design) but only writable for your own row. Scores are NEVER
--   written directly by the browser: the client calls submit_run(), which
--   revalidates the inputs and recomputes the official score server-side.
--   The browser only ever holds the publishable ("anon") key.
-- =============================================================================

-- -----------------------------------------------------------------------------
-- 1. TABLES
-- -----------------------------------------------------------------------------

create table if not exists public.profiles (
  user_id    uuid primary key references auth.users(id) on delete cascade,
  nickname   text not null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),

  -- 3-16 characters, already trimmed, no HTML/control characters
  constraint profiles_nickname_length check (char_length(nickname) between 3 and 16),
  constraint profiles_nickname_trimmed check (nickname = btrim(nickname)),
  constraint profiles_nickname_charset check (
    nickname !~ '[<>&"''`\\/]' and
    nickname !~ '[\u0001-\u001F\u007F]'
  )
);

create table if not exists public.runs (
  id           uuid primary key default gen_random_uuid(),
  user_id      uuid not null references auth.users(id) on delete cascade,
  score        integer not null check (score between 0 and 1000),
  success      boolean not null,
  escapes      integer not null check (escapes between 0 and 20),
  min_dist     integer not null check (min_dist between 0 and 5000),
  peak_gf      integer not null check (peak_gf between 0 and 100),
  elapsed_ms   integer not null check (elapsed_ms between 0 and 3600000),
  attempts     integer not null check (attempts between 1 and 3),
  game_version text not null default 'v5.0' check (char_length(game_version) <= 20),
  created_at   timestamptz not null default now()
);

-- -----------------------------------------------------------------------------
-- 2. INDEXES
-- -----------------------------------------------------------------------------

-- nickname uniqueness is case-insensitive: Daniel / daniel / DANIEL collide
create unique index if not exists profiles_nickname_lower_key
  on public.profiles (lower(nickname));

create index if not exists runs_user_id_idx        on public.runs (user_id);
create index if not exists runs_score_desc_idx     on public.runs (score desc);
create index if not exists runs_success_score_idx  on public.runs (success, score desc);
create index if not exists runs_user_created_idx   on public.runs (user_id, created_at desc);

-- -----------------------------------------------------------------------------
-- 3. ROW LEVEL SECURITY
-- -----------------------------------------------------------------------------

alter table public.profiles enable row level security;
alter table public.runs     enable row level security;

-- profiles ---------------------------------------------------------------
drop policy if exists profiles_select_all on public.profiles;
create policy profiles_select_all on public.profiles
  for select to authenticated using (true);

drop policy if exists profiles_insert_own on public.profiles;
create policy profiles_insert_own on public.profiles
  for insert to authenticated with check (user_id = auth.uid());

drop policy if exists profiles_update_own on public.profiles;
create policy profiles_update_own on public.profiles
  for update to authenticated
  using (user_id = auth.uid()) with check (user_id = auth.uid());

-- No DELETE policy exists, so nobody can delete any profile through the API.

-- runs -------------------------------------------------------------------
drop policy if exists runs_select_all on public.runs;
create policy runs_select_all on public.runs
  for select to authenticated using (true);

-- Defence in depth. Note that `authenticated` is deliberately NOT granted the
-- INSERT privilege on runs below, so the only write path in practice is
-- submit_run(), which decides the score itself. If you ever grant direct
-- inserts, this policy still prevents writing rows as another player.
drop policy if exists runs_insert_own on public.runs;
create policy runs_insert_own on public.runs
  for insert to authenticated with check (user_id = auth.uid());

-- No UPDATE and no DELETE policies: historical scores are immutable.

-- -----------------------------------------------------------------------------
-- 4. LEADERBOARD VIEW — one row per player, their best successful run
-- -----------------------------------------------------------------------------

create or replace view public.leaderboard as
select
  b.user_id,
  p.nickname,
  b.best_score,
  rank() over (order by b.best_score desc, b.first_reached asc) as rank
from (
  select user_id,
         max(score)      as best_score,
         min(created_at) as first_reached
  from public.runs
  where success
  group by user_id
) b
join public.profiles p on p.user_id = b.user_id;

-- Run the view with the caller's own permissions rather than the owner's.
-- Needs Postgres 15+; on anything older the view still only exposes data that
-- is public by design, so we degrade with a notice instead of failing.
do $invoker$
begin
  execute 'alter view public.leaderboard set (security_invoker = on)';
exception when others then
  raise notice 'security_invoker unsupported here; leaderboard view runs as owner';
end
$invoker$;

-- -----------------------------------------------------------------------------
-- 5. submit_run() — the server owns the score
-- -----------------------------------------------------------------------------
-- Mirrors computeFinalScore() in the game exactly:
--   stealth   = max(0, 100 - peak_gf)
--   precision = max(0, 100 - max(0, min_dist - 20) * 0.5)
--   speed     = max(0, 20 - elapsed_seconds * 2)
--   score     = max(1, round(precision*0.4 + stealth*0.35 + speed
--                            - escapes*8 - (attempts-1)*10))
-- Only successful runs are scored; a failed run is recorded with score 0 and
-- never reaches the leaderboard.
-- -----------------------------------------------------------------------------

create or replace function public.submit_run(
  p_success      boolean,
  p_escapes      integer,
  p_min_dist     integer,
  p_peak_gf      integer,
  p_elapsed_ms   integer,
  p_attempts     integer,
  p_game_version text default 'v5.0'
)
returns json
language plpgsql
security definer
set search_path = public
as $$
declare
  v_user          uuid := auth.uid();
  v_recent        integer;
  v_stealth       numeric;
  v_precision     numeric;
  v_speed         numeric;
  v_score         integer;
  v_previous_best integer;
  v_previous_rank bigint;
  v_best          integer;
  v_rank          bigint;
begin
  if v_user is null then
    raise exception 'not authenticated' using errcode = '28000';
  end if;

  -- ---- validation -----------------------------------------------------
  if p_escapes    is null or p_escapes    not between 0 and 20      then raise exception 'invalid escapes';    end if;
  if p_min_dist   is null or p_min_dist   not between 0 and 5000    then raise exception 'invalid min_dist';   end if;
  if p_peak_gf    is null or p_peak_gf    not between 0 and 100     then raise exception 'invalid peak_gf';    end if;
  if p_attempts   is null or p_attempts   not between 1 and 3       then raise exception 'invalid attempts';   end if;
  if p_elapsed_ms is null or p_elapsed_ms not between 200 and 600000 then raise exception 'invalid elapsed_ms'; end if;
  if p_success is null then raise exception 'invalid success'; end if;

  -- cheap rate limit: a human cannot finish 20 games in a minute
  select count(*) into v_recent
  from public.runs
  where user_id = v_user and created_at > now() - interval '1 minute';
  if v_recent >= 20 then
    raise exception 'too many runs' using errcode = '54000';
  end if;

  -- ---- official score, computed here and nowhere else -------------------
  if p_success then
    v_stealth   := greatest(0, 100 - p_peak_gf);
    v_precision := greatest(0, 100 - greatest(0, p_min_dist - 20) * 0.5);
    v_speed     := greatest(0, 20 - (p_elapsed_ms / 1000.0) * 2);
    v_score     := greatest(1, round(
                     v_precision * 0.4 + v_stealth * 0.35 + v_speed
                     - p_escapes * 8 - (p_attempts - 1) * 10
                   ))::integer;
  else
    v_score := 0;
  end if;

  -- ---- standing before this run ----------------------------------------
  select best_score, rank into v_previous_best, v_previous_rank
  from public.leaderboard where user_id = v_user;

  insert into public.runs (user_id, score, success, escapes, min_dist,
                           peak_gf, elapsed_ms, attempts, game_version)
  values (v_user, v_score, p_success, p_escapes, p_min_dist,
          p_peak_gf, p_elapsed_ms, p_attempts, coalesce(p_game_version, 'v5.0'));

  -- ---- standing after this run -----------------------------------------
  select best_score, rank into v_best, v_rank
  from public.leaderboard where user_id = v_user;

  return json_build_object(
    'official_score', v_score,
    'personal_best',  v_best,
    'previous_best',  v_previous_best,
    'global_rank',    v_rank,
    'previous_rank',  v_previous_rank,
    'improved',       (v_previous_best is null and p_success) or
                      (v_previous_best is not null and v_score > v_previous_best)
  );
end;
$$;

-- -----------------------------------------------------------------------------
-- 6. GRANTS
-- -----------------------------------------------------------------------------

grant usage on schema public to authenticated;

grant select                 on public.profiles     to authenticated;
grant insert, update         on public.profiles     to authenticated;
grant select                 on public.runs         to authenticated;
grant select                 on public.leaderboard  to authenticated;
grant execute on function public.submit_run(boolean, integer, integer, integer, integer, integer, text)
  to authenticated;

-- Deliberately NOT granted: insert/update/delete on runs, delete on profiles,
-- and anything at all to the unauthenticated `anon` role.
revoke all on public.profiles    from anon;
revoke all on public.runs        from anon;
revoke all on public.leaderboard from anon;

-- =============================================================================
-- Done. Quick check:
--   select * from public.leaderboard limit 10;
-- =============================================================================
