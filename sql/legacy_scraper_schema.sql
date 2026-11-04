-- Run once in the shared Supabase project's SQL Editor.
-- New tables only. Earlier lesson_* tables and existing Shoppie data are preserved.
-- If these scraper tables already exist, inspect them instead of dropping them.
begin;

create table public.scraper_members (
    user_id uuid primary key references auth.users(id) on delete cascade
);
alter table public.scraper_members enable row level security;
revoke all on public.scraper_members from anon, authenticated;
grant select on public.scraper_members to authenticated;
create policy "Students can check their own scraper membership"
on public.scraper_members for select to authenticated
using (user_id = (select auth.uid()));

create table public.scraped_laptops (
    id uuid primary key default gen_random_uuid(),
    retailer text not null check (retailer in ('amazon', 'bestbuy', 'target', 'walmart')),
    product_id text not null check (length(product_id) > 0),
    product_url text not null,
    title text not null check (length(trim(title)) between 5 and 1000),
    price numeric(12,2) not null check (price > 0 and price < 10000000000),
    currency text not null check (currency = 'USD'),
    availability text check (availability in ('InStock', 'OutOfStock', 'PreOrder', 'PreSale',
        'BackOrder', 'LimitedAvailability', 'SoldOut', 'Discontinued', 'OnlineOnly', 'InStoreOnly')),
    seller text check (length(seller) <= 300),
    discount numeric check (discount is null),
    extraction_method text not null check (extraction_method in ('json-ld', 'html')),
    observed_at timestamptz not null,
    collected_by uuid not null references auth.users(id),
    created_at timestamptz not null default now(),
    -- Stable conflict key: running again updates this product, not a new row.
    unique (retailer, product_id)
);

alter table public.scraped_laptops enable row level security;
revoke all on public.scraped_laptops from anon, authenticated;
grant select, insert, update on public.scraped_laptops to authenticated;

create policy "Class can read shared laptop rows"
on public.scraped_laptops for select to authenticated
using (exists (select 1 from public.scraper_members where user_id = (select auth.uid())));

create policy "Class can insert laptop rows with their own attribution"
on public.scraped_laptops for insert to authenticated
with check (
    collected_by = (select auth.uid())
    and exists (select 1 from public.scraper_members where user_id = (select auth.uid()))
);

-- Upserts need SELECT and UPDATE policies as well as INSERT.
-- Members update the shared row and attribute the newest collection to themselves.
create policy "Class can update shared laptop rows"
on public.scraped_laptops for update to authenticated
using (exists (select 1 from public.scraper_members where user_id = (select auth.uid())))
with check (
    collected_by = (select auth.uid())
    and exists (select 1 from public.scraper_members where user_id = (select auth.uid()))
);
commit;

-- Mentor: confirm each account in Authentication > Users, copy its UUID,
-- and run separately for each student (replace the placeholder):
-- insert into public.scraper_members (user_id) values ('STUDENT-USER-UUID');

-- Verify upserts: save the same live product twice, then run:
-- select retailer, product_id, count(*) from public.scraped_laptops
-- group by retailer, product_id; -- one row per product
-- select retailer, title, price, currency, observed_at, collected_by
-- from public.scraped_laptops order by observed_at desc;
