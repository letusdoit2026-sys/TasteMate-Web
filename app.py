import os
from dotenv import load_dotenv
load_dotenv()  # Load .env file before any os.environ.get() calls

import json
import uuid
import sqlite3
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

# ── App setup ──
app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "")
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "data", "tastemate.db")

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
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
    return g.db


@app.teardown_appcontext
def close_db(exception):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    db = sqlite3.connect(DB_PATH)
    db.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id TEXT PRIMARY KEY,
            username TEXT UNIQUE NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            security_question TEXT,
            security_answer_hash TEXT,
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS audit_logs (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            username TEXT NOT NULL,
            action TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            source_cuisine TEXT,
            favorite_dishes TEXT,
            taste_preferences TEXT,
            target_cuisines TEXT,
            recommendations TEXT,
            scoring_details TEXT,
            user_profile_vector TEXT,
            FOREIGN KEY (user_id) REFERENCES users(id)
        );
        CREATE INDEX IF NOT EXISTS idx_audit_user ON audit_logs(user_id);
        CREATE INDEX IF NOT EXISTS idx_audit_ts ON audit_logs(timestamp);
    """)
    db.commit()
    db.close()


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
    row = db.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    if row:
        return User(row["id"], row["username"], row["email"])
    return None


# ══════════════════════════════════════════════════════════════════════════════
#  AUDIT LOGGING
# ══════════════════════════════════════════════════════════════════════════════

def log_audit(user_id, username, action, **kwargs):
    db = get_db()
    db.execute(
        """INSERT INTO audit_logs
           (id, user_id, username, action, timestamp,
            source_cuisine, favorite_dishes, taste_preferences,
            target_cuisines, recommendations, scoring_details, user_profile_vector)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            str(uuid.uuid4()),
            user_id,
            username,
            action,
            datetime.datetime.utcnow().isoformat(),
            kwargs.get("source_cuisine"),
            json.dumps(kwargs.get("favorite_dishes")) if kwargs.get("favorite_dishes") else None,
            json.dumps(kwargs.get("taste_preferences")) if kwargs.get("taste_preferences") else None,
            json.dumps(kwargs.get("target_cuisines")) if kwargs.get("target_cuisines") else None,
            json.dumps(kwargs.get("recommendations")) if kwargs.get("recommendations") else None,
            json.dumps(kwargs.get("scoring_details")) if kwargs.get("scoring_details") else None,
            json.dumps(kwargs.get("user_profile_vector")) if kwargs.get("user_profile_vector") else None,
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
    row = db.execute("SELECT security_question FROM users WHERE email = ?", (email,)).fetchone()
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
    row = db.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
    if not row:
        return jsonify({"error": "No account found with that email"}), 404

    # Verify security answer
    if not row["security_answer_hash"] or not bcrypt.check_password_hash(row["security_answer_hash"], answer):
        return jsonify({"error": "Incorrect security answer"}), 401

    # Reset password to "tastemate"
    new_hash = bcrypt.generate_password_hash("tastemate").decode("utf-8")
    db.execute("UPDATE users SET password_hash = ? WHERE email = ?", (new_hash, email))
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
    existing = db.execute("SELECT id FROM users WHERE username = ? OR email = ?", (username, email)).fetchone()
    if existing:
        return jsonify({"error": "Username or email already exists"}), 400

    user_id = str(uuid.uuid4())
    pw_hash = bcrypt.generate_password_hash("tastemate").decode("utf-8")
    answer_hash = bcrypt.generate_password_hash(security_answer).decode("utf-8")
    db.execute(
        """INSERT INTO users (id, username, email, password_hash, security_question, security_answer_hash, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (user_id, username, email, pw_hash, security_question, answer_hash, datetime.datetime.utcnow().isoformat()),
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
    row = db.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
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
            cat = str(row["category"])
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
        if dietary_pref == "any":
            fav_dietaries = [f.get("dietary_type", "") for f in fav_data]
            all_veg = all(_is_veg(d) for d in fav_dietaries)
            all_vegan = all("vegan" in d for d in fav_dietaries)
            if all_vegan:
                dietary_pref = "vegan"
            elif all_veg:
                dietary_pref = "veg"

        if dietary_pref == "veg":
            tdf = tdf[tdf["dietary_type"].str.lower().isin(["veg", "vegan"])]
        elif dietary_pref == "vegan":
            tdf = tdf[tdf["dietary_type"].str.lower() == "vegan"]
        elif dietary_pref == "pescatarian":
            tdf = tdf[tdf["dietary_type"].str.lower().isin(["veg", "vegan", "pescatarian"])]

        # Protein filter — exclude meats the user doesn't eat
        allowed_proteins = taste_prefs.get("allowed_proteins", "any")
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

            all_scores.append({
                "dish_name": row["dish_name"],
                "score": round(final * 100, 1),
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

        # ── Group by course, pick top ITEMS_PER_COURSE per course ──
        # Only show course sections where user has at least one favorite
        # Strict same-course matching: Main Course → Main Course only
        fav_course_set = set(f.get("course", "") for f in fav_data)
        # Appetizer↔Salad are siblings — if user has either, show both
        show_courses = set(fav_course_set)
        if "Appetizer" in show_courses or "Salad" in show_courses:
            show_courses |= {"Appetizer", "Salad"}

        courses_result = {}
        for course_name in COURSE_ORDER:
            if course_name not in show_courses:
                continue
            course_dishes = [d for d in all_scores if d["course"] == course_name]
            if not course_dishes:
                continue
            top_dishes = course_dishes[:ITEMS_PER_COURSE]
            # Add similar alternatives
            for dish in top_dishes:
                dish_vec = np.array([dish["flavor"].get(FLAVOR_LABELS.get(c, c), 0) for c in FLAVOR_COLS])
                dish["similar_alternatives"] = find_similar_alternatives(
                    dish["dish_name"], dish_vec, all_scores
                )
            courses_result[course_name] = top_dishes

        recommendations[tc_title] = {
            "cuisine_similarity": round(c_sim, 2),
            "total_dishes_evaluated": len(all_scores),
            "courses": courses_result,
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
           WHERE user_id = ? AND action = 'RECOMMENDATION'
           ORDER BY timestamp DESC LIMIT 20""",
        (current_user.id,),
    ).fetchall()
    results = []
    for row in rows:
        results.append({
            "id": row["id"],
            "timestamp": row["timestamp"],
            "source_cuisine": row["source_cuisine"],
            "favorite_dishes": json.loads(row["favorite_dishes"]) if row["favorite_dishes"] else [],
            "taste_preferences": json.loads(row["taste_preferences"]) if row["taste_preferences"] else {},
            "target_cuisines": json.loads(row["target_cuisines"]) if row["target_cuisines"] else [],
            "recommendations": json.loads(row["recommendations"]) if row["recommendations"] else {},
            "user_profile_vector": json.loads(row["user_profile_vector"]) if row["user_profile_vector"] else {},
        })
    return jsonify(results)


@app.route("/api/audit/detail/<log_id>")
@login_required
def audit_detail(log_id):
    db = get_db()
    row = db.execute("SELECT * FROM audit_logs WHERE id = ? AND user_id = ?", (log_id, current_user.id)).fetchone()
    if not row:
        return jsonify({"error": "Not found"}), 404
    return jsonify({
        "id": row["id"],
        "timestamp": row["timestamp"],
        "source_cuisine": row["source_cuisine"],
        "favorite_dishes": json.loads(row["favorite_dishes"]) if row["favorite_dishes"] else [],
        "taste_preferences": json.loads(row["taste_preferences"]) if row["taste_preferences"] else {},
        "target_cuisines": json.loads(row["target_cuisines"]) if row["target_cuisines"] else [],
        "recommendations": json.loads(row["recommendations"]) if row["recommendations"] else {},
        "scoring_details": json.loads(row["scoring_details"]) if row["scoring_details"] else {},
        "user_profile_vector": json.loads(row["user_profile_vector"]) if row["user_profile_vector"] else {},
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

        courses_dict = {}
        total_evaluated = 0

        for fav in favorite_dishes:
            result = hybrid_engine.get_recommendations(
                seed_dish=fav,
                user_preferences={"dietary": dietary, "target_cuisine": tc, "discovery_mode": True, "allowed_proteins": allowed_proteins},
            )
            if isinstance(result, dict) and "recommendations" in result:
                total_evaluated += result.get("pipeline_stats", {}).get("after_hard_filter", 0)
                for rec in result["recommendations"]:
                    cat = rec.get("category", "Main Course")
                    dish_entry = {
                        "dish_name": rec["dish_name"],
                        "score": rec["match_score"],
                        "category": cat,
                        "dietary": rec.get("dietary_type", ""),
                        "protein": rec.get("primary_protein", ""),
                        "description": rec.get("context_string", ""),
                        "why": rec.get("match_reason", f"Flavor distance: {rec['flavor_distance']:.3f}"),
                        "matched_favorite": fav,
                        "matched_favorite_score": rec["match_score"],
                        "course": cat,
                        "spice_level": "",
                        "ingredients": "",
                        "flavor_distance": rec["flavor_distance"],
                        "flavor": rec.get("flavor", {}),
                        "seed_flavor": rec.get("seed_flavor", {}),
                        "scoring": {
                            "cosine_sim": rec["match_score"],
                            "cooking_method": 0,
                            "ingredient_match": 0,
                            "temperature_match": 100 if rec.get("temp") else 0,
                            "ingredient_category": 0,
                            "dietary_compat": 100,
                        },
                    }
                    if cat not in courses_dict:
                        courses_dict[cat] = []
                    courses_dict[cat].append(dish_entry)

        # Deduplicate and sort within each course
        for cat in courses_dict:
            seen = set()
            unique = []
            for d in sorted(courses_dict[cat], key=lambda x: x["score"], reverse=True):
                if d["dish_name"] not in seen:
                    seen.add(d["dish_name"])
                    unique.append(d)
            courses_dict[cat] = unique

        all_recommendations[tc] = {
            "cuisine_similarity": c_sim,
            "total_dishes_evaluated": total_evaluated,
            "courses": courses_dict,
        }

    return jsonify({
        "engine": "hybrid",
        "source_cuisine": source_cuisine,
        "favorites_used": favorite_dishes,
        "taste_preferences": taste_prefs,
        "favorites_with_courses": favorites_with_courses,
        "user_profile": user_profile,
        "recommendations": all_recommendations,
    })


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5001))
    app.run(host="0.0.0.0", port=port, debug=True)
