
CREATE TABLE IF NOT EXISTS symbol_tf(
    id SERIAL PRIMARY KEY,
    symbol	VARCHAR (12),
    tf	VARCHAR (3)
);

ALTER TABLE symbol_tf ALTER COLUMN symbol TYPE VARCHAR (12);
ALTER TABLE symbol_tf DROP CONSTRAINT IF EXISTS UQ_symbol_tf;

ALTER TABLE symbol_tf ADD CONSTRAINT UQ_symbol_tf UNIQUE (symbol,tf);

CREATE TABLE IF NOT EXISTS candles (
                       timestamp TIMESTAMP NOT NULL,
                        symbol	VARCHAR (16),
                        tf	VARCHAR (16),
                        o   DOUBLE PRECISION,
                        h   DOUBLE PRECISION,
                        l   DOUBLE PRECISION,
                        c   DOUBLE PRECISION,
                        v   DOUBLE PRECISION,
                        PRIMARY KEY (symbol, tf, timestamp)
                       );


SELECT create_hypertable('candles', 'timestamp', if_not_exists => TRUE, create_default_indexes => FALSE);

CREATE TABLE IF NOT EXISTS trades (
                       timestamp TIMESTAMP NOT NULL,
                       symbol_tf_id INTEGER,
                       price   DOUBLE PRECISION,
                       volume   DOUBLE PRECISION,
                       is_buyer   boolean,
                       PRIMARY KEY (symbol_tf_id, timestamp),
                       FOREIGN KEY (symbol_tf_id) REFERENCES symbol_tf (id)
                       );


SELECT create_hypertable('trades', 'timestamp', if_not_exists => TRUE, create_default_indexes => FALSE, chunk_time_interval => 86400000);
