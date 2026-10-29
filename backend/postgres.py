"""Explicit backend-only adapter for the proposed shoppie PostgreSQL schema."""

from contextlib import contextmanager
import json
import os

from backend.storage import json_value, listing_id
from db.embeddings import MODEL_NAME, MODEL_REVISION, TEMPLATE_VERSION, validate_vector, build_text, metadata_for
from db.normalize import normalize
from backend.settings import setting


class PostgresStore:
    def __init__(self, dsn=None, allow_writes=False):
        self.dsn = dsn or setting("SHOPPIE_DATABASE_URL")
        self.allow_writes = allow_writes
        if not self.dsn:
            raise ValueError("Set backend-only SHOPPIE_DATABASE_URL after mentor schema approval")

    @contextmanager
    def connect(self):
        import psycopg
        from psycopg.rows import dict_row
        # transaction-pooler compatible connections never appear in the frontend
        try:
            options = "-c default_transaction_read_only=off" if self.allow_writes else "-c default_transaction_read_only=on"
            with psycopg.connect(self.dsn, row_factory=dict_row, prepare_threshold=None, connect_timeout=10, options=options) as db:
                yield db
        except psycopg.Error:
            raise ValueError("PostgreSQL operation failed; check connectivity, role grants, and approved schema. Connection details were withheld.") from None

    def inspect(self):
        with self.connect() as db:
            columns = db.execute("""SELECT table_name,column_name,data_type,udt_name
                FROM information_schema.columns WHERE table_schema=%s
                ORDER BY table_name,ordinal_position""", ("shoppie",)).fetchall()
            vector = db.execute("SELECT extversion FROM pg_extension WHERE extname=%s", ("vector",)).fetchone()
        return {"columns": columns, "pgvector_installed": bool(vector), "read_only": not self.allow_writes}

    def require_writes(self):
        if (not self.allow_writes or setting("SHOPPIE_DATABASE_WRITES") != "1"
                or setting("SHOPPIE_DATABASE_ENV") not in {"development", "test"}
                or setting("SHOPPIE_SCHEMA_APPROVED") != "1"):
            raise ValueError("Shared writes disabled: explicit allow_writes, test/development environment, schema approval, and SHOPPIE_DATABASE_WRITES=1 are all required.")
        report = self.inspect()
        names = {row["table_name"] for row in report["columns"]}
        if not report["pgvector_installed"] or not {"listings", "observations", "embeddings"} <= names:
            raise ValueError("Required approved shoppie schema is missing; no writes performed")

    def ingest(self, row):
        self.require_writes()
        from psycopg.types.json import Jsonb
        record = normalize(row)
        identity = listing_id(record)
        with self.connect() as db:
            existing = db.execute("SELECT * FROM shoppie.observations WHERE listing_id=%s AND scraped_at=%s FOR UPDATE",
                                  (identity, record["scraped_at"])).fetchone()
            if existing:
                fields = ("price", "shipping_cost", "currency", "condition", "seller", "availability", "raw_payload")
                if all(existing[field] == record[field] for field in fields):
                    return "skipped"
                raise ValueError("observation conflicts at the same listing/time")
            fields = ("retailer_key", "retailer_sku", "source_url", "source_url_hash", "title",
                      "description", "brand", "model_number", "gtin", "category")
            db.execute("""INSERT INTO shoppie.listings
                (id,retailer_key,retailer_sku,source_url,source_url_hash,title,description,
                 brand,model_number,gtin,category,attributes,details_observed_at,identity_input_hash)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                ON CONFLICT(id) DO UPDATE SET retailer_sku=excluded.retailer_sku,
                title=excluded.title, description=excluded.description, brand=excluded.brand,
                model_number=excluded.model_number, gtin=excluded.gtin, category=excluded.category,
                attributes=excluded.attributes, details_observed_at=excluded.details_observed_at,
                identity_input_hash=excluded.identity_input_hash
                WHERE excluded.details_observed_at > shoppie.listings.details_observed_at""",
                (identity,) + tuple(record[field] for field in fields) + (Jsonb(record["attributes"]), record["scraped_at"], metadata_for(build_text(record) or "")["input_hash"]))
            db.execute("""INSERT INTO shoppie.observations
                (listing_id,scraped_at,price,shipping_cost,currency,condition,seller,availability,raw_payload)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                (identity, record["scraped_at"], record["price"], record["shipping_cost"], record["currency"],
                 record["condition"], record["seller"], record["availability"], Jsonb(record["raw_payload"])))
        return "imported"

    def listings(self):
        with self.connect() as db:
            rows = db.execute("""SELECT l.*, o.scraped_at, o.price, o.shipping_cost, o.currency,
                o.condition, o.seller, o.availability, o.raw_payload FROM shoppie.listings l
                JOIN shoppie.current_offers o ON o.listing_id=l.id ORDER BY l.id""").fetchall()
        return json.loads(json.dumps(rows, default=json_value))

    def history(self, identity):
        with self.connect() as db:
            rows = db.execute("SELECT * FROM shoppie.observations WHERE listing_id=%s ORDER BY scraped_at", (identity,)).fetchall()
        return json.loads(json.dumps(rows, default=json_value))

    def get_embedding(self, identity):
        with self.connect() as db:
            row = db.execute("""SELECT *, embedding::text AS vector_text FROM shoppie.embeddings
                WHERE listing_id=%s AND model_name=%s AND model_revision=%s AND template_version=%s""",
                (identity, MODEL_NAME, MODEL_REVISION, TEMPLATE_VERSION)).fetchone()
        if row:
            row["vector"] = json.loads(row.pop("vector_text"))
            row.pop("embedding", None)
        return row

    def put_embedding(self, identity, data):
        self.require_writes()
        vector = json.dumps(validate_vector(data["vector"]))
        with self.connect() as db:
            db.execute("""INSERT INTO shoppie.embeddings
                (listing_id,model_name,model_revision,template_version,input_text,input_hash,dimensions,embedding,created_at)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s::extensions.vector,%s)
                ON CONFLICT(listing_id,model_name,model_revision,template_version)
                DO UPDATE SET input_text=excluded.input_text,input_hash=excluded.input_hash,
                embedding=excluded.embedding,created_at=excluded.created_at""",
                (identity, data["model_name"], data["model_revision"], data["template_version"],
                 data["input_text"], data["input_hash"], 384, vector, data["created_at"]))

    def vector_candidates(self, query_vector, request):
        with self.connect() as db:
            return db.execute("SELECT * FROM shoppie.vector_candidates(%s::extensions.vector,%s,%s,%s,%s,%s,%s,%s,%s)",
                (json.dumps(validate_vector(query_vector)), MODEL_REVISION, TEMPLATE_VERSION, request.category,
                 request.min_price, request.max_price, request.availability, request.brand, request.limit)).fetchall()
