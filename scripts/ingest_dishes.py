"""
One-time dish ingestion script.

Reads the four dish CSVs (taste_chemistry, vibe_category, Metadata_Filters,
dish_facets), joins them on (dish_name, cuisine), computes 384-d embeddings
from each dish's context_string using sentence-transformers, and UPSERTs
everything into the `dishes` table in Postgres.

Usage:
    python3 scripts/ingest_dishes.py

Safe to re-run: it uses ON CONFLICT (dish_name, cuisine) DO UPDATE so
changes to CSVs propagate cleanly without creating duplicates.

After a successful run, the recommendation engine reads from Postgres and
the CSVs become import artifacts (still useful for cold-start / disaster
recovery, but no longer read at runtime).
"""

from __future__ import annotations

import os
import sys
import json
from pathlib import Path

import numpy as np
import pandas as pd
from dotenv import load_dotenv

# Make sibling imports work when run from project root
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

load_dotenv(ROOT / ".env")

from psycopg.types.json import Jsonb  # noqa: E402
from pgvector.psycopg import register_vector  # noqa: E402

from db import _pool  # noqa: E402


DATA_DIR = ROOT / "data"

FLAVOR_DIMS = [
    "sweet", "salt", "sour", "bitter", "umami",
    "spicy", "fat", "aromatic", "crunch", "chew",
]

FACET_COLUMNS = [
    "cooking_methods", "heat_intensity", "preparation_complexity",
    "flavor_anchors", "spice_lineage", "fat_character", "aromatic_signature",
    "texture_profile", "marinade_family", "sauce_role", "course_role",
    "serving_temperature", "portion_format", "richness",
    "substitution_class", "ingredient_swaps", "regional_origin",
    "cultural_kin", "meal_occasion", "dominant_color", "visual_appeal",
]


def _clean(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    # Drop duplicate header rows that sometimes appear mid-file
    if "dish_name" in df.columns:
        df = df[df["dish_name"] != "dish_name"].copy()
    # Drop trailing Unnamed columns
    df = df.drop(columns=[c for c in df.columns if str(c).startswith("Unnamed")], errors="ignore")
    # Trim strings
    for c in ("dish_name", "cuisine"):
        if c in df.columns:
            df[c] = df[c].astype(str).str.strip()
    df = df.reset_index(drop=True)
    return df


def load_and_merge() -> pd.DataFrame:
    """Read all four CSVs and merge on (dish_name, cuisine)."""
    taste = _clean(pd.read_csv(DATA_DIR / "taste_chemistry.csv"))
    vibe  = _clean(pd.read_csv(DATA_DIR / "vibe_category.csv"))
    meta  = _clean(pd.read_csv(DATA_DIR / "Metadata_Filters.csv"))
    facets = _clean(pd.read_csv(DATA_DIR / "dish_facets.csv"))

    # Coerce flavor dims to float
    for col in FLAVOR_DIMS:
        if col in taste.columns:
            taste[col] = pd.to_numeric(taste[col], errors="coerce").fillna(0.0)

    # Coerce importance to float
    if "importance" in meta.columns:
        meta["importance"] = pd.to_numeric(meta["importance"], errors="coerce").fillna(0.0)

    keys = ["dish_name", "cuisine"]
    merged = (
        meta.merge(taste, on=keys, how="inner")
            .merge(vibe, on=keys, how="inner")
            .merge(facets, on=keys, how="left")
            .reset_index(drop=True)
    )
    print(f"Merged rows: {len(merged)}  (meta={len(meta)}, taste={len(taste)}, vibe={len(vibe)}, facets={len(facets)})")
    return merged


def compute_embeddings(contexts: list[str]) -> np.ndarray:
    """Encode context_strings with the same model the engine uses."""
    from sentence_transformers import SentenceTransformer

    print("Loading sentence-transformer (all-MiniLM-L6-v2)...")
    model = SentenceTransformer("all-MiniLM-L6-v2")
    print(f"Encoding {len(contexts)} dish contexts...")
    emb = model.encode(
        contexts,
        show_progress_bar=True,
        normalize_embeddings=True,  # so cosine = dot product later
    ).astype(np.float32)
    assert emb.shape[1] == 384, f"expected 384-d embeddings, got {emb.shape}"
    return emb


def build_facet_json(row: pd.Series) -> dict:
    out = {}
    for col in FACET_COLUMNS:
        if col in row and pd.notna(row[col]):
            val = str(row[col]).strip()
            if val:
                out[col] = val
    return out


def upsert(df: pd.DataFrame, embeddings: np.ndarray) -> None:
    sql = """
        INSERT INTO dishes (
            dish_name, cuisine, category, dietary_type, temp, importance,
            primary_protein,
            sweet, salt, sour, bitter, umami, spicy, fat, aromatic, crunch, chew,
            context_string, facets, embedding, updated_at
        ) VALUES (
            %(dish_name)s, %(cuisine)s, %(category)s, %(dietary_type)s,
            %(temp)s, %(importance)s, %(primary_protein)s,
            %(sweet)s, %(salt)s, %(sour)s, %(bitter)s, %(umami)s, %(spicy)s,
            %(fat)s, %(aromatic)s, %(crunch)s, %(chew)s,
            %(context_string)s, %(facets)s, %(embedding)s, NOW()
        )
        ON CONFLICT (dish_name, cuisine) DO UPDATE SET
            category = EXCLUDED.category,
            dietary_type = EXCLUDED.dietary_type,
            temp = EXCLUDED.temp,
            importance = EXCLUDED.importance,
            primary_protein = EXCLUDED.primary_protein,
            sweet = EXCLUDED.sweet, salt = EXCLUDED.salt, sour = EXCLUDED.sour,
            bitter = EXCLUDED.bitter, umami = EXCLUDED.umami, spicy = EXCLUDED.spicy,
            fat = EXCLUDED.fat, aromatic = EXCLUDED.aromatic,
            crunch = EXCLUDED.crunch, chew = EXCLUDED.chew,
            context_string = EXCLUDED.context_string,
            facets = EXCLUDED.facets,
            embedding = EXCLUDED.embedding,
            updated_at = NOW();
    """

    with _pool.connection() as conn:
        register_vector(conn)
        with conn.cursor() as cur:
            batch = []
            for (_, row), emb in zip(df.iterrows(), embeddings):
                params = {
                    "dish_name": str(row["dish_name"]),
                    "cuisine": str(row["cuisine"]),
                    "category": str(row.get("category") or "") or None,
                    "dietary_type": str(row.get("dietary_type") or "") or None,
                    "temp": str(row.get("temp") or "") or None,
                    "importance": float(row.get("importance") or 0.0),
                    "primary_protein": str(row.get("primary_protein") or "") or None,
                    "context_string": str(row.get("context_string") or "") or None,
                    "facets": Jsonb(build_facet_json(row)),
                    "embedding": emb,
                }
                for dim in FLAVOR_DIMS:
                    params[dim] = float(row.get(dim) or 0.0)
                batch.append(params)

            cur.executemany(sql, batch)
        conn.commit()
    print(f"UPSERTed {len(df)} dishes.")


def main() -> int:
    df = load_and_merge()
    emb = compute_embeddings(df["context_string"].fillna("").tolist())
    upsert(df, emb)

    # Verify
    with _pool.connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) AS n FROM dishes")
        n = cur.fetchone()["n"]
        cur.execute("SELECT COUNT(*) AS n FROM dishes WHERE embedding IS NOT NULL")
        with_emb = cur.fetchone()["n"]
        cur.execute("SELECT cuisine, COUNT(*) AS n FROM dishes GROUP BY cuisine ORDER BY cuisine")
        by_cuisine = cur.fetchall()

    print(f"\n✓ dishes table: {n} rows, {with_emb} with embeddings")
    print("  By cuisine:")
    for r in by_cuisine:
        print(f"    {r['cuisine']:<20} {r['n']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
