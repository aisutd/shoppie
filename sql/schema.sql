-- Shoppie: latest laptop observations, uploaded by the instructor's backend.
-- Run sql/inspect_products.sql FIRST in the shared Supabase SQL Editor.
-- New-table creation only; existing-table guidance is in sql/PRODUCTS.md.
-- Earlier classroom schema: sql/legacy_scraper_schema.sql (preserved).

begin;

do $$
begin
    if to_regclass('public.products') is not null then
        raise exception 'public.products already exists; no changes were made.'
            using hint = 'Run sql/inspect_products.sql and review sql/PRODUCTS.md before preparing a compatible migration.';
    end if;
end;
$$;

create table public.products (
    -- UUID generation requires no sequence grants for the uploader.
    id uuid primary key default gen_random_uuid(),

    title text not null,
    constraint products_title_min_characters
        check (length(regexp_replace(title, '[[:space:]]', '', 'g')) >= 3),

    -- 10 digits before the decimal and 2 after it; reject zero/negative/NaN.
    price numeric(12, 2) not null,
    constraint products_price_positive_finite
        check (price > 0 and price < 10000000000),

    -- No default: currency must be explicitly established by the source.
    currency text not null,
    constraint products_currency_usd check (currency = 'USD'),

    product_url text not null,
    constraint products_product_url_https check (
        product_url ~ '^https://(www[.])?(amazon[.]com|bestbuy[.]com|target[.]com|walmart[.]com)/[^[:space:]#]*$'
    ),
    constraint products_product_url_unique unique (product_url),

    -- Lowercase retailer domain without www., e.g. bestbuy.com.
    source text not null,
    constraint products_source_retailer check (
        source in ('amazon.com', 'bestbuy.com', 'target.com', 'walmart.com')
    ),
    constraint products_source_matches_url check (
        regexp_replace(split_part(product_url, '/', 3), '^www[.]', '') = source
    ),

    category text not null,
    constraint products_category_laptops check (category = 'laptops'),

    -- Actual observation time with UTC offset, not the later upload time.
    scraped_at timestamptz not null
);

alter table public.products enable row level security;

-- Remove Supabase default table grants; no anonymous/student policies are added.
revoke all privileges on table public.products from public, anon, authenticated;
revoke all privileges on table public.products from service_role;

-- Supabase's existing service_role is the instructor BACKEND role and bypasses
-- RLS. Its secret key belongs only on that backend, never in student code.
-- SELECT + INSERT + UPDATE are sufficient for upsert. No DELETE/DDL grant.
grant usage on schema public to service_role;
grant select, insert, update on table public.products to service_role;

commit;

-- Upsert conflict target: product_url.
-- Update title, price, currency, source, category and scraped_at on conflict.
-- Omit id from the upload so the existing generated ID survives.
-- This table stores the latest observation per exact URL, NOT price history.
