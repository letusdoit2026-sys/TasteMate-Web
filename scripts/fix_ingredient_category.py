#!/usr/bin/env python3
"""
Fix main_ingredient_category for Indian and Thai dishes in dishes.csv.

Validates and corrects mismatches between dish names, dietary_type,
primary_protein, ingredients, and their main_ingredient_category.
"""

import csv
import shutil
import re
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
CSV_PATH = DATA_DIR / "dishes.csv"
BACKUP_PATH = DATA_DIR / "dishes_backup_before_fix.csv"


def load_csv(path):
    with open(path, "r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        rows = list(reader)
    return fieldnames, rows


def save_csv(path, fieldnames, rows):
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def name_lower(row):
    return row["dish_name"].lower()


def ingr_lower(row):
    return row["ingredients"].lower()


def fix_indian_dishes(rows):
    """Apply known-food-knowledge corrections for Indian dishes."""
    changes = []

    for row in rows:
        if row["cuisine_name"] != "Indian":
            continue

        old_cat = row["main_ingredient_category"]
        new_cat = old_cat
        name = name_lower(row)
        ingr = ingr_lower(row)
        diet = row["dietary_type"]
        protein = row["primary_protein"]

        # ── PANEER dishes → Cheese Dish ──
        if "paneer" in name and old_cat != "Cheese Dish":
            # Exception: Paneer Paratha could stay Cheese Dish (filling) — already correct
            new_cat = "Cheese Dish"

        # ── DAL / LENTIL dishes → Lentil Dish ──
        elif re.search(r'\bdal\b|\bdaal\b|\blentil\b', name) and "vindaloo" not in name:
            if old_cat not in ("Lentil Dish",):
                # Moong Dal Halwa is a lentil-based dessert → Lentil Dish
                new_cat = "Lentil Dish"

        # ── DOSA / IDLI / UTTAPAM → Rice Dish (rice-lentil batter, rice dominant) ──
        elif re.search(r'\bdosa\b|\bidli\b|\buttapam\b|\bappam\b', name):
            if "masala dosa" in name:
                # Masala Dosa: potato filling is the star, keep Potato Dish
                pass
            elif old_cat == "Lentil Dish":
                new_cat = "Rice Dish"

        # ── NAAN → Wheat Dish ──
        elif re.search(r'\bnaan\b', name):
            if old_cat not in ("Wheat Dish", "Nut Dish"):
                # Peshawari Naan → keep Nut Dish (stuffed with nuts)
                new_cat = "Wheat Dish"

        # ── ROTI / CHAPATI → Wheat Dish ──
        elif re.search(r'\broti\b|\bchapati\b', name):
            if old_cat != "Wheat Dish":
                new_cat = "Wheat Dish"

        # ── PARATHA → Wheat Dish (unless filling dominates) ──
        elif re.search(r'\bparatha\b', name):
            if "paneer" in name:
                new_cat = "Cheese Dish"  # already handled above
            elif "aloo" in name:
                pass  # Aloo Paratha → Potato Dish is fine (potato filling)
            elif "keema" in name:
                pass  # Keema Paratha → Wheat Dish already, or meat — keep as is
            elif "methi" in name:
                pass  # Methi Paratha → Wheat Dish already
            elif old_cat in ("Milk Dish",):
                new_cat = "Wheat Dish"  # Lachha Paratha, Malabar Paratha

        # ── KULCHA → Wheat Dish ──
        elif re.search(r'\bkulcha\b', name):
            if old_cat not in ("Wheat Dish",):
                new_cat = "Wheat Dish"

        # ── BHATURA → Wheat Dish (deep-fried wheat bread) ──
        elif "bhatura" in name:
            if old_cat != "Wheat Dish":
                new_cat = "Wheat Dish"

        # ── BIRYANI → based on protein ──
        elif "biryani" in name:
            if "vegetable" in name:
                if old_cat != "Rice Dish":
                    new_cat = "Rice Dish"
            elif "egg" in name:
                pass  # Egg Biryani → Egg Dish is acceptable
            # Others (Mutton, Prawn, Hyderabadi) are already correct

        # ── CHICKEN dishes → Chicken Dish ──
        elif "chicken" in name and old_cat != "Chicken Dish":
            new_cat = "Chicken Dish"

        # ── LAMB / MUTTON dishes → Lamb Dish ──
        elif re.search(r'\blamb\b|\bmutton\b|\bgosht\b', name):
            if old_cat != "Lamb Dish":
                new_cat = "Lamb Dish"
        elif name in ("rogan josh", "laal maas", "nihari"):
            if old_cat != "Lamb Dish":
                new_cat = "Lamb Dish"

        # ── FISH dishes (explicit) → Fish Dish ──
        elif re.search(r'\bfish\b|\bmeen\b|\bmachh\b|\bmachhi\b', name):
            if old_cat != "Fish Dish":
                new_cat = "Fish Dish"

        # ── PRAWN / SHRIMP dishes → Shrimp Dish ──
        elif re.search(r'\bprawn\b|\bshrimp\b', name):
            if old_cat != "Shrimp Dish":
                new_cat = "Shrimp Dish"

        # ── Bread items marked Milk Dish → Wheat Dish ──
        elif "naan" not in name and "butter naan" == name:
            pass  # handled above
        elif name in ("butter naan", "garlic naan"):
            new_cat = "Wheat Dish"

        # ── Halwa corrections ──
        elif "gajar" in name and "halwa" in name:
            # Gajar Ka Halwa: carrots are the star, not milk
            if old_cat == "Milk Dish":
                new_cat = "Vegetable Dish"

        elif "rava kesari" in name or "kesari" in name:
            # Semolina dessert
            if old_cat == "Milk Dish":
                new_cat = "Wheat Dish"

        # ── Vegetable Biryani → Rice Dish ──
        elif "vegetable biryani" in name and old_cat != "Rice Dish":
            new_cat = "Rice Dish"

        # ── Momos: if Non-Veg, category should reflect protein, not Vegetable ──
        elif "momos" in name or "momo" in name:
            if diet == "Non-Veg" and old_cat == "Vegetable Dish":
                if "meat" in ingr or "minced" in ingr:
                    new_cat = "Meat Dish"

        # ── Curd Rice → Rice Dish (rice is the base) ──
        elif "curd rice" in name:
            if old_cat == "Yogurt Dish":
                new_cat = "Rice Dish"

        # ── Dum Aloo → Potato Dish (potato is the star) ──
        elif "dum aloo" in name:
            if old_cat == "Yogurt Dish":
                new_cat = "Potato Dish"

        # ── Chaat items: Keep yogurt for chaats where yogurt is a key topping ──
        # Aloo Tikki Chaat, Papri Chaat, Samosa Chaat, Dahi Vada, Dahi Puri → yogurt is key, keep

        # ── Plain Naan → Wheat Dish (not Yogurt Dish) ──
        elif "plain naan" in name:
            new_cat = "Wheat Dish"

        # ── Onion Kulcha → Wheat Dish ──
        elif "onion kulcha" in name:
            new_cat = "Wheat Dish"

        # ── Mughlai Paratha → Egg Dish is fine (egg-stuffed) ──

        # ── Sol Kadhi → Coconut Dish or Vegetable Dish (kokum + coconut milk) ──
        elif "sol kadhi" in name:
            if old_cat == "Milk Dish":
                new_cat = "Coconut Dish"

        # ── Lentils Dish → Lentil Dish (normalize) ──
        elif old_cat == "Lentils Dish":
            new_cat = "Lentil Dish"

        # ── Chickpeas Dish → Chickpea Dish (normalize) ──
        elif old_cat == "Chickpeas Dish":
            new_cat = "Chickpea Dish"

        # ── DIETARY CONFLICT: Veg/Vegan dish with meat category ──
        # Egg dishes marked as Veg: In Indian cuisine, eggs are sometimes Veg — leave as is

        if new_cat != old_cat:
            changes.append((row["dish_name"], old_cat, new_cat))
            row["main_ingredient_category"] = new_cat

    return changes


def fix_thai_dishes(rows):
    """Apply known-food-knowledge corrections for Thai dishes."""
    changes = []

    for row in rows:
        if row["cuisine_name"] != "Thai":
            continue

        old_cat = row["main_ingredient_category"]
        new_cat = old_cat
        name = name_lower(row)
        ingr = ingr_lower(row)
        diet = row["dietary_type"]
        protein = row["primary_protein"]

        # ── COCONUT MILK desserts marked as "Milk Dish" → "Coconut Dish" or "Rice Dish" ──
        # Thai "Milk Dish" almost always means coconut milk, not dairy
        # For desserts with sticky rice as base → Rice Dish
        # For coconut milk desserts without rice → Coconut Dish

        # ── Mango Sticky Rice → Rice Dish ──
        if "mango sticky rice" in name:
            new_cat = "Rice Dish"

        # ── Khao (rice) dishes in Milk category → Rice Dish ──
        elif name.startswith("khao") and old_cat == "Milk Dish":
            new_cat = "Rice Dish"  # Khao Lam, Khao Tom Mat, Khao Niao Ping

        # ── Pad Thai → Noodle Dish (rice noodles are the star) ──
        elif "pad thai" in name:
            new_cat = "Noodle Dish"

        # ── Pad Kee Mao → Noodle Dish ──
        elif "pad kee mao" in name or "phat mi" in name:
            if "noodle" in ingr:
                new_cat = "Noodle Dish"

        # ── Phat Si-io → Noodle Dish ──
        elif "phat si" in name:
            if "noodle" in ingr:
                new_cat = "Noodle Dish"

        # ── Phat Wun Sen → Noodle Dish ──
        elif "phat wun sen" in name:
            new_cat = "Noodle Dish"

        # ── Kuai Tiao / Kuaitiao / Kuaichap → Noodle Dish ──
        elif re.search(r'kuai\s*tiao|kuaitiao|kuaichap', name):
            new_cat = "Noodle Dish"

        # ── Bami → Noodle Dish (egg noodles) ──
        elif name.startswith("bami") or name.startswith("ba mee"):
            new_cat = "Noodle Dish"

        # ── Khao Soi → Noodle Dish (curry noodle soup) ──
        elif "khao soi" in name:
            new_cat = "Noodle Dish"

        # ── Khanom Chin → Noodle Dish (fermented rice noodles) ──
        elif "khanom chin" in name or "khanom jeen" in name:
            new_cat = "Noodle Dish"

        # ── Sukhothai Noodles → Noodle Dish ──
        elif "sukhothai noodle" in name:
            new_cat = "Noodle Dish"

        # ── Rat Na → Noodle Dish ──
        elif "rat na" in name:
            new_cat = "Noodle Dish"

        # ── Yentafo → Noodle Dish ──
        elif "yentafo" in name:
            new_cat = "Noodle Dish"

        # ── Mi Krop → Noodle Dish (crispy noodles) ──
        elif "mi krop" in name:
            new_cat = "Noodle Dish"

        # ── Yam Wun Sen → Noodle Dish (glass noodle salad) ──
        elif "yam wun sen" in name:
            new_cat = "Noodle Dish"

        # ── Tom Yam Boran Noodles → Noodle Dish ──
        elif "tom yam boran noodle" in name:
            new_cat = "Noodle Dish"

        # ── Lot Chong → Coconut Dish (pandan noodles in coconut milk dessert) ──
        elif "lot chong" in name:
            if old_cat == "Milk Dish":
                new_cat = "Coconut Dish"

        # ── Sarim → Coconut Dish (rice noodles in coconut milk dessert) ──
        elif "sarim" in name:
            if old_cat == "Milk Dish":
                new_cat = "Coconut Dish"

        # ── Som Tam → Vegetable Dish (green papaya salad) ──
        elif "som tam" in name or "som tum" in name:
            if old_cat != "Vegetable Dish":
                new_cat = "Vegetable Dish"

        # ── Thai coconut milk desserts → Coconut Dish ──
        elif old_cat == "Milk Dish" and "coconut milk" in ingr:
            # These are coconut-based, not dairy
            if any(x in name for x in [
                "bua loy", "kluai buat", "fakthong kaeng buat",
                "thapthim krop", "thua khiao", "sago",
                "khanom chan", "khanom krok", "khanom thuai",
                "khanom piakpun", "khanom sai bua", "khanom thang",
                "khanom babin", "khanom phing",
                "kleeb lamduan", "luk chup",
            ]):
                new_cat = "Coconut Dish"

        # ── Roti (Thai) → Wheat Dish ──
        elif name == "roti" and row["cuisine_name"] == "Thai":
            if old_cat == "Milk Dish":
                new_cat = "Wheat Dish"

        # ── Pathongko (Thai fried dough) → Wheat Dish ──
        elif "pathongko" in name:
            if old_cat == "Milk Dish":
                new_cat = "Wheat Dish"

        # ── Khrongkhraeng Krop → Wheat Dish ──
        elif "khrongkhraeng" in name:
            if old_cat == "Milk Dish":
                new_cat = "Wheat Dish"

        # ── Rice Desserts marked as Milk Dish → Rice Dessert ──
        # (Some Thai desserts are rice-based with coconut milk topping)

        # ── Nam Sup: Non-Veg + Rice Dish → it's a broth/soup, keep Rice Dish? ──
        # Actually it's a clear broth soup, not rice-based. But protein=Rice.
        # Leave as-is since it's ambiguous.

        # ── Vegetables Dish → Vegetable Dish (normalize) ──
        elif old_cat == "Vegetables Dish":
            new_cat = "Vegetable Dish"

        # ── Kaeng Ho: leftover curries + glass noodles → Mixed Dish ──
        elif "kaeng ho" in name:
            if old_cat == "Fruit Dish":
                new_cat = "Noodle Dish"

        # ── Chim Chum: hotpot → based on protein ──
        # Currently Egg Dish but it's a hotpot. Keep as-is (egg is listed).

        if new_cat != old_cat:
            changes.append((row["dish_name"], old_cat, new_cat))
            row["main_ingredient_category"] = new_cat

    return changes


def main():
    print(f"Loading {CSV_PATH}")
    fieldnames, rows = load_csv(CSV_PATH)

    total_rows = len(rows)
    indian_count = sum(1 for r in rows if r["cuisine_name"] == "Indian")
    thai_count = sum(1 for r in rows if r["cuisine_name"] == "Thai")
    print(f"Total rows: {total_rows}, Indian: {indian_count}, Thai: {thai_count}")

    # Backup
    print(f"\nCreating backup at {BACKUP_PATH}")
    shutil.copy2(CSV_PATH, BACKUP_PATH)

    # Fix Indian
    print("\n" + "=" * 60)
    print("FIXING INDIAN DISHES")
    print("=" * 60)
    indian_changes = fix_indian_dishes(rows)
    for dish, old, new in indian_changes:
        print(f"  {dish}: {old} → {new}")
    print(f"\nIndian changes: {len(indian_changes)}")

    # Fix Thai
    print("\n" + "=" * 60)
    print("FIXING THAI DISHES")
    print("=" * 60)
    thai_changes = fix_thai_dishes(rows)
    for dish, old, new in thai_changes:
        print(f"  {dish}: {old} → {new}")
    print(f"\nThai changes: {len(thai_changes)}")

    # Verify row count unchanged
    assert len(rows) == total_rows, f"Row count changed! {total_rows} → {len(rows)}"

    # Save
    print(f"\nSaving to {CSV_PATH}")
    save_csv(CSV_PATH, fieldnames, rows)

    # Print new distribution
    from collections import Counter
    print("\n" + "=" * 60)
    print("NEW DISTRIBUTION")
    print("=" * 60)
    for cuisine in ["Indian", "Thai"]:
        dishes = [r for r in rows if r["cuisine_name"] == cuisine]
        cats = Counter(r["main_ingredient_category"] for r in dishes)
        print(f"\n--- {cuisine} ({len(dishes)} dishes) ---")
        for cat, count in cats.most_common():
            print(f"  {cat}: {count}")

    print(f"\n{'=' * 60}")
    print(f"SUMMARY: {len(indian_changes) + len(thai_changes)} total changes "
          f"({len(indian_changes)} Indian, {len(thai_changes)} Thai)")
    print(f"Row count verified: {len(rows)} (unchanged)")
    print(f"Backup saved at: {BACKUP_PATH}")


if __name__ == "__main__":
    main()
