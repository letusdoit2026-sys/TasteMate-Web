import os
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

# ── App setup ──
app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "tastemate-secret-key-change-in-prod-2024")
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "data", "tastemate.db")

bcrypt = Bcrypt(app)
login_manager = LoginManager(app)
login_manager.login_view = "login_page"

# ── Load food data at startup ──
FLAVOR_COLS = [
    "sweet_score", "salt_score", "sour_score", "bitter_score", "umami_score",
    "spicy_score", "rich_fat_score", "astringency_score", "viscosity_score",
    "crunchy_score", "chewy_score", "aromatic_score", "funk_score",
]

FLAVOR_LABELS = {
    "sweet_score": "Sweet", "salt_score": "Salty", "sour_score": "Sour",
    "bitter_score": "Bitter", "umami_score": "Umami", "spicy_score": "Spicy",
    "rich_fat_score": "Rich/Fat", "astringency_score": "Astringent",
    "viscosity_score": "Thick/Saucy", "crunchy_score": "Crunchy",
    "chewy_score": "Chewy", "aromatic_score": "Aromatic", "funk_score": "Funky",
}

# Course grouping: map raw course values to display categories
COURSE_MAP = {
    "Main": "Entrees",
    "Appetizer": "Appetizers",
    "Soup": "Soups",
    "Side": "Sides & Breads",
    "Salad": "Salads",
    "Dessert": "Desserts",
    "Snack": "Snacks & Street Food",
    "Drink": "Drinks",
}
COURSE_ORDER = ["Appetizers", "Soups", "Salads", "Entrees", "Sides & Breads", "Snacks & Street Food", "Desserts", "Drinks"]
ITEMS_PER_COURSE = 4

df = pd.read_csv(os.path.join(BASE_DIR, "data", "dishes.csv"))
for col in FLAVOR_COLS:
    df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
df["dish_importance_score"] = pd.to_numeric(df["dish_importance_score"], errors="coerce").fillna(3.0)

# Normalize course column
df["course_group"] = df["course"].map(COURSE_MAP).fillna("Entrees")

sim_df = pd.read_csv(os.path.join(BASE_DIR, "data", "similarity.csv"), index_col=0)
CUISINES = sorted(sim_df.columns.tolist())


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
    na, nb = np.linalg.norm(a), np.linalg.norm(b)
    if na == 0 or nb == 0:
        return 0.0
    return float(np.dot(a, b) / (na * nb))


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


def find_closest_favorite(dish_vec, dish_ingredients_str, fav_data):
    """Find which user favorite is most similar to this recommended dish."""
    best_name = None
    best_score = -1
    dish_ing_words = set(
        w.strip().lower()
        for item in str(dish_ingredients_str).split(",")
        for w in item.strip().split()
        if len(w.strip()) > 2
    )
    for fav in fav_data:
        # Flavor cosine
        cs = cosine_sim(dish_vec, fav["vector"])
        # Ingredient overlap
        fav_ing_words = set(
            w.strip().lower()
            for item in str(fav["ingredients"]).split(",")
            for w in item.strip().split()
            if len(w.strip()) > 2
        )
        ing_overlap = len(dish_ing_words & fav_ing_words) / max(len(dish_ing_words | fav_ing_words), 1)
        combined = 0.6 * cs + 0.4 * ing_overlap
        if combined > best_score:
            best_score = combined
            best_name = fav["name"]
    return best_name, round(best_score * 100, 1)


def build_detailed_explanation(user_vec, dish_vec, dish_row, user_prefs, c_sim,
                                scores_breakdown, matched_fav_name, ingredient_score):
    """Build a rich explanation of why this dish was recommended."""
    close_dims = []
    diff_dims = []
    for i, col in enumerate(FLAVOR_COLS):
        label = FLAVOR_LABELS.get(col, col)
        uv, dv = user_vec[i], dish_vec[i]
        diff = abs(uv - dv)
        if uv > 2.0 or dv > 2.0:
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

    # 2. Flavor match
    top_matches = close_dims[:3]
    match_str = ", ".join([f"{label} (you: {uv:.0f}, dish: {dv:.0f})" for _, label, uv, dv in top_matches])
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
        if spice_pref == "mild" and dish_spice <= 3:
            parts.append("Mild spice — matches your preference")
        elif spice_pref == "hot" and dish_spice >= 6:
            parts.append(f"Spicy ({dish_spice:.0f}/10) — matches your love for heat!")
        elif spice_pref == "medium" and 3 <= dish_spice <= 6:
            parts.append(f"Medium spice ({dish_spice:.0f}/10) — your sweet spot")

        if user_prefs.get("likes_creamy") and float(dish_row.get("rich_fat_score", 0)) >= 5:
            parts.append(f"Rich & creamy ({float(dish_row.get('rich_fat_score', 0)):.0f}/10)")
        if user_prefs.get("likes_aromatic") and float(dish_row.get("aromatic_score", 0)) >= 5:
            parts.append(f"Highly aromatic ({float(dish_row.get('aromatic_score', 0)):.0f}/10)")

    # 5. Key differences
    if diff_dims:
        top_diff = diff_dims[0]
        if top_diff[0] > 3:
            direction = "higher" if top_diff[3] > top_diff[2] else "lower"
            parts.append(f"Note: {top_diff[1]} is {direction} than usual (dish={top_diff[3]:.0f} vs you={top_diff[2]:.0f})")

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
                        if abs(dish_vec[i] - other_vec[i]) > 2
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

    if not email or not answer or not new_password:
        return jsonify({"error": "All fields are required"}), 400
    if len(new_password) < 6:
        return jsonify({"error": "New password must be at least 6 characters"}), 400

    db = get_db()
    row = db.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
    if not row:
        return jsonify({"error": "No account found with that email"}), 404

    # Verify security answer
    if not row["security_answer_hash"] or not bcrypt.check_password_hash(row["security_answer_hash"], answer):
        return jsonify({"error": "Incorrect security answer"}), 401

    # Reset password
    new_hash = bcrypt.generate_password_hash(new_password).decode("utf-8")
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

    if not username or not email or not password:
        return jsonify({"error": "All fields are required"}), 400
    if len(password) < 6:
        return jsonify({"error": "Password must be at least 6 characters"}), 400
    if not security_question or not security_answer:
        return jsonify({"error": "Security question and answer are required for password recovery"}), 400

    db = get_db()
    existing = db.execute("SELECT id FROM users WHERE username = ? OR email = ?", (username, email)).fetchone()
    if existing:
        return jsonify({"error": "Username or email already exists"}), 400

    user_id = str(uuid.uuid4())
    pw_hash = bcrypt.generate_password_hash(password).decode("utf-8")
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


@app.route("/api/auth/change-password", methods=["POST"])
@login_required
def api_change_password():
    data = request.json
    current_pw = data.get("current_password", "")
    new_pw = data.get("new_password", "")

    if not current_pw or not new_pw:
        return jsonify({"error": "Both current and new password are required"}), 400
    if len(new_pw) < 6:
        return jsonify({"error": "New password must be at least 6 characters"}), 400

    db = get_db()
    row = db.execute("SELECT * FROM users WHERE id = ?", (current_user.id,)).fetchone()
    if not row or not bcrypt.check_password_hash(row["password_hash"], current_pw):
        return jsonify({"error": "Current password is incorrect"}), 401

    new_hash = bcrypt.generate_password_hash(new_pw).decode("utf-8")
    db.execute("UPDATE users SET password_hash = ? WHERE id = ?", (new_hash, current_user.id))
    db.commit()

    log_audit(current_user.id, current_user.username, "PASSWORD_CHANGE")
    return jsonify({"success": True})


# ══════════════════════════════════════════════════════════════════════════════
#  ROUTES — Data & Recommendations
# ══════════════════════════════════════════════════════════════════════════════

@app.route("/api/cuisines")
@login_required
def get_cuisines():
    return jsonify(CUISINES)


@app.route("/api/dishes")
@login_required
def get_dishes():
    """Return dishes grouped by course for the favorites selection screen."""
    cuisine = request.args.get("cuisine", "")
    cdf = df[df["cuisine_name"].str.lower() == cuisine.lower()]
    cdf = cdf.sort_values("dish_importance_score", ascending=False)

    grouped = {}
    for _, row in cdf.iterrows():
        course = row["course_group"]
        if course not in grouped:
            grouped[course] = []
        grouped[course].append({
            "name": row["dish_name"],
            "category": str(row.get("sub_category", "")),
            "dietary": str(row.get("dietary_type", "")),
            "protein": str(row.get("primary_protein", "")),
            "importance": float(row["dish_importance_score"]),
            "course": course,
        })

    # Return in defined order
    result = []
    for course_name in COURSE_ORDER:
        if course_name in grouped:
            result.append({
                "course": course_name,
                "dishes": grouped[course_name],
            })
    # Any remaining courses not in COURSE_ORDER
    for course_name, dishes in grouped.items():
        if course_name not in COURSE_ORDER:
            result.append({"course": course_name, "dishes": dishes})

    return jsonify(result)


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
        })

    # Apply taste preference adjustments
    if taste_prefs.get("spice_level") == "mild":
        user_profile[FLAVOR_COLS.index("spicy_score")] *= 0.5
    elif taste_prefs.get("spice_level") == "hot":
        user_profile[FLAVOR_COLS.index("spicy_score")] = max(user_profile[FLAVOR_COLS.index("spicy_score")], 7)
    if taste_prefs.get("likes_creamy"):
        user_profile[FLAVOR_COLS.index("rich_fat_score")] = max(user_profile[FLAVOR_COLS.index("rich_fat_score")], 6)
    if taste_prefs.get("likes_aromatic"):
        user_profile[FLAVOR_COLS.index("aromatic_score")] = max(user_profile[FLAVOR_COLS.index("aromatic_score")], 7)
    if taste_prefs.get("likes_sweet"):
        user_profile[FLAVOR_COLS.index("sweet_score")] = max(user_profile[FLAVOR_COLS.index("sweet_score")], 5)
    if taste_prefs.get("likes_sour"):
        user_profile[FLAVOR_COLS.index("sour_score")] = max(user_profile[FLAVOR_COLS.index("sour_score")], 5)

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

        # Dietary filter
        dietary_pref = taste_prefs.get("dietary", "any")
        if dietary_pref == "veg":
            tdf = tdf[tdf["dietary_type"].str.lower().isin(["veg", "vegan"])]
        elif dietary_pref == "vegan":
            tdf = tdf[tdf["dietary_type"].str.lower() == "vegan"]
        elif dietary_pref == "pescatarian":
            tdf = tdf[tdf["dietary_type"].str.lower().isin(["veg", "vegan", "pescatarian"])]

        if tdf.empty:
            recommendations[tc_title] = {"cuisine_similarity": round(c_sim, 2), "courses": {}, "total_dishes_evaluated": 0}
            continue

        all_scores = []
        scoring_log = []

        for idx, row in tdf.iterrows():
            dish_vec = row[FLAVOR_COLS].values.astype(float)
            cs = cosine_sim(user_profile, dish_vec)

            # Euclidean distance score
            ed = np.linalg.norm(dish_vec - user_profile)
            es = 1.0 / (1.0 + ed)

            # Importance
            imp = float(row["dish_importance_score"]) / 10.0

            # ── NEW: Ingredient overlap score ──
            dish_ing_str = str(row.get("ingredients", ""))
            ing_score = ingredient_overlap(all_fav_ingredient_words, dish_ing_str)

            # Spice preference bonus
            spice_bonus = 0.0
            dish_spice = float(row.get("spicy_score", 0))
            spice_pref = taste_prefs.get("spice_level", "medium")
            if spice_pref == "mild" and dish_spice <= 3:
                spice_bonus = 0.05
            elif spice_pref == "medium" and 3 <= dish_spice <= 6:
                spice_bonus = 0.03
            elif spice_pref == "hot" and dish_spice >= 6:
                spice_bonus = 0.05

            # ── NEW scoring weights: ingredients gets 15%, others adjusted ──
            # cosine:30% + ingredients:15% + euclidean:13% + cuisine_sim:20% + importance:10% + spice:5% + base:7%
            final = (
                0.30 * cs
                + 0.15 * ing_score
                + 0.13 * es
                + 0.12 * max(c_sim, 0)
                + 0.10 * imp
                + 0.08 * max(c_sim, 0)
                + (0.05 if spice_bonus > 0 else 0.0)
            )

            # Find which favorite this dish is most similar to
            matched_fav, matched_fav_score = find_closest_favorite(dish_vec, dish_ing_str, fav_data)

            explanation = build_detailed_explanation(
                user_profile, dish_vec, row, taste_prefs, c_sim, None, matched_fav, ing_score
            )

            # Scoring breakdown for audit
            breakdown = {
                "dish_name": row["dish_name"],
                "course": row["course_group"],
                "cosine_similarity": round(cs, 4),
                "ingredient_overlap": round(ing_score, 4),
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
                    "ingredient_match": round(ing_score * 100, 1),
                    "euclidean_sim": round(es * 100, 1),
                    "cuisine_affinity": round(c_sim * 100, 1),
                    "dish_importance": round(imp * 100, 1),
                    "spice_bonus": round(spice_bonus * 100, 1),
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
        courses_result = {}
        for course_name in COURSE_ORDER:
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


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5001))
    app.run(host="0.0.0.0", port=port, debug=True)
