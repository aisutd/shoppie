-- optional MySQL local-development extension; review before applying.
CREATE TABLE IF NOT EXISTS listing_embeddings (
    listing_id BIGINT UNSIGNED NOT NULL,
    model_name VARCHAR(191) NOT NULL,
    model_revision VARCHAR(64) NOT NULL,
    template_version VARCHAR(32) NOT NULL,
    input_text TEXT NOT NULL,
    input_hash CHAR(64) NOT NULL,
    dimensions INT NOT NULL CHECK (dimensions = 384),
    vector JSON NOT NULL,
    created_at DATETIME(6) NOT NULL,
    PRIMARY KEY (listing_id, model_name, model_revision, template_version),
    FOREIGN KEY (listing_id) REFERENCES listings(id) ON DELETE RESTRICT,
    CHECK (JSON_TYPE(vector) = 'ARRAY' AND JSON_LENGTH(vector) = 384)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
