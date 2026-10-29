-- review-only, additive, backend-only Data API access after shoppie_backend.sql.
-- mentor must verify a development/test project and the vector extension schema.
-- the owner must add shoppie to exposed schemas in Supabase settings separately.
BEGIN;
GRANT USAGE ON SCHEMA shoppie TO service_role;
GRANT SELECT ON shoppie.retailers, shoppie.listings, shoppie.observations,
    shoppie.current_offers, shoppie.embeddings TO service_role;
GRANT USAGE ON SCHEMA extensions TO service_role;
GRANT EXECUTE ON FUNCTION shoppie.vector_candidates(
    extensions.vector, text, text, text, numeric, numeric, text, text, integer
) TO service_role;
-- no anonymous, authenticated-browser, insert, update, or delete grants.
COMMIT;
