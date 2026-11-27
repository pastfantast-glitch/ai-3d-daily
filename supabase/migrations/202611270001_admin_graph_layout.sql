-- Private presentation storage, independent of GitHub collection configuration.
begin;
create table if not exists public.admin_graph_layout (
  user_id uuid primary key references auth.users(id) on delete cascade,
  layout jsonb not null,
  revision bigint not null check (revision > 0),
  updated_at timestamptz not null default now(),
  check (octet_length(layout::text) <= 200000)
);
alter table public.admin_graph_layout enable row level security;
revoke all on public.admin_graph_layout from public, anon, authenticated;

create or replace function public.validate_admin_graph_layout(p jsonb) returns boolean
language plpgsql immutable set search_path = '' as $$
declare e jsonb; n jsonb; c jsonb;
begin
  if p is null or jsonb_path_exists(p,'$.** ? (@ == null)') or jsonb_typeof(p->'schema') <> 'number' or jsonb_typeof(p) <> 'object' or (p - array['schema','positions','camera','mode','navigation']) <> '{}'::jsonb
     or p->>'schema' <> '3' or p->>'mode' not in ('configuration','operations')
     or jsonb_typeof(p->'positions') <> 'array' or jsonb_array_length(p->'positions') > 1000 then return false; end if;
  if (select count(distinct x->>0) from jsonb_array_elements(p->'positions') x) <> jsonb_array_length(p->'positions') then return false; end if;
  for e in select * from jsonb_array_elements(p->'positions') loop
    if jsonb_typeof(e) <> 'array' or jsonb_array_length(e) <> 2 or (e->>0) !~ '^(source|topic|stage):[a-z0-9-]{1,100}$'
       or jsonb_typeof(e->1) <> 'object' or ((e->1) - array['x','y']) <> '{}'::jsonb then return false; end if;
    if jsonb_typeof(e->1->'x') <> 'number' or jsonb_typeof(e->1->'y') <> 'number'
       or abs((e->1->>'x')::numeric) > 1e9 or abs((e->1->>'y')::numeric) > 1e9 then return false; end if;
  end loop;
  n := p->'navigation';
  if jsonb_typeof(n) <> 'object' or (n - array['locks','views','groups']) <> '{}'::jsonb
     or jsonb_typeof(n->'locks') <> 'array' or jsonb_array_length(n->'locks') > 1000
     or jsonb_typeof(n->'views') <> 'array' or jsonb_array_length(n->'views') > 8
     or jsonb_typeof(n->'groups') <> 'array' or jsonb_array_length(n->'groups') > 20 then return false; end if;
  for e in select * from jsonb_array_elements(n->'locks') loop
    if jsonb_typeof(e) <> 'string' or (e #>> '{}') !~ '^(source|topic|stage):[a-z0-9-]{1,100}$' then return false; end if;
  end loop;
  for e in select * from jsonb_array_elements(n->'groups') loop
    if jsonb_typeof(e) <> 'object' or (e - array['name','ids']) <> '{}'::jsonb or jsonb_typeof(e->'name') <> 'string'
       or length(e->>'name') not between 1 and 40 or jsonb_typeof(e->'ids') <> 'array' or jsonb_array_length(e->'ids') > 1000 then return false; end if;
    if exists(select 1 from jsonb_array_elements(e->'ids') k where jsonb_typeof(k) <> 'string' or (k #>> '{}') !~ '^(source|topic|stage):[a-z0-9-]{1,100}$') then return false; end if;
  end loop;
  for e in select * from jsonb_array_elements(n->'views') loop
    if jsonb_typeof(e) <> 'object' or (e - array['name','camera']) <> '{}'::jsonb or jsonb_typeof(e->'name') <> 'string' or length(e->>'name') not between 1 and 40 then return false; end if;
  end loop;
  for c in select p->'camera' union all select x->'camera' from jsonb_array_elements(n->'views') x loop
    if jsonb_typeof(c) <> 'object' or (c - array['x','y','zoom']) <> '{}'::jsonb
       or jsonb_typeof(c->'x') <> 'number' or jsonb_typeof(c->'y') <> 'number' or jsonb_typeof(c->'zoom') <> 'number'
       or abs((c->>'x')::numeric) > 1e9 or abs((c->>'y')::numeric) > 1e9 or (c->>'zoom')::numeric not between 0.02 and 2 then return false; end if;
  end loop;
  -- Missing fields must fail, not pass SQL's NULL condition semantics.
  return p ?& array['schema','positions','camera','mode','navigation']
    and n ?& array['locks','views','groups']
    and (p->'camera') ?& array['x','y','zoom']
    and not exists(select 1 from jsonb_array_elements(p->'positions') x where not (x->1) ?& array['x','y'])
    and not exists(select 1 from jsonb_array_elements(n->'views') x where not x ?& array['name','camera'] or not (x->'camera') ?& array['x','y','zoom'])
    and not exists(select 1 from jsonb_array_elements(n->'groups') x where not x ?& array['name','ids']);
exception when others then return false;
end $$;

create or replace function public.get_admin_graph_layout() returns jsonb
language plpgsql security definer set search_path = '' as $$
declare result jsonb;
begin
  if auth.uid() is null or not exists(select 1 from public.app_owner where singleton = true and user_id = auth.uid()) then raise exception 'owner_required' using errcode = '42501'; end if;
  select jsonb_build_object('layout',layout,'revision',revision,'updated_at',updated_at) into result from public.admin_graph_layout where user_id = auth.uid();
  return coalesce(result,jsonb_build_object('layout',null,'revision',0,'updated_at',null));
end $$;

create or replace function public.save_admin_graph_layout(p_expected_revision bigint,p_layout jsonb) returns jsonb
language plpgsql security definer set search_path = '' as $$
declare result jsonb;
begin
  if auth.uid() is null or not exists(select 1 from public.app_owner where singleton = true and user_id = auth.uid()) then raise exception 'owner_required' using errcode = '42501'; end if;
  if p_expected_revision is null or p_expected_revision < 0 or p_layout is null or octet_length(p_layout::text) > 200000 or public.validate_admin_graph_layout(p_layout) is not true then raise exception 'invalid_layout' using errcode = '22023'; end if;
  -- Serializes initial inserts as well as updates, scoped to this user's layout.
  perform pg_advisory_xact_lock(hashtextextended('admin_graph_layout:' || auth.uid()::text,0));
  if coalesce((select revision from public.admin_graph_layout where user_id=auth.uid()),0) <> p_expected_revision then raise exception 'layout_version_conflict' using errcode = '40001'; end if;
  insert into public.admin_graph_layout(user_id,layout,revision) values(auth.uid(),p_layout,p_expected_revision+1)
  on conflict(user_id) do update set layout=excluded.layout,revision=excluded.revision,updated_at=now();
  return public.get_admin_graph_layout();
end $$;
revoke all on function public.validate_admin_graph_layout(jsonb) from public, anon, authenticated;
revoke all on function public.get_admin_graph_layout() from public, anon;
revoke all on function public.save_admin_graph_layout(bigint,jsonb) from public, anon;
grant execute on function public.get_admin_graph_layout() to authenticated;
grant execute on function public.save_admin_graph_layout(bigint,jsonb) to authenticated;
commit;

