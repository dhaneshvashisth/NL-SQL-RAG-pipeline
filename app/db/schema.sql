
CREATE TYPE user_role AS ENUM ('admin', 'supervisor', 'agent');

CREATE TYPE transaction_status AS ENUM ('pending', 'completed',  'failed', 'reversed');

CREATE TYPE transaction_type AS ENUM ('deposit', 'withdrawal', 'bonus', 'adjustment');

CREATE TABLE IF NOT EXISTS users (
    id              SERIAL PRIMARY KEY,
    username        VARCHAR(50)  UNIQUE NOT NULL,
    email           VARCHAR(100) UNIQUE NOT NULL,
    hashed_password VARCHAR(255) NOT NULL,
    full_name       VARCHAR(100) NOT NULL,
    role            user_role    NOT NULL,

    parent_id       INTEGER REFERENCES users(id) ON DELETE SET NULL,

    is_active       BOOLEAN     DEFAULT TRUE,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);


CREATE INDEX IF NOT EXISTS idx_users_role      ON users(role);
CREATE INDEX IF NOT EXISTS idx_users_parent_id ON users(parent_id);
CREATE INDEX IF NOT EXISTS idx_users_username  ON users(username);

CREATE TABLE IF NOT EXISTS platforms (
    id           SERIAL PRIMARY KEY,
    name         VARCHAR(100) UNIQUE NOT NULL,
    code         VARCHAR(20)  UNIQUE NOT NULL,  -- short code e.g. 'DK', 'FD'
    is_active    BOOLEAN DEFAULT TRUE,
    created_at   TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS transactions (
    id               SERIAL PRIMARY KEY,
    reference_code   VARCHAR(50) UNIQUE NOT NULL,  -- external transaction ID
    agent_id         INTEGER NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    platform_id      INTEGER NOT NULL REFERENCES platforms(id) ON DELETE RESTRICT,

    -- The end user (customer) — not a registered system user
    -- We store their info directly, they don't log into our system
    customer_name    VARCHAR(100) NOT NULL,
    customer_phone   VARCHAR(20),

    amount           NUMERIC(12, 2) NOT NULL,  -- 12 digits, 2 decimal places
    transaction_type transaction_type NOT NULL,
    status           transaction_status NOT NULL DEFAULT 'pending',

    -- WHY STORE BOTH created_at AND processed_at?
    -- created_at = when transaction was received
    -- processed_at = when it was completed/failed
    -- Difference = processing time. Business KPI.
    created_at       TIMESTAMPTZ DEFAULT NOW(),
    processed_at     TIMESTAMPTZ,

    notes            TEXT  -- any manual notes added by agent
);

CREATE INDEX IF NOT EXISTS idx_txn_agent_id    ON transactions(agent_id);
CREATE INDEX IF NOT EXISTS idx_txn_platform_id ON transactions(platform_id);
CREATE INDEX IF NOT EXISTS idx_txn_status      ON transactions(status);
CREATE INDEX IF NOT EXISTS idx_txn_created_at  ON transactions(created_at);
CREATE INDEX IF NOT EXISTS idx_txn_type        ON transactions(transaction_type);


CREATE TABLE IF NOT EXISTS query_logs (
    id              SERIAL PRIMARY KEY,
    user_id         INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    natural_language_query  TEXT NOT NULL,       -- what user typed
    generated_sql           TEXT,                -- what pipeline generated
    was_cache_hit           BOOLEAN DEFAULT FALSE,
    execution_time_ms       INTEGER,             -- how long the full pipeline took
    row_count               INTEGER,             -- how many rows returned
    error_message           TEXT,                -- NULL if successful
    created_at              TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_query_logs_user_id    ON query_logs(user_id);
CREATE INDEX IF NOT EXISTS idx_query_logs_created_at ON query_logs(created_at);


CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_users_updated_at
    BEFORE UPDATE ON users
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();