#!/usr/bin/env python3
"""
Add serving_temperature column to dishes.csv.
Values: "hot", "cold", "room_temp"
"""

import csv
import sys
from collections import Counter

CSV_PATH = "/Users/praveengiri/Documents/TasteAltlas/TasteMate-Web/data/dishes.csv"


# ── Sub-category keyword sets (matched case-insensitively against sub_category) ──

HOT_SUB_KEYWORDS = [
    "curry", "stew", "soup", "hot pot", "hotpot", "braise", "braised",
    "porridge", "fried", "fritter", "stir-fry", "stir fry", "grill",
    "roast", "kebab", "kebap", "kabab", "egg dish", "baked egg",
    "pasta", "noodle", "flatbread", "bread", "savory pie", "dumpling",
    "dim sum", "sausage", "casserole", "risotto", "pilaf", "biryani",
    "paella", "congee", "chowder", "bisque", "fondue", "tagine",
    "ramen", "pho", "laksa", "rendang", "tempura", "tonkatsu",
    "steamed", "boiled", "simmered", "poached", "sauteed", "saute",
    "scrambled", "omelette", "omelet", "pancake", "waffle", "crepe",
    "pot pie", "empanada", "samosa", "spring roll", "egg roll",
    "wonton", "meatball", "meatloaf", "schnitzel", "cutlet",
    "chili", "gumbo", "jambalaya", "etouffee",
    "baked dish", "baked meat", "baked fish", "baked potato",
    "baked pasta", "baked rice", "baked seafood", "baked shellfish",
    "baked casserole", "baked gnocchi", "baked cod",
    "wrapped baked", "wrapped braise", "wrapped kebab",
    "warm dip", "warm mezze", "warm chickpea", "warm dessert",
    "vegetable bake", "vegetable braise", "vegetable casserole",
    "vegetable curry", "vegetable saute", "vegetable stew",
    "vegetable stir-fry", "vegetable soup",
    "fish soup", "bean broth", "bean casserole",
    "barley soup", "wheat soup", "wine soup",
    "yogurt stew", "yogurt meatball soup", "yogurt meatball stew",
    "yogurt noodle soup", "yogurt grain soup", "yogurt rice soup",
    "rice dish", "anchovy rice", "vegetable rice",
    "wedding pilaf", "vermicelli dish",
    "wheat and meat porridge", "baked bread soup",
    "čorba",
]

COLD_SUB_KEYWORDS = [
    "salad", "ice cream", "sorbet", "gelato", "frozen",
    "smoothie", "cold drink", "milkshake", "shake",
    "ceviche", "crudo", "tartare", "carpaccio",
    "popsicle", "granita", "semifreddo", "parfait",
    "raw", "sashimi", "cold soup", "gazpacho",
    "yogurt dip", "yogurt herb dip", "yogurt salad",
    "yogurt vegetable meze", "yogurt drink",
    "aspic", "aspic fish",
    "beverage",  # most beverages are served cold or room temp; cold is closer
]

ROOM_TEMP_SUB_KEYWORDS = [
    "sweet", "cake", "cookie", "candy", "pastry", "snack",
    "chaat", "rice cake", "sandwich", "sauce", "condiment",
    "chutney", "pickle", "jam", "preserve", "relish",
    "spread", "dip", "meze", "pate",
    "chocolate", "truffle", "fudge", "toffee", "nougat",
    "marzipan", "halva", "halvah", "baklava", "lokum",
    "macaron", "meringue", "biscuit", "cracker", "rusk",
    "wafer", "bar cookie", "bagel", "wrap",
    "cheese", "aged cheese", "baked cheese", "baked feta",
    "walnut bread dip", "walnut sauce", "walnut cream",
    "almond cream", "vanilla custard sauce",
    "vegetable spread", "vegetable walnut pate",
    "wild greens walnut pate",
    "bacon", "bag snack", "bakery snack",
    "almond biscuit", "anise biscuit",
]

# ── Category-level defaults ──

HOT_CATEGORIES = {"soup", "main dish", "breakfast"}
COLD_CATEGORIES = set()
ROOM_TEMP_CATEGORIES = {"sauce", "sauce/condiment", "snack", "dessert", "dairy", "drink"}


# ── Dish name keyword heuristics ──

COLD_NAME_KEYWORDS = ["ice ", "ice-", "iced ", "frozen", "cold", "chilled", "raw ",
                       "salad", "smoothie", "shake", "juice", "sorbet", "gelato",
                       "granita", "semifreddo", "popsicle", "ceviche", "crudo",
                       "tartare", "carpaccio", "sashimi", "gazpacho",
                       "lassi", "falooda", "lemonade", "limeade"]

HOT_NAME_KEYWORDS = ["soup", "stew", "curry", "fried", "grilled", "roast",
                      "baked", "hot ", "steamed", "boiled", "braised",
                      "simmered", "sauteed", "stir-fry", "kebab", "kebap",
                      "chai", "coffee", "tea ", " tea"]

ROOM_TEMP_NAME_KEYWORDS = ["pickle", "chutney", "jam", "preserve", "relish",
                            "candy", "cookie", "biscuit", "cracker"]


def classify_temperature(row):
    """Classify a dish's serving temperature."""
    sub_cat = (row.get("sub_category") or "").lower().strip()
    category = (row.get("category") or "").lower().strip()
    dish_name = (row.get("dish_name") or "").lower().strip()
    course = (row.get("course") or "").lower().strip()

    # ── 1. Dish name heuristics (highest priority — overrides sub_category) ──
    #    e.g. "Masala Chai" is hot even though sub_category is "Beverage"

    # Hot name keywords first (catches chai, coffee, tea, soup in name, etc.)
    for kw in HOT_NAME_KEYWORDS:
        if kw in dish_name:
            return "hot"

    # Cold name keywords
    for kw in COLD_NAME_KEYWORDS:
        if kw in dish_name:
            return "cold"

    # Room temp name keywords
    for kw in ROOM_TEMP_NAME_KEYWORDS:
        if kw in dish_name:
            return "room_temp"

    # ── 2. Sub-category keyword matching ──

    # Check cold first (more specific)
    for kw in COLD_SUB_KEYWORDS:
        if kw in sub_cat:
            return "cold"

    # Check hot sub-category keywords
    for kw in HOT_SUB_KEYWORDS:
        if kw in sub_cat:
            return "hot"

    # Check room_temp sub-category keywords
    for kw in ROOM_TEMP_SUB_KEYWORDS:
        if kw in sub_cat:
            return "room_temp"

    # ── 3. Category-level fallback ──

    if category in HOT_CATEGORIES:
        return "hot"
    if category in COLD_CATEGORIES:
        return "cold"
    if category in ROOM_TEMP_CATEGORIES:
        return "room_temp"

    # ── 4. Course-based fallback ──
    if course in ("main", "side"):
        return "hot"
    if course in ("dessert",):
        return "room_temp"

    # ── 5. Default ──
    return "hot"


def main():
    # Read CSV
    with open(CSV_PATH, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        rows = list(reader)

    # Remove old column if re-running
    if "serving_temperature" in fieldnames:
        fieldnames = [f for f in fieldnames if f != "serving_temperature"]

    # Add new column
    fieldnames = fieldnames + ["serving_temperature"]

    for row in rows:
        row["serving_temperature"] = classify_temperature(row)

    # Write back
    with open(CSV_PATH, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    # ── Stats ──
    total = Counter()
    by_cuisine = {}
    for row in rows:
        temp = row["serving_temperature"]
        cuisine = row.get("cuisine_name", "Unknown")
        total[temp] += 1
        if cuisine not in by_cuisine:
            by_cuisine[cuisine] = Counter()
        by_cuisine[cuisine][temp] += 1

    print(f"\n=== Overall Temperature Distribution ({len(rows)} dishes) ===")
    for t in ["hot", "cold", "room_temp"]:
        pct = total[t] / len(rows) * 100
        print(f"  {t:12s}: {total[t]:5d}  ({pct:.1f}%)")

    for cuisine_name in ["Indian", "Thai"]:
        if cuisine_name in by_cuisine:
            c = by_cuisine[cuisine_name]
            ct = sum(c.values())
            print(f"\n=== {cuisine_name} ({ct} dishes) ===")
            for t in ["hot", "cold", "room_temp"]:
                pct = c[t] / ct * 100 if ct else 0
                print(f"  {t:12s}: {c[t]:5d}  ({pct:.1f}%)")

    print("\nDone. Updated:", CSV_PATH)


if __name__ == "__main__":
    main()
