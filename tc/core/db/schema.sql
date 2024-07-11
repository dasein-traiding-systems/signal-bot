
CREATE TABLE IF NOT EXISTS symbol_tf(
    id SERIAL PRIMARY KEY,
    symbol	VARCHAR (12),
    tf	VARCHAR (3),
    UNIQUE (symbol, tf)
);


CREATE TABLE IF NOT EXISTS candles (
                       timestamp TIMESTAMP NOT NULL,
                       symbol_tf_id INTEGER,
                        o   DOUBLE PRECISION,
                        h   DOUBLE PRECISION,
                        l   DOUBLE PRECISION,
                        c   DOUBLE PRECISION,
                        v   DOUBLE PRECISION,
                       PRIMARY KEY (symbol_tf_id, timestamp),
                       FOREIGN KEY (symbol_tf_id) REFERENCES symbol_tf (id)
                       );


SELECT create_hypertable('candles', 'timestamp', if_not_exists => TRUE);

CREATE TABLE IF NOT EXISTS trades (
                       timestamp TIMESTAMP NOT NULL,
                       symbol_tf_id INTEGER,
                       price   DOUBLE PRECISION,
                       volume   DOUBLE PRECISION,
                       is_buyer   boolean,
                       PRIMARY KEY (symbol_tf_id, timestamp),
                       FOREIGN KEY (symbol_tf_id) REFERENCES symbol_tf (id)
                       );


SELECT create_hypertable('trades', 'timestamp', if_not_exists => TRUE, chunk_time_interval => 86400000);

CREATE TABLE IF NOT EXISTS symbol_status (
                       symbol_tf_id INTEGER,
                       last_sync   TIMESTAMP NOT NULL,
                       last_volume   DOUBLE PRECISION,
                       active   boolean,
                       cluster_size DOUBLE PRECISION,
                       PRIMARY KEY (symbol_tf_id),
                       FOREIGN KEY (symbol_tf_id) REFERENCES symbol_tf (id)
                       );

CREATE TABLE IF NOT EXISTS clusters (
                       symbol_tf_id INTEGER,
                       timestamp   TIMESTAMP NOT NULL,
                       step DOUBLE PRECISION,
                       price_from   DOUBLE PRECISION,
                       price_to DOUBLE PRECISION,
                       volume  DOUBLE PRECISION
                       );

SELECT create_hypertable('clusters', 'timestamp', if_not_exists => TRUE, chunk_time_interval => 86400000);

CREATE TABLE IF NOT EXISTS levels (
                       symbol_tf_id INTEGER,
                       timestamp   TIMESTAMP NOT NULL,
                       level_value DOUBLE PRECISION,
                       level_type   INTEGER
                       );

CREATE TABLE IF NOT EXISTS arbitrage_delta (
                       symbol_tf_id INTEGER,
                       timestamp   TIMESTAMP NOT NULL,
                       delta DOUBLE PRECISION,
                       delta_perc DOUBLE PRECISION
                       );

SELECT create_hypertable('arbitrage_delta', 'timestamp', if_not_exists => TRUE);
