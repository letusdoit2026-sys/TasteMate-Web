"""
Generate per-dish facet ontology for every dish in the catalog using Grok (x.AI).

Output:     data/dish_facets.csv
Checkpoint: data/dish_facets_checkpoint.csv  (resume-safe)

Powers Hybrid 3.0 facet-overlap recommendation engine.

Usage:
    python3 scripts/generate_dish_facets.py
"""

import os
import json
import time
import csv
import threading
import pandas as pd
from concurrent.futures import ThreadPoolExecutor, as_completed
from openai import OpenAI
from dotenv import load_dotenv

# ── Config ──────────────────────────────────────────────────────────────────
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "..", ".env"))

XAI_API_KEY          = os.environ.get("XAI_API_KEY", "")
MODEL                = "grok-4-1-fast-reasoning"
BATCH_SIZE           = 2       # dishes per API call (facets are larger than recs)
MAX_WORKERS          = 3
SLEEP_BETWEEN_CALLS  = 0.3
MAX_RETRIES          = 3

BASE_DIR    = os.path.join(os.path.dirname(__file__), "..")
DATA_DIR    = os.path.join(BASE_DIR, "data")
OUTPUT_CSV  = os.path.join(DATA_DIR, "dish_facets.csv")
CHECKPOINT  = os.path.join(DATA_DIR, "dish_facets_checkpoint.csv")

CSV_COLUMNS = [
    "dish_name", "cuisine",
    "cooking_methods", "heat_intensity", "preparation_complexity",
    "flavor_anchors", "spice_lineage", "fat_character", "aromatic_signature",
    "texture_profile",
    "marinade_family", "sauce_role",
    "course_role", "serving_temperature", "portion_format", "richness",
    "substitution_class", "ingredient_swaps",
    "regional_origin", "cultural_kin", "meal_occasion",
    "dominant_color", "visual_appeal",
]

_write_lock = threading.Lock()
_done_lock  = threading.Lock()

# ── Load source dishes ──────────────────────────────────────────────────────

def load_dishes():
    tc   = pd.read_csv(os.path.join(DATA_DIR, "taste_chemistry.csv"))
    tc   = tc[tc["dish_name"] != "dish_name"].copy()
    tc["dish_name"] = tc["dish_name"].astype(str).str.strip()
    tc["cuisine"]   = tc["cuisine"].astype(str).str.strip()

    meta = pd.read_csv(os.path.join(DATA_DIR, "Metadata_Filters.csv"))
    meta = meta[meta["dish_name"] != "dish_name"].copy()
    meta["dish_name"] = meta["dish_name"].astype(str).str.strip()
    meta["cuisine"]   = meta["cuisine"].astype(str).str.strip()

    merged = tc.merge(
        meta[["dish_name", "cuisine", "category", "dietary_type", "primary_protein"]],
        on=["dish_name", "cuisine"], how="left",
    )
    return merged

# ── Checkpoint ──────────────────────────────────────────────────────────────

def load_done():
    done = set()
    if os.path.exists(CHECKPOINT):
        with open(CHECKPOINT, newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                done.add((row["dish_name"], row["cuisine"]))
    return done

_output_header_written     = os.path.exists(OUTPUT_CSV)
_checkpoint_header_written = os.path.exists(CHECKPOINT)
_total_written             = [0]

def write_rows(rows):
    global _output_header_written, _checkpoint_header_written
    with _write_lock:
        with open(OUTPUT_CSV, "a", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=CSV_COLUMNS)
            if not _output_header_written:
                w.writeheader()
                _output_header_written = True
            w.writerows(rows)
        with open(CHECKPOINT, "a", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=CSV_COLUMNS)
            if not _checkpoint_header_written:
                w.writeheader()
                _checkpoint_header_written = True
            w.writerows(rows)
        _total_written[0] += len(rows)

# ── Grok prompt ─────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """You are an expert food ontologist. For each dish provided, return a structured facet profile that captures cooking technique, flavor fingerprint, cultural lineage, substitution options, and visual/sensory signals.

Be concise — use short slug-style values (lowercase, hyphenated, no whitespace). Always return valid JSON only — no markdown, no commentary."""

def build_prompt(batch):
    dishes_text = "\n".join(
        f'- NAME="{d["dish_name"]}" | CUISINE="{d["cuisine"]}" | meta=(category={d.get("category","?")}, dietary={d.get("dietary_type","?")}, protein={d.get("primary_protein","?")})'
        for d in batch
    )
    return f"""For each dish below, return a facet profile.

DISHES:
{dishes_text}

CRITICAL OUTPUT RULES:
- "dish_name" MUST be EXACTLY the string inside NAME="..." — nothing else. Do NOT include cuisine, category, dietary, protein, or any parenthetical metadata.
- "cuisine" MUST be EXACTLY the string inside CUISINE="...".
- The meta=(...) block is context only; never copy it into any output field.

For EACH dish, output a JSON object with these exact keys:

{{
  "dish_name": "<EXACT value of NAME — just the dish name, no metadata, no parentheses>",
  "cuisine": "<EXACT value of CUISINE>",

  "cooking_methods": ["<1-3 short slugs e.g. tandoor, char-grill, smoke, deep-fry, slow-stew, raw, bake, steam, pan-sear>"],
  "heat_intensity": "<one of: high-dry-heat | medium-stew | raw | bake | fry | steam>",
  "preparation_complexity": "<simple | moderate | elaborate>",

  "flavor_anchors": ["<2-4 slugs e.g. smoky, aromatic-spice, tangy, umami-rich, sweet-caramel, herbal-fresh, citrus-bright, fermented-funk, buttery-rich, chili-heat>"],
  "spice_lineage": "<warming-spice | chili-heat | herb-fresh | umami-fermented | sweet-spice | none>",
  "fat_character": "<creamy-dairy | nutty-oil | rendered-meat | vegetable-oil | coconut-fat | none>",
  "aromatic_signature": "<short slug e.g. garam-masala, herbs-de-provence, five-spice, sofrito, ras-el-hanout, none>",

  "texture_profile": ["<1-3 slugs e.g. charred-crust, juicy-interior, crispy-shell, creamy-soft, chewy-bread, silky-sauce, crunchy-raw, layered-flaky>"],

  "marinade_family": "<yogurt-spice | citrus-herb | soy-fermented | dry-rub | wine-aromatic | none>",
  "sauce_role": "<integral | side | dressing | none>",

  "course_role": "<short slug describing role e.g. main-grilled-protein, grain-bowl, dip-and-bread, soup-comfort, dessert-baked, salad-fresh, breakfast-savory, snack-fried>",
  "serving_temperature": "<hot | warm | room | cold>",
  "portion_format": "<skewers | bowl | wrap | platter | shared-plate | individual | hand-held | composed-plate>",
  "richness": "<light | medium | rich | indulgent>",

  "substitution_class": {{
    "veg":   ["<2-3 substitute dishes/styles that recreate this dish vegetarian, e.g. paneer-tikka-style, halloumi-grilled>"],
    "vegan": ["<2-3 vegan substitutes e.g. grilled-cauliflower-steak, tempeh-skewers, tofu-tikka>"],
    "fish":  ["<1-2 pescatarian substitutes if relevant, else empty list>"],
    "any":   ["<2-3 same-protein-class substitutes from any cuisine>"]
  }},
  "ingredient_swaps": {{
    "<key ingredient>": ["<2-3 substitutes>"]
  }},

  "regional_origin": "<specific region slug e.g. punjab-north-india, tuscany, yucatan, sichuan, andalusia>",
  "cultural_kin": ["<2-4 cousin-cuisine slugs e.g. levantine-grill, mediterranean-stew, east-asian-stir-fry, north-african-tagine>"],
  "meal_occasion": ["<1-3 slugs e.g. everyday, festive, street-food, celebratory, ritual, comfort, picnic, fast-day>"],

  "dominant_color": "<red-orange | green | golden-brown | white | multicolor | brown | yellow | dark-red>",
  "visual_appeal": "<rustic | refined | colorful | minimalist>"
}}

Return ONLY a JSON array of objects (one per dish), no other text."""


def call_grok(prompt):
    client = OpenAI(api_key=XAI_API_KEY, base_url="https://api.x.ai/v1", timeout=90.0)
    for attempt in range(MAX_RETRIES):
        try:
            resp = client.chat.completions.create(
                model=MODEL,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user",   "content": prompt},
                ],
                temperature=0.2,
                max_tokens=8192,
                timeout=90.0,
            )
            content = resp.choices[0].message.content.strip()
            if content.startswith("```"):
                parts = content.split("```")
                content = parts[1] if len(parts) > 1 else content
                if content.startswith("json"):
                    content = content[4:]
            content = content.strip().rstrip("`").strip()
            parsed = json.loads(content)
            if isinstance(parsed, list):
                return parsed
        except json.JSONDecodeError as e:
            print(f"  [WARN] JSON err attempt {attempt+1}: {e}")
        except Exception as e:
            print(f"  [ERROR] API err attempt {attempt+1}: {e}")
        if attempt < MAX_RETRIES - 1:
            time.sleep(3)
    return None

# ── Worker ──────────────────────────────────────────────────────────────────

def to_csv_value(v):
    """Serialise lists/dicts as JSON; pass strings through."""
    if isinstance(v, (list, dict)):
        return json.dumps(v, separators=(",", ":"))
    return "" if v is None else str(v)

def process_batch(batch_num, batch, done_set):
    prompt = build_prompt(batch)
    result = call_grok(prompt)

    if result is None:
        print(f"  [{batch_num}] SKIP {batch[0]['dish_name']}...")
        return 0

    # Build an index of expected (dish_name, cuisine) pairs for this batch,
    # so we can reconcile if Grok returns polluted names.
    expected_by_cuisine = {}
    for d in batch:
        expected_by_cuisine.setdefault(d["cuisine"].strip(), []).append(d["dish_name"].strip())

    rows = []
    for facet in result:
        raw_name = str(facet.get("dish_name", "")).strip()
        cuisine  = str(facet.get("cuisine", "")).strip()
        candidates = expected_by_cuisine.get(cuisine, [])
        lower_map  = {c.lower(): c for c in candidates}

        # Try match in order: exact → case-insensitive → strip-paren → strip-paren + ci.
        # This preserves dish names that legitimately contain "(...)" annotations
        # (e.g. "Paletas (Mexican Popsicles)") while still stripping Grok metadata pollution.
        resolved = None
        if raw_name in candidates:
            resolved = raw_name
        elif raw_name.lower() in lower_map:
            resolved = lower_map[raw_name.lower()]
        elif " (" in raw_name:
            stripped = raw_name.split(" (", 1)[0].strip()
            if stripped in candidates:
                resolved = stripped
            elif stripped.lower() in lower_map:
                resolved = lower_map[stripped.lower()]

        if not resolved:
            print(f"  [{batch_num}] [WARN] unmatched dish_name: {raw_name!r} ({cuisine}) — expected one of {candidates}")
            continue
        facet["dish_name"] = resolved
        facet["cuisine"]   = cuisine

        row = {col: to_csv_value(facet.get(col, "")) for col in CSV_COLUMNS}
        if row["dish_name"] and row["cuisine"]:
            rows.append(row)

    if rows:
        write_rows(rows)
        with _done_lock:
            for r in rows:
                done_set.add((r["dish_name"], r["cuisine"]))

    print(f"  [{batch_num}] ✓ {batch[0]['dish_name']}{'...' if len(batch)>1 else ''} "
          f"| {len(rows)} rows | Total: {_total_written[0]}")
    return len(rows)

# ── Main ────────────────────────────────────────────────────────────────────

def main():
    if not XAI_API_KEY:
        print("ERROR: XAI_API_KEY not set in .env")
        return

    dishes_df = load_dishes()
    print(f"Loaded {len(dishes_df)} dishes")
    print(f"Model: {MODEL} | Batch: {BATCH_SIZE} | Workers: {MAX_WORKERS}")

    done = load_done()
    print(f"Checkpoint: {len(done)} dishes already done")

    pending = [
        {"dish_name": r["dish_name"], "cuisine": r["cuisine"],
         "category": r.get("category", ""), "dietary_type": r.get("dietary_type", ""),
         "primary_protein": r.get("primary_protein", "")}
        for _, r in dishes_df.iterrows()
        if (r["dish_name"], r["cuisine"]) not in done
    ]
    print(f"Pending dishes: {len(pending)}")

    batches = []
    batch_num = 0
    for i in range(0, len(pending), BATCH_SIZE):
        batch_num += 1
        batches.append((batch_num, pending[i:i+BATCH_SIZE]))

    total_batches = len(batches)
    print(f"Total batches: {total_batches} | Est. ~{total_batches * 20 / MAX_WORKERS / 60:.0f} min")
    print("─" * 60)

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {executor.submit(process_batch, bn, batch, done): bn for bn, batch in batches}
        for future in as_completed(futures):
            try:
                future.result()
            except Exception as e:
                print(f"  [THREAD ERROR] {e}")

    print("\n" + "═" * 60)
    print(f"DONE. Total rows written: {_total_written[0]}")
    print(f"Output: {OUTPUT_CSV}")


if __name__ == "__main__":
    main()
