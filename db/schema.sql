-- local MySQL 8.0.16+ schema for the schema_version 1 listing contract.
-- run only against a new, mentor-approved local database; this is not a migration.
-- db/legacy_lesson_schema.sql and sql/schema.sql are separate Supabase lessons.

CREATE TABLE IF NOT EXISTS retailers (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
    retailer_key VARCHAR(32) NOT NULL UNIQUE,
    name VARCHAR(100) NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

INSERT INTO retailers (retailer_key, name) VALUES
    ('amazon', 'Amazon'), ('walmart', 'Walmart'),
    ('target', 'Target'), ('best_buy', 'Best Buy')
ON DUPLICATE KEY UPDATE retailer_key = VALUES(retailer_key);

CREATE TABLE IF NOT EXISTS listings (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
    retailer_id BIGINT UNSIGNED NOT NULL,
    retailer_sku VARCHAR(255) NULL,
    source_url TEXT NOT NULL,
    source_url_hash CHAR(64) NOT NULL,
    title TEXT NULL,
    brand VARCHAR(255) NULL,
    model_number VARCHAR(255) NULL,
    gtin VARCHAR(32) NULL,
    category VARCHAR(100) NULL,
    attributes JSON NOT NULL,
    details_observed_at DATETIME(6) NOT NULL,
    CONSTRAINT fk_listings_retailer FOREIGN KEY (retailer_id) REFERENCES retailers(id) ON DELETE RESTRICT,
    CONSTRAINT uq_listing_source UNIQUE (retailer_id, source_url_hash),
    INDEX ix_listing_model (brand, model_number),
    INDEX ix_listing_category (category)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS listing_observations (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
    listing_id BIGINT UNSIGNED NOT NULL,
    scraped_at DATETIME(6) NOT NULL,
    price DECIMAL(12,2) NULL,
    shipping_cost DECIMAL(12,2) NULL,
    currency CHAR(3) NULL,
    `condition` VARCHAR(32) NULL,
    seller VARCHAR(255) NULL,
    availability VARCHAR(32) NULL,
    raw_payload JSON NOT NULL,
    CONSTRAINT fk_observation_listing FOREIGN KEY (listing_id) REFERENCES listings(id) ON DELETE RESTRICT,
    CONSTRAINT uq_observation_time UNIQUE (listing_id, scraped_at),
    CONSTRAINT ck_price CHECK (price IS NULL OR price >= 0),
    CONSTRAINT ck_shipping CHECK (shipping_cost IS NULL OR shipping_cost >= 0),
    CONSTRAINT ck_currency CHECK (currency IS NULL OR currency = 'USD'),
    CONSTRAINT ck_money_currency CHECK ((price IS NULL AND shipping_cost IS NULL) OR (currency IS NOT NULL AND currency = 'USD')),
    CONSTRAINT ck_condition CHECK (`condition` IS NULL OR `condition` IN ('new', 'used', 'refurbished', 'open_box')),
    CONSTRAINT ck_availability CHECK (availability IS NULL OR availability IN ('in_stock', 'out_of_stock', 'unknown')),
    INDEX ix_observation_history (listing_id, scraped_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
