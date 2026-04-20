"""
Hybrid Intersection Recommendation Engine
==========================================
Postgres + pgvector 6-step pipeline:
  1. Hard Filtering    (dishes table — boolean masks on in-memory DataFrame)
  2. Semantic Recall   (pgvector cosine — replaces FAISS)
  3. Threshold Guard   (flavor mouthfeel)
  4. Euclidean Rank    (flavor distance)
  5. Cuisine Bridge    (discovery bonus)
  6. Tie-Breaking      (importance)

Data source: Postgres `dishes` table (loaded once at __init__).
Embeddings:  pulled from the VECTOR(384) column — no re-encoding at startup.
"""

from __future__ import annotations

import os
import numpy as np
import pandas as pd
from pgvector.psycopg import register_vector

# ══════════════════════════════════════════════════════════════════════════════
#  CONSTANTS
# ══════════════════════════════════════════════════════════════════════════════

FLAVOR_DIMS = [
    "sweet", "salt", "sour", "bitter", "umami",
    "spicy", "fat", "aromatic", "crunch", "chew",
]

# Embedding model — small & fast (~80 MB, runs on CPU)
EMBED_MODEL_NAME = "all-MiniLM-L6-v2"

# Pipeline tunables
SEMANTIC_TOP_K = 30          # Step 2: retrieve top-K from FAISS
CRUNCH_THRESHOLD = 0.7       # Step 3: seed threshold for crunch guard
SPICY_THRESHOLD = 0.7        # Step 3: seed threshold for spicy guard
MOUTHFEEL_MIN = 0.6          # Step 3: candidate must exceed this
ANCHOR_THRESHOLD = 0.8       # Step 3: seed umami/aromatic anchor trigger
ANCHOR_MIN = 0.7             # Step 3: candidate must exceed this for anchored dims
FLAVOR_WEIGHT = 2.0          # Step 4: multiply flavor distance weight vs semantic
DISCOVERY_BONUS = 0.10       # Step 5: 10% distance reduction
DISCOVERY_MAX_DIST = 0.5     # Step 5: only apply bonus if distance is already below this
RESULTS_COUNT = 3            # Final output size
CROSS_COURSE_OVERFLOW_MARGIN = 0.0   # Cross-course dish overflows if it beats the worst in-course score (0 = just needs to be better)

# Refinement 1: Warm Spice Cluster — keywords that indicate warm aromatic DNA
# Uses substring matching, so "cinnamon," or "cloves" will both match
WARM_SPICE_KEYWORDS = [
    "cinnamon", "clove", "allspice", "nutmeg", "cardamom",
    "star anise", "mace", "whole spice", "warm spice",
    "garam masala", "saffron", "bay leaf",
]
WARM_SPICE_DISTANCE_REDUCTION = 0.15   # 15% euclidean distance reduction

# Refinement 2: Integrated Carbs — rice/pasta cooked INTO the dish
INTEGRATED_CARB_KEYWORDS = [
    "cooked with rice", "rice cooked", "baked with pasta", "pasta baked",
    "cooked in rice", "rice dish", "layered rice", "one-pot rice",
    "layered basmati", "basmati rice",
    "pilaf", "biryani", "paella", "risotto", "pulao", "fried rice",
    "youvetsi", "orzo", "rice casserole", "noodle soup",
    "khao", "arroz", "turmeric rice",
]
INTEGRATED_CARB_BOOST = 0.25           # 25% distance reduction for matching integrated-carb dishes
PROTEIN_MATCH_BOOST = 0.15             # 15% distance reduction when candidate protein matches seed

# Fix 3: Cross-region aromatic relaxation — Mediterranean aromatics (oregano/garlic)
# differ from Indian aromatics (cumin/cardamom), so lower the gate when crossing
AROMATIC_RELAXED_CUISINES = {
    ("indian", "greek"), ("indian", "italian"), ("indian", "mexican"),
    ("thai", "greek"), ("thai", "italian"), ("thai", "mexican"),
}
AROMATIC_GATE_RELAXATION = 0.2         # lower the hard-gate by this amount for cross-region

# Protein group mapping: UI selection → primary_protein values in CSV
PROTEIN_GROUPS = {
    "chicken": {"Chicken", "Chicken Liver"},
    "fish": {"Fish", "Salmon", "Tuna", "Sardines", "Anchovies", "Fish Roe",
             "Shrimp", "Dried Shrimp", "Squid", "Octopus", "Crab", "Lobster",
             "Clams", "Mussels", "Scallops", "Mixed Seafood"},
    "lamb": {"Lamb", "Goat"},
    "beef": {"Beef", "Veal"},
    "pork": {"Pork", "Wild Boar"},
    "duck": {"Duck", "Quail", "Rabbit"},
    "egg": {"Egg"},
}

# All meat/animal proteins (union of all groups)
ALL_MEAT_PROTEINS = set()
for _v in PROTEIN_GROUPS.values():
    ALL_MEAT_PROTEINS |= _v
ALL_MEAT_PROTEINS.add("Mixed Meats")
ALL_MEAT_PROTEINS.add("Mixed")


class HybridEngine:
    """Postgres-backed hybrid recommendation engine (pgvector for semantic recall)."""

    def __init__(self, data_dir, similarity_csv=None):
        # data_dir is kept for backward compat (used only for similarity.csv).
        self.data_dir = data_dir

        # ── Load all dishes from Postgres into an in-memory DataFrame ──
        # At 668 dishes this is ~a few MB; filters use vectorised numpy masks.
        # Postgres is the source of truth; this is the working set.
        from db import _pool
        with _pool.connection() as conn:
            register_vector(conn)
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT dish_id, dish_name, cuisine, category, dietary_type,
                           temp, importance, primary_protein,
                           sweet, salt, sour, bitter, umami, spicy, fat,
                           aromatic, crunch, chew,
                           context_string, facets, embedding
                    FROM dishes
                    ORDER BY dish_id
                """)
                rows = cur.fetchall()

        if not rows:
            raise RuntimeError(
                "dishes table is empty — run `python3 scripts/ingest_dishes.py` first."
            )

        # Build the DataFrame (same schema the rest of the engine expects)
        self.dishes = pd.DataFrame(rows)
        # Coerce flavor dims + importance to float
        for col in FLAVOR_DIMS + ["importance"]:
            if col in self.dishes.columns:
                self.dishes[col] = pd.to_numeric(
                    self.dishes[col], errors="coerce",
                ).fillna(0.0)

        # Extract embeddings as a single (N, 384) numpy matrix.
        # Kept in memory for fast access when we batch-compute during pipeline
        # fallbacks, but the primary semantic-recall path uses pgvector (below).
        self.embeddings = np.vstack(self.dishes["embedding"].tolist()).astype(np.float32)
        self.dishes = self.dishes.drop(columns=["embedding"])

        # ── Cuisine similarity matrix (optional, still CSV for now) ──
        self.sim_df = None
        if similarity_csv and os.path.exists(similarity_csv):
            self.sim_df = pd.read_csv(similarity_csv, index_col=0)

        # ── Flavour matrix (NumPy, vectorised for Euclidean step) ──
        self.flavor_matrix = self.dishes[FLAVOR_DIMS].values.astype(np.float32)

        # Name → row mapping (dish names may not be unique → first match wins)
        self._name_to_idx = {}
        for i, name in enumerate(self.dishes["dish_name"]):
            if name not in self._name_to_idx:
                self._name_to_idx[name] = i

        # dish_id → row index mapping (used to map pgvector results back to
        # DataFrame rows)
        self._id_to_idx = {
            int(did): i for i, did in enumerate(self.dishes["dish_id"].tolist())
        }

    # ──────────────────────────────────────────────────────────────────────
    #  Semantic recall via pgvector (replaces FAISS)
    # ──────────────────────────────────────────────────────────────────────
    def _semantic_recall(
        self,
        seed_idx: int,
        eligible_indices: np.ndarray,
        k: int,
    ) -> list[tuple[int, float]]:
        """
        Return up to `k` (row_idx, cosine_score) pairs from `eligible_indices`,
        ranked by cosine similarity to the seed's embedding — using pgvector.

        Uses `<=>` (cosine distance): score = 1 - distance, so larger is closer.
        """
        from db import _pool

        seed_emb = self.embeddings[seed_idx]
        # Map pandas row indices → dish_ids for the WHERE clause
        eligible_ids = self.dishes.iloc[eligible_indices]["dish_id"].astype(int).tolist()
        if not eligible_ids:
            return []

        with _pool.connection() as conn:
            register_vector(conn)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT dish_id,
                           1 - (embedding <=> %s::vector) AS score
                    FROM dishes
                    WHERE dish_id = ANY(%s)
                    ORDER BY embedding <=> %s::vector
                    LIMIT %s
                    """,
                    (seed_emb, eligible_ids, seed_emb, k),
                )
                rows = cur.fetchall()

        out: list[tuple[int, float]] = []
        for r in rows:
            idx = self._id_to_idx.get(int(r["dish_id"]))
            if idx is not None and idx != seed_idx:
                out.append((idx, float(r["score"])))
        return out

    # ──────────────────────────────────────────────────────────────────────
    #  PUBLIC API
    # ──────────────────────────────────────────────────────────────────────

    def get_recommendations(
        self,
        seed_dish: str,
        user_preferences: dict | None = None,
        discovery_mode: bool = True,
        target_cuisine: str | None = None,
    ) -> list[dict]:
        """
        Run the 6-step hybrid pipeline with Course Overflow.

        First runs within the seed's course (or sibling courses).
        Then runs a cross-course pass (all categories). If any cross-course
        dish scores higher than the worst in-course result by at least
        CROSS_COURSE_OVERFLOW_MARGIN points, it replaces that result.

        Parameters
        ----------
        seed_dish : str
            Name of the dish the user likes.
        user_preferences : dict, optional
            Keys: dietary, category, target_cuisine, discovery_mode.
        target_cuisine : str, optional
            If provided, only recommend from this cuisine.
        discovery_mode : bool
            If True, apply cross-cuisine bonus (Step 5).

        Returns
        -------
        list[dict]  – Top recommendations with scores and metadata.
        """
        prefs = user_preferences or {}
        dietary = prefs.get("dietary", "").strip().lower()
        category_filter = prefs.get("category", "").strip()
        target_cuisine = target_cuisine or prefs.get("target_cuisine", "")
        discovery_mode = prefs.get("discovery_mode", discovery_mode)
        allowed_proteins = prefs.get("allowed_proteins", "any")

        seed_idx = self._name_to_idx.get(seed_dish)
        if seed_idx is None:
            return {"error": f"Seed dish '{seed_dish}' not found in dataset."}

        seed_row = self.dishes.iloc[seed_idx]
        seed_cuisine = str(seed_row["cuisine"]).strip()
        seed_category = str(seed_row["category"]).strip()

        # ── Build base mask (dietary + protein + target cuisine) ─────────
        base_mask = np.ones(len(self.dishes), dtype=bool)
        base_mask[seed_idx] = False
        if dietary:
            base_mask = base_mask & self._dietary_mask(dietary)
        if allowed_proteins != "any" and isinstance(allowed_proteins, list):
            base_mask = base_mask & self._protein_mask(allowed_proteins, dietary)
        if target_cuisine:
            base_mask = base_mask & (
                self.dishes["cuisine"].str.lower() == target_cuisine.lower()
            )

        # ── Pass 1: Within-course (same category or siblings) ────────────
        if category_filter:
            course_mask = base_mask & (
                self.dishes["category"].str.lower() == category_filter.lower()
            )
        else:
            SIBLING_CATEGORIES = {"appetizer": {"appetizer", "salad"}, "salad": {"appetizer", "salad"}}
            allowed_cats = SIBLING_CATEGORIES.get(seed_category.lower(), {seed_category.lower()})
            course_mask = base_mask & (
                self.dishes["category"].str.lower().isin(allowed_cats)
            )

        in_course_indices = np.where(course_mask)[0]
        in_course_results = []
        in_course_stats = {}
        if len(in_course_indices) > 0:
            in_course_results, in_course_stats = self._run_pipeline(
                seed_idx, in_course_indices, discovery_mode, count=RESULTS_COUNT,
            )

        # ── Pass 2: Cross-course (all categories) ───────────────────────
        all_indices = np.where(base_mask)[0]
        cross_course_results = []
        cross_course_stats = {}
        if len(all_indices) > 0:
            cross_course_results, cross_course_stats = self._run_pipeline(
                seed_idx, all_indices, discovery_mode, count=RESULTS_COUNT * 2,
            )

        # ── Course Overflow: merge best of both passes ───────────────────
        # Start with in-course results; overflow cross-course dishes that
        # beat the worst in-course score by the margin threshold
        results = list(in_course_results)
        in_course_names = {r["dish_name"] for r in results}

        if results:
            worst_in_course_score = min(r["match_score"] for r in results)
        else:
            worst_in_course_score = 0.0  # no in-course results → accept anything

        overflow_added = []
        for xr in cross_course_results:
            if xr["dish_name"] in in_course_names:
                continue  # already included
            if xr["match_score"] > worst_in_course_score + CROSS_COURSE_OVERFLOW_MARGIN or len(results) < RESULTS_COUNT:
                xr["cross_course"] = True  # tag for UI
                xr["match_reason"] = xr["match_reason"] + " · cross-course pick"
                overflow_added.append(xr)

        # Add overflows, then re-sort by score and trim to RESULTS_COUNT
        results.extend(overflow_added)
        results.sort(key=lambda r: r["match_score"], reverse=True)
        results = results[:RESULTS_COUNT]

        # Re-number ranks
        for i, r in enumerate(results):
            r["rank"] = i + 1

        # Merge stats
        stats = {
            "total_dishes": len(self.dishes),
            "in_course_eligible": len(in_course_indices) if len(in_course_indices) > 0 else 0,
            "cross_course_eligible": len(all_indices),
            "in_course_results": len(in_course_results),
            "overflow_added": len(overflow_added),
            "final_results": len(results),
        }
        stats.update({f"in_course_{k}": v for k, v in in_course_stats.items()})
        stats.update({f"cross_course_{k}": v for k, v in cross_course_stats.items()})

        return {
            "seed_dish": seed_dish,
            "seed_cuisine": seed_cuisine,
            "seed_category": seed_category,
            "filters_applied": {
                "dietary": dietary or "any",
                "category": category_filter or seed_category,
                "target_cuisine": target_cuisine or "any",
                "discovery_mode": discovery_mode,
            },
            "pipeline_stats": stats,
            "recommendations": results,
            "engine": "hybrid",
        }

    # ──────────────────────────────────────────────────────────────────────
    #  CORE PIPELINE (Steps 2-6)
    # ──────────────────────────────────────────────────────────────────────

    def _run_pipeline(
        self,
        seed_idx: int,
        eligible_indices: np.ndarray,
        discovery_mode: bool,
        count: int = RESULTS_COUNT,
    ) -> tuple[list[dict], dict]:
        """
        Run Steps 2-6 of the hybrid pipeline on a set of eligible dish indices.

        Returns (results_list, stats_dict).
        """
        seed_row = self.dishes.iloc[seed_idx]
        seed_cuisine = str(seed_row["cuisine"]).strip()
        seed_temp = str(seed_row["temp"]).strip().lower()
        seed_flavor = self.flavor_matrix[seed_idx]

        # ── Step 2: Semantic Recall (pgvector cosine top-K) ──────────────
        # Pre-filter via `dish_id = ANY(...)` and let Postgres rank.
        semantic_candidates = self._semantic_recall(
            seed_idx, eligible_indices, k=SEMANTIC_TOP_K,
        )

        if not semantic_candidates:
            return [], {"semantic_recall": 0, "mouthfeel_guard": 0}

        # ── Step 3: Threshold Intersection (Mouthfeel Guard + Bonuses) ────
        seed_context = str(seed_row["context_string"]).lower()
        seed_warm_spice = any(kw in seed_context for kw in WARM_SPICE_KEYWORDS)
        seed_integrated_carb = any(kw in seed_context for kw in INTEGRATED_CARB_KEYWORDS)

        guarded = []
        for idx, sem_score in semantic_candidates:
            cand_flavor = self.flavor_matrix[idx]
            cand_row = self.dishes.iloc[idx]
            cand_temp = str(cand_row["temp"]).strip().lower()

            # ── Check warm spice & integrated carb FIRST (needed for guard exemptions) ──
            cand_context = str(cand_row["context_string"]).lower()

            # Refinement 1: Warm Spice Bonus
            warm_spice_match = False
            if seed_warm_spice:
                if any(kw in cand_context for kw in WARM_SPICE_KEYWORDS):
                    warm_spice_match = True

            # Refinement 2: Integrated Carb Bonus
            integrated_carb_match = False
            if seed_integrated_carb:
                if any(kw in cand_context for kw in INTEGRATED_CARB_KEYWORDS):
                    integrated_carb_match = True

            # Crunch guard
            if seed_flavor[FLAVOR_DIMS.index("crunch")] > CRUNCH_THRESHOLD:
                if cand_flavor[FLAVOR_DIMS.index("crunch")] < MOUTHFEEL_MIN:
                    continue

            # Spicy guard — EXEMPT warm-spice matches (warm spice ≠ chili heat)
            if seed_flavor[FLAVOR_DIMS.index("spicy")] > SPICY_THRESHOLD:
                if cand_flavor[FLAVOR_DIMS.index("spicy")] < MOUTHFEEL_MIN:
                    if not warm_spice_match:
                        continue  # only gate non-warm-spice dishes

            # Umami anchor: if seed is umami-heavy, candidate must also be
            if seed_flavor[FLAVOR_DIMS.index("umami")] > ANCHOR_THRESHOLD:
                if cand_flavor[FLAVOR_DIMS.index("umami")] < ANCHOR_MIN:
                    continue

            # Aromatic anchor (tightened): if seed aromatic > 0.8,
            # hard-gate out candidates below threshold, penalize "low aroma"
            # Cross-region relaxation: lower gates when crossing Indian/Thai → Greek/Italian/Mexican
            aromatic_penalty = False
            if seed_flavor[FLAVOR_DIMS.index("aromatic")] > ANCHOR_THRESHOLD:
                cand_aroma = cand_flavor[FLAVOR_DIMS.index("aromatic")]
                cand_cuisine_str = str(cand_row["cuisine"]).strip().lower()
                aromatic_gate = 0.5
                aromatic_soft = 0.6
                if (seed_cuisine.lower(), cand_cuisine_str) in AROMATIC_RELAXED_CUISINES:
                    aromatic_gate -= AROMATIC_GATE_RELAXATION   # 0.3
                    aromatic_soft -= AROMATIC_GATE_RELAXATION   # 0.4
                if cand_aroma < aromatic_gate:
                    continue  # hard gate: too bland, excluded
                if cand_aroma < aromatic_soft:
                    aromatic_penalty = True  # soft penalty: penalized in Step 4

            # Temperature guard
            if seed_temp in ("cold", "hot"):
                if cand_temp != seed_temp:
                    continue

            guarded.append((idx, sem_score, warm_spice_match, integrated_carb_match, aromatic_penalty))

        if not guarded:
            # Fallback: relax guards, keep semantic candidates (no bonuses/penalties)
            guarded = [(idx, sem, False, False, False) for idx, sem in semantic_candidates]

        # ── Step 4: Blended Re-Ranking (Flavor 2x + Semantic) ───────────
        candidate_indices = np.array([g[0] for g in guarded])
        sem_scores = np.array([g[1] for g in guarded])
        warm_spice_flags = [g[2] for g in guarded]
        integrated_carb_flags = [g[3] for g in guarded]
        aromatic_penalty_flags = [g[4] for g in guarded]
        candidate_flavors = self.flavor_matrix[candidate_indices]

        # Euclidean flavor distance (weighted 2x)
        flavor_distances = np.linalg.norm(candidate_flavors - seed_flavor, axis=1)

        # ── Refinement 1: Warm Spice distance reduction ──
        for i, is_warm in enumerate(warm_spice_flags):
            if is_warm:
                flavor_distances[i] *= (1.0 - WARM_SPICE_DISTANCE_REDUCTION)

        # ── Refinement 2: Integrated Carb distance reduction ──
        for i, is_carb in enumerate(integrated_carb_flags):
            if is_carb:
                flavor_distances[i] *= (1.0 - INTEGRATED_CARB_BOOST)

        # ── Tightened Aromatic Anchor: penalize low-aroma candidates ──
        # Inflate distance by 20% for "boring" dishes (aromatic 0.5-0.6 when seed > 0.8)
        for i, has_penalty in enumerate(aromatic_penalty_flags):
            if has_penalty:
                flavor_distances[i] *= 1.20

        # ── Fix 1: Protein Match Boost ──
        # If candidate's primary_protein matches seed's, reduce flavor distance by 15%
        seed_protein = str(seed_row.get("primary_protein", "")).strip()
        if seed_protein:
            for i, idx in enumerate(candidate_indices):
                cand_protein = str(self.dishes.iloc[idx].get("primary_protein", "")).strip()
                if cand_protein and cand_protein == seed_protein:
                    flavor_distances[i] *= (1.0 - PROTEIN_MATCH_BOOST)

        # Convert semantic similarity (0-1, higher=better) to a distance (lower=better)
        # sem_scores are cosine similarity from FAISS, range ~[0, 1]
        semantic_distances = 1.0 - sem_scores

        # Blend: flavor gets 2x weight
        distances = (FLAVOR_WEIGHT * flavor_distances + semantic_distances) / (FLAVOR_WEIGHT + 1.0)

        # ── Step 5: Cuisine Bridge (Discovery Bonus) ─────────────────────
        # Only reward cross-cuisine if the flavor distance is already low
        if discovery_mode:
            for i, idx in enumerate(candidate_indices):
                cand_cuisine = str(self.dishes.iloc[idx]["cuisine"]).strip()
                if cand_cuisine.lower() != seed_cuisine.lower():
                    if flavor_distances[i] < DISCOVERY_MAX_DIST:
                        distances[i] *= (1.0 - DISCOVERY_BONUS)

        # ── Step 6: Tie-Breaking (Importance) ────────────────────────────
        # Add tiny importance-based nudge to break ties
        importances = self.dishes.iloc[candidate_indices]["importance"].values.astype(float)
        # Normalise importance to [0, 0.01] range so it only breaks ties
        imp_max = importances.max() if importances.max() > 0 else 1.0
        tie_breaker = (1.0 - importances / imp_max) * 0.01
        distances = distances + tie_breaker

        # ── Sort and build results ───────────────────────────────────────
        order = np.argsort(distances)
        top_n = order[:count]

        results = []
        for rank, pos in enumerate(top_n):
            idx = int(candidate_indices[pos])
            dist = float(distances[pos])
            row = self.dishes.iloc[idx]
            is_warm = warm_spice_flags[pos]
            is_carb = integrated_carb_flags[pos]

            # ── Refinement 3: Gaussian Kernel match score ──
            # e^(-(d²)/2) × 100  →  close matches score 80-90%+
            match_score = float(np.exp(-(dist ** 2) / 2.0) * 100.0)

            # Cuisine similarity
            c_sim = 0.0
            if self.sim_df is not None:
                try:
                    c_sim = float(self.sim_df.loc[seed_cuisine, str(row["cuisine"])])
                except (KeyError, ValueError):
                    c_sim = 0.0

            # Build rich match reason
            match_reason = self._build_match_reason(
                seed_flavor, self.flavor_matrix[idx],
                seed_row, row, is_warm, is_carb, c_sim,
            )

            results.append({
                "rank": rank + 1,
                "dish_name": str(row["dish_name"]),
                "cuisine": str(row["cuisine"]),
                "category": str(row["category"]),
                "dietary_type": str(row["dietary_type"]),
                "temp": str(row["temp"]),
                "primary_protein": str(row.get("primary_protein", "")),
                "importance": float(row["importance"]),
                "match_score": round(match_score, 1),
                "flavor_distance": round(dist, 4),
                "cuisine_similarity": round(c_sim, 2),
                "context_string": str(row["context_string"]),
                "match_reason": match_reason,
                "cross_course": False,
                "flavor": {
                    dim: round(float(row[dim]), 2) for dim in FLAVOR_DIMS
                },
                "seed_flavor": {
                    dim: round(float(seed_flavor[i]), 2)
                    for i, dim in enumerate(FLAVOR_DIMS)
                },
            })

        stats = {
            "semantic_recall": len(semantic_candidates),
            "mouthfeel_guard": len(guarded),
        }
        return results, stats

    # ──────────────────────────────────────────────────────────────────────
    #  HELPERS
    # ──────────────────────────────────────────────────────────────────────

    def _build_match_reason(
        self, seed_flavor, cand_flavor, seed_row, cand_row,
        is_warm_spice: bool, is_integrated_carb: bool, cuisine_sim: float,
    ) -> str:
        """Build a rich, human-readable explanation of why this dish matched."""
        parts = []

        # 1. Shared flavor traits (dimensions where both are strong)
        LABELS = {
            "sweet": "sweet", "salt": "savory", "sour": "tangy/citrus-forward",
            "bitter": "bitter", "umami": "umami-rich", "spicy": "spicy",
            "fat": "rich/creamy", "aromatic": "aromatic", "crunch": "crunchy",
            "chew": "chewy",
        }
        shared_strong = []
        for i, dim in enumerate(FLAVOR_DIMS):
            sv, cv = float(seed_flavor[i]), float(cand_flavor[i])
            if sv >= 0.6 and cv >= 0.6:
                shared_strong.append(LABELS.get(dim, dim))
        if shared_strong:
            parts.append("Both are " + ", ".join(shared_strong[:4]))

        # 2. Temperature match
        seed_temp = str(seed_row["temp"]).strip().lower()
        cand_temp = str(cand_row["temp"]).strip().lower()
        if seed_temp == cand_temp and seed_temp in ("hot", "cold"):
            parts.append(f"served {seed_temp}")

        # 3. Warm spice bonus
        if is_warm_spice:
            parts.append("share warm-spice DNA (cinnamon, clove, cardamom)")

        # 4. Integrated carb bonus
        if is_integrated_carb:
            parts.append("both cook protein with the grain/starch (not on the side)")

        # 5. Cuisine bridge
        if cuisine_sim > 0.4:
            parts.append(f"strong cuisine affinity ({cuisine_sim:.0%})")
        elif cuisine_sim > 0.2:
            parts.append(f"moderate cuisine affinity ({cuisine_sim:.0%})")

        if not parts:
            parts.append("similar overall flavor profile")

        return " · ".join(parts)

    def _dietary_mask(self, dietary: str) -> np.ndarray:
        """Return boolean mask for dietary compatibility."""
        col = self.dishes["dietary_type"].str.lower()
        if dietary == "vegan":
            return (col == "vegan").values
        elif dietary in ("veg", "vegetarian"):
            return col.isin(["veg", "vegan", "vegetarian"]).values
        elif dietary == "pescatarian":
            return col.isin(["veg", "vegan", "vegetarian", "pescatarian"]).values
        else:
            return np.ones(len(self.dishes), dtype=bool)

    def _protein_mask(self, allowed_proteins: list[str], dietary: str) -> np.ndarray:
        """Return boolean mask that excludes dishes with proteins the user doesn't eat.

        Vegetarian/vegan dishes always pass (they have no meat).
        For non-veg dishes, only allow those whose primary_protein is in the
        user's selected protein groups.
        """
        # Build set of allowed protein values from user selections
        allowed_values = set()
        for group_key in allowed_proteins:
            if group_key in PROTEIN_GROUPS:
                allowed_values |= PROTEIN_GROUPS[group_key]

        proteins = self.dishes["primary_protein"].fillna("")
        diet_col = self.dishes["dietary_type"].str.lower()

        # Veg/vegan dishes always allowed; non-veg must have allowed protein
        is_veg = diet_col.isin(["veg", "vegan", "vegetarian"])
        has_allowed_protein = proteins.isin(allowed_values)
        has_no_protein = (proteins == "") | proteins.isna()

        return (is_veg | has_allowed_protein | has_no_protein).values

    def list_cuisines(self) -> list[str]:
        """Return sorted unique cuisines in the dataset."""
        return sorted(self.dishes["cuisine"].dropna().unique().tolist())

    def list_dishes(self, cuisine: str = "", category: str = "") -> list[str]:
        """Return dish names, optionally filtered by cuisine/category."""
        df = self.dishes
        if cuisine:
            df = df[df["cuisine"].str.lower() == cuisine.lower()]
        if category:
            df = df[df["category"].str.lower() == category.lower()]
        return df["dish_name"].tolist()

    def get_dish_info(self, dish_name: str) -> dict | None:
        """Return full info for a single dish."""
        idx = self._name_to_idx.get(dish_name)
        if idx is None:
            return None
        row = self.dishes.iloc[idx]
        return {
            "dish_name": str(row["dish_name"]),
            "cuisine": str(row["cuisine"]),
            "category": str(row["category"]),
            "dietary_type": str(row["dietary_type"]),
            "temp": str(row["temp"]),
            "primary_protein": str(row.get("primary_protein", "")),
            "importance": float(row["importance"]),
            "context_string": str(row["context_string"]),
            "flavor": {dim: round(float(row[dim]), 2) for dim in FLAVOR_DIMS},
        }
