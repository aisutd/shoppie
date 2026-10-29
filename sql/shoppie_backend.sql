-- review-only additive PostgreSQL/Supabase proposal; never run automatically.
-- requires mentor approval, a test project, and inspection of existing extensions.
-- leaves public.products and the earlier lesson tables untouched.
BEGIN;
CREATE SCHEMA IF NOT EXISTS extensions;
CREATE EXTENSION IF NOT EXISTS vector WITH SCHEMA extensions;
CREATE SCHEMA IF NOT EXISTS shoppie;

CREATE TABLE shoppie.retailers (
    retailer_key text PRIMARY KEY,
    name text NOT NULL
);
INSERT INTO shoppie.retailers VALUES
    ('amazon','Amazon'), ('best_buy','Best Buy'), ('target','Target'), ('walmart','Walmart');

CREATE TABLE shoppie.listings (
    id text PRIMARY KEY,
    retailer_key text NOT NULL REFERENCES shoppie.retailers(retailer_key),
    retailer_sku text,
    source_url text NOT NULL,
    source_url_hash text NOT NULL CHECK (length(source_url_hash)=64),
    title text, description text, brand text, model_number text, gtin text, category text,
    attributes jsonb NOT NULL CHECK (jsonb_typeof(attributes)='object'),
    details_observed_at timestamptz NOT NULL,
    identity_input_hash text NOT NULL CHECK(length(identity_input_hash)=64),
    UNIQUE (retailer_key, source_url_hash)
);
CREATE INDEX shoppie_model_lookup ON shoppie.listings(brand, model_number);

CREATE TABLE shoppie.observations (
    listing_id text NOT NULL REFERENCES shoppie.listings(id),
    scraped_at timestamptz NOT NULL,
    price numeric(12,2) CHECK(price >= 0 AND price < 10000000000),
    shipping_cost numeric(12,2) CHECK(shipping_cost >= 0 AND shipping_cost < 10000000000),
    currency text CHECK(currency='USD'),
    condition text CHECK(condition IN ('new','used','refurbished','open_box')),
    seller text,
    availability text CHECK(availability IN ('in_stock','out_of_stock','unknown')),
    raw_payload jsonb NOT NULL,
    PRIMARY KEY(listing_id, scraped_at),
    CHECK ((price IS NULL AND shipping_cost IS NULL) OR (currency IS NOT NULL AND currency='USD'))
);
CREATE VIEW shoppie.current_offers WITH (security_invoker=true) AS
    SELECT DISTINCT ON (listing_id) * FROM shoppie.observations
    ORDER BY listing_id, scraped_at DESC;

CREATE TABLE shoppie.embeddings (
    listing_id text NOT NULL REFERENCES shoppie.listings(id),
    model_name text NOT NULL, model_revision text NOT NULL, template_version text NOT NULL,
    input_text text NOT NULL, input_hash text NOT NULL CHECK(length(input_hash)=64),
    dimensions integer NOT NULL CHECK(dimensions=384),
    embedding extensions.vector(384) NOT NULL,
    created_at timestamptz NOT NULL,
    PRIMARY KEY(listing_id, model_name, model_revision, template_version),
    CHECK (abs(extensions.vector_norm(embedding)-1) < 0.0001)
);

-- invoker function has no extra privileges; stale hashes must match current text.
CREATE FUNCTION shoppie.vector_candidates(
    query_vector extensions.vector(384), wanted_revision text, wanted_template text,
    wanted_category text DEFAULT NULL, minimum_price numeric DEFAULT NULL,
    maximum_price numeric DEFAULT NULL, wanted_availability text DEFAULT NULL,
    wanted_brand text DEFAULT NULL, result_limit integer DEFAULT 10
) RETURNS TABLE(listing_id text, cosine_score double precision)
LANGUAGE sql STABLE SECURITY INVOKER SET search_path = '' AS $$
    SELECT l.id, 1 - (e.embedding OPERATOR(extensions.<=>) query_vector)
    FROM shoppie.listings l JOIN shoppie.current_offers o ON o.listing_id=l.id
    JOIN shoppie.embeddings e ON e.listing_id=l.id
    WHERE e.model_name='sentence-transformers/all-MiniLM-L6-v2'
      AND e.model_revision=wanted_revision AND e.template_version=wanted_template
      AND (wanted_category IS NULL OR l.category=wanted_category)
      AND (minimum_price IS NULL OR o.price>=minimum_price)
      AND (maximum_price IS NULL OR o.price<=maximum_price)
      AND (wanted_availability IS NULL OR o.availability=wanted_availability)
      AND (wanted_brand IS NULL OR lower(l.brand)=lower(wanted_brand))
      -- unchanged prices can reuse vectors; changed identity text cannot
      AND e.input_hash = l.identity_input_hash
    ORDER BY e.embedding OPERATOR(extensions.<=>) query_vector
    LIMIT greatest(1,least(result_limit,50));
$$;

-- no anonymous/browser access; a mentor grants a dedicated backend role later.
ALTER TABLE shoppie.retailers ENABLE ROW LEVEL SECURITY;
ALTER TABLE shoppie.listings ENABLE ROW LEVEL SECURITY;
ALTER TABLE shoppie.observations ENABLE ROW LEVEL SECURITY;
ALTER TABLE shoppie.embeddings ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON SCHEMA shoppie FROM PUBLIC;
REVOKE ALL ON ALL TABLES IN SCHEMA shoppie FROM PUBLIC, anon, authenticated;
REVOKE EXECUTE ON ALL FUNCTIONS IN SCHEMA shoppie FROM PUBLIC, anon, authenticated;
-- no HNSW index yet: measure real catalog size and query latency first.

COMMIT;
