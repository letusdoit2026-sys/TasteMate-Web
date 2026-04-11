"""
Hybrid Intersection Recommendation Engine
==========================================
3-file, 6-step pipeline:
  1. Hard Filtering    (Metadata_Filters.csv)
  2. Semantic Recall   (vibe_category.csv → FAISS)
  3. Threshold Guard   (taste_chemistry.csv mouthfeel)
  4. Euclidean Rank    (taste_chemistry.csv flavor distance)
  5. Cuisine Bridge    (discovery bonus)
  6. Tie-Breaking      (importance)
"""

from __future__ import annotations

import os
import numpy as np
import pandas as pd
import faiss
from sentence_transformers import SentenceTransformer

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

# Refinement 1: Warm Spice Cluster — keywords that indicate warm aromatic DNA
WARM_SPICE_KEYWORDS = {"cinnamon", "clove", "allspice", "nutmeg", "cardamom", "star anise", "mace"}
WARM_SPICE_DISTANCE_REDUCTION = 0.15   # 15% euclidean distance reduction

# Refinement 2: Integrated Carbs — rice/pasta cooked INTO the dish
INTEGRATED_CARB_KEYWORDS = {
    "cooked with rice", "rice cooked", "baked with pasta", "pasta baked",
    "cooked in rice", "rice dish", "layered rice", "one-pot rice",
    "pilaf", "biryani", "paella", "risotto", "pulao", "fried rice",
    "youvetsi", "orzo baked", "rice casserole", "noodle soup",
    "khao", "arroz",
}
INTEGRATED_CARB_BOOST = 0.15           # distance reduction for matching integrated-carb dishes

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
    """Three-file hybrid recommendation engine."""

    def __init__(self, data_dir, similarity_csv=None):
        self.data_dir = data_dir

        # ── Load the three CSVs ──
        self.taste = pd.read_csv(os.path.join(data_dir, "taste_chemistry.csv"))
        self.vibe = pd.read_csv(os.path.join(data_dir, "vibe_category.csv"))
        self.meta = pd.read_csv(os.path.join(data_dir, "Metadata_Filters.csv"))

        # Clean: drop duplicate header rows, trailing empty columns
        for df in (self.taste, self.vibe, self.meta):
            df.drop(df[df["dish_name"] == "dish_name"].index, inplace=True)
            df.drop(columns=[c for c in df.columns if c.startswith("Unnamed")], errors="ignore", inplace=True)
            df.reset_index(drop=True, inplace=True)

        # Convert flavor columns to numeric
        for col in FLAVOR_DIMS:
            if col in self.taste.columns:
                self.taste[col] = pd.to_numeric(self.taste[col], errors="coerce").fillna(0.0)

        # Normalise dish names
        for df in (self.taste, self.vibe, self.meta):
            df["dish_name"] = df["dish_name"].str.strip()
            if "cuisine" in df.columns:
                df["cuisine"] = df["cuisine"].str.strip()

        # Use (dish_name, cuisine) as composite join key to handle
        # same dish names across different cuisines (e.g. Grilled Octopus)
        join_keys = ["dish_name", "cuisine"]

        # Merge into a single lookup
        self.dishes = (
            self.meta
            .merge(self.taste, on=join_keys, how="inner")
            .merge(self.vibe, on=join_keys, how="inner")
        )
        self.dishes.reset_index(drop=True, inplace=True)

        # ── Cuisine similarity matrix (optional) ──
        self.sim_df = None
        if similarity_csv and os.path.exists(similarity_csv):
            self.sim_df = pd.read_csv(similarity_csv, index_col=0)

        # ── Build flavour matrix (NumPy, vectorised) ──
        self.flavor_matrix = self.dishes[FLAVOR_DIMS].values.astype(np.float32)

        # ── Build FAISS index on context_string embeddings ──
        self.model = SentenceTransformer(EMBED_MODEL_NAME)
        # context_string is already in self.dishes after merge
        ordered_contexts = self.dishes["context_string"].fillna("").tolist()
        self.embeddings = self.model.encode(
            ordered_contexts, show_progress_bar=False, normalize_embeddings=True,
        ).astype(np.float32)

        dim = self.embeddings.shape[1]
        self.index = faiss.IndexFlatIP(dim)  # Inner-product on L2-normed = cosine
        self.index.add(self.embeddings)

        # Name → row mapping (dish names may not be unique, so first match wins)
        self._name_to_idx = {}
        for i, name in enumerate(self.dishes["dish_name"]):
            if name not in self._name_to_idx:
                self._name_to_idx[name] = i

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
        Run the 6-step hybrid pipeline.

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
        list[dict]  – Top-5 recommendations with scores and metadata.
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
        seed_temp = str(seed_row["temp"]).strip().lower()
        seed_flavor = self.flavor_matrix[seed_idx]

        # ── Step 1: Hard Filtering (Metadata) ───────────────────────────
        mask = np.ones(len(self.dishes), dtype=bool)

        # Exclude the seed itself
        mask[seed_idx] = False

        # Dietary constraint
        if dietary:
            mask = mask & self._dietary_mask(dietary)

        # Protein constraint
        if allowed_proteins != "any" and isinstance(allowed_proteins, list):
            mask = mask & self._protein_mask(allowed_proteins, dietary)

        # Category constraint
        if category_filter:
            mask = mask & (
                self.dishes["category"].str.lower() == category_filter.lower()
            )
        else:
            # Default: same category as seed (Appetizer→Appetizer, Main→Main)
            mask = mask & (
                self.dishes["category"].str.lower() == seed_category.lower()
            )

        # Target cuisine constraint
        if target_cuisine:
            mask = mask & (
                self.dishes["cuisine"].str.lower() == target_cuisine.lower()
            )

        eligible_indices = np.where(mask)[0]
        if len(eligible_indices) == 0:
            return {"error": "No dishes match the given filters."}

        # ── Step 2: Semantic Recall (FAISS top-30) ───────────────────────
        seed_embedding = self.embeddings[seed_idx].reshape(1, -1)
        # Search full index, then intersect with eligible
        k_search = min(len(self.dishes), SEMANTIC_TOP_K * 5)
        scores, idxs = self.index.search(seed_embedding, k_search)

        eligible_set = set(eligible_indices)
        semantic_candidates = []
        for score, idx in zip(scores[0], idxs[0]):
            if idx in eligible_set:
                semantic_candidates.append((idx, float(score)))
            if len(semantic_candidates) >= SEMANTIC_TOP_K:
                break

        if not semantic_candidates:
            return {"error": "No semantically similar dishes found after filtering."}

        # ── Step 3: Threshold Intersection (Mouthfeel Guard + Bonuses) ────
        seed_context = str(seed_row["context_string"]).lower()
        seed_warm_spice = bool(WARM_SPICE_KEYWORDS & set(seed_context.split()))
        seed_integrated_carb = any(kw in seed_context for kw in INTEGRATED_CARB_KEYWORDS)

        guarded = []
        for idx, sem_score in semantic_candidates:
            cand_flavor = self.flavor_matrix[idx]
            cand_row = self.dishes.iloc[idx]
            cand_temp = str(cand_row["temp"]).strip().lower()

            # Crunch guard
            if seed_flavor[FLAVOR_DIMS.index("crunch")] > CRUNCH_THRESHOLD:
                if cand_flavor[FLAVOR_DIMS.index("crunch")] < MOUTHFEEL_MIN:
                    continue

            # Spicy guard
            if seed_flavor[FLAVOR_DIMS.index("spicy")] > SPICY_THRESHOLD:
                if cand_flavor[FLAVOR_DIMS.index("spicy")] < MOUTHFEEL_MIN:
                    continue

            # Umami anchor: if seed is umami-heavy, candidate must also be
            if seed_flavor[FLAVOR_DIMS.index("umami")] > ANCHOR_THRESHOLD:
                if cand_flavor[FLAVOR_DIMS.index("umami")] < ANCHOR_MIN:
                    continue

            # Aromatic anchor: if seed is aromatic-heavy, candidate must also be
            if seed_flavor[FLAVOR_DIMS.index("aromatic")] > ANCHOR_THRESHOLD:
                if cand_flavor[FLAVOR_DIMS.index("aromatic")] < ANCHOR_MIN:
                    continue

            # Temperature guard
            if seed_temp in ("cold", "hot"):
                if cand_temp != seed_temp:
                    continue

            # ── Refinement 1: Warm Spice Bonus ──
            # If both seed and candidate share warm-spice DNA, flag for distance reduction
            warm_spice_match = False
            if seed_warm_spice:
                cand_context = str(cand_row["context_string"]).lower()
                if WARM_SPICE_KEYWORDS & set(cand_context.split()):
                    warm_spice_match = True

            # ── Refinement 2: Integrated Carb Bonus ──
            # If seed is a "meat+carb integrated" dish, prefer candidates with same trait
            integrated_carb_match = False
            if seed_integrated_carb:
                cand_context = str(cand_row["context_string"]).lower()
                if any(kw in cand_context for kw in INTEGRATED_CARB_KEYWORDS):
                    integrated_carb_match = True

            guarded.append((idx, sem_score, warm_spice_match, integrated_carb_match))

        if not guarded:
            # Fallback: relax guards, keep semantic candidates (no bonuses)
            guarded = [(idx, sem, False, False) for idx, sem in semantic_candidates]

        # ── Step 4: Blended Re-Ranking (Flavor 2x + Semantic) ───────────
        candidate_indices = np.array([g[0] for g in guarded])
        sem_scores = np.array([g[1] for g in guarded])
        warm_spice_flags = [g[2] for g in guarded]
        integrated_carb_flags = [g[3] for g in guarded]
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
        top_n = order[:RESULTS_COUNT]

        results = []
        for rank, pos in enumerate(top_n):
            idx = int(candidate_indices[pos])
            dist = float(distances[pos])
            row = self.dishes.iloc[idx]

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
                "flavor": {
                    dim: round(float(row[dim]), 2) for dim in FLAVOR_DIMS
                },
                "seed_flavor": {
                    dim: round(float(seed_flavor[i]), 2)
                    for i, dim in enumerate(FLAVOR_DIMS)
                },
            })

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
            "pipeline_stats": {
                "total_dishes": len(self.dishes),
                "after_hard_filter": len(eligible_indices),
                "after_semantic_recall": len(semantic_candidates),
                "after_mouthfeel_guard": len(guarded),
                "final_results": len(results),
            },
            "recommendations": results,
            "engine": "hybrid",
        }

    # ──────────────────────────────────────────────────────────────────────
    #  HELPERS
    # ──────────────────────────────────────────────────────────────────────

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
