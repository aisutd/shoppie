"""Isolated demo storage; same small methods are provided by PostgresStore."""

from datetime import datetime
from contextlib import contextmanager
from decimal import Decimal
from hashlib import sha256
import json
from pathlib import Path
import sqlite3

from db.normalize import normalize
from db.embeddings import validate_vector

ROOT = Path(__file__).resolve().parents[1]


def json_value(value):
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    raise TypeError("unsupported stored value")


def listing_id(row):
    return sha256((row["retailer_key"] + "\n" + row["source_url"]).encode()).hexdigest()


class LocalStore:
    def __init__(self, path=None):
        self.path = Path(path or ROOT / ".local/demo.sqlite3")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS catalog (id TEXT PRIMARY KEY, observed_at TEXT NOT NULL, data TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS observations (
                    listing_id TEXT NOT NULL REFERENCES catalog(id), observed_at TEXT NOT NULL,
                    data TEXT NOT NULL, PRIMARY KEY (listing_id, observed_at));
                CREATE TABLE IF NOT EXISTS embeddings (
                    listing_id TEXT PRIMARY KEY REFERENCES catalog(id), data TEXT NOT NULL);
            """)

    @contextmanager
    def connect(self):
        connection = sqlite3.connect(self.path, timeout=10)
        connection.execute("PRAGMA foreign_keys = ON")
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def ingest(self, row):
        record = normalize(row)
        identity = listing_id(record)
        data = json.dumps(record, default=json_value, sort_keys=True, allow_nan=False)
        time = record["scraped_at"].isoformat()
        with self.connect() as db:
            # checks conflicts before changing the latest descriptive snapshot
            existing = db.execute("SELECT data FROM observations WHERE listing_id=? AND observed_at=?",
                                  (identity, time)).fetchone()
            if existing:
                if json.loads(existing[0]) == json.loads(data):
                    return "skipped"
                raise ValueError("observation conflicts at the same listing/time")
            db.execute("""INSERT INTO catalog VALUES (?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET observed_at=excluded.observed_at, data=excluded.data
                WHERE excluded.observed_at > catalog.observed_at""", (identity, time, data))
            db.execute("INSERT INTO observations VALUES (?, ?, ?)", (identity, time, data))
        return "imported"

    def listings(self):
        with self.connect() as db:
            rows = db.execute("SELECT id, data FROM catalog ORDER BY id").fetchall()
        return [{**json.loads(data), "id": identity} for identity, data in rows]

    def history(self, identity):
        with self.connect() as db:
            rows = db.execute("SELECT data FROM observations WHERE listing_id=? ORDER BY observed_at", (identity,)).fetchall()
        return [json.loads(row[0]) for row in rows]

    def get_embedding(self, identity):
        with self.connect() as db:
            row = db.execute("SELECT data FROM embeddings WHERE listing_id=?", (identity,)).fetchone()
        return json.loads(row[0]) if row else None

    def put_embedding(self, identity, data):
        data = {**data, "vector": validate_vector(data["vector"])}
        with self.connect() as db:
            db.execute("INSERT INTO embeddings VALUES (?, ?) ON CONFLICT(listing_id) DO UPDATE SET data=excluded.data",
                       (identity, json.dumps(data, allow_nan=False)))
