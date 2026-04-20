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
--  Dishes — source-of-truth for the recommendation engine
--  Replaces taste_chemistry.csv + vibe_category.csv + Metadata_Filters.csv
--  + dish_facets.csv (joined on dish_name + cuisine).
-- ───────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS dishes (
    -- Composite natural key (same dish_name can exist across cuisines)
    dish_id         SERIAL PRIMARY KEY,
    dish_name       TEXT NOT NULL,
    cuisine         TEXT NOT NULL,

    -- From Metadata_Filters.csv
    category            TEXT,
    dietary_type        TEXT,
    temp                TEXT,
    importance          REAL,
    primary_protein     TEXT,

    -- From taste_chemistry.csv (13 flavor dims — app.py has 13, engine uses 10)
    sweet       REAL DEFAULT 0,
    salt        REAL DEFAULT 0,
    sour        REAL DEFAULT 0,
    bitter      REAL DEFAULT 0,
    umami       REAL DEFAULT 0,
    spicy       REAL DEFAULT 0,
    fat         REAL DEFAULT 0,
    aromatic    REAL DEFAULT 0,
    crunch      REAL DEFAULT 0,
    chew        REAL DEFAULT 0,

    -- From vibe_category.csv
    context_string  TEXT,

    -- Facets (from dish_facets.csv) — kept as JSONB for flexibility
    facets          JSONB,

    -- Semantic embedding (384-d, from sentence-transformers all-MiniLM-L6-v2,
    -- L2-normalised so cosine distance = 1 - dot product)
    embedding       VECTOR(384),

    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    UNIQUE (dish_name, cuisine)
);

CREATE INDEX IF NOT EXISTS idx_dishes_cuisine  ON dishes(cuisine);
CREATE INDEX IF NOT EXISTS idx_dishes_category ON dishes(category);

-- ANN index for semantic recall (cosine). ivfflat needs rows before it
-- performs well; for now lists=50 is fine at 668 rows and will scale.
CREATE INDEX IF NOT EXISTS idx_dishes_embedding
    ON dishes USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 50);

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
