-- Allow normalized tech categories in the existing public.products table.
-- This preserves all product rows and replaces only the laptop-only constraint.
begin;

alter table public.products
    drop constraint if exists products_category_laptops;

alter table public.products
    drop constraint if exists products_category_format;

alter table public.products
    add constraint products_category_format check (
        category ~ '^[a-z0-9]+(-[a-z0-9]+)*$' and length(category) <= 64
    );

commit;
