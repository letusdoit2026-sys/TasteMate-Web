import os
from dotenv import load_dotenv
load_dotenv()  # Load .env file before any os.environ.get() calls

import json
import uuid
import datetime
import numpy as np
import pandas as pd
from functools import wraps
from flask import Flask, jsonify, request, render_template, redirect, url_for, g
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from flask_bcrypt import Bcrypt
import groq
from google import genai as google_genai
from openai import OpenAI as XAIClient
from hybrid_engine import HybridEngine
from db import get_db as _pg_get_db, close_db as _pg_close_db, init_db as _pg_init_db

# ── App setup ──
app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "")
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

bcrypt = Bcrypt(app)
login_manager = LoginManager(app)
login_manager.login_view = "login_page"

# ── Load food data at startup (from 3-file hybrid system) ──
# 10 flavor dimensions from taste_chemistry.csv
FLAVOR_COLS = [
    "sweet_score", "salt_score", "sour_score", "bitter_score", "umami_score",
    "spicy_score", "fat_score", "aromatic_score", "crunch_score", "chew_score",
]

SCORING_COLS = FLAVOR_COLS

# Scoring weights for the 10 dimensions
SCORING_WEIGHTS = {
    "umami_score": 1.5,
    "spicy_score": 1.4,
    "sweet_score": 1.5,
    "bitter_score": 1.3,
    "fat_score": 1.2,
    "crunch_score": 1.2,
    "aromatic_score": 1.3,
    "chew_score": 1.1,
    "sour_score": 1.1,
    "salt_score": 1.0,
}

# Deviation penalty for polarizing dimensions
DEVIATION_PENALTY_DIMS = {
    "sweet_score": 1.5,
    "bitter_score": 1.2,
    "spicy_score": 1.0,
}
DEVIATION_THRESHOLD = 0.3  # on 0-1 scale now

# Temperature groups for serving_temperature matching
TEMP_GROUPS = {"hot", "cold", "room_temp"}

# Main ingredient category groups for matching
INGREDIENT_CATEGORY_GROUPS = {
    # Proteins
    "chicken dish": "poultry", "duck dish": "poultry", "turkey dish": "poultry",
    "beef dish": "red_meat", "lamb dish": "red_meat", "goat dish": "red_meat",
    "meat dish": "red_meat", "mutton dish": "red_meat",
    "pork dish": "pork",
    "fish dish": "seafood", "shrimp dish": "seafood", "seafood dish": "seafood",
    "crab dish": "seafood", "squid dish": "seafood", "clam dish": "seafood",
    "shellfish dish": "seafood", "octopus dish": "seafood",
    # Plant-based
    "vegetable dish": "vegetable", "potato dish": "vegetable", "mushroom dish": "vegetable",
    "eggplant dish": "vegetable", "corn dish": "vegetable",
    "lentil dish": "legume", "chickpea dish": "legume", "bean dish": "legume",
    "tofu dish": "legume", "soybean dish": "legume",
    # Dairy
    "cheese dish": "dairy", "milk dish": "dairy", "yogurt dish": "dairy",
    "butter dish": "dairy", "paneer dish": "dairy",
    # Grains
    "rice dish": "grain", "wheat dish": "grain", "noodle dish": "grain",
    "bread dish": "grain", "oat dish": "grain", "semolina dish": "grain",
    # Other
    "coconut dish": "coconut", "nut dish": "nut",
    "egg dish": "egg", "fruit dish": "fruit",
}

# Cooking method groups for sub_category matching
COOKING_METHOD_GROUPS = {
    "curry": "braised_saucy", "stew": "braised_saucy", "bean stew": "braised_saucy",
    "fish stew": "braised_saucy", "seafood stew": "braised_saucy", "vegetable stew": "braised_saucy",
    "hot pot": "braised_saucy", "braised dish": "braised_saucy",
    "grilled dish": "grilled_roasted", "grill": "grilled_roasted", "roast": "grilled_roasted",
    "skewer": "grilled_roasted", "kebab": "grilled_roasted",
    "fried dish": "fried", "fried pastry": "fried", "fritter": "fried",
    "stir-fry": "fried", "fried": "fried",
    "soup": "soup", "noodle soup": "soup", "fish soup": "soup", "vegetable soup": "soup",
    "rice dish": "rice_noodle", "noodle dish": "rice_noodle", "pasta": "rice_noodle",
    "flatbread": "bread", "bread": "bread",
    "salad": "fresh_raw", "rice salad": "fresh_raw",
    "sweet": "dessert", "cake": "dessert", "cookie": "dessert", "pastry": "dessert",
    "candy": "dessert", "custard": "dessert", "ice cream": "dessert",
    "savory pie": "baked_savory", "savory pastry": "baked_savory",
    "sandwich": "bread", "porridge": "rice_noodle",
    "sausage": "grilled_roasted", "egg dish": "other",
    "snack": "snack", "chaat": "snack", "rice cake": "snack",
    "dumpling": "dumpling", "dim sum": "dumpling",
}

FLAVOR_LABELS = {
    "sweet_score": "Sweet", "salt_score": "Salty", "sour_score": "Sour",
    "bitter_score": "Bitter", "umami_score": "Umami", "spicy_score": "Spicy",
    "fat_score": "Rich/Fat", "aromatic_score": "Aromatic",
    "crunch_score": "Crunchy", "chew_score": "Chewy",
}

# Course ordering for display
COURSE_ORDER = ["Appetizer", "Soup", "Salad", "Main Course", "Dessert", "Drink"]
ITEMS_PER_COURSE = 3

# ── df will be built from hybrid engine data after it loads (see below) ──
df = None  # placeholder, set after hybrid engine init

sim_df = pd.read_csv(os.path.join(BASE_DIR, "data", "similarity.csv"), index_col=0)
_ALL_CUISINES = sorted(sim_df.columns.tolist())
# Limit to cuisines available in hybrid engine data
CUISINES = ["Greek", "Indian", "Italian", "Mexican", "Thai"]

# ── Hybrid engine (lazy init — only loads when CSV data files exist) ──
HYBRID_DATA_DIR = os.path.join(BASE_DIR, "data")
SIMILARITY_CSV = os.path.join(BASE_DIR, "data", "similarity.csv")
hybrid_engine = None
try:
    hybrid_engine = HybridEngine(HYBRID_DATA_DIR, similarity_csv=SIMILARITY_CSV)
    app.logger.info(f"Hybrid engine loaded: {len(hybrid_engine.dishes)} dishes")

    # Build unified df from hybrid engine data for algorithm/LLM/Gemini endpoints
    df = hybrid_engine.dishes.copy()
    # Map new column names → old names used by algorithm/LLM/Gemini code
    df = df.rename(columns={
        "cuisine": "cuisine_name",
        "importance": "dish_importance_score",
        "temp": "serving_temperature",
        "sweet": "sweet_score",
        "salt": "salt_score",
        "sour": "sour_score",
        "bitter": "bitter_score",
        "umami": "umami_score",
        "spicy": "spicy_score",
        "fat": "fat_score",
        "aromatic": "aromatic_score",
        "crunch": "crunch_score",
        "chew": "chew_score",
        "context_string": "description",
    })
    # Add columns expected by old code
    df["course_group"] = df["category"]  # category IS the course now
    df["course"] = df["category"]
    df["sub_category"] = df["category"]
    df["main_ingredient_category"] = df["primary_protein"].fillna("")
    df["ingredients"] = ""  # not available in 3-file data
    df["spice_level"] = df["spicy_score"].apply(
        lambda x: "Hot" if x > 0.7 else ("Medium" if x > 0.4 else "Mild")
    )
    for col in FLAVOR_COLS:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
    df["dish_importance_score"] = pd.to_numeric(df["dish_importance_score"], errors="coerce").fillna(5.0)
    app.logger.info(f"Unified df built: {len(df)} dishes, {sorted(df['cuisine_name'].unique())}")
except Exception as e:
    app.logger.warning(f"Hybrid engine not loaded (CSV data may be missing): {e}")
    df = pd.DataFrame()  # empty fallback


# ══════════════════════════════════════════════════════════════════════════════
#  DATABASE
# ══════════════════════════════════════════════════════��═══════════════════════

def get_db():
    return _pg_get_db()


@app.teardown_appcontext
def close_db(exception):
    _pg_close_db(exception)


def init_db():
    _pg_init_db()


init_db()


# ══════════════════════════════════════════════════════════════════════════════
#  USER MODEL
# ══════════════════════════════════════════════════════════════════════════════

class User(UserMixin):
    def __init__(self, id, username, email):
        self.id = id
        self.username = username
        self.email = email


@login_manager.user_loader
def load_user(user_id):
    db = get_db()
    row = db.execute("SELECT * FROM users WHERE id = %s", (user_id,)).fetchone()
    if row:
        return User(row["id"], row["username"], row["email"])
    return None


# ══════════════════════════════════════════════════════════════════════════════
#  AUDIT LOGGING
# ══════════════════════════════════════════════════════════════════════════════

def log_audit(user_id, username, action, **kwargs):
    from psycopg.types.json import Jsonb

    def _j(v):
        return Jsonb(v) if v else None

    db = get_db()
    db.execute(
        """INSERT INTO audit_logs
           (id, user_id, username, action, timestamp,
            source_cuisine, favorite_dishes, taste_preferences,
            target_cuisines, recommendations, scoring_details, user_profile_vector)
           VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
        (
            str(uuid.uuid4()),
            user_id,
            username,
            action,
            datetime.datetime.utcnow(),
            kwargs.get("source_cuisine"),
            _j(kwargs.get("favorite_dishes")),
            _j(kwargs.get("taste_preferences")),
            _j(kwargs.get("target_cuisines")),
            _j(kwargs.get("recommendations")),
            _j(kwargs.get("scoring_details")),
            _j(kwargs.get("user_profile_vector")),
        ),
    )
    db.commit()


# ══════════════════════════════════════════════════════════════════════════════
#  RECOMMENDATION ENGINE
# ══════════════════════════════════════════════════════════════════════════════

def cosine_sim(a, b):
    """Basic cosine similarity on full vectors (used for closest-favorite matching)."""
    na, nb = np.linalg.norm(a), np.linalg.norm(b)
    if na == 0 or nb == 0:
        return 0.0
    return float(np.dot(a, b) / (na * nb))


def weighted_cosine_sim(a_full, b_full):
    """Weighted cosine similarity using only active SCORING_COLS with dimension weights."""
    indices = [FLAVOR_COLS.index(c) for c in SCORING_COLS]
    weights = np.array([SCORING_WEIGHTS.get(c, 1.0) for c in SCORING_COLS])
    a = np.array([a_full[i] for i in indices]) * weights
    b = np.array([b_full[i] for i in indices]) * weights
    na, nb = np.linalg.norm(a), np.linalg.norm(b)
    if na == 0 or nb == 0:
        return 0.0
    return float(np.dot(a, b) / (na * nb))


def weighted_euclidean_score(a_full, b_full):
    """Weighted euclidean distance score using only active SCORING_COLS."""
    indices = [FLAVOR_COLS.index(c) for c in SCORING_COLS]
    weights = np.array([SCORING_WEIGHTS.get(c, 1.0) for c in SCORING_COLS])
    a = np.array([a_full[i] for i in indices]) * weights
    b = np.array([b_full[i] for i in indices]) * weights
    ed = np.linalg.norm(a - b)
    return 1.0 / (1.0 + ed)


def cooking_method_score(fav_data, dish_sub_category):
    """Score how well this dish's cooking method matches user favorites."""
    dish_subcat = str(dish_sub_category).strip().lower()
    dish_group = COOKING_METHOD_GROUPS.get(dish_subcat)
    if not dish_group:
        return 0.0
    # Count how many favorites share this cooking method group
    match_count = 0
    total = len(fav_data)
    for fav in fav_data:
        fav_subcat = fav.get("sub_category", "").strip().lower()
        fav_group = COOKING_METHOD_GROUPS.get(fav_subcat)
        if fav_group == dish_group:
            match_count += 1
    return match_count / max(total, 1)


def temperature_match_score(fav_data, dish_temp):
    """Score how well this dish's serving temperature matches user favorites."""
    dish_t = str(dish_temp).strip().lower()
    if dish_t not in TEMP_GROUPS:
        return 0.5  # unknown, neutral
    match_count = 0
    total = len(fav_data)
    for fav in fav_data:
        fav_t = fav.get("serving_temperature", "hot").strip().lower()
        if fav_t == dish_t:
            match_count += 1
        elif (fav_t == "hot" and dish_t == "room_temp") or (fav_t == "room_temp" and dish_t == "hot"):
            match_count += 0.5  # partial match: hot↔room_temp
    return match_count / max(total, 1)


def ingredient_category_score(fav_data, dish_main_ing_cat):
    """Score how well this dish's main ingredient category matches user favorites."""
    dish_cat = str(dish_main_ing_cat).strip().lower()
    dish_group = INGREDIENT_CATEGORY_GROUPS.get(dish_cat)
    if not dish_group:
        return 0.0
    match_count = 0
    total = len(fav_data)
    for fav in fav_data:
        fav_cat = fav.get("main_ingredient_category", "").strip().lower()
        fav_group = INGREDIENT_CATEGORY_GROUPS.get(fav_cat)
        if fav_group == dish_group:
            match_count += 1
        # Partial credit: vegetable↔legume, grain↔grain, etc.
        elif fav_group and dish_group:
            PARTIAL_MATCHES = {
                frozenset({"vegetable", "legume"}): 0.5,
                frozenset({"red_meat", "pork"}): 0.5,
                frozenset({"poultry", "red_meat"}): 0.3,
                frozenset({"dairy", "coconut"}): 0.3,
            }
            pair = frozenset({fav_group, dish_group})
            partial = PARTIAL_MATCHES.get(pair, 0.0)
            match_count += partial
    return match_count / max(total, 1)


def flavor_deviation_penalty(user_profile, dish_vec):
    """Penalize dishes that deviate sharply on polarizing dimensions from user profile.
    Returns a penalty value (0.0 = no penalty, up to ~0.15 for severe mismatches)."""
    total_penalty = 0.0
    for dim, weight in DEVIATION_PENALTY_DIMS.items():
        idx = FLAVOR_COLS.index(dim)
        user_val = user_profile[idx]
        dish_val = dish_vec[idx]
        diff = abs(user_val - dish_val)
        if diff > DEVIATION_THRESHOLD:
            # Scaled penalty on 0-1 scale: max diff after threshold is ~0.7
            norm_diff = (diff - DEVIATION_THRESHOLD) / 0.7
            total_penalty += norm_diff * weight * 0.03
    return min(total_penalty, 0.15)  # cap total penalty


def dietary_compatibility_score(fav_data, dish_dietary):
    """Score dietary compatibility between user favorites and this dish.
    Returns 1.0 for perfect match, 0.0 for incompatible."""
    dish_is_veg = _is_veg(dish_dietary)
    dish_is_nonveg = _is_nonveg(dish_dietary)
    dish_d = str(dish_dietary).lower()
    is_pescatarian = "pescatarian" in dish_d

    match_count = 0
    total = len(fav_data)
    for fav in fav_data:
        fav_d = fav.get("dietary_type", "").lower()
        fav_is_veg = _is_veg(fav_d)
        fav_is_nonveg = _is_nonveg(fav_d)

        if fav_is_veg and dish_is_veg:
            match_count += 1
        elif fav_is_nonveg and dish_is_nonveg:
            match_count += 1
        elif fav_is_veg and is_pescatarian:
            match_count += 0.3  # partial: veg user might tolerate pescatarian
        elif fav_is_nonveg and is_pescatarian:
            match_count += 0.7  # non-veg user likely OK with fish
        elif fav_is_veg and dish_is_nonveg:
            match_count += 0.0  # incompatible
        elif fav_is_nonveg and dish_is_veg:
            match_count += 0.6  # non-veg user can eat veg
        else:
            match_count += 0.5  # neutral
    return match_count / max(total, 1)


def ingredient_overlap(fav_ingredients_set, dish_ingredients_str):
    """Compute Jaccard-like overlap between user's favorite ingredients and this dish."""
    dish_ings = set(
        w.strip().lower()
        for item in str(dish_ingredients_str).split(",")
        for w in item.strip().split()
        if len(w.strip()) > 2
    )
    if not dish_ings or not fav_ingredients_set:
        return 0.0
    overlap = fav_ingredients_set & dish_ings
    # weighted: more shared words = higher score, normalize by dish size
    return min(len(overlap) / max(len(dish_ings), 1), 1.0)


def _is_veg(dietary_str):
    """Check if a dietary type string indicates vegetarian/vegan."""
    d = str(dietary_str).lower()
    return ("veg" in d or "vegan" in d) and "non" not in d


def _is_nonveg(dietary_str):
    """Check if a dietary type string indicates non-vegetarian."""
    d = str(dietary_str).lower()
    return "non" in d or ("veg" not in d and "vegan" not in d and d not in ("", "nan"))


def find_closest_favorite(dish_vec, dish_ingredients_str, fav_data, dish_course=None,
                          dish_category="", dish_sub_category="", dish_dietary=""):
    """Find which user favorite is most similar to this recommended dish.
    Matching tiers: 1) same course + same dietary, 2) same course, 3) same dietary, 4) compatible fallback.
    Never matches veg favorites to non-veg dishes or vice versa."""
    dish_ing_words = set(
        w.strip().lower()
        for item in str(dish_ingredients_str).split(",")
        for w in item.strip().split()
        if len(w.strip()) > 2
    )
    dish_cat = str(dish_category).lower()
    dish_is_veg = _is_veg(dish_dietary)
    dish_is_nonveg = _is_nonveg(dish_dietary)

    # Categories that are fundamentally incompatible
    INCOMPATIBLE_CAT = {
        "sauce/condiment": {"bread", "main dish", "dessert", "snack", "street food"},
        "sauce": {"bread", "main dish", "dessert", "snack", "street food"},
        "bread": {"sauce/condiment", "sauce", "salad", "drink"},
        "drink": {"bread", "main dish", "snack", "street food"},
    }

    def _score_fav(fav):
        cs = cosine_sim(dish_vec, fav["vector"])
        fav_ing_words = set(
            w.strip().lower()
            for item in str(fav["ingredients"]).split(",")
            for w in item.strip().split()
            if len(w.strip()) > 2
        )
        ing_overlap = len(dish_ing_words & fav_ing_words) / max(len(dish_ing_words | fav_ing_words), 1)
        score = 0.6 * cs + 0.4 * ing_overlap

        # Penalize incompatible category matches
        fav_cat = fav.get("category", "").lower()
        incompat_set = INCOMPATIBLE_CAT.get(dish_cat, set())
        if fav_cat in incompat_set:
            score *= 0.5

        return score

    def _best_from(candidates):
        best_name, best_score = None, -1
        for fav in candidates:
            s = _score_fav(fav)
            if s > best_score:
                best_score = s
                best_name = fav["name"]
        return best_name, best_score

    def _dietary_compatible(fav):
        """Check if favorite is dietary-compatible for matching display."""
        fav_is_veg = _is_veg(fav.get("dietary_type", ""))
        fav_is_nonveg = _is_nonveg(fav.get("dietary_type", ""))
        # Non-veg dish should not match to veg favorite
        if dish_is_nonveg and fav_is_veg:
            return False
        # Veg dish should not match to non-veg favorite
        if dish_is_veg and fav_is_nonveg:
            return False
        return True

    # Filter to dietary-compatible favorites first
    diet_compat = [f for f in fav_data if _dietary_compatible(f)]

    # Tier 1: Same course + dietary compatible
    if dish_course and diet_compat:
        same_course = [f for f in diet_compat if f.get("course") == dish_course]
        if same_course:
            name, score = _best_from(same_course)
            if score > 0.2:
                return name, round(score * 100, 1)

    # Tier 2: Same course (any dietary, if no dietary-compatible course match)
    if dish_course:
        same_course = [f for f in fav_data if f.get("course") == dish_course]
        if same_course:
            # Still prefer dietary compatible within same course
            diet_same = [f for f in same_course if _dietary_compatible(f)]
            pool = diet_same if diet_same else same_course
            name, score = _best_from(pool)
            if score > 0.2:
                return name, round(score * 100, 1)

    # Tier 3: Dietary compatible, any course (but exclude incompatible courses)
    COURSE_INCOMPATIBLE = {
        "Dessert": {"Main Course", "Appetizer", "Soup", "Salad"},
        "Drink": {"Main Course", "Appetizer", "Soup", "Salad", "Dessert"},
        "Main Course": {"Dessert", "Drink"},
        "Appetizer": {"Dessert", "Drink"},
        "Soup": {"Dessert", "Drink"},
        "Salad": {"Dessert", "Drink"},
    }
    incompat_courses = COURSE_INCOMPATIBLE.get(dish_course, set())

    if diet_compat:
        compatible_favs = [f for f in diet_compat if f.get("course", "") not in incompat_courses]
        if compatible_favs:
            name, score = _best_from(compatible_favs)
            if score > 0.2:
                return name, round(score * 100, 1)

    # Tier 4: Any remaining compatible favorites
    fav_courses = set(f.get("course", "") for f in fav_data)
    if incompat_courses and fav_courses and fav_courses.issubset(incompat_courses):
        return None, 0.0

    remaining = [f for f in fav_data if f.get("course", "") not in incompat_courses]
    if remaining:
        name, score = _best_from(remaining)
        return name, round(score * 100, 1)

    return None, 0.0


def build_detailed_explanation(user_vec, dish_vec, dish_row, user_prefs, c_sim,
                                scores_breakdown, matched_fav_name, ingredient_score):
    """Build a rich explanation of why this dish was recommended."""
    close_dims = []
    diff_dims = []
    for i, col in enumerate(FLAVOR_COLS):
        label = FLAVOR_LABELS.get(col, col)
        uv, dv = user_vec[i], dish_vec[i]
        diff = abs(uv - dv)
        if uv > 0.2 or dv > 0.2:  # 0-1 scale: threshold at 0.2
            close_dims.append((diff, label, uv, dv))
            diff_dims.append((diff, label, uv, dv))

    close_dims.sort(key=lambda x: x[0])
    diff_dims.sort(key=lambda x: x[0], reverse=True)

    parts = []

    # 0. Matched favorite
    if matched_fav_name:
        parts.append(f"Because you liked <strong>{matched_fav_name}</strong>")

    # 1. Ingredient match
    if ingredient_score > 0.3:
        parts.append(f"Strong ingredient overlap ({ingredient_score:.0%}) with your favorites")
    elif ingredient_score > 0.1:
        parts.append(f"Some shared ingredients ({ingredient_score:.0%}) with your favorites")

    # 2. Flavor match (0-1 scale, show as percentage)
    top_matches = close_dims[:3]
    match_str = ", ".join([f"{label} (you: {uv:.0%}, dish: {dv:.0%})" for _, label, uv, dv in top_matches])
    parts.append(f"Flavor match: {match_str}")

    # 3. Cuisine affinity
    if c_sim > 0.3:
        parts.append(f"Strong cuisine affinity ({c_sim:+.0%})")
    elif c_sim > 0:
        parts.append(f"Moderate cuisine affinity ({c_sim:+.0%})")
    else:
        parts.append(f"Low cuisine affinity ({c_sim:+.0%}) — but this dish bridges the gap")

    # 4. Taste preferences
    if user_prefs:
        dietary = user_prefs.get("dietary", "any")
        dish_dietary = str(dish_row.get("dietary_type", "")).lower()
        if dietary == "veg" and "veg" in dish_dietary and "non" not in dish_dietary:
            parts.append("Matches your vegetarian preference")
        elif dietary == "non-veg" and "non-veg" in dish_dietary:
            parts.append("Matches your non-veg preference")

        spice_pref = user_prefs.get("spice_level", "medium")
        dish_spice = float(dish_row.get("spicy_score", 0))
        if spice_pref == "mild" and dish_spice <= 0.3:
            parts.append("Mild spice — matches your preference")
        elif spice_pref == "hot" and dish_spice >= 0.6:
            parts.append(f"Spicy ({dish_spice:.0%}) — matches your love for heat!")
        elif spice_pref == "medium" and 0.3 <= dish_spice <= 0.6:
            parts.append(f"Medium spice ({dish_spice:.0%}) — your sweet spot")

        if user_prefs.get("likes_creamy") and float(dish_row.get("fat_score", 0)) >= 0.5:
            parts.append(f"Rich & creamy ({float(dish_row.get('fat_score', 0)):.0%})")
        if user_prefs.get("likes_aromatic") and float(dish_row.get("aromatic_score", 0)) >= 0.5:
            parts.append(f"Highly aromatic ({float(dish_row.get('aromatic_score', 0)):.0%})")

    # 5. Key differences (0-1 scale)
    if diff_dims:
        top_diff = diff_dims[0]
        if top_diff[0] > 0.3:
            direction = "higher" if top_diff[3] > top_diff[2] else "lower"
            parts.append(f"Note: {top_diff[1]} is {direction} than usual (dish={top_diff[3]:.0%} vs you={top_diff[2]:.0%})")

    return " | ".join(parts)


def find_similar_alternatives(dish_name, dish_vec, all_scored, top_n=2):
    alternatives = []
    for other in all_scored:
        if other["dish_name"] == dish_name:
            continue
        other_vec = np.array([other["flavor"].get(FLAVOR_LABELS.get(c, c), 0) for c in FLAVOR_COLS])
        sim = cosine_sim(dish_vec, other_vec)
        if sim > 0.85:
            alternatives.append({
                "name": other["dish_name"],
                "similarity_to_this": round(sim * 100, 1),
                "score": other["score"],
                "course": other.get("course", ""),
                "score_diff_reason": (
                    f"Scored {'higher' if other['score'] > 0 else 'lower'} — "
                    f"differs in: " + ", ".join(
                        f"{FLAVOR_LABELS.get(c, c)}" for i, c in enumerate(FLAVOR_COLS)
                        if abs(dish_vec[i] - other_vec[i]) > 0.2
                    )[:80]
                ),
            })
    alternatives.sort(key=lambda x: x["similarity_to_this"], reverse=True)
    return alternatives[:top_n]


# ══════════════════════════════════════════════════════════════════════════════
#  ROUTES — Auth
# ══════════════════════════════════════════════════════════════════════════════

@app.route("/")
def index():
    if current_user.is_authenticated:
        return render_template("index.html", user=current_user)
    return redirect(url_for("login_page"))


@app.route("/login")
def login_page():
    if current_user.is_authenticated:
        return redirect(url_for("index"))
    return render_template("auth.html", mode="login")


@app.route("/register")
def register_page():
    return render_template("auth.html", mode="register")


@app.route("/forgot-password")
def forgot_password_page():
    return render_template("auth.html", mode="forgot")


@app.route("/api/auth/forgot-get-question", methods=["POST"])
def api_forgot_get_question():
    """Step 1: User provides email, we return their security question."""
    data = request.json
    email = data.get("email", "").strip().lower()
    if not email:
        return jsonify({"error": "Please enter your email"}), 400

    db = get_db()
    row = db.execute("SELECT security_question FROM users WHERE email = %s", (email,)).fetchone()
    if not row:
        return jsonify({"error": "No account found with that email"}), 404
    if not row["security_question"]:
        return jsonify({"error": "This account has no security question set. Please contact support."}), 400

    return jsonify({"security_question": row["security_question"]})


@app.route("/api/auth/forgot-reset", methods=["POST"])
def api_forgot_reset():
    """Step 2: User answers security question + sets new password."""
    data = request.json
    email = data.get("email", "").strip().lower()
    answer = data.get("security_answer", "").strip().lower()
    new_password = data.get("new_password", "")

    if not email or not answer:
        return jsonify({"error": "Email and security answer are required"}), 400

    db = get_db()
    row = db.execute("SELECT * FROM users WHERE email = %s", (email,)).fetchone()
    if not row:
        return jsonify({"error": "No account found with that email"}), 404

    # Verify security answer
    if not row["security_answer_hash"] or not bcrypt.check_password_hash(row["security_answer_hash"], answer):
        return jsonify({"error": "Incorrect security answer"}), 401

    # Reset password to "tastemate"
    new_hash = bcrypt.generate_password_hash("tastemate").decode("utf-8")
    db.execute("UPDATE users SET password_hash = %s WHERE email = %s", (new_hash, email))
    db.commit()

    log_audit(row["id"], row["username"], "PASSWORD_RESET_VIA_SECURITY_QUESTION")
    return jsonify({"success": True})


@app.route("/api/auth/register", methods=["POST"])
def api_register():
    data = request.json
    username = data.get("username", "").strip()
    email = data.get("email", "").strip().lower()
    password = data.get("password", "")
    security_question = data.get("security_question", "").strip()
    security_answer = data.get("security_answer", "").strip().lower()

    if not username or not email:
        return jsonify({"error": "Username and email are required"}), 400
    if not security_question or not security_answer:
        return jsonify({"error": "Security question and answer are required for password recovery"}), 400

    db = get_db()
    existing = db.execute("SELECT id FROM users WHERE username = %s OR email = %s", (username, email)).fetchone()
    if existing:
        return jsonify({"error": "Username or email already exists"}), 400

    user_id = str(uuid.uuid4())
    pw_hash = bcrypt.generate_password_hash("tastemate").decode("utf-8")
    answer_hash = bcrypt.generate_password_hash(security_answer).decode("utf-8")
    db.execute(
        """INSERT INTO users (id, username, email, password_hash, security_question, security_answer_hash, created_at)
           VALUES (%s, %s, %s, %s, %s, %s, %s)""",
        (user_id, username, email, pw_hash, security_question, answer_hash, datetime.datetime.utcnow()),
    )
    db.commit()

    user = User(user_id, username, email)
    login_user(user)
    log_audit(user_id, username, "REGISTER")
    return jsonify({"success": True, "username": username})


@app.route("/api/auth/login", methods=["POST"])
def api_login():
    data = request.json
    email = data.get("email", "").strip().lower()
    password = data.get("password", "")

    db = get_db()
    row = db.execute("SELECT * FROM users WHERE email = %s", (email,)).fetchone()
    if not row or not bcrypt.check_password_hash(row["password_hash"], password):
        return jsonify({"error": "Invalid email or password"}), 401

    user = User(row["id"], row["username"], row["email"])
    login_user(user)
    log_audit(row["id"], row["username"], "LOGIN")
    return jsonify({"success": True, "username": row["username"]})


@app.route("/api/auth/logout", methods=["POST"])
@login_required
def api_logout():
    log_audit(current_user.id, current_user.username, "LOGOUT")
    logout_user()
    return jsonify({"success": True})


@app.route("/api/auth/me")
def api_me():
    if current_user.is_authenticated:
        return jsonify({"authenticated": True, "username": current_user.username})
    return jsonify({"authenticated": False})




# ══════════════════════════════════════════════════════════════════════════════
#  ROUTES — Data & Recommendations
# ══════════════════════════════════════════════════════════════════════════════

@app.route("/api/cuisines")
@login_required
def get_cuisines():
    return jsonify(CUISINES)


HYBRID_COURSE_ORDER = ["Appetizer", "Soup", "Salad", "Main Course", "Dessert", "Drink"]

# ── Canonical course-label mapping ─────────────────────────────────────────────
# The source data has inconsistent casing/aliases ("Main", "Mains", "Main Course";
# "Appetizer" vs "Appetizers"). Every endpoint that surfaces a course name to the
# UI must run it through canonical_category() so the same course never splits
# into multiple buckets downstream.
_COURSE_CANONICAL = {
    "main":         "Main Course",
    "main course":  "Main Course",
    "mains":        "Main Course",
    "appetizer":    "Appetizer",
    "appetizers":   "Appetizer",
    "soup":         "Soup",
    "soups":        "Soup",
    "salad":        "Salad",
    "salads":       "Salad",
    "dessert":      "Dessert",
    "desserts":     "Dessert",
    "drink":        "Drink",
    "drinks":       "Drink",
}

def canonical_category(c):
    """Map raw category string to the canonical display label."""
    raw = str(c or "").strip()
    if not raw:
        return "Main Course"
    return _COURSE_CANONICAL.get(raw.lower(), raw)


def humanize_facet_reasons(matched, max_values=6):
    """Turn raw facet tokens like 'flavor:smoky,umami-rich' into a human-
    readable phrase. Layer-1 formatting: strip the `category:` prefix, split
    comma-packed values, dedupe while preserving order, and join with ", ".

    Example input (list of tokens the facet engine returned):
      ['flavor:smoky,umami-rich', 'texture:charred-crust,juicy-interior',
       'heat_intensity:high-dry-heat', 'fat_character:rendered-meat',
       'richness:rich']
    Output: 'smoky, umami-rich, charred-crust, juicy-interior,
             high-dry-heat, rendered-meat'
    """
    if not matched:
        return ""
    seen = []
    for tok in matched:
        if not tok:
            continue
        # Split "category:value1,value2" → just the value side
        raw = str(tok)
        body = raw.split(":", 1)[1] if ":" in raw else raw
        for v in body.split(","):
            v = v.strip().replace("_", " ")
            if v and v not in seen:
                seen.append(v)
    return ", ".join(seen[:max_values])


# ── Layer 2: natural-language facet phrasing ──
# Maps facet category → (priority, phrase builder). Builder takes the list of
# human-readable values for that category and returns a fragment like
# "smoky, umami-rich flavors". Fragments are joined in priority order into a
# single sentence. Unknown categories fall through to a generic "with X" tail,
# so we degrade gracefully rather than silently dropping signal.
def _fmt_list(vals, max_n=3):
    vals = vals[:max_n]
    if not vals:
        return ""
    if len(vals) == 1:
        return vals[0]
    if len(vals) == 2:
        return f"{vals[0]} and {vals[1]}"
    return ", ".join(vals[:-1]) + f", and {vals[-1]}"


_FACET_PHRASERS = {
    # Flavor anchors — the headline. "smoky, umami-rich flavors"
    "flavor_anchors":   (10, lambda vs: f"{_fmt_list(vs)} flavors"),
    "flavor":           (10, lambda vs: f"{_fmt_list(vs)} flavors"),
    # Texture — very tangible, second-most salient
    "texture_profile":  (20, lambda vs: f"a {_fmt_list(vs)} texture"),
    "texture":          (20, lambda vs: f"a {_fmt_list(vs)} texture"),
    # Aromatics — perfume of the dish
    "aromatic_signature": (30, lambda vs: f"{_fmt_list(vs)} aromatics"),
    "aromatic":           (30, lambda vs: f"{_fmt_list(vs)} aromatics"),
    # Cooking & heat — strip trailing "-heat"/"heat" from values so we don't
    # get tautologies like "high-dry-heat heat"
    "cooking_methods":  (40, lambda vs: f"{_fmt_list(vs)} cooking"),
    "heat_intensity":   (50, lambda vs: f"{_fmt_list([v.replace(' heat','').replace('-heat','').strip() or v for v in vs])} heat"),
    # Richness / fat — mouthfeel
    "richness":         (60, lambda vs: f"a {_fmt_list(vs)} mouthfeel"),
    "fat_character":    (65, lambda vs: f"{_fmt_list(vs)} fat character"),
    # Spice lineage / marinade — provenance of the seasoning
    "spice_lineage":    (70, lambda vs: f"{_fmt_list(vs)} spice lineage"),
    "marinade_family":  (75, lambda vs: f"a {_fmt_list(vs)} marinade"),
    # Role / format — lowest priority; often redundant with course
    "sauce_role":       (80, lambda vs: f"{_fmt_list(vs)} sauce role"),
    "course_role":      (85, lambda vs: f"{_fmt_list(vs)} course role"),
    "regional_origin":  (90, lambda vs: f"roots in {_fmt_list(vs)}"),
    "cultural_kin":     (92, lambda vs: f"kin with {_fmt_list(vs)}"),
}


def humanize_facet_reasons_v2(matched, max_fragments=4):
    """Layer-2 formatting: group facet tokens by category and emit a natural-
    language sentence. Falls back to Layer-1 comma list if nothing parses.

    Example input:
      ['flavor:smoky,umami-rich', 'texture:charred-crust,juicy-interior',
       'richness:rich']
    Output: 'Shares smoky and umami-rich flavors, a charred-crust, juicy-interior
             texture, and a rich mouthfeel.'
    """
    if not matched:
        return ""
    # Group values by category, dedupe within each, preserving first-seen order
    by_cat = {}
    for tok in matched:
        if not tok:
            continue
        raw = str(tok)
        if ":" in raw:
            cat, body = raw.split(":", 1)
        else:
            cat, body = "_other", raw
        cat = cat.strip().lower()
        vals = by_cat.setdefault(cat, [])
        for v in body.split(","):
            v = v.strip().replace("_", " ")
            if v and v not in vals:
                vals.append(v)

    # Build fragments from known categories, ordered by priority
    fragments = []
    leftover = []
    for cat, vals in by_cat.items():
        if not vals:
            continue
        phraser = _FACET_PHRASERS.get(cat)
        if phraser:
            prio, fn = phraser
            fragments.append((prio, fn(vals)))
        else:
            leftover.extend(vals)

    fragments.sort(key=lambda x: x[0])
    frags = [f for _, f in fragments[:max_fragments] if f]

    if not frags:
        # Pure Layer-1 fallback
        return humanize_facet_reasons(matched)

    sentence = "Shares " + _fmt_list(frags, max_n=max_fragments) + "."
    # Capitalize only the leading "Shares"; rest stays lowercase (values are
    # lowercase tokens like "smoky", "umami-rich").
    return sentence


def infer_effective_dietary(user_dietary, fav_dish_names):
    """Auto-upgrade dietary preference from 'any' (or unset) to 'veg'/'vegan'
    when ALL of the user's favorites are vegetarian. Protects users who
    forget to set the dietary toggle on step 2 from silently getting
    non-veg recommendations attributed to veg seeds.

    Returns: (effective_dietary, was_auto_inferred)
      - If user already set a non-'any' preference, returns it unchanged.
      - If all favorites are strictly vegan → 'vegan'.
      - Else if all favorites are veg/vegan → 'veg'.
      - Otherwise returns the original preference unchanged.
    """
    raw = str(user_dietary or "").strip().lower()
    if raw and raw != "any":
        return raw, False
    if hybrid_engine is None or not fav_dish_names:
        return (raw or "any"), False
    dietaries = []
    for name in fav_dish_names:
        info = hybrid_engine.get_dish_info(name)
        if info and info.get("dietary_type"):
            dietaries.append(str(info["dietary_type"]).strip().lower())
    if not dietaries:
        return (raw or "any"), False
    all_vegan = all("vegan" in d for d in dietaries)
    all_veg   = all(d in ("veg", "vegan", "vegetarian") for d in dietaries)
    if all_vegan:
        return "vegan", True
    if all_veg:
        return "veg", True
    return (raw or "any"), False


def infer_effective_proteins(user_allowed, user_dietary, fav_dish_names):
    """Auto-narrow allowed proteins from 'any' to the subset actually represented
    in the user's favorites. Cuisine-agnostic — the signal is the user's own picks.

    Only fires when:
      - User left allowed_proteins as "any" (didn't uncheck anything on step 2)
      - User's dietary is non-veg or unset (veg/vegan/pescatarian already filter meat)

    Returns: (effective_allowed, was_auto_inferred)
      - effective_allowed: either "any" (unchanged) or a list of PROTEIN_GROUPS keys
      - was_auto_inferred: True only when a strict subset was inferred
    """
    # Respect explicit user choice
    if isinstance(user_allowed, list):
        return user_allowed, False
    if user_allowed != "any":
        return user_allowed, False

    # Veg-family dietary preferences already handle protein filtering upstream
    d = str(user_dietary or "").strip().lower()
    if d in ("veg", "vegan", "vegetarian", "pescatarian"):
        return "any", False

    if hybrid_engine is None or not fav_dish_names:
        return "any", False

    try:
        from hybrid_engine import PROTEIN_GROUPS
    except Exception:
        return "any", False

    # Build reverse lookup: raw protein name → group key
    raw_to_group = {}
    for gk, vals in PROTEIN_GROUPS.items():
        for v in vals:
            raw_to_group[str(v).strip().lower()] = gk

    observed = []
    saw_any_meat = False
    for name in fav_dish_names:
        info = hybrid_engine.get_dish_info(name)
        if not info:
            continue
        # Skip veg/vegan favorites — they carry no meat signal
        diet = str(info.get("dietary_type", "")).strip().lower()
        if diet in ("veg", "vegan", "vegetarian"):
            continue
        proto = str(info.get("primary_protein", "")).strip().lower()
        if not proto:
            continue
        saw_any_meat = True
        gk = raw_to_group.get(proto)
        if gk and gk not in observed:
            observed.append(gk)

    # No meat favorites at all → don't infer (dietary inference will catch all-veg)
    if not saw_any_meat or not observed:
        return "any", False

    # Only infer if observed set is a strict subset of all groups
    all_groups = set(PROTEIN_GROUPS.keys())
    if set(observed) >= all_groups:
        return "any", False

    return observed, True


# ── Visible / hidden selection with Option-C allocation + multi-fav attribution ──
# Each engine collects up to `cap_per_seed` candidates per seed dish. This helper
# then deduplicates across seeds, attaches the full list of seeds that ranked each
# candidate (so UI can say "Because you liked X and Y"), and partitions the pool
# into a "visible" slice (shown by default) and a "hidden" slice (revealed via
# "Show more"). Visible selection uses Option C:
#   - If #seeds-in-course ≤ max_visible: guarantee ≥1 slot per seed, fill rest
#     by top score.
#   - Otherwise: just take global top-`max_visible` by score.
# Hidden pool is score-descending, capped at `max_hidden`.
def select_with_show_more(per_seed_picks, max_visible=3, max_hidden=6, score_floor=0.0):
    """
    per_seed_picks: dict[seed_name] -> list of (score, matched_list, cand) tuples.
                    Each seed's list should already be sorted desc and capped at 3.
    Returns: (visible_entries, hidden_entries)
    Each entry is:
        {
          "cand": <original candidate row/dict>,
          "top_score": float,
          "matched_favorites": [{"name": seed, "score": float, "matched": [facet,...]}, ...]
                               (sorted by score desc)
        }
    """
    # Dedup by dish_name; collect every seed that ranked this candidate.
    # We keep the first `cand` we see (they're equivalent rows across seeds).
    by_dish = {}
    for seed, picks in per_seed_picks.items():
        for s, matched, cand in picks:
            if s < score_floor:
                continue
            # Support both pandas Series and plain dicts for `cand`.
            try:
                name = cand["dish_name"]
            except Exception:
                name = cand.get("dish_name") if isinstance(cand, dict) else None
            if not name:
                continue
            entry = by_dish.get(name)
            if entry is None:
                entry = {"cand": cand, "matched_favorites": []}
                by_dish[name] = entry
            entry["matched_favorites"].append({
                "name": seed, "score": float(s), "matched": list(matched or []),
            })

    # Sort each entry's seed list by score desc; stamp top_score.
    for entry in by_dish.values():
        entry["matched_favorites"].sort(key=lambda x: -x["score"])
        entry["top_score"] = entry["matched_favorites"][0]["score"]

    # Global score-descending order (used both as a tiebreaker and as hidden order).
    all_sorted = sorted(by_dish.values(), key=lambda e: -e["top_score"])

    # Seeds that actually contributed at least one candidate in this course.
    seeds_in_course = [s for s, picks in per_seed_picks.items() if picks]
    n_seeds = len(seeds_in_course)

    visible = []
    used = set()  # identity-keyed (id(entry))

    if 0 < n_seeds <= max_visible:
        # Option C: reserve one slot per contributing seed by taking that seed's
        # top non-used candidate. Iterate seeds in their favourites-order so the
        # reservation is deterministic and matches the order the user picked them.
        for seed in seeds_in_course:
            for entry in all_sorted:
                if id(entry) in used:
                    continue
                if any(mf["name"] == seed for mf in entry["matched_favorites"]):
                    visible.append(entry)
                    used.add(id(entry))
                    break
            if len(visible) >= max_visible:
                break

    # Fill any remaining visible slots with the next-highest scoring entries.
    for entry in all_sorted:
        if len(visible) >= max_visible:
            break
        if id(entry) in used:
            continue
        visible.append(entry)
        used.add(id(entry))

    # Hidden pool: everything else, ordered by score, capped.
    hidden = [e for e in all_sorted if id(e) not in used][:max_hidden]

    return visible, hidden

@app.route("/api/dishes")
@login_required
def get_dishes():
    """Return dishes grouped by category for the favorites selection screen."""
    cuisine = request.args.get("cuisine", "")

    if hybrid_engine is not None:
        # Serve from hybrid engine data (3-file system)
        hdf = hybrid_engine.dishes
        cdf = hdf[hdf["cuisine"].str.lower() == cuisine.lower()]
        cdf = cdf.sort_values("importance", ascending=False)

        grouped = {}
        for _, row in cdf.iterrows():
            cat = canonical_category(row["category"])
            if cat not in grouped:
                grouped[cat] = []
            grouped[cat].append({
                "name": str(row["dish_name"]),
                "category": cat,
                "dietary": str(row.get("dietary_type", "")),
                "protein": str(row.get("primary_protein", "")),
                "importance": float(row["importance"]),
                "course": cat,
            })

        result = []
        for cat_name in HYBRID_COURSE_ORDER:
            if cat_name in grouped:
                result.append({"course": cat_name, "dishes": grouped[cat_name]})
        for cat_name, dishes in grouped.items():
            if cat_name not in HYBRID_COURSE_ORDER:
                result.append({"course": cat_name, "dishes": dishes})

        return jsonify(result)

    # No hybrid engine available — return empty
    return jsonify([])


@app.route("/api/recommend", methods=["POST"])
@login_required
def recommend():
    data = request.json
    source_cuisine = data.get("source_cuisine", "")
    favorite_names = data.get("favorite_dishes", [])
    target_cuisines = data.get("target_cuisines", [])
    taste_prefs = data.get("taste_preferences", {})

    if not favorite_names or not target_cuisines:
        return jsonify({"error": "Please select favorites and target cuisines"}), 400

    # ── 1. Build user taste profile ──
    src_df = df[df["cuisine_name"].str.lower() == source_cuisine.lower()]
    fav_df = src_df[src_df["dish_name"].isin(favorite_names)]

    if fav_df.empty:
        return jsonify({"error": "No matching dishes found"}), 400

    weights = fav_df["dish_importance_score"].values
    fav_vectors = fav_df[FLAVOR_COLS].values
    user_profile = np.average(fav_vectors, axis=0, weights=weights)

    # Build favorites data for ingredient matching & closest-favorite lookup
    fav_data = []
    all_fav_ingredient_words = set()
    for _, frow in fav_df.iterrows():
        ing_str = str(frow.get("ingredients", ""))
        words = set(
            w.strip().lower()
            for item in ing_str.split(",")
            for w in item.strip().split()
            if len(w.strip()) > 2
        )
        all_fav_ingredient_words |= words
        fav_data.append({
            "name": frow["dish_name"],
            "vector": frow[FLAVOR_COLS].values.astype(float),
            "ingredients": ing_str,
            "course": frow["course_group"],
            "category": str(frow.get("category", "")),
            "sub_category": str(frow.get("sub_category", "")),
            "dietary_type": str(frow.get("dietary_type", "")).lower(),
            "main_ingredient_category": str(frow.get("main_ingredient_category", "")),
            "serving_temperature": str(frow.get("serving_temperature", "hot")),
        })

    # Apply taste preference adjustments (0-1 scale)
    if taste_prefs.get("spice_level") == "mild":
        user_profile[FLAVOR_COLS.index("spicy_score")] *= 0.5
    elif taste_prefs.get("spice_level") == "hot":
        user_profile[FLAVOR_COLS.index("spicy_score")] = max(user_profile[FLAVOR_COLS.index("spicy_score")], 0.7)
    if taste_prefs.get("likes_creamy"):
        user_profile[FLAVOR_COLS.index("fat_score")] = max(user_profile[FLAVOR_COLS.index("fat_score")], 0.6)
    if taste_prefs.get("likes_aromatic"):
        user_profile[FLAVOR_COLS.index("aromatic_score")] = max(user_profile[FLAVOR_COLS.index("aromatic_score")], 0.7)
    if taste_prefs.get("likes_sweet"):
        user_profile[FLAVOR_COLS.index("sweet_score")] = max(user_profile[FLAVOR_COLS.index("sweet_score")], 0.5)
    if taste_prefs.get("likes_sour"):
        user_profile[FLAVOR_COLS.index("sour_score")] = max(user_profile[FLAVOR_COLS.index("sour_score")], 0.5)

    profile_dict = {FLAVOR_LABELS.get(col, col): round(float(user_profile[i]), 1) for i, col in enumerate(FLAVOR_COLS)}

    # Build favorites summary with courses for response
    favorites_with_courses = []
    for fd in fav_data:
        favorites_with_courses.append({"name": fd["name"], "course": fd["course"]})

    # Auto-narrow allowed_proteins from 'any' based on favorites (once, before tc loop)
    _raw_allowed_proteins = taste_prefs.get("allowed_proteins", "any")
    _raw_dietary_for_protein_infer = taste_prefs.get("dietary", "any")
    _effective_allowed_proteins, _proteins_auto_inferred_flag = infer_effective_proteins(
        _raw_allowed_proteins, _raw_dietary_for_protein_infer, favorite_names
    )

    # ── 2. Score dishes per target cuisine ──
    recommendations = {}
    all_scoring_details = {}

    for tc in target_cuisines:
        tc_title = tc.title()
        try:
            c_sim = float(sim_df.loc[source_cuisine.title(), tc_title])
        except KeyError:
            c_sim = 0.0

        tdf = df[df["cuisine_name"].str.lower() == tc.lower()].copy()
        if tdf.empty:
            continue

        # Dietary filter — explicit preference OR inferred from favorites
        dietary_pref = taste_prefs.get("dietary", "any")
        # Auto-infer: if ALL favorites are veg/vegan and user didn't set preference, treat as veg
        _dietary_auto_inferred_flag = False
        if dietary_pref == "any":
            fav_dietaries = [f.get("dietary_type", "") for f in fav_data]
            all_veg = all(_is_veg(d) for d in fav_dietaries)
            all_vegan = all("vegan" in d for d in fav_dietaries)
            if all_vegan:
                dietary_pref = "vegan"
                _dietary_auto_inferred_flag = True
            elif all_veg:
                dietary_pref = "veg"
                _dietary_auto_inferred_flag = True

        if dietary_pref == "veg":
            tdf = tdf[tdf["dietary_type"].str.lower().isin(["veg", "vegan"])]
        elif dietary_pref == "vegan":
            tdf = tdf[tdf["dietary_type"].str.lower() == "vegan"]
        elif dietary_pref == "pescatarian":
            tdf = tdf[tdf["dietary_type"].str.lower().isin(["veg", "vegan", "pescatarian"])]

        # ── Vegetarian protein preference: hard-filter to veg/vegan ──
        # Falls back to original tdf if no veg dishes exist for this cuisine.
        if taste_prefs.get("prefer_vegetarian"):
            tdf_veg = tdf[tdf["dietary_type"].str.lower().isin(["veg", "vegan", "vegetarian"])]
            if not tdf_veg.empty:
                tdf = tdf_veg

        # Protein filter — exclude meats the user doesn't eat (uses inferred list if any)
        allowed_proteins = _effective_allowed_proteins
        if allowed_proteins != "any" and isinstance(allowed_proteins, list):
            from hybrid_engine import PROTEIN_GROUPS, ALL_MEAT_PROTEINS
            allowed_vals = set()
            for gk in allowed_proteins:
                if gk in PROTEIN_GROUPS:
                    allowed_vals |= PROTEIN_GROUPS[gk]
            # Keep veg/vegan dishes + dishes with allowed protein + dishes with no protein
            protein_col = tdf["primary_protein"].fillna("")
            diet_lower = tdf["dietary_type"].str.lower()
            is_veg = diet_lower.isin(["veg", "vegan", "vegetarian"])
            has_allowed = protein_col.isin(allowed_vals)
            has_none = (protein_col == "")
            tdf = tdf[is_veg | has_allowed | has_none]

        # Exclude sauces/condiments unless user explicitly picked some as favorites
        fav_categories = set(f.get("category", "").lower() for f in fav_data)
        if "sauce/condiment" not in fav_categories and "sauce" not in fav_categories:
            tdf = tdf[~tdf["category"].str.lower().isin(["sauce/condiment", "sauce"])]

        if tdf.empty:
            recommendations[tc_title] = {"cuisine_similarity": round(c_sim, 2), "courses": {}, "total_dishes_evaluated": 0}
            continue

        all_scores = []
        scoring_log = []

        for idx, row in tdf.iterrows():
            dish_vec = row[FLAVOR_COLS].values.astype(float)

            # Weighted cosine & euclidean on active dimensions only
            cs = weighted_cosine_sim(user_profile, dish_vec)
            es = weighted_euclidean_score(user_profile, dish_vec)

            # Importance
            imp = float(row["dish_importance_score"]) / 10.0

            # Ingredient overlap score
            dish_ing_str = str(row.get("ingredients", ""))
            ing_score = ingredient_overlap(all_fav_ingredient_words, dish_ing_str)

            # Cooking method match
            cook_score = cooking_method_score(fav_data, row.get("sub_category", ""))

            # Temperature match
            temp_score = temperature_match_score(fav_data, row.get("serving_temperature", "hot"))

            # Main ingredient category match
            ing_cat_score = ingredient_category_score(fav_data, row.get("main_ingredient_category", ""))

            # Flavor deviation penalty (funk, sweet, bitter, spicy)
            dev_penalty = flavor_deviation_penalty(user_profile, dish_vec)

            # Dietary compatibility score
            diet_score = dietary_compatibility_score(fav_data, str(row.get("dietary_type", "")))

            # Spice preference bonus (0-1 scale)
            spice_bonus = 0.0
            dish_spice = float(row.get("spicy_score", 0))
            spice_pref = taste_prefs.get("spice_level", "medium")
            if spice_pref == "mild" and dish_spice <= 0.3:
                spice_bonus = 0.05
            elif spice_pref == "medium" and 0.3 <= dish_spice <= 0.6:
                spice_bonus = 0.03
            elif spice_pref == "hot" and dish_spice >= 0.6:
                spice_bonus = 0.05

            # Category-based penalty
            dish_cat = str(row.get("category", "")).lower()
            cat_penalty = 0.0
            if dish_cat == "drink" and "drink" not in fav_categories:
                cat_penalty = 0.10

            # ── Scoring weights (revised with temperature, ingredient category, dietary, deviation) ──
            # cosine:22% + cooking_method:8% + ingredients:10% + euclidean:8% +
            # cuisine_sim:12% + importance:5% + spice:3% +
            # temperature:7% + ingredient_category:10% + dietary:8%
            # - category_penalty - deviation_penalty
            final = (
                0.22 * cs
                + 0.08 * cook_score
                + 0.10 * ing_score
                + 0.08 * es
                + 0.12 * max(c_sim, 0)
                + 0.05 * imp
                + (0.03 if spice_bonus > 0 else 0.0)
                + 0.07 * temp_score
                + 0.10 * ing_cat_score
                + 0.08 * diet_score
                - cat_penalty
                - dev_penalty
            )
            final = max(final, 0.0)

            # Find which favorite this dish is most similar to
            matched_fav, matched_fav_score = find_closest_favorite(
                dish_vec, dish_ing_str, fav_data,
                dish_course=row["course_group"],
                dish_category=str(row.get("category", "")),
                dish_sub_category=str(row.get("sub_category", "")),
                dish_dietary=str(row.get("dietary_type", ""))
            )

            explanation = build_detailed_explanation(
                user_profile, dish_vec, row, taste_prefs, c_sim, None, matched_fav, ing_score
            )

            # Scoring breakdown for audit
            breakdown = {
                "dish_name": row["dish_name"],
                "course": row["course_group"],
                "cosine_similarity": round(cs, 4),
                "cooking_method": round(cook_score, 4),
                "ingredient_overlap": round(ing_score, 4),
                "temperature_match": round(temp_score, 4),
                "ingredient_category": round(ing_cat_score, 4),
                "dietary_compatibility": round(diet_score, 4),
                "flavor_deviation_penalty": round(dev_penalty, 4),
                "euclidean_score": round(es, 4),
                "cuisine_similarity": round(c_sim, 4),
                "importance_score": round(imp, 4),
                "spice_bonus": round(spice_bonus, 4),
                "final_score": round(final, 4),
                "matched_favorite": matched_fav,
            }
            scoring_log.append(breakdown)

            _mf_score = round(final * 100, 1)
            all_scores.append({
                "dish_name": row["dish_name"],
                "score": _mf_score,
                "cosine": round(cs * 100, 1),
                "euclidean": round(es * 100, 1),
                "ingredient_score": round(ing_score * 100, 1),
                "cooking_method_score": round(cook_score * 100, 1),
                "course": row["course_group"],
                "category": str(row.get("sub_category", "")),
                "dietary": str(row.get("dietary_type", "")),
                "protein": str(row.get("primary_protein", "")),
                "spice_level": str(row.get("spice_level", "")),
                "description": str(row.get("description", "")),
                "ingredients": str(row.get("ingredients", "")),
                "matched_favorite": matched_fav,
                "matched_favorite_score": matched_fav_score,
                "matched_favorites": [{"name": matched_fav, "score": matched_fav_score, "facets": []}] if matched_fav else [],
                "why": explanation,
                "scoring": {
                    "cosine_sim": round(cs * 100, 1),
                    "cooking_method": round(cook_score * 100, 1),
                    "ingredient_match": round(ing_score * 100, 1),
                    "euclidean_sim": round(es * 100, 1),
                    "cuisine_affinity": round(c_sim * 100, 1),
                    "dish_importance": round(imp * 100, 1),
                    "spice_bonus": round(spice_bonus * 100, 1),
                    "temperature_match": round(temp_score * 100, 1),
                    "ingredient_category": round(ing_cat_score * 100, 1),
                    "dietary_compat": round(diet_score * 100, 1),
                    "deviation_penalty": round(dev_penalty * 100, 1),
                },
                "flavor": {
                    FLAVOR_LABELS.get(col, col): float(row[col])
                    for col in FLAVOR_COLS
                },
            })

        # Sort descending
        all_scores.sort(key=lambda x: x["score"], reverse=True)
        scoring_log.sort(key=lambda x: x["final_score"], reverse=True)

        # (prefer_vegetarian was applied as a hard filter on tdf above)

        # ── Pick top 3 overall per target cuisine, then group by course ──
        # Strict same-course matching: only include dishes whose course has a favorite.
        fav_course_set = set(f.get("course", "") for f in fav_data)
        # Appetizer↔Salad are siblings — if user has either, show both
        show_courses = set(fav_course_set)
        if "Appetizer" in show_courses or "Salad" in show_courses:
            show_courses |= {"Appetizer", "Salad"}

        eligible = [d for d in all_scores if d["course"] in show_courses]
        top_overall = eligible[:3]

        courses_result = {}
        for course_name in COURSE_ORDER:
            course_dishes = [d for d in top_overall if d["course"] == course_name]
            if not course_dishes:
                continue
            for dish in course_dishes:
                dish_vec = np.array([dish["flavor"].get(FLAVOR_LABELS.get(c, c), 0) for c in FLAVOR_COLS])
                dish["similar_alternatives"] = find_similar_alternatives(
                    dish["dish_name"], dish_vec, all_scores
                )
            courses_result[course_name] = course_dishes

        recommendations[tc_title] = {
            "cuisine_similarity": round(c_sim, 2),
            "total_dishes_evaluated": len(all_scores),
            "courses": courses_result,
            "visible_per_course": 3,
        }
        all_scoring_details[tc_title] = scoring_log[:30]

    # ── 3. Audit Log ──
    audit_recs = {}
    for cuisine, info in recommendations.items():
        audit_recs[cuisine] = {}
        for course, dishes in info.get("courses", {}).items():
            audit_recs[cuisine][course] = [
                f"{d['dish_name']} ({d['score']}%) [matched: {d['matched_favorite']}]"
                for d in dishes
            ]

    log_audit(
        current_user.id,
        current_user.username,
        "RECOMMENDATION",
        source_cuisine=source_cuisine,
        favorite_dishes=favorite_names,
        taste_preferences=taste_prefs,
        target_cuisines=target_cuisines,
        recommendations=audit_recs,
        scoring_details=all_scoring_details,
        user_profile_vector=profile_dict,
    )

    return jsonify({
        "user_profile": profile_dict,
        "source_cuisine": source_cuisine.title(),
        "favorites_used": favorite_names,
        "favorites_with_courses": favorites_with_courses,
        "taste_preferences": taste_prefs,
        "recommendations": recommendations,
        "auto_inferred_dietary": (dietary_pref if _dietary_auto_inferred_flag else None),
        "auto_inferred_proteins": (_effective_allowed_proteins if _proteins_auto_inferred_flag else None),
    })


# ══════════════════════════════════════════════════════════════════════════════
#  LLM-BASED RECOMMENDATION ENGINE
# ══════════════════════════════════════════════════════════════════════════════

GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
XAI_API_KEY = os.environ.get("XAI_API_KEY", "")


def build_short_llm_prompt(fav_info, target_cuisine, dishes_by_course, dietary_pref):
    """Build a compact prompt optimized for small local models."""
    fav_lines = []
    for f in fav_info:
        fav_lines.append(f"{f['name']} ({f['sub_category']}, {f['dietary_type']}) - {f['ingredients'][:80]}")

    course_lines = []
    for course, dishes in dishes_by_course.items():
        names = [d["name"] for d in dishes]
        course_lines.append(f"{course}: {', '.join(names)}")

    diet_note = ""
    if dietary_pref in ("veg", "inferred_veg"):
        diet_note = "User is VEGETARIAN - only recommend Veg/Vegan dishes."
    elif dietary_pref == "vegan":
        diet_note = "User is VEGAN - only recommend Vegan dishes."

    return f"""User's favorite dishes:
{chr(10).join(fav_lines)}

Available {target_cuisine} dishes by course:
{chr(10).join(course_lines)}

{diet_note}

For each course listed above, pick the 3 best {target_cuisine} dishes that match the user's favorites. Consider cooking method, texture, flavor profile, and ingredients.

Return JSON:
{{"recommendations": {{"CourseName": [{{"dish_name": "exact name", "matched_favorite": "which favorite", "match_score": 85, "why": "2 sentences why", "flavor_bridge": "one line connection"}}]}}}}"""


def get_available_dishes_by_course(cuisine, course_group, dietary_pref="any", **kwargs):
    """Get all available dishes from a cuisine for a specific course group."""
    tdf = df[
        (df["cuisine_name"].str.lower() == cuisine.lower()) &
        (df["course_group"] == course_group)
    ].copy()

    if dietary_pref == "veg":
        tdf = tdf[tdf["dietary_type"].str.lower().isin(["veg", "vegan"])]
    elif dietary_pref == "vegan":
        tdf = tdf[tdf["dietary_type"].str.lower() == "vegan"]
    elif dietary_pref == "pescatarian":
        tdf = tdf[tdf["dietary_type"].str.lower().isin(["veg", "vegan", "pescatarian"])]

    # Protein filter (passed via allowed_proteins kwarg)
    allowed_proteins = kwargs.get("allowed_proteins", "any")
    if allowed_proteins != "any" and isinstance(allowed_proteins, list):
        from hybrid_engine import PROTEIN_GROUPS
        allowed_vals = set()
        for gk in allowed_proteins:
            if gk in PROTEIN_GROUPS:
                allowed_vals |= PROTEIN_GROUPS[gk]
        protein_col = tdf["primary_protein"].fillna("")
        diet_lower = tdf["dietary_type"].str.lower()
        is_veg = diet_lower.isin(["veg", "vegan", "vegetarian"])
        has_allowed = protein_col.isin(allowed_vals)
        has_none = (protein_col == "")
        tdf = tdf[is_veg | has_allowed | has_none]

    dishes = []
    for _, row in tdf.iterrows():
        dishes.append({
            "name": row["dish_name"],
            "sub_category": str(row.get("sub_category", "")),
            "dietary_type": str(row.get("dietary_type", "")),
            "main_ingredient_category": str(row.get("main_ingredient_category", "")),
            "ingredients": str(row.get("ingredients", "")),
            "description": str(row.get("description", "")),
        })
    return dishes


def build_llm_prompt(favorite_dishes_info, target_cuisine, available_dishes_by_course, dietary_pref):
    """Build the prompt for Claude to recommend dishes."""
    # Group favorites by course
    fav_sections = []
    for fav in favorite_dishes_info:
        fav_sections.append(
            f"- {fav['name']} (Course: {fav['course']}, Category: {fav['sub_category']}, "
            f"Dietary: {fav['dietary_type']}, Ingredient Type: {fav['main_ingredient_category']}, "
            f"Ingredients: {fav['ingredients']})"
        )

    # Build available dishes sections per course
    course_sections = []
    for course, dishes in available_dishes_by_course.items():
        dish_list = "\n".join([
            f"  - {d['name']}: {d['description']} [Dietary: {d['dietary_type']}, "
            f"Type: {d['main_ingredient_category']}, Ingredients: {d['ingredients']}]"
            for d in dishes
        ])
        course_sections.append(f"### {course}\n{dish_list}")

    dietary_instruction = ""
    if dietary_pref == "veg":
        dietary_instruction = "\nIMPORTANT: The user is vegetarian. Only recommend Veg or Vegan dishes."
    elif dietary_pref == "vegan":
        dietary_instruction = "\nIMPORTANT: The user is vegan. Only recommend Vegan dishes."
    elif dietary_pref == "inferred_veg":
        dietary_instruction = "\nIMPORTANT: All user's favorites are vegetarian/vegan, so strongly prefer Veg/Vegan recommendations. Only suggest non-veg if there is an exceptionally strong match."

    prompt = f"""You are a world-class food recommendation expert. A user who loves certain dishes from one cuisine wants to try {target_cuisine} cuisine.

## User's Favorite Dishes:
{chr(10).join(fav_sections)}

## Available {target_cuisine} Dishes (grouped by course):
{chr(10).join(course_sections)}
{dietary_instruction}

## Your Task:
Recommend exactly 3 dishes from EACH course section listed above. CRITICAL: a favorite that is a "Main" can ONLY be matched to dishes under the "Main" section. A favorite that is an "Appetizer" can ONLY be matched to dishes under the "Appetizer" section. NEVER cross courses — do NOT recommend appetizers for a main-course favorite or vice versa. If fewer than 3 dishes are available in a course, recommend all that exist.

For each recommendation, explain WHY it matches the user's taste based on:
- Cooking method similarity (fried, grilled, curry, stir-fry, etc.)
- Ingredient/flavor profile similarity (spicy, savory, sweet-sour, etc.)
- Texture similarity (crunchy, chewy, creamy, etc.)
- The specific favorite it maps to and why

## Response Format (strict JSON):
{{
  "recommendations": {{
    "Course Name": [
      {{
        "dish_name": "exact dish name from the available list",
        "matched_favorite": "which user favorite this maps to",
        "match_score": 85,
        "why": "2-3 sentence explanation of why this is a great match",
        "flavor_bridge": "one-line description of the flavor connection"
      }}
    ]
  }}
}}

IMPORTANT RULES:
1. ONLY recommend dishes from the available list provided above — do not invent dishes
2. The "Course Name" keys in your response MUST exactly match the course headings above (e.g. "Main", "Appetizer", "Dessert")
3. NEVER put a dish from one course section into a different course key
4. match_score should be 0-100 reflecting how well it matches the user's taste
5. Be specific in your explanations — reference actual ingredients, cooking methods, textures
6. Consider dietary compatibility when scoring
7. Return ONLY valid JSON, no other text"""

    return prompt


@app.route("/api/recommend-llm", methods=["POST"])
@login_required
def recommend_llm():
    """LLM-powered recommendation endpoint using Claude."""
    data = request.json
    source_cuisine = data.get("source_cuisine", "")
    favorite_names = data.get("favorite_dishes", [])
    target_cuisines = data.get("target_cuisines", [])
    taste_prefs = data.get("taste_preferences", {})

    if not favorite_names or not target_cuisines:
        return jsonify({"error": "Please select favorites and target cuisines"}), 400

    api_key = GROQ_API_KEY or data.get("api_key", "")
    if not api_key:
        return jsonify({"error": "Groq API key not configured."}), 400

    # ── 1. Gather favorite dish info ──
    src_df = df[df["cuisine_name"].str.lower() == source_cuisine.lower()]
    fav_df = src_df[src_df["dish_name"].isin(favorite_names)]

    if fav_df.empty:
        return jsonify({"error": "No matching favorite dishes found"}), 400

    favorite_dishes_info = []
    for _, row in fav_df.iterrows():
        favorite_dishes_info.append({
            "name": row["dish_name"],
            "course": row["course_group"],
            "sub_category": str(row.get("sub_category", "")),
            "dietary_type": str(row.get("dietary_type", "")),
            "main_ingredient_category": str(row.get("main_ingredient_category", "")),
            "ingredients": str(row.get("ingredients", "")),
        })

    # Determine dietary preference (explicit or inferred)
    dietary_pref = taste_prefs.get("dietary", "any")
    if dietary_pref == "any":
        fav_dietaries = [f["dietary_type"].lower() for f in favorite_dishes_info]
        all_veg = all(_is_veg(d) for d in fav_dietaries)
        if all_veg:
            dietary_pref = "inferred_veg"

    # Get unique courses from favorites
    fav_courses = set(f["course"] for f in favorite_dishes_info)

    # ── 2. Call Groq (Llama 3.3 70B — free & fast) for each target cuisine ──
    client = groq.Groq(api_key=api_key)
    recommendations = {}

    for tc in target_cuisines:
        tc_title = tc.title()

        # Get available dishes for each course the user has favorites in
        available_by_course = {}
        for course in fav_courses:
            dishes = get_available_dishes_by_course(
                tc_title, course,
                dietary_pref if dietary_pref != "inferred_veg" else "any",
                allowed_proteins=taste_prefs.get("allowed_proteins", "any"),
            )
            if dishes:
                available_by_course[course] = dishes

        if not available_by_course:
            recommendations[tc_title] = {"courses": {}, "error": "No matching dishes found"}
            continue

        # Build prompt and call Groq
        prompt = build_llm_prompt(favorite_dishes_info, tc_title, available_by_course, dietary_pref)

        try:
            response = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[
                    {"role": "system", "content": "You are a world-class food recommendation expert. Always respond with valid JSON only."},
                    {"role": "user", "content": prompt},
                ],
                max_tokens=2000,
                temperature=0.3,
                response_format={"type": "json_object"},
            )

            response_text = response.choices[0].message.content.strip()

            # Parse JSON from response (handle markdown code blocks)
            if response_text.startswith("```"):
                response_text = response_text.split("```")[1]
                if response_text.startswith("json"):
                    response_text = response_text[4:]
                response_text = response_text.strip()

            llm_result = json.loads(response_text)
            llm_courses = llm_result.get("recommendations", {})

            # Enrich with data from our DB — enforce course matching
            # Build a set of valid dish names per course for enforcement
            valid_dishes_per_course = {}
            for course_key, dish_list in available_by_course.items():
                valid_dishes_per_course[course_key] = set(d["name"] for d in dish_list)

            courses_result = {}
            for course_name, dishes in llm_courses.items():
                # Map LLM course name back to our course_group key
                matched_course = None
                for vc in valid_dishes_per_course:
                    if vc.lower().rstrip('s') == course_name.lower().rstrip('s') or vc.lower() == course_name.lower():
                        matched_course = vc
                        break
                if not matched_course:
                    continue

                enriched_dishes = []
                for dish in dishes[:3]:  # cap at 3
                    dish_name = dish.get("dish_name", "")

                    # Server-side enforcement: only accept dishes that are actually in this course
                    if dish_name not in valid_dishes_per_course[matched_course]:
                        app.logger.warning(f"LLM cross-course violation: '{dish_name}' not in {matched_course}, skipping")
                        continue

                    # Look up in our DB
                    db_row = df[
                        (df["cuisine_name"].str.lower() == tc.lower()) &
                        (df["dish_name"] == dish_name)
                    ]
                    if not db_row.empty:
                        r = db_row.iloc[0]
                        enriched_dishes.append({
                            "dish_name": dish_name,
                            "score": dish.get("match_score", 0),
                            "matched_favorite": dish.get("matched_favorite", ""),
                            "matched_favorite_score": dish.get("match_score", 0),
                            "why": dish.get("why", ""),
                            "flavor_bridge": dish.get("flavor_bridge", ""),
                            "course": course_name,
                            "category": str(r.get("sub_category", "")),
                            "dietary": str(r.get("dietary_type", "")),
                            "protein": str(r.get("primary_protein", "")),
                            "spice_level": str(r.get("spice_level", "")),
                            "description": str(r.get("description", "")),
                            "ingredients": str(r.get("ingredients", "")),
                            "scoring": {
                                "llm_match": dish.get("match_score", 0),
                            },
                            "flavor": {
                                FLAVOR_LABELS.get(col, col): float(r[col])
                                for col in FLAVOR_COLS
                            },
                        })
                    else:
                        # Dish not found in DB — still include with LLM data
                        enriched_dishes.append({
                            "dish_name": dish_name,
                            "score": dish.get("match_score", 0),
                            "matched_favorite": dish.get("matched_favorite", ""),
                            "matched_favorite_score": dish.get("match_score", 0),
                            "why": dish.get("why", ""),
                            "flavor_bridge": dish.get("flavor_bridge", ""),
                            "course": course_name,
                            "category": "",
                            "dietary": "",
                            "protein": "",
                            "spice_level": "",
                            "description": "",
                            "ingredients": "",
                            "scoring": {"llm_match": dish.get("match_score", 0)},
                            "flavor": {},
                        })
                if enriched_dishes:
                    courses_result[matched_course] = enriched_dishes

            try:
                c_sim = float(sim_df.loc[source_cuisine.title(), tc_title])
            except KeyError:
                c_sim = 0.0

            recommendations[tc_title] = {
                "cuisine_similarity": round(c_sim, 2),
                "total_dishes_evaluated": sum(len(v) for v in available_by_course.values()),
                "courses": courses_result,
                "engine": "llm",
            }

        except json.JSONDecodeError as e:
            recommendations[tc_title] = {
                "courses": {},
                "error": f"Failed to parse LLM response: {str(e)}",
                "raw_response": response_text[:500] if 'response_text' in dir() else "",
            }
        except Exception as e:
            recommendations[tc_title] = {
                "courses": {},
                "error": f"LLM API error: {str(e)}",
            }

    # Build user profile for display
    fav_vectors = fav_df[FLAVOR_COLS].values
    weights = fav_df["dish_importance_score"].values
    user_profile = np.average(fav_vectors, axis=0, weights=weights)
    profile_dict = {FLAVOR_LABELS.get(col, col): round(float(user_profile[i]), 1) for i, col in enumerate(FLAVOR_COLS)}

    favorites_with_courses = [{"name": f["name"], "course": f["course"]} for f in favorite_dishes_info]

    # Audit log
    log_audit(
        current_user.id, current_user.username, "RECOMMENDATION_LLM",
        source_cuisine=source_cuisine,
        favorite_dishes=favorite_names,
        taste_preferences=taste_prefs,
        target_cuisines=target_cuisines,
        recommendations={c: {k: [d["dish_name"] for d in ds] for k, ds in v.get("courses", {}).items()} for c, v in recommendations.items()},
        user_profile_vector=profile_dict,
    )

    return jsonify({
        "user_profile": profile_dict,
        "source_cuisine": source_cuisine.title(),
        "favorites_used": favorite_names,
        "favorites_with_courses": favorites_with_courses,
        "taste_preferences": taste_prefs,
        "recommendations": recommendations,
        "engine": "llm",
    })


# ══════════════════════════════════════════════════════════════════════════════
#  GEMINI-BASED RECOMMENDATION ENGINE
# ══════════════════════════════════════════════════════════════════════════════

@app.route("/api/recommend-gemini", methods=["POST"])
@login_required
def recommend_gemini():
    """Gemini-powered recommendation endpoint using Google AI."""
    data = request.json
    source_cuisine = data.get("source_cuisine", "")
    favorite_names = data.get("favorite_dishes", [])
    target_cuisines = data.get("target_cuisines", [])
    taste_prefs = data.get("taste_preferences", {})

    if not favorite_names or not target_cuisines:
        return jsonify({"error": "Please select favorites and target cuisines"}), 400

    api_key = GEMINI_API_KEY or data.get("api_key", "")
    if not api_key:
        return jsonify({"error": "Gemini API key not configured."}), 400

    # ── 1. Gather favorite dish info ──
    src_df = df[df["cuisine_name"].str.lower() == source_cuisine.lower()]
    fav_df = src_df[src_df["dish_name"].isin(favorite_names)]

    if fav_df.empty:
        return jsonify({"error": "No matching favorite dishes found"}), 400

    favorite_dishes_info = []
    for _, row in fav_df.iterrows():
        favorite_dishes_info.append({
            "name": row["dish_name"],
            "course": row["course_group"],
            "sub_category": str(row.get("sub_category", "")),
            "dietary_type": str(row.get("dietary_type", "")),
            "main_ingredient_category": str(row.get("main_ingredient_category", "")),
            "ingredients": str(row.get("ingredients", "")),
        })

    # Determine dietary preference (explicit or inferred)
    dietary_pref = taste_prefs.get("dietary", "any")
    if dietary_pref == "any":
        fav_dietaries = [f["dietary_type"].lower() for f in favorite_dishes_info]
        all_veg = all(_is_veg(d) for d in fav_dietaries)
        if all_veg:
            dietary_pref = "inferred_veg"

    # Get unique courses from favorites
    fav_courses = set(f["course"] for f in favorite_dishes_info)

    # ── 2. Call Gemini for each target cuisine ──
    client = google_genai.Client(api_key=api_key)
    recommendations = {}

    for tc in target_cuisines:
        tc_title = tc.title()

        # Get available dishes for each course the user has favorites in
        available_by_course = {}
        for course in fav_courses:
            dishes = get_available_dishes_by_course(
                tc_title, course,
                dietary_pref if dietary_pref != "inferred_veg" else "any",
                allowed_proteins=taste_prefs.get("allowed_proteins", "any"),
            )
            if dishes:
                available_by_course[course] = dishes

        if not available_by_course:
            recommendations[tc_title] = {"courses": {}, "error": "No matching dishes found"}
            continue

        # Build prompt (reuse the same prompt builder as Groq)
        prompt = build_llm_prompt(favorite_dishes_info, tc_title, available_by_course, dietary_pref)

        try:
            response = client.models.generate_content(
                model="gemini-2.5-flash-lite",
                contents=prompt,
                config={
                    "temperature": 0.3,
                    "max_output_tokens": 2000,
                    "response_mime_type": "application/json",
                },
            )

            response_text = response.text.strip()

            # Parse JSON from response (handle markdown code blocks)
            if response_text.startswith("```"):
                response_text = response_text.split("```")[1]
                if response_text.startswith("json"):
                    response_text = response_text[4:]
                response_text = response_text.strip()

            llm_result = json.loads(response_text)
            llm_courses = llm_result.get("recommendations", {})

            # Enrich with data from our DB — enforce course matching
            valid_dishes_per_course = {}
            for course_key, dish_list in available_by_course.items():
                valid_dishes_per_course[course_key] = set(d["name"] for d in dish_list)

            courses_result = {}
            for course_name, dishes in llm_courses.items():
                # Map LLM course name back to our course_group key
                matched_course = None
                for vc in valid_dishes_per_course:
                    if vc.lower().rstrip('s') == course_name.lower().rstrip('s') or vc.lower() == course_name.lower():
                        matched_course = vc
                        break
                if not matched_course:
                    continue

                enriched_dishes = []
                for dish in dishes[:3]:
                    dish_name = dish.get("dish_name", "")

                    # Server-side enforcement: only accept dishes in this course
                    if dish_name not in valid_dishes_per_course[matched_course]:
                        app.logger.warning(f"Gemini cross-course violation: '{dish_name}' not in {matched_course}, skipping")
                        continue

                    db_row = df[
                        (df["cuisine_name"].str.lower() == tc.lower()) &
                        (df["dish_name"] == dish_name)
                    ]
                    if not db_row.empty:
                        r = db_row.iloc[0]
                        enriched_dishes.append({
                            "dish_name": dish_name,
                            "score": dish.get("match_score", 0),
                            "matched_favorite": dish.get("matched_favorite", ""),
                            "matched_favorite_score": dish.get("match_score", 0),
                            "why": dish.get("why", ""),
                            "flavor_bridge": dish.get("flavor_bridge", ""),
                            "course": course_name,
                            "category": str(r.get("sub_category", "")),
                            "dietary": str(r.get("dietary_type", "")),
                            "protein": str(r.get("primary_protein", "")),
                            "spice_level": str(r.get("spice_level", "")),
                            "description": str(r.get("description", "")),
                            "ingredients": str(r.get("ingredients", "")),
                            "scoring": {"llm_match": dish.get("match_score", 0)},
                            "flavor": {
                                FLAVOR_LABELS.get(col, col): float(r[col])
                                for col in FLAVOR_COLS
                            },
                        })
                    else:
                        enriched_dishes.append({
                            "dish_name": dish_name,
                            "score": dish.get("match_score", 0),
                            "matched_favorite": dish.get("matched_favorite", ""),
                            "matched_favorite_score": dish.get("match_score", 0),
                            "why": dish.get("why", ""),
                            "flavor_bridge": dish.get("flavor_bridge", ""),
                            "course": course_name,
                            "category": "", "dietary": "", "protein": "",
                            "spice_level": "", "description": "", "ingredients": "",
                            "scoring": {"llm_match": dish.get("match_score", 0)},
                            "flavor": {},
                        })
                if enriched_dishes:
                    courses_result[matched_course] = enriched_dishes

            try:
                c_sim = float(sim_df.loc[source_cuisine.title(), tc_title])
            except KeyError:
                c_sim = 0.0

            recommendations[tc_title] = {
                "cuisine_similarity": round(c_sim, 2),
                "total_dishes_evaluated": sum(len(v) for v in available_by_course.values()),
                "courses": courses_result,
                "engine": "gemini",
            }

        except json.JSONDecodeError as e:
            recommendations[tc_title] = {
                "courses": {},
                "error": f"Failed to parse Gemini response: {str(e)}",
                "raw_response": response_text[:500] if 'response_text' in dir() else "",
            }
        except Exception as e:
            recommendations[tc_title] = {
                "courses": {},
                "error": f"Gemini API error: {str(e)}",
            }

    # Build user profile for display
    fav_vectors = fav_df[FLAVOR_COLS].values
    weights = fav_df["dish_importance_score"].values
    user_profile = np.average(fav_vectors, axis=0, weights=weights)
    profile_dict = {FLAVOR_LABELS.get(col, col): round(float(user_profile[i]), 1) for i, col in enumerate(FLAVOR_COLS)}
    favorites_with_courses = [{"name": f["name"], "course": f["course"]} for f in favorite_dishes_info]

    log_audit(
        current_user.id, current_user.username, "RECOMMENDATION_GEMINI",
        source_cuisine=source_cuisine,
        favorite_dishes=favorite_names,
        taste_preferences=taste_prefs,
        target_cuisines=target_cuisines,
        recommendations={c: {k: [d["dish_name"] for d in ds] for k, ds in v.get("courses", {}).items()} for c, v in recommendations.items()},
        user_profile_vector=profile_dict,
    )

    return jsonify({
        "user_profile": profile_dict,
        "source_cuisine": source_cuisine.title(),
        "favorites_used": favorite_names,
        "favorites_with_courses": favorites_with_courses,
        "taste_preferences": taste_prefs,
        "recommendations": recommendations,
        "engine": "gemini",
    })


# ══════════════════════════════════════════════════════════════════════════════
#  X.AI (GROK) RECOMMENDATION ENGINE
# ══════════════════════════════════════════════════════════════════════════════

@app.route("/api/recommend-xai", methods=["POST"])
@login_required
def recommend_xai():
    """x.AI Grok-powered recommendation endpoint."""
    data = request.json
    source_cuisine = data.get("source_cuisine", "")
    favorite_names = data.get("favorite_dishes", [])
    target_cuisines = data.get("target_cuisines", [])
    taste_prefs = data.get("taste_preferences", {})

    if not favorite_names or not target_cuisines:
        return jsonify({"error": "Please select favorites and target cuisines"}), 400

    api_key = XAI_API_KEY or data.get("api_key", "")
    if not api_key:
        return jsonify({"error": "x.AI API key not configured."}), 400

    # ── 1. Gather favorite dish info ──
    src_df = df[df["cuisine_name"].str.lower() == source_cuisine.lower()]
    fav_df = src_df[src_df["dish_name"].isin(favorite_names)]

    if fav_df.empty:
        return jsonify({"error": "No matching favorite dishes found"}), 400

    favorite_dishes_info = []
    for _, row in fav_df.iterrows():
        favorite_dishes_info.append({
            "name": row["dish_name"],
            "course": row["course_group"],
            "sub_category": str(row.get("sub_category", "")),
            "dietary_type": str(row.get("dietary_type", "")),
            "main_ingredient_category": str(row.get("main_ingredient_category", "")),
            "ingredients": str(row.get("ingredients", "")),
        })

    # Determine dietary preference (explicit or inferred)
    dietary_pref = taste_prefs.get("dietary", "any")
    if dietary_pref == "any":
        fav_dietaries = [f["dietary_type"].lower() for f in favorite_dishes_info]
        all_veg = all(_is_veg(d) for d in fav_dietaries)
        if all_veg:
            dietary_pref = "inferred_veg"

    # Get unique courses from favorites
    fav_courses = set(f["course"] for f in favorite_dishes_info)

    # ── 2. Call x.AI Grok for each target cuisine ──
    client = XAIClient(api_key=api_key, base_url="https://api.x.ai/v1")
    recommendations = {}

    for tc in target_cuisines:
        tc_title = tc.title()

        # Get available dishes for each course the user has favorites in
        available_by_course = {}
        for course in fav_courses:
            dishes = get_available_dishes_by_course(
                tc_title, course,
                dietary_pref if dietary_pref != "inferred_veg" else "any",
                allowed_proteins=taste_prefs.get("allowed_proteins", "any"),
            )
            if dishes:
                available_by_course[course] = dishes

        if not available_by_course:
            recommendations[tc_title] = {"courses": {}, "error": "No matching dishes found"}
            continue

        # Build prompt (reuse the same prompt builder)
        prompt = build_llm_prompt(favorite_dishes_info, tc_title, available_by_course, dietary_pref)

        try:
            response = client.chat.completions.create(
                model="grok-3-mini-fast",
                messages=[
                    {"role": "system", "content": "You are a world-class food recommendation expert. Always respond with valid JSON only."},
                    {"role": "user", "content": prompt},
                ],
                max_tokens=2000,
                temperature=0.3,
            )

            response_text = response.choices[0].message.content.strip()

            # Parse JSON from response (handle markdown code blocks)
            if response_text.startswith("```"):
                response_text = response_text.split("```")[1]
                if response_text.startswith("json"):
                    response_text = response_text[4:]
                response_text = response_text.strip()

            llm_result = json.loads(response_text)
            llm_courses = llm_result.get("recommendations", {})

            # Enrich with data from our DB — enforce course matching
            valid_dishes_per_course = {}
            for course_key, dish_list in available_by_course.items():
                valid_dishes_per_course[course_key] = set(d["name"] for d in dish_list)

            courses_result = {}
            for course_name, dishes in llm_courses.items():
                # Map LLM course name back to our course_group key
                matched_course = None
                for vc in valid_dishes_per_course:
                    if vc.lower().rstrip('s') == course_name.lower().rstrip('s') or vc.lower() == course_name.lower():
                        matched_course = vc
                        break
                if not matched_course:
                    continue

                enriched_dishes = []
                for dish in dishes[:3]:
                    dish_name = dish.get("dish_name", "")

                    # Server-side enforcement: only accept dishes in this course
                    if dish_name not in valid_dishes_per_course[matched_course]:
                        app.logger.warning(f"xAI cross-course violation: '{dish_name}' not in {matched_course}, skipping")
                        continue

                    db_row = df[
                        (df["cuisine_name"].str.lower() == tc.lower()) &
                        (df["dish_name"] == dish_name)
                    ]
                    if not db_row.empty:
                        r = db_row.iloc[0]
                        enriched_dishes.append({
                            "dish_name": dish_name,
                            "score": dish.get("match_score", 0),
                            "matched_favorite": dish.get("matched_favorite", ""),
                            "matched_favorite_score": dish.get("match_score", 0),
                            "why": dish.get("why", ""),
                            "flavor_bridge": dish.get("flavor_bridge", ""),
                            "course": course_name,
                            "category": str(r.get("sub_category", "")),
                            "dietary": str(r.get("dietary_type", "")),
                            "protein": str(r.get("primary_protein", "")),
                            "spice_level": str(r.get("spice_level", "")),
                            "description": str(r.get("description", "")),
                            "ingredients": str(r.get("ingredients", "")),
                            "scoring": {"llm_match": dish.get("match_score", 0)},
                            "flavor": {
                                FLAVOR_LABELS.get(col, col): float(r[col])
                                for col in FLAVOR_COLS
                            },
                        })
                    else:
                        enriched_dishes.append({
                            "dish_name": dish_name,
                            "score": dish.get("match_score", 0),
                            "matched_favorite": dish.get("matched_favorite", ""),
                            "matched_favorite_score": dish.get("match_score", 0),
                            "why": dish.get("why", ""),
                            "flavor_bridge": dish.get("flavor_bridge", ""),
                            "course": course_name,
                            "category": "", "dietary": "", "protein": "",
                            "spice_level": "", "description": "", "ingredients": "",
                            "scoring": {"llm_match": dish.get("match_score", 0)},
                            "flavor": {},
                        })
                if enriched_dishes:
                    courses_result[matched_course] = enriched_dishes

            try:
                c_sim = float(sim_df.loc[source_cuisine.title(), tc_title])
            except KeyError:
                c_sim = 0.0

            recommendations[tc_title] = {
                "cuisine_similarity": round(c_sim, 2),
                "total_dishes_evaluated": sum(len(v) for v in available_by_course.values()),
                "courses": courses_result,
                "engine": "xai",
            }

        except json.JSONDecodeError as e:
            recommendations[tc_title] = {
                "courses": {},
                "error": f"Failed to parse Grok response: {str(e)}",
                "raw_response": response_text[:500] if 'response_text' in dir() else "",
            }
        except Exception as e:
            recommendations[tc_title] = {
                "courses": {},
                "error": f"x.AI API error: {str(e)}",
            }

    # Build user profile for display
    fav_vectors = fav_df[FLAVOR_COLS].values
    weights = fav_df["dish_importance_score"].values
    user_profile = np.average(fav_vectors, axis=0, weights=weights)
    profile_dict = {FLAVOR_LABELS.get(col, col): round(float(user_profile[i]), 1) for i, col in enumerate(FLAVOR_COLS)}
    favorites_with_courses = [{"name": f["name"], "course": f["course"]} for f in favorite_dishes_info]

    log_audit(
        current_user.id, current_user.username, "RECOMMENDATION_XAI",
        source_cuisine=source_cuisine,
        favorite_dishes=favorite_names,
        taste_preferences=taste_prefs,
        target_cuisines=target_cuisines,
        recommendations={c: {k: [d["dish_name"] for d in ds] for k, ds in v.get("courses", {}).items()} for c, v in recommendations.items()},
        user_profile_vector=profile_dict,
    )

    return jsonify({
        "user_profile": profile_dict,
        "source_cuisine": source_cuisine.title(),
        "favorites_used": favorite_names,
        "favorites_with_courses": favorites_with_courses,
        "taste_preferences": taste_prefs,
        "recommendations": recommendations,
        "engine": "xai",
    })


# ══════════════════════════════════════════════════════════════════════════════
#  ROUTES — Audit
# ══════════════════════════════════════════════════════════════════════════════

@app.route("/api/audit/my-history")
@login_required
def my_audit_history():
    db = get_db()
    rows = db.execute(
        """SELECT * FROM audit_logs
           WHERE user_id = %s AND action = 'RECOMMENDATION'
           ORDER BY timestamp DESC LIMIT 20""",
        (current_user.id,),
    ).fetchall()
    results = []
    for row in rows:
        ts = row["timestamp"]
        results.append({
            "id": row["id"],
            "timestamp": ts.isoformat() if hasattr(ts, "isoformat") else ts,
            "source_cuisine": row["source_cuisine"],
            "favorite_dishes": row["favorite_dishes"] or [],
            "taste_preferences": row["taste_preferences"] or {},
            "target_cuisines": row["target_cuisines"] or [],
            "recommendations": row["recommendations"] or {},
            "user_profile_vector": row["user_profile_vector"] or {},
        })
    return jsonify(results)


@app.route("/api/audit/detail/<log_id>")
@login_required
def audit_detail(log_id):
    db = get_db()
    row = db.execute("SELECT * FROM audit_logs WHERE id = %s AND user_id = %s", (log_id, current_user.id)).fetchone()
    if not row:
        return jsonify({"error": "Not found"}), 404
    ts = row["timestamp"]
    return jsonify({
        "id": row["id"],
        "timestamp": ts.isoformat() if hasattr(ts, "isoformat") else ts,
        "source_cuisine": row["source_cuisine"],
        "favorite_dishes": row["favorite_dishes"] or [],
        "taste_preferences": row["taste_preferences"] or {},
        "target_cuisines": row["target_cuisines"] or [],
        "recommendations": row["recommendations"] or {},
        "scoring_details": row["scoring_details"] or {},
        "user_profile_vector": row["user_profile_vector"] or {},
    })


@app.route("/history")
@login_required
def history_page():
    return render_template("history.html", user=current_user)


# ══════════════════════════════════════════════════════════════════════════════
#  HYBRID ENGINE ENDPOINT
# ══════════════════════════════════════════════════════════════════════════════

@app.route("/api/recommend-hybrid", methods=["POST"])
@login_required
def recommend_hybrid():
    """Hybrid Intersection Engine — 3-file, 6-step pipeline."""
    if hybrid_engine is None:
        return jsonify({"error": "Hybrid engine not available. CSV data files may be missing."}), 503

    data = request.json
    source_cuisine = data.get("source_cuisine", "")
    favorite_dishes = data.get("favorite_dishes", [])
    target_cuisines = data.get("target_cuisines", [])
    taste_prefs = data.get("taste_preferences", {})
    dietary = taste_prefs.get("dietary", "")
    allowed_proteins = taste_prefs.get("allowed_proteins", "any")

    if not favorite_dishes:
        return jsonify({"error": "No favorite dishes provided."})

    # Auto-infer: if user left dietary as "any" but every favorite is veg,
    # upgrade to veg to prevent silent non-veg leaks attributed to veg seeds.
    dietary, auto_inferred = infer_effective_dietary(dietary, favorite_dishes)
    auto_inferred_dietary = dietary if auto_inferred else None

    # Auto-narrow protein whitelist from 'any' to groups observed in favorites
    allowed_proteins, proteins_auto_inferred = infer_effective_proteins(
        allowed_proteins, dietary, favorite_dishes
    )
    auto_inferred_proteins = allowed_proteins if proteins_auto_inferred else None

    # prefer_vegetarian (from Protein Preferences) hard-filters to veg/vegan dishes.
    # If no veg results come back for a cuisine, we fall back to the user's original
    # dietary preference for that cuisine only.
    prefer_veg = bool(taste_prefs.get("prefer_vegetarian"))
    engine_dietary = "veg" if prefer_veg else dietary

    # Build user flavor profile from favorites (average of seed flavors)
    from hybrid_engine import FLAVOR_DIMS as HF_DIMS
    user_profile = {}
    fav_vectors = []
    for fav in favorite_dishes:
        info = hybrid_engine.get_dish_info(fav)
        if info and "flavor" in info:
            fav_vectors.append(info["flavor"])
    if fav_vectors:
        for dim in HF_DIMS:
            vals = [v[dim] for v in fav_vectors if dim in v]
            user_profile[dim] = round(sum(vals) / len(vals), 2) if vals else 0.0

    # Resolve favorite courses for display
    favorites_with_courses = []
    for fav in favorite_dishes:
        info = hybrid_engine.get_dish_info(fav)
        course = info["category"] if info else "—"
        favorites_with_courses.append({"name": fav, "course": course})

    def _collect_for_cuisine(tc, dietary_arg):
        """Run the hybrid pipeline for one target cuisine and return courses_dict + counters.

        Uses the shared select_with_show_more helper so a single candidate matched by
        multiple favorites is rendered once with all seed attributions (matched_favorites
        array). The first `visible_per_course` entries per course are the defaults;
        the remainder are revealed by a frontend "Show more" toggle.
        """
        # Tier 1 (same-course seed→candidate) goes straight into per_seed_by_course.
        # Tier 2 (cross-course) is held in tier2_by_course and only merged in if
        # a target bucket is thin after Tier 1. This preserves "appetizer seeds
        # own the appetizer bucket" while still filling sparse courses (e.g. no
        # salad favorites) from cross-course overflow.
        MIN_PER_COURSE = 3   # if Tier 1 gives fewer than 3 in a course, top up
        fav_course_map = {f["name"]: canonical_category(f["course"]) for f in favorites_with_courses}

        per_seed_by_course = {}   # cat → seed → [(score, matched, cand), ...]
        tier2_by_course    = {}   # same shape, held back
        total_eval = 0
        for fav in favorite_dishes:
            fav_course = fav_course_map.get(fav, "Main Course")
            result = hybrid_engine.get_recommendations(
                seed_dish=fav,
                user_preferences={"dietary": dietary_arg, "target_cuisine": tc, "discovery_mode": True, "allowed_proteins": allowed_proteins},
            )
            if isinstance(result, dict) and "recommendations" in result:
                total_eval += result.get("pipeline_stats", {}).get("after_hard_filter", 0)
                for rec in result["recommendations"]:
                    cat = canonical_category(rec.get("category", "Main Course"))
                    rec_cand = dict(rec)
                    rec_cand["dish_name"] = rec["dish_name"]
                    score   = float(rec.get("match_score", 0.0))
                    matched = [rec.get("match_reason")] if rec.get("match_reason") else []
                    entry   = (score, matched, rec_cand)
                    if cat == fav_course:
                        per_seed_by_course.setdefault(cat, {}).setdefault(fav, []).append(entry)
                    else:
                        tier2_by_course.setdefault(cat, {}).setdefault(fav, []).append(entry)

        # Tier 2 top-up: for each course with held-back candidates, merge them
        # into per_seed_by_course only if the Tier 1 bucket is under the threshold.
        for cat, t2_seeds in tier2_by_course.items():
            existing = per_seed_by_course.get(cat, {})
            total_existing = sum(len(v) for v in existing.values())
            if total_existing >= MIN_PER_COURSE:
                continue
            for seed, picks in t2_seeds.items():
                per_seed_by_course.setdefault(cat, {}).setdefault(seed, []).extend(picks)

        def _build_h1_entry(entry, cat):
            cand = entry["cand"]
            mfs = entry["matched_favorites"]
            top = mfs[0]
            display_score = float(top["score"])
            why_text = (
                top["matched"][0] if top["matched"]
                else f"Flavor distance: {cand.get('flavor_distance', 0):.3f}"
            )
            matched_favorites_display = [
                {
                    "name":   mf["name"],
                    "score":  float(mf["score"]),
                    "facets": mf["matched"][:5],
                }
                for mf in mfs
            ]
            return {
                "dish_name":              str(cand["dish_name"]),
                "score":                  display_score,
                "category":               cat,
                "dietary":                cand.get("dietary_type", ""),
                "protein":                cand.get("primary_protein", ""),
                "description":            cand.get("context_string", ""),
                "why":                    why_text,
                "matched_favorite":       top["name"],
                "matched_favorite_score": display_score,
                "matched_favorites":      matched_favorites_display,
                "course":                 cat,
                "spice_level":            "",
                "ingredients":            "",
                "flavor_distance":        cand.get("flavor_distance", 0),
                "flavor":                 cand.get("flavor", {}),
                "seed_flavor":            cand.get("seed_flavor", {}),
                "scoring": {
                    "cosine_sim":          display_score,
                    "cooking_method":      0,
                    "ingredient_match":    0,
                    "temperature_match":   100 if cand.get("temp") else 0,
                    "ingredient_category": 0,
                    "dietary_compat":      100,
                },
            }

        courses_dict_local = {}
        for cat, per_seed in per_seed_by_course.items():
            visible_entries, hidden_entries = select_with_show_more(
                per_seed, max_visible=3, max_hidden=6, score_floor=0.0,
            )
            entries = [_build_h1_entry(e, cat) for e in visible_entries]
            entries += [_build_h1_entry(e, cat) for e in hidden_entries]
            if entries:
                courses_dict_local[cat] = entries
        return courses_dict_local, total_eval

    # Run hybrid pipeline: top 3 per favorite, per target cuisine
    all_recommendations = {}
    for tc in target_cuisines:
        tc_title = tc.strip().title()
        # Cuisine similarity
        c_sim = 0.0
        if hybrid_engine.sim_df is not None:
            try:
                c_sim = float(hybrid_engine.sim_df.loc[source_cuisine.title(), tc_title])
            except (KeyError, ValueError):
                c_sim = 0.0

        courses_dict, total_evaluated = _collect_for_cuisine(tc, engine_dietary)

        # Vegetarian preference: if veg-only returned nothing, fall back to original dietary
        if prefer_veg and not any(courses_dict.get(c) for c in courses_dict):
            courses_dict, total_evaluated = _collect_for_cuisine(tc, dietary)

        all_recommendations[tc] = {
            "cuisine_similarity": c_sim,
            "total_dishes_evaluated": total_evaluated,
            "courses": courses_dict,
            "visible_per_course": 3,
        }

    return jsonify({
        "engine": "hybrid",
        "source_cuisine": source_cuisine,
        "favorites_used": favorite_dishes,
        "taste_preferences": taste_prefs,
        "favorites_with_courses": favorites_with_courses,
        "user_profile": user_profile,
        "recommendations": all_recommendations,
        "auto_inferred_dietary": auto_inferred_dietary,
        "auto_inferred_proteins": auto_inferred_proteins,
    })


# ══════════════════════════════════════════════════════════════════════════════
#  HYBRID 2.0 — Grok-cached recommendations filtered by user preferences
# ══════════════════════════════════════════════════════════════════════════════

_grok_enriched_df = None


def _load_grok_enriched():
    """Load grok_recommendations.csv and enrich with authoritative metadata.
    Cached in memory after first call.
    """
    global _grok_enriched_df
    if _grok_enriched_df is not None:
        return _grok_enriched_df

    grok_path = os.path.join(os.path.dirname(__file__), "data", "grok_recommendations.csv")
    meta_path = os.path.join(os.path.dirname(__file__), "data", "Metadata_Filters.csv")
    if not os.path.exists(grok_path):
        return None

    import pandas as pd
    grok = pd.read_csv(grok_path)
    grok["recommended_dish"] = grok["recommended_dish"].astype(str).str.strip()
    grok["target_cuisine"]   = grok["target_cuisine"].astype(str).str.strip()
    grok["dish_name"]        = grok["dish_name"].astype(str).str.strip()
    grok["cuisine"]          = grok["cuisine"].astype(str).str.strip()

    meta = pd.read_csv(meta_path)
    meta = meta[meta["dish_name"] != "dish_name"].copy()
    meta["dish_name"] = meta["dish_name"].astype(str).str.strip()
    meta["cuisine"]   = meta["cuisine"].astype(str).str.strip()

    # Join Grok recs against authoritative metadata (by recommended_dish + target_cuisine)
    meta_renamed = meta[["dish_name", "cuisine", "category", "dietary_type", "primary_protein"]].rename(
        columns={
            "dish_name": "recommended_dish",
            "cuisine": "target_cuisine",
            "category": "meta_category",
            "dietary_type": "meta_dietary_type",
            "primary_protein": "meta_primary_protein",
        }
    )
    enriched = grok.merge(meta_renamed, on=["recommended_dish", "target_cuisine"], how="left")
    _grok_enriched_df = enriched
    return enriched


@app.route("/api/recommend-hybrid-v2", methods=["POST"])
@login_required
def recommend_hybrid_v2():
    """Hybrid 2.0 — Grok-cached top-10 with user-preference filtering.

    For each favorite × target cuisine:
      1. Look up Grok's top 10 in grok_recommendations.csv
      2. Enrich with authoritative metadata (dietary_type, primary_protein, category)
      3. Filter by user dietary + allowed_proteins
      4. Return top 3 survivors
    """
    df = _load_grok_enriched()
    if df is None:
        return jsonify({"error": "Hybrid 2.0 cache not available. data/grok_recommendations.csv missing."}), 503

    data = request.json
    source_cuisine  = data.get("source_cuisine", "")
    favorite_dishes = data.get("favorite_dishes", [])
    target_cuisines = data.get("target_cuisines", [])
    taste_prefs     = data.get("taste_preferences", {})
    dietary         = str(taste_prefs.get("dietary", "")).strip().lower()
    allowed_proteins = taste_prefs.get("allowed_proteins", "any")

    if not favorite_dishes:
        return jsonify({"error": "No favorite dishes provided."})

    # Auto-infer veg/vegan from favorites when dietary is "any" or unset.
    dietary, auto_inferred = infer_effective_dietary(dietary, favorite_dishes)
    auto_inferred_dietary  = dietary if auto_inferred else None

    # Auto-narrow protein whitelist from 'any' based on observed favorites.
    allowed_proteins, proteins_auto_inferred = infer_effective_proteins(
        allowed_proteins, dietary, favorite_dishes
    )
    auto_inferred_proteins = allowed_proteins if proteins_auto_inferred else None

    # ── Protein whitelist (reuse hybrid engine's grouping) ──
    from hybrid_engine import PROTEIN_GROUPS
    allowed_protein_values = None
    if allowed_proteins != "any" and isinstance(allowed_proteins, list):
        allowed_protein_values = set()
        for group_key in allowed_proteins:
            if group_key in PROTEIN_GROUPS:
                allowed_protein_values |= PROTEIN_GROUPS[group_key]

    # prefer_vegetarian (from Protein Preferences) hard-filters Grok's candidates to
    # veg/vegan. If no veg candidates exist for a favorite, we fall back per-favorite.
    # Belt-and-suspenders: also trigger if user picked Veg/Vegan in Diet Preferences.
    prefer_veg = bool(taste_prefs.get("prefer_vegetarian")) or dietary in ("veg", "vegan", "vegetarian")
    print(f"[hybrid-v2] taste_prefs={taste_prefs} → prefer_veg={prefer_veg}", flush=True)

    def is_veg_dish(diet_val):
        d = str(diet_val or "").strip().lower()
        return d in ("veg", "vegan", "vegetarian")

    def dietary_ok(diet_val):
        if not dietary or dietary == "any":
            return True
        d = str(diet_val or "").strip().lower()
        if dietary == "vegan":
            return d == "vegan"
        if dietary in ("veg", "vegetarian"):
            return d in ("veg", "vegan", "vegetarian")
        if dietary == "pescatarian":
            return d in ("veg", "vegan", "vegetarian", "pescatarian")
        return True

    def protein_ok(diet_val, protein_val):
        d = str(diet_val or "").strip().lower()
        # Veg/vegan dishes always OK (no meat)
        if d in ("veg", "vegan", "vegetarian"):
            return True
        # No protein restriction set → allow all
        if allowed_protein_values is None:
            return True
        # Missing protein info → allow (be permissive)
        p = str(protein_val or "").strip()
        if not p or p.lower() in ("nan", "none", ""):
            return True
        return p in allowed_protein_values

    # ── Favorites with courses (for display) ──
    favorites_with_courses = []
    for fav in favorite_dishes:
        info = hybrid_engine.get_dish_info(fav) if hybrid_engine else None
        course = info["category"] if info else "—"
        favorites_with_courses.append({"name": fav, "course": course})

    # ── Build user flavor profile (average of seed flavor vectors) ──
    user_profile = {}
    if hybrid_engine:
        from hybrid_engine import FLAVOR_DIMS as HF_DIMS
        fav_vectors = []
        for fav in favorite_dishes:
            info = hybrid_engine.get_dish_info(fav)
            if info and "flavor" in info:
                fav_vectors.append(info["flavor"])
        if fav_vectors:
            for dim in HF_DIMS:
                vals = [v[dim] for v in fav_vectors if dim in v]
                user_profile[dim] = round(sum(vals) / len(vals), 2) if vals else 0.0

    # ── Main loop: per target cuisine ──
    all_recommendations = {}
    import pandas as pd
    for tc in target_cuisines:
        tc_title = tc.strip().title()

        # Cuisine similarity
        c_sim = 0.0
        if hybrid_engine and hybrid_engine.sim_df is not None:
            try:
                c_sim = float(hybrid_engine.sim_df.loc[source_cuisine.title(), tc_title])
            except (KeyError, ValueError):
                c_sim = 0.0

        courses_dict = {}
        total_evaluated = 0
        # per_seed_by_course[cat][fav] = [(score, matched_list, cand_dict), ...]
        per_seed_by_course = {}

        for fav in favorite_dishes:
            # Pull all 10 Grok recommendations for this favorite → target
            sub = df[(df["dish_name"] == fav) & (df["target_cuisine"].str.lower() == tc_title.lower())].copy()
            sub = sub.sort_values("rank")
            total_evaluated += len(sub)

            # First pass: collect all candidates that pass filters (no limit yet)
            candidates = []
            for _, row in sub.iterrows():
                # Prefer authoritative metadata; fallback to Grok-reported values
                diet = row.get("meta_dietary_type")
                if pd.isna(diet) or not str(diet).strip():
                    diet = row.get("dietary_type", "")
                protein = row.get("meta_primary_protein")
                if pd.isna(protein) or not str(protein).strip():
                    protein = ""  # unknown
                cat = row.get("meta_category")
                if pd.isna(cat) or not str(cat).strip():
                    cat = row.get("course", "Main Course")

                if not dietary_ok(diet):
                    continue
                if not protein_ok(diet, protein):
                    continue

                # Gaussian-style score from confidence (0-99 → ~0-99)
                confidence = row.get("confidence", 0)
                try:
                    confidence_f = float(confidence)
                except (ValueError, TypeError):
                    confidence_f = 0.0
                match_score_raw = row.get("match_score", 0)
                try:
                    score_0_100 = float(match_score_raw) * 10.0  # 9.6 → 96.0
                except (ValueError, TypeError):
                    score_0_100 = confidence_f

                dish_entry = {
                    "dish_name": row["recommended_dish"],
                    "score": round(score_0_100, 1),
                    "category": str(cat),
                    "dietary": str(diet),
                    "protein": str(protein),
                    "description": "",
                    "why": str(row.get("why_it_matches", "")),
                    "matched_favorite": fav,
                    "matched_favorite_score": round(score_0_100, 1),
                    "course": str(cat),
                    "spice_level": "",
                    "ingredients": "",
                    "confidence": int(confidence_f),
                    "grok_rank": int(row.get("rank", 0) or 0),
                    "scoring": {
                        "cosine_sim": round(score_0_100, 1),
                        "cooking_method": 0,
                        "ingredient_match": 0,
                        "temperature_match": 0,
                        "ingredient_category": 0,
                        "dietary_compat": 100,
                    },
                }
                candidates.append(dish_entry)

            # Vegetarian preference: hard-filter to veg/vegan candidates from Grok's pool.
            # If THIS favorite's pool has zero veg (typical when seed is a meat dish),
            # fall back to top-scoring veg dishes for the target cuisine across ALL
            # Grok rows (any source seed) — this guarantees veg-only output.
            if prefer_veg:
                veg_only = [c for c in candidates if is_veg_dish(c.get("dietary", ""))]
                if veg_only:
                    pool = veg_only
                else:
                    # Cross-seed veg fallback for this target cuisine
                    cross = df[df["target_cuisine"].str.lower() == tc_title.lower()].copy()
                    # Use authoritative metadata when available
                    diet_series = cross["meta_dietary_type"].where(
                        cross["meta_dietary_type"].notna() & (cross["meta_dietary_type"].astype(str).str.strip() != ""),
                        cross["dietary_type"]
                    )
                    veg_mask = diet_series.astype(str).str.strip().str.lower().isin(["veg", "vegan", "vegetarian"])
                    veg_cross = cross[veg_mask].copy()
                    # Best score wins, dedupe by recommended_dish
                    veg_cross["score_sort"] = pd.to_numeric(veg_cross["match_score"], errors="coerce").fillna(0)
                    veg_cross = veg_cross.sort_values("score_sort", ascending=False)
                    veg_cross = veg_cross.drop_duplicates(subset=["recommended_dish"], keep="first")
                    pool = []
                    for _, vrow in veg_cross.head(20).iterrows():
                        d2 = vrow.get("meta_dietary_type") if pd.notna(vrow.get("meta_dietary_type")) and str(vrow.get("meta_dietary_type")).strip() else vrow.get("dietary_type", "")
                        cat2 = vrow.get("meta_category") if pd.notna(vrow.get("meta_category")) and str(vrow.get("meta_category")).strip() else vrow.get("course", "Main Course")
                        prot2 = vrow.get("meta_primary_protein") if pd.notna(vrow.get("meta_primary_protein")) and str(vrow.get("meta_primary_protein")).strip() else ""
                        try:
                            sc = float(vrow.get("match_score", 0)) * 10.0
                        except (ValueError, TypeError):
                            sc = 0.0
                        pool.append({
                            "dish_name":        vrow["recommended_dish"],
                            "score":            round(sc, 1),
                            "category":         str(cat2),
                            "dietary":          str(d2),
                            "protein":          str(prot2),
                            "description":      "",
                            "why":              str(vrow.get("why_it_matches", "")) + f" (veg fallback — meat seed '{fav}' had no veg matches in Grok cache)",
                            "matched_favorite": fav,
                            "matched_favorite_score": round(sc, 1),
                            "course":           str(cat2),
                            "spice_level":      "",
                            "ingredients":      "",
                            "confidence":       int(float(vrow.get("confidence", 0) or 0)),
                            "grok_rank":        int(vrow.get("rank", 0) or 0),
                            "scoring":          {"cosine_sim": round(sc, 1), "cooking_method": 0, "ingredient_match": 0,
                                                 "temperature_match": 0, "ingredient_category": 0, "dietary_compat": 100},
                        })
            else:
                pool = candidates

            # Pool is in priority order. Cap at ≤3 per seed, feed into
            # per_seed_by_course for downstream Option-C selection + dedup.
            for dish_entry in pool[:3]:
                cat = canonical_category(dish_entry["course"])
                dish_entry["category"] = cat
                dish_entry["course"]   = cat
                score = float(dish_entry.get("score", 0.0))
                matched = [dish_entry.get("why")] if dish_entry.get("why") else []
                per_seed_by_course.setdefault(cat, {}).setdefault(fav, []).append((score, matched, dish_entry))

        def _build_h2_entry(entry, cat):
            cand = entry["cand"]
            mfs = entry["matched_favorites"]
            top = mfs[0]
            display_score = float(top["score"])
            matched_favorites_display = [
                {"name": mf["name"], "score": float(mf["score"]), "facets": mf["matched"][:5]}
                for mf in mfs
            ]
            # Start from the original cand (already has all Hybrid 2.0 fields),
            # then overlay updated attribution + score.
            out = dict(cand)
            out["score"] = display_score
            out["category"] = cat
            out["course"] = cat
            out["matched_favorite"] = top["name"]
            out["matched_favorite_score"] = display_score
            out["matched_favorites"] = matched_favorites_display
            return out

        # ── Same-course priority (Tier 1 vs Tier 2) ──
        # Users expect appetizer picks to attribute to appetizer seeds first.
        # For each bucket: run Option-C on seeds whose course matches the
        # bucket (Tier 1). Tier 2 (cross-course seeds) is only consulted when
        # Tier 1's combined pool is below MIN_PER_COURSE — matches the same
        # threshold rule used in Hybrid 1.0 / 3.0.
        MIN_PER_COURSE = 3
        seed_course = {
            f["name"]: canonical_category(f["course"])
            for f in favorites_with_courses
        }

        for cat, per_seed in per_seed_by_course.items():
            same_seed  = {s: picks for s, picks in per_seed.items() if seed_course.get(s) == cat}
            cross_seed = {s: picks for s, picks in per_seed.items() if seed_course.get(s) != cat}

            # Tier 1: same-course
            t1_visible, t1_hidden = select_with_show_more(
                same_seed, max_visible=3, max_hidden=6, score_floor=0.0,
            )

            # Tier 2: only invoked if Tier 1's total pool is thin. Once Tier 1
            # fills >= MIN_PER_COURSE candidates, cross-course seeds stay out
            # of both visible and Show-More pools entirely.
            t2_visible, t2_hidden = [], []
            t1_total = len(t1_visible) + len(t1_hidden)
            if cross_seed and t1_total < MIN_PER_COURSE:
                need = max(0, 3 - len(t1_visible))
                t2_visible, t2_hidden = select_with_show_more(
                    cross_seed, max_visible=need, max_hidden=6, score_floor=0.0,
                )

            # Dedup across tiers by dish_name (same dish may appear in both)
            seen_names = {e["cand"].get("dish_name") for e in t1_visible}
            t2_visible = [e for e in t2_visible if e["cand"].get("dish_name") not in seen_names]
            seen_names |= {e["cand"].get("dish_name") for e in t2_visible}
            t1_hidden  = [e for e in t1_hidden  if e["cand"].get("dish_name") not in seen_names]
            seen_names |= {e["cand"].get("dish_name") for e in t1_hidden}
            t2_hidden  = [e for e in t2_hidden  if e["cand"].get("dish_name") not in seen_names]

            visible = t1_visible + t2_visible
            hidden  = t1_hidden  + t2_hidden

            entries = [_build_h2_entry(e, cat) for e in visible]
            entries += [_build_h2_entry(e, cat) for e in hidden]
            if entries:
                courses_dict[cat] = entries

        all_recommendations[tc] = {
            "cuisine_similarity": c_sim,
            "total_dishes_evaluated": total_evaluated,
            "courses": courses_dict,
            "visible_per_course": 3,
        }

    return jsonify({
        "engine": "hybrid-v2",
        "source_cuisine": source_cuisine,
        "favorites_used": favorite_dishes,
        "taste_preferences": taste_prefs,
        "favorites_with_courses": favorites_with_courses,
        "user_profile": user_profile,
        "recommendations": all_recommendations,
        "prefer_vegetarian_applied": prefer_veg,
        "auto_inferred_dietary": auto_inferred_dietary,
        "auto_inferred_proteins": auto_inferred_proteins,
    })


# ══════════════════════════════════════════════════════════════════════════════
#  HYBRID 3.0 — Facet-ontology overlap engine
# ══════════════════════════════════════════════════════════════════════════════
#
# Reads data/dish_facets.csv (one row per dish, ~19 facet fields generated by
# scripts/generate_dish_facets.py). At query time, scores each candidate dish
# in the target cuisine by counting facet overlaps with the seed favorite,
# weighted by importance. Honours all user filters (dietary, allowed_proteins,
# prefer_vegetarian) as hard pre-filters on the candidate pool — so no need
# for fallbacks: we always search the ENTIRE valid candidate set.

_facets_df = None

def _load_facets():
    """Load and cache dish_facets.csv joined with Metadata_Filters.csv."""
    global _facets_df
    if _facets_df is not None:
        return _facets_df

    facets_path = os.path.join(os.path.dirname(__file__), "data", "dish_facets.csv")
    meta_path   = os.path.join(os.path.dirname(__file__), "data", "Metadata_Filters.csv")
    if not os.path.exists(facets_path):
        return None

    import pandas as pd
    fdf = pd.read_csv(facets_path)
    fdf["dish_name"] = fdf["dish_name"].astype(str).str.strip()
    fdf["cuisine"]   = fdf["cuisine"].astype(str).str.strip()

    meta = pd.read_csv(meta_path)
    meta = meta[meta["dish_name"] != "dish_name"].copy()
    meta["dish_name"] = meta["dish_name"].astype(str).str.strip()
    meta["cuisine"]   = meta["cuisine"].astype(str).str.strip()

    enriched = fdf.merge(
        meta[["dish_name", "cuisine", "category", "dietary_type", "primary_protein"]],
        on=["dish_name", "cuisine"], how="left",
    )
    _facets_df = enriched
    return enriched


def _parse_list(val):
    """Parse a CSV cell into a list — handles JSON arrays and bare strings."""
    if val is None:
        return []
    s = str(val).strip()
    if not s or s.lower() in ("nan", "none"):
        return []
    if s.startswith("["):
        try:
            parsed = json.loads(s)
            return [str(x).strip().lower() for x in parsed if x]
        except (json.JSONDecodeError, ValueError):
            pass
    # Comma-separated fallback
    return [p.strip().lower() for p in s.split(",") if p.strip()]


def _parse_dict(val):
    """Parse a JSON-object cell. Returns {} on any failure."""
    if val is None:
        return {}
    s = str(val).strip()
    if not s or s.lower() in ("nan", "none"):
        return {}
    try:
        parsed = json.loads(s)
        return parsed if isinstance(parsed, dict) else {}
    except (json.JSONDecodeError, ValueError):
        return {}


def _facet_overlap_score(seed_row, cand_row, dietary_pref):
    """Compute facet-overlap score between seed and candidate.

    Returns: (score: float, matched_facets: list[str])
    """
    score = 0.0
    matched = []

    # ── Cooking methods (heavy weight) ──
    seed_cm = set(_parse_list(seed_row.get("cooking_methods")))
    cand_cm = set(_parse_list(cand_row.get("cooking_methods")))
    cm_overlap = seed_cm & cand_cm
    if cm_overlap:
        score += 3 * len(cm_overlap)
        matched.append(f"cooking:{','.join(sorted(cm_overlap))}")

    # ── Flavor anchors (heavy) ──
    seed_fa = set(_parse_list(seed_row.get("flavor_anchors")))
    cand_fa = set(_parse_list(cand_row.get("flavor_anchors")))
    fa_overlap = seed_fa & cand_fa
    if fa_overlap:
        score += 3 * len(fa_overlap)
        matched.append(f"flavor:{','.join(sorted(fa_overlap))}")

    # ── Texture profile ──
    seed_tx = set(_parse_list(seed_row.get("texture_profile")))
    cand_tx = set(_parse_list(cand_row.get("texture_profile")))
    tx_overlap = seed_tx & cand_tx
    if tx_overlap:
        score += 2 * len(tx_overlap)
        matched.append(f"texture:{','.join(sorted(tx_overlap))}")

    # ── Single-value matches ──
    for facet, weight in [
        ("marinade_family", 2),
        ("course_role", 2),
        ("heat_intensity", 2),
        ("spice_lineage", 2),
        ("fat_character", 2),
        ("aromatic_signature", 1),
        ("portion_format", 1),
        ("richness", 1),
        ("preparation_complexity", 1),
        ("dominant_color", 1),
        ("visual_appeal", 1),
        ("sauce_role", 1),
    ]:
        sv = str(seed_row.get(facet, "")).strip().lower()
        cv = str(cand_row.get(facet, "")).strip().lower()
        if sv and cv and sv == cv and sv != "none":
            score += weight
            matched.append(f"{facet}:{sv}")

    # ── Cultural kin (lightweight) ──
    seed_ck = set(_parse_list(seed_row.get("cultural_kin")))
    cand_ck = set(_parse_list(cand_row.get("cultural_kin")))
    ck_overlap = seed_ck & cand_ck
    if ck_overlap:
        score += 1 * len(ck_overlap)
        matched.append(f"cultural-kin:{','.join(sorted(ck_overlap))}")

    # ── Meal occasion ──
    seed_mo = set(_parse_list(seed_row.get("meal_occasion")))
    cand_mo = set(_parse_list(cand_row.get("meal_occasion")))
    mo_overlap = seed_mo & cand_mo
    if mo_overlap:
        score += 1 * len(mo_overlap)
        matched.append(f"occasion:{','.join(sorted(mo_overlap))}")

    # ── Substitution-class boost (the killer field) ──
    # If seed explicitly names this candidate (or its name-substring) under the
    # user's dietary class, give a heavy bonus.
    sub_class = _parse_dict(seed_row.get("substitution_class"))
    cand_name_low = str(cand_row.get("dish_name", "")).strip().lower()
    sub_keys_to_check = ["any"]
    if dietary_pref in ("veg", "vegetarian", "prefer-veg"):
        sub_keys_to_check = ["veg", "vegan", "any"]
    elif dietary_pref == "vegan":
        sub_keys_to_check = ["vegan", "any"]
    elif dietary_pref == "pescatarian":
        sub_keys_to_check = ["fish", "veg", "vegan", "any"]

    for k in sub_keys_to_check:
        for sub_hint in sub_class.get(k, []) or []:
            hint_low = str(sub_hint).strip().lower().replace("-", " ")
            if hint_low and (hint_low in cand_name_low or
                             any(tok in cand_name_low for tok in hint_low.split() if len(tok) > 3)):
                score += 5
                matched.append(f"named-substitute({k}):{sub_hint}")
                break  # one bonus per dietary class

    # ── Serving temperature: penalty on mismatch ──
    st_seed = str(seed_row.get("serving_temperature", "")).strip().lower()
    st_cand = str(cand_row.get("serving_temperature", "")).strip().lower()
    if st_seed and st_cand and st_seed != st_cand:
        # cold↔hot is a bigger mismatch than warm↔hot
        if {st_seed, st_cand} in ({"cold", "hot"}, {"hot", "cold"}):
            score -= 4
            matched.append(f"temp-mismatch:{st_seed}→{st_cand}")
        else:
            score -= 1

    # ── Protein affinity (new) ──
    # Facets describe how a dish is made/eaten; they don't carry protein signal.
    # Without this bonus, a chicken-curry seed scores a Greek chickpea stew nearly
    # as high as a Greek chicken stew because stew-ness dominates the shared
    # facets. Reward same-protein and same-protein-group matches so real chicken
    # picks win ties within the candidate pool.
    sp = str(seed_row.get("primary_protein", "") or "").strip()
    cp = str(cand_row.get("primary_protein", "") or "").strip()
    if sp and cp and sp.lower() not in ("nan", "none") and cp.lower() not in ("nan", "none"):
        if sp == cp:
            score += 4
            matched.append(f"protein-match:{sp}")
        else:
            try:
                from hybrid_engine import PROTEIN_GROUPS
                for group_vals in PROTEIN_GROUPS.values():
                    if sp in group_vals and cp in group_vals:
                        score += 2
                        matched.append(f"protein-kin:{sp}↔{cp}")
                        break
            except Exception:
                pass

    return score, matched


@app.route("/api/recommend-hybrid-v3", methods=["POST"])
@login_required
def recommend_hybrid_v3():
    """Hybrid 3.0 — Facet-ontology overlap engine.

    For each (favorite, target_cuisine):
      1. Look up seed dish in dish_facets.csv
      2. Pull all target-cuisine candidates that satisfy user filters (hard)
      3. Score each by facet overlap with seed
      4. Return top 3 with structured "why" listing matched facets
    """
    fdf = _load_facets()
    if fdf is None:
        return jsonify({"error": "Hybrid 3.0 cache not available. Run scripts/generate_dish_facets.py first."}), 503

    data = request.json
    source_cuisine  = data.get("source_cuisine", "")
    favorite_dishes = data.get("favorite_dishes", [])
    target_cuisines = data.get("target_cuisines", [])
    taste_prefs     = data.get("taste_preferences", {})
    dietary         = str(taste_prefs.get("dietary", "")).strip().lower()
    allowed_proteins = taste_prefs.get("allowed_proteins", "any")

    if not favorite_dishes:
        return jsonify({"error": "No favorite dishes provided."})

    # Auto-infer veg/vegan from favorites when dietary is "any" or unset.
    dietary, auto_inferred = infer_effective_dietary(dietary, favorite_dishes)
    auto_inferred_dietary  = dietary if auto_inferred else None

    # Auto-narrow protein whitelist from 'any' based on observed favorites.
    allowed_proteins, proteins_auto_inferred = infer_effective_proteins(
        allowed_proteins, dietary, favorite_dishes
    )
    auto_inferred_proteins = allowed_proteins if proteins_auto_inferred else None

    prefer_veg = bool(taste_prefs.get("prefer_vegetarian")) or dietary in ("veg", "vegan", "vegetarian")
    print(f"[hybrid-v3] taste_prefs={taste_prefs} → prefer_veg={prefer_veg} auto_inferred={auto_inferred} proteins_auto_inferred={proteins_auto_inferred}", flush=True)

    # ── Protein whitelist ──
    from hybrid_engine import PROTEIN_GROUPS
    allowed_protein_values = None
    if allowed_proteins != "any" and isinstance(allowed_proteins, list):
        allowed_protein_values = set()
        for gk in allowed_proteins:
            if gk in PROTEIN_GROUPS:
                allowed_protein_values |= PROTEIN_GROUPS[gk]

    def is_veg(diet_val):
        d = str(diet_val or "").strip().lower()
        return d in ("veg", "vegan", "vegetarian")

    def passes_dietary(diet_val):
        d = str(diet_val or "").strip().lower()
        if prefer_veg:
            return d in ("veg", "vegan", "vegetarian")
        if dietary == "vegan":
            return d == "vegan"
        if dietary in ("veg", "vegetarian"):
            return d in ("veg", "vegan", "vegetarian")
        if dietary == "pescatarian":
            return d in ("veg", "vegan", "vegetarian", "pescatarian")
        return True

    def passes_protein(diet_val, protein_val):
        # "Any / No Preference" → admit everything
        if allowed_protein_values is None:
            return True
        # The allowed-proteins list is a MEAT whitelist. Veg/vegan dishes
        # don't carry meat, so the list doesn't apply to them — admit. This
        # also lets dessert, salad, and side-dish candidates (often veg, with
        # proteins like Milk/Walnuts/Semolina) reach the pool for veg seeds
        # like Gajar Ka Halwa without being blocked by the chicken whitelist.
        # Leakage of veg main-courses into a chicken-seed query is prevented
        # downstream by the category gate and the protein-affinity bonus.
        if is_veg(diet_val):
            return True
        p = str(protein_val or "").strip()
        if not p or p.lower() in ("nan", "none", ""):
            return True  # unknown protein → admit; scoring will sort it out
        return p in allowed_protein_values

    # ── Favorites with courses (display) ──
    favorites_with_courses = []
    for fav in favorite_dishes:
        info = hybrid_engine.get_dish_info(fav) if hybrid_engine else None
        course = info["category"] if info else "—"
        favorites_with_courses.append({"name": fav, "course": course})

    # ── User flavor profile (display only — reused from seed flavor avg) ──
    user_profile = {}
    if hybrid_engine:
        from hybrid_engine import FLAVOR_DIMS as HF_DIMS
        fav_vectors = []
        for fav in favorite_dishes:
            info = hybrid_engine.get_dish_info(fav)
            if info and "flavor" in info:
                fav_vectors.append(info["flavor"])
        if fav_vectors:
            for dim in HF_DIMS:
                vals = [v[dim] for v in fav_vectors if dim in v]
                user_profile[dim] = round(sum(vals) / len(vals), 2) if vals else 0.0

    import pandas as pd

    all_recommendations = {}

    for tc in target_cuisines:
        tc_title = tc.strip().title()

        c_sim = 0.0
        if hybrid_engine and hybrid_engine.sim_df is not None:
            try:
                c_sim = float(hybrid_engine.sim_df.loc[source_cuisine.title(), tc_title])
            except (KeyError, ValueError):
                c_sim = 0.0

        # Candidate pool: target cuisine, hard-filter by dietary + protein
        pool = fdf[fdf["cuisine"].str.lower() == tc_title.lower()].copy()
        if pool.empty:
            all_recommendations[tc] = {"cuisine_similarity": c_sim, "courses": {}, "total_dishes_evaluated": 0}
            continue

        keep_mask = pool.apply(
            lambda r: passes_dietary(r.get("dietary_type", "")) and
                      passes_protein(r.get("dietary_type", ""), r.get("primary_protein", "")),
            axis=1,
        )
        pool = pool[keep_mask]

        total_eval = len(pool)
        courses_dict = {}

        def _norm_cat(c):
            """Normalise category strings so 'Main' and 'Main Course' compare equal."""
            c = str(c or "").strip().lower()
            if c in ("main", "main course", "mains"):
                return "main course"
            return c

        # Delegate to the module-level canonicalizer so every endpoint agrees
        # on display labels (see canonical_category above).
        _display_cat = canonical_category

        # ── Phase 1: collect Tier 1 (same-course) + Tier 2 (cross-course held back) ──
        # Tier 1: each seed contributes its top-3 SAME-COURSE matches. These go
        # straight into per_seed_by_course[cat][seed].
        # Tier 2: each seed also keeps its top-6 cross-course matches stashed in
        # tier2_by_course. They only get merged into per_seed_by_course later if
        # the target bucket is thinner than MIN_PER_COURSE — preserves "appetizer
        # seeds own the appetizer bucket" while letting sparse buckets (e.g. no
        # salad favorites) fill from cross-course overflow rather than stay empty.
        MIN_PER_COURSE = 3
        per_seed_by_course = {}
        tier2_by_course    = {}
        for fav in favorite_dishes:
            seed_rows = fdf[fdf["dish_name"] == fav]
            if seed_rows.empty:
                continue
            seed = seed_rows.iloc[0].to_dict()
            seed_cat = _norm_cat(seed.get("category"))

            scored_t1 = []   # same-course
            scored_t2 = []   # cross-course (held back)
            for _, cand in pool.iterrows():
                if cand["dish_name"] == fav and str(cand["cuisine"]).lower() == source_cuisine.lower():
                    continue  # skip self
                s, matched = _facet_overlap_score(seed, cand, "veg" if prefer_veg else dietary)
                if s <= 0:
                    continue
                cand_d = cand.to_dict()
                if seed_cat and _norm_cat(cand.get("category")) != seed_cat:
                    scored_t2.append((s, matched, cand_d))
                else:
                    scored_t1.append((s, matched, cand_d))

            scored_t1.sort(key=lambda x: x[0], reverse=True)
            scored_t2.sort(key=lambda x: x[0], reverse=True)

            for s, matched, cand in scored_t1[:3]:
                cat = _display_cat(cand.get("category"))
                per_seed_by_course.setdefault(cat, {}).setdefault(fav, []).append((s, matched, cand))
            for s, matched, cand in scored_t2[:6]:
                cat = _display_cat(cand.get("category"))
                tier2_by_course.setdefault(cat, {}).setdefault(fav, []).append((s, matched, cand))

        # Tier 2 top-up: only merge when same-course bucket is below threshold.
        for cat, t2_seeds in tier2_by_course.items():
            existing = per_seed_by_course.get(cat, {})
            total_existing = sum(len(v) for v in existing.values())
            if total_existing >= MIN_PER_COURSE:
                continue
            for seed, picks in t2_seeds.items():
                per_seed_by_course.setdefault(cat, {}).setdefault(seed, []).extend(picks)

        # ── Phase 2: dedup + Option-C visible slice + hidden pool ──
        def _build_dish_entry(entry, cat):
            cand = entry["cand"]
            mfs = entry["matched_favorites"]
            top = mfs[0]
            # Score scaling: facet score → 0-100 display. Typical strong matches
            # land around 15-25; cap at 100.
            display_score = min(100, round(top["score"] * 4, 1))
            # Human-readable reason: strip schema prefixes, dedupe values.
            why_text = (
                humanize_facet_reasons_v2(top["matched"])
                or f"Facet overlap score: {top['score']:.1f}"
            )
            # Multi-favorite attribution array — each seed's similarity shown
            # as a display percentage, same scaling as `score`.
            matched_favorites_display = [
                {
                    "name":  mf["name"],
                    "score": min(100, round(mf["score"] * 4, 1)),
                    "facets": mf["matched"][:5],
                    # Human-readable phrase for this specific seed
                    "why":   humanize_facet_reasons_v2(mf["matched"]),
                }
                for mf in mfs
            ]
            return {
                "dish_name":        str(cand["dish_name"]),
                "score":            display_score,
                "category":         cat,
                "dietary":          str(cand.get("dietary_type", "")),
                "protein":          str(cand.get("primary_protein", "") or ""),
                "description":      "",
                "why":              why_text,
                # Backward-compat single fields (top matching seed)
                "matched_favorite":       top["name"],
                "matched_favorite_score": display_score,
                # New: full list of seeds that ranked this dish
                "matched_favorites":      matched_favorites_display,
                "course":           cat,
                "spice_level":      "",
                "ingredients":      "",
                "facet_overlap":    round(top["score"], 2),
                "facet_matches":    top["matched"],
                "scoring": {
                    "cosine_sim":          display_score,
                    "cooking_method":      0,
                    "ingredient_match":    0,
                    "temperature_match":   0,
                    "ingredient_category": 0,
                    "dietary_compat":      100,
                },
            }

        for cat, per_seed in per_seed_by_course.items():
            visible_entries, hidden_entries = select_with_show_more(
                per_seed, max_visible=3, max_hidden=6, score_floor=5.0,
            )
            # Flat list: first N are visible defaults, rest are revealed via "Show more".
            entries = [_build_dish_entry(e, cat) for e in visible_entries]
            entries += [_build_dish_entry(e, cat) for e in hidden_entries]
            if entries:
                courses_dict[cat] = entries

        all_recommendations[tc] = {
            "cuisine_similarity": c_sim,
            "total_dishes_evaluated": total_eval,
            "courses": courses_dict,
            "visible_per_course": 3,  # first N entries per course shown by default; rest behind "Show more"
        }

    return jsonify({
        "engine": "hybrid-v3",
        "source_cuisine": source_cuisine,
        "favorites_used": favorite_dishes,
        "taste_preferences": taste_prefs,
        "favorites_with_courses": favorites_with_courses,
        "user_profile": user_profile,
        "recommendations": all_recommendations,
        "prefer_vegetarian_applied": prefer_veg,
        "auto_inferred_dietary": auto_inferred_dietary,
        "auto_inferred_proteins": auto_inferred_proteins,
    })


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5001))
    app.run(host="0.0.0.0", port=port, debug=True)
