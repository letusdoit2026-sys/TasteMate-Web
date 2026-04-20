-- ═══════════════════════════════════════════════════════════════════════════
--  TasteMate Web — Postgres Schema
--  Requires: Postgres 17+ with pgvector extension
-- ═══════════════════════════════════════════════════════════════════════════

CREATE EXTENSION IF NOT EXISTS vector;

-- ───────────────────────────────────────────────────────────────────────────
--  Users
-- ───────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS users (
    id                    TEXT PRIMARY KEY,
    username              TEXT UNIQUE NOT NULL,
    email                 TEXT UNIQUE NOT NULL,
    password_hash         TEXT NOT NULL,
    security_question     TEXT,
    security_answer_hash  TEXT,
    created_at            TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ───────────────────────────────────────────────────────────────────────────
--  Audit Logs
-- ───────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS audit_logs (
    id                   TEXT PRIMARY KEY,
    user_id              TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    username             TEXT NOT NULL,
    action               TEXT NOT NULL,
    timestamp            TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    source_cuisine       TEXT,
    favorite_dishes      JSONB,
    taste_preferences    JSONB,
    target_cuisines      JSONB,
    recommendations      JSONB,
    scoring_details      JSONB,
    user_profile_vector  JSONB
);

CREATE INDEX IF NOT EXISTS idx_audit_user ON audit_logs(user_id);
CREATE INDEX IF NOT EXISTS idx_audit_ts   ON audit_logs(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_audit_action ON audit_logs(action);

-- ───────────────────────────────────────────────────────────────────────────
--  Personas — per-user long-term taste profile
--  Six layers: flavor_vector, facet_affinity, embedding_centroid,
--  cuisine_affinity, hard_constraints, rejection_history
-- ───────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS personas (
    user_id              TEXT PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,

    -- Layer 1: Flavor vector (13-dim) averaged from user's favorite dishes
    flavor_vector        JSONB,

    -- Layer 2: Facet affinity — { category: { value: weight } }
    facet_affinity       JSONB,

    -- Layer 3: Embedding centroid (384-dim from all-MiniLM-L6-v2)
    embedding_centroid   VECTOR(384),

    -- Layer 4: Cuisine affinity — { cuisine_name: weight }
    cuisine_affinity     JSONB,

    -- Layer 5: Hard constraints — { dietary: "...", allowed_proteins: [...] }
    hard_constraints     JSONB,

    -- Layer 6: Rejection history — list of dish_ids or names the user disliked
    rejection_history    JSONB DEFAULT '[]'::jsonb,

    favorite_dish_ids    JSONB DEFAULT '[]'::jsonb,
    favorite_cuisines    JSONB DEFAULT '[]'::jsonb,

    last_rebuilt_at      TIMESTAMPTZ,
    created_at           TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at           TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Approximate nearest-neighbor index on the persona centroid
-- (for future "find similar users" / group matching use cases)
CREATE INDEX IF NOT EXISTS idx_persona_centroid
    ON personas USING ivfflat (embedding_centroid vector_cosine_ops)
    WITH (lists = 100);

-- ───────────────────────────────────────────────────────────────────────────
--  Groups — for group dining recommendations
-- ───────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS groups (
    id           TEXT PRIMARY KEY,
    name         TEXT NOT NULL,
    owner_id     TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    city         TEXT,
    zip_code     TEXT,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    metadata     JSONB
);

CREATE INDEX IF NOT EXISTS idx_groups_owner ON groups(owner_id);

-- ───────────────────────────────────────────────────────────────────────────
--  Group Members (junction)
-- ───────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS group_members (
    group_id    TEXT NOT NULL REFERENCES groups(id) ON DELETE CASCADE,
    user_id     TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    role        TEXT NOT NULL DEFAULT 'member',   -- 'owner' | 'member'
    joined_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (group_id, user_id)
);

CREATE INDEX IF NOT EXISTS idx_group_members_user ON group_members(user_id);
