-- Read-only: run in the shared Supabase SQL Editor before schema.sql.
-- No credentials, product rows or user records are selected.
select to_regclass('public.products') as existing_products_relation;

select column_name, data_type, udt_name, is_nullable, column_default,
       is_identity, identity_generation, numeric_precision, numeric_scale
from information_schema.columns
where table_schema = 'public' and table_name = 'products'
order by ordinal_position;

select c.conname as constraint_name, c.contype as constraint_type,
       c.convalidated as validated, pg_get_constraintdef(c.oid) as definition
from pg_constraint c
where c.conrelid = to_regclass('public.products')
order by c.conname;

select indexname, indexdef from pg_indexes
where schemaname = 'public' and tablename = 'products';

select c.relkind, c.relrowsecurity as rls_enabled, c.relforcerowsecurity as force_rls
from pg_class c join pg_namespace n on n.oid = c.relnamespace
where n.nspname = 'public' and c.relname = 'products';

select policyname, permissive, roles, cmd, qual, with_check from pg_policies
where schemaname = 'public' and tablename = 'products';

select grantee, privilege_type, is_grantable
from information_schema.table_privileges
where table_schema = 'public' and table_name = 'products'
order by grantee, privilege_type;

select grantee, column_name, privilege_type
from information_schema.column_privileges
where table_schema = 'public' and table_name = 'products'
order by grantee, column_name, privilege_type;

-- Incoming foreign keys matter before changing an existing primary key/type.
select conrelid::regclass as referencing_table, conname, pg_get_constraintdef(oid)
from pg_constraint
where confrelid = to_regclass('public.products') and contype = 'f';
