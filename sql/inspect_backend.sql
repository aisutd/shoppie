-- read-only inspection for the mentor; no schema or product changes.
BEGIN READ ONLY;
SELECT current_database(), current_user;
SELECT n.nspname AS extension_schema, e.extname, e.extversion
FROM pg_extension e JOIN pg_namespace n ON n.oid=e.extnamespace
WHERE e.extname='vector';
SELECT table_schema,table_name,column_name,data_type,udt_schema,udt_name
FROM information_schema.columns
WHERE table_schema='shoppie' OR (table_schema='public' AND table_name='products')
ORDER BY table_schema,table_name,ordinal_position;
SELECT n.nspname, c.relname, con.conname, pg_get_constraintdef(con.oid)
FROM pg_constraint con JOIN pg_class c ON c.oid=con.conrelid
JOIN pg_namespace n ON n.oid=c.relnamespace
WHERE n.nspname='shoppie' OR (n.nspname='public' AND c.relname='products');
SELECT schemaname,tablename,policyname,roles,cmd FROM pg_policies
WHERE schemaname='shoppie' OR (schemaname='public' AND tablename='products');
ROLLBACK;
