-- LEGACY LESSON SCHEMA: used by lesson/, NOT by the current scraper/ uploader.
-- For scraper/main.py --check-db and --save, use sql/schema.sql (public.products).
-- Run sql/inspect_products.sql first; do not drop these older tables.
-- Mentor runs this ONCE in the shared Supabase project's SQL Editor.
-- Additive lesson tables: no drops, no changes to other Shoppie tables.
begin;

create table public.lesson_members (
    user_id uuid primary key references auth.users(id) on delete cascade
);
alter table public.lesson_members enable row level security;
revoke all on public.lesson_members from anon, authenticated;
grant select on public.lesson_members to authenticated;
create policy "Members can check their own membership"
on public.lesson_members for select to authenticated
using (user_id = (select auth.uid()));

create table public.lesson_laptop_observations (
    id uuid primary key default gen_random_uuid(),
    retailer text not null check (retailer in ('amazon', 'bestbuy', 'target', 'walmart')),
    product_id text not null check (length(product_id) > 0),
    product_url text not null,
    title text not null check (length(trim(title)) between 5 and 1000),
    price numeric(12,2) not null check (price > 0 and price < 10000000000),
    currency text not null check (currency = 'USD'),
    availability text check (availability in ('InStock', 'OutOfStock', 'PreOrder', 'PreSale',
        'BackOrder', 'LimitedAvailability', 'SoldOut', 'Discontinued', 'OnlineOnly', 'InStoreOnly')),
    seller text,
    discount numeric check (discount is null),
    extraction_method text not null check (extraction_method in ('json-ld', 'html')),
    observed_at timestamptz not null,
    submitted_by uuid not null default auth.uid() references auth.users(id),
    created_at timestamptz not null default now(),
    unique (retailer, product_id, observed_at, submitted_by)
);

alter table public.lesson_laptop_observations enable row level security;
revoke all on public.lesson_laptop_observations from anon, authenticated;
grant select, insert on public.lesson_laptop_observations to authenticated;

create policy "Class can read shared observations"
on public.lesson_laptop_observations for select to authenticated
using (exists (select 1 from public.lesson_members where user_id = (select auth.uid())));

create policy "Class can insert their own observations"
on public.lesson_laptop_observations for insert to authenticated
with check (
    submitted_by = (select auth.uid())
    and exists (select 1 from public.lesson_members where user_id = (select auth.uid()))
);
commit;

-- After creating/confirming each student in Authentication > Users, copy their UUID.
-- Run separately for each student (replace the placeholder; never use passwords here):
-- insert into public.lesson_members (user_id) values ('STUDENT-USER-UUID');

-- Inspect the shared result in SQL Editor:
-- select retailer, title, price, currency, availability, observed_at
-- from public.lesson_laptop_observations order by created_at desc;
