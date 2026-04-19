"""
Generate top-10 cross-cuisine recommendations for every dish using Grok (x.AI).

Output: data/grok_recommendations.csv
Checkpoint: data/grok_recommendations_checkpoint.csv (resume-safe)

Usage:
    python3 scripts/generate_grok_recommendations.py

Parallelism: 3 threads → ~2 hours for all 668 dishes × 4 target cuisines
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
BATCH_SIZE           = 3       # dishes per API call
MAX_WORKERS          = 3       # parallel threads
SLEEP_BETWEEN_CALLS  = 0.5     # seconds between launches (per thread)
MAX_RETRIES          = 3

BASE_DIR   = os.path.join(os.path.dirname(__file__), "..")
DATA_DIR   = os.path.join(BASE_DIR, "data")
OUTPUT_CSV  = os.path.join(DATA_DIR, "grok_recommendations.csv")
CHECKPOINT  = os.path.join(DATA_DIR, "grok_recommendations_checkpoint.csv")

CSV_COLUMNS = [
    "dish_name", "cuisine", "target_cuisine",
    "recommended_dish", "rank",
    "why_it_matches", "confidence", "match_score",
    "course", "dietary_type",
]

# Thread-safe write lock
_write_lock  = threading.Lock()
_done_lock   = threading.Lock()

# ── Load data ────────────────────────────────────────────────────────────────

def load_dishes():
    tc   = pd.read_csv(os.path.join(DATA_DIR, "taste_chemistry.csv"))
    tc   = tc[tc["dish_name"] != "dish_name"].copy()
    tc["dish_name"] = tc["dish_name"].str.strip()
    tc["cuisine"]   = tc["cuisine"].str.strip()

    meta = pd.read_csv(os.path.join(DATA_DIR, "Metadata_Filters.csv"))
    meta = meta[meta["dish_name"] != "dish_name"].copy()
    meta["dish_name"] = meta["dish_name"].str.strip()
    meta["cuisine"]   = meta["cuisine"].str.strip()

    return tc.merge(
        meta[["dish_name", "cuisine", "category", "dietary_type", "primary_protein"]],
        on=["dish_name", "cuisine"], how="left",
    )

# ── Checkpoint helpers ───────────────────────────────────────────────────────

def load_checkpoint():
    done = set()
    if os.path.exists(CHECKPOINT):
        with open(CHECKPOINT, newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                done.add((row["dish_name"], row["cuisine"], row["target_cuisine"]))
    return done

_output_header_written    = os.path.exists(OUTPUT_CSV)
_checkpoint_header_written = os.path.exists(CHECKPOINT)
_total_written = [0]   # mutable counter shared across threads

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

# ── Grok API ─────────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """You are an expert cross-cuisine food recommender. Use deep reasoning based on technique, marinade, cooking method, texture, and flavor translation.

For each dish provided, return the top 10 recommendations from the specified target cuisine. Rank by similarity strength — consider: preparation technique, key ingredients, flavor profile (spicy/aromatic/umami/fat/sweet/sour), texture, and eating experience.

Always return valid JSON — no markdown, no explanation outside the JSON."""

def build_prompt(source_batch, target_cuisine, target_dish_list):
    dishes_json = json.dumps(source_batch, indent=2)
    target_str  = "\n".join(f"- {d}" for d in target_dish_list)
    return f"""For each source dish below, return top 10 recommendations from {target_cuisine} cuisine.

SOURCE DISHES:
{dishes_json}

{target_cuisine.upper()} CUISINE DISH LIST (choose only from these):
{target_str}

Return a JSON array. Each element = one source dish's recommendations:
[
  {{
    "dish_name": "<source dish name>",
    "cuisine": "<source cuisine>",
    "recommendations": [
      {{
        "rank": 1,
        "recommended_dish": "<name from the target list>",
        "why_it_matches": "<1-2 sentence explanation>",
        "confidence": <integer 50-99>,
        "match_score": <float e.g. 9.6>,
        "course": "<Appetizer|Main Course|Dessert|Salad|Bread|Drink>",
        "dietary_type": "<Veg|Vegan|Non-Veg|Pescatarian>"
      }}
      ... (10 total)
    ]
  }}
]

Rules: only use dishes from the target list. Rank 1 = strongest match. Return ONLY the JSON array."""


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
                temperature=0.3,
                max_tokens=8192,
                timeout=90.0,
            )
            content = resp.choices[0].message.content.strip()
            # Strip markdown fences
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
            print(f"  [WARN] JSON error attempt {attempt+1}: {e}")
        except Exception as e:
            print(f"  [ERROR] API error attempt {attempt+1}: {e}")
        if attempt < MAX_RETRIES - 1:
            time.sleep(3)
    return None


# ── Worker ───────────────────────────────────────────────────────────────────

def process_batch(batch_num, batch, src_cuisine, tgt_cuisine, tgt_dish_list, done_set):
    """Process one batch: call Grok, parse, write rows."""
    source_info = [
        {
            "dish_name":       d["dish_name"],
            "cuisine":         src_cuisine,
            "category":        d.get("category", ""),
            "dietary_type":    d.get("dietary_type", ""),
            "primary_protein": d.get("primary_protein", ""),
            "flavor_notes": {
                "spicy":    round(float(d.get("spicy",   0)), 2),
                "aromatic": round(float(d.get("aromatic",0)), 2),
                "umami":    round(float(d.get("umami",   0)), 2),
                "fat":      round(float(d.get("fat",     0)), 2),
                "sweet":    round(float(d.get("sweet",   0)), 2),
            },
        }
        for d in batch
    ]

    prompt = build_prompt(source_info, tgt_cuisine, tgt_dish_list)
    result = call_grok(prompt)

    if result is None:
        print(f"  [{batch_num}] SKIP {src_cuisine}→{tgt_cuisine} | {batch[0]['dish_name']}...")
        return 0

    rows = []
    for dish_result in result:
        dish_name = dish_result.get("dish_name", "")
        for rec in dish_result.get("recommendations", [])[:10]:
            rows.append({
                "dish_name":        dish_name,
                "cuisine":          src_cuisine,
                "target_cuisine":   tgt_cuisine,
                "recommended_dish": rec.get("recommended_dish", ""),
                "rank":             rec.get("rank", ""),
                "why_it_matches":   rec.get("why_it_matches", ""),
                "confidence":       rec.get("confidence", ""),
                "match_score":      rec.get("match_score", ""),
                "course":           rec.get("course", ""),
                "dietary_type":     rec.get("dietary_type", ""),
            })

    if rows:
        write_rows(rows)
        # Update done set thread-safely
        with _done_lock:
            for d in batch:
                done_set.add((d["dish_name"], src_cuisine, tgt_cuisine))

    print(f"  [{batch_num}] ✓ {src_cuisine}→{tgt_cuisine} | "
          f"{batch[0]['dish_name']}{'...' if len(batch)>1 else ''} "
          f"| {len(rows)} rows | Total: {_total_written[0]}")
    return len(rows)


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    if not XAI_API_KEY:
        print("ERROR: XAI_API_KEY not set in .env")
        return

    dishes_df = load_dishes()
    cuisines  = sorted(dishes_df["cuisine"].unique().tolist())
    target_dishes = {
        c: dishes_df[dishes_df["cuisine"] == c]["dish_name"].tolist()
        for c in cuisines
    }

    print(f"Loaded {len(dishes_df)} dishes | {len(cuisines)} cuisines: {cuisines}")
    print(f"Model: {MODEL} | Batch: {BATCH_SIZE} | Workers: {MAX_WORKERS}")

    done = load_checkpoint()
    print(f"Checkpoint: {len(done)} combos already done")

    # Build all pending batches
    all_batches = []
    batch_num = 0
    for src_cuisine in cuisines:
        src_dishes = dishes_df[dishes_df["cuisine"] == src_cuisine].to_dict("records")
        for tgt_cuisine in cuisines:
            if tgt_cuisine == src_cuisine:
                continue
            tgt_list = target_dishes[tgt_cuisine]
            pending = [d for d in src_dishes
                       if (d["dish_name"], src_cuisine, tgt_cuisine) not in done]
            for i in range(0, len(pending), BATCH_SIZE):
                batch_num += 1
                all_batches.append((batch_num, pending[i:i+BATCH_SIZE], src_cuisine, tgt_cuisine, tgt_list))

    total_batches = len(all_batches)
    print(f"Pending batches: {total_batches} | Est. time @ {MAX_WORKERS} workers: "
          f"~{total_batches * 25 / MAX_WORKERS / 60:.0f} min")
    print("─" * 60)

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {
            executor.submit(process_batch, bn, batch, src, tgt, tgt_list, done): bn
            for bn, batch, src, tgt, tgt_list in all_batches
        }
        completed = 0
        for future in as_completed(futures):
            completed += 1
            try:
                future.result()
            except Exception as e:
                print(f"  [THREAD ERROR] {e}")

    print("\n" + "═" * 60)
    print(f"DONE. Total rows written: {_total_written[0]}")
    print(f"Output: {OUTPUT_CSV}")


if __name__ == "__main__":
    main()
