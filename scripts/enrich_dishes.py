#!/usr/bin/env python3
"""
TasteMate Data Enrichment Script
=================================
Uses Claude Haiku to re-score dead flavor dimensions (bitter, astringency, funk)
and enrich ingredients for all dishes in the CSV.

Usage:
  export ANTHROPIC_API_KEY="sk-ant-..."
  python3 scripts/enrich_dishes.py

Features:
  - Processes dishes in batches of 15 per API call
  - Saves progress after each batch (resume-safe)
  - Writes enriched data to data/dishes_enriched.csv
  - Logs progress to scripts/enrich_progress.json
"""

import os
import sys
import json
import time
import pandas as pd
import anthropic

# ── Configuration ──
BATCH_SIZE = 15
MODEL = "claude-haiku-4-20250414"
INPUT_CSV = os.path.join(os.path.dirname(__file__), "..", "data", "dishes.csv")
OUTPUT_CSV = os.path.join(os.path.dirname(__file__), "..", "data", "dishes_enriched.csv")
PROGRESS_FILE = os.path.join(os.path.dirname(__file__), "enrich_progress.json")
MAX_RETRIES = 3
RETRY_DELAY = 5  # seconds

# ── Scoring rubric sent to Claude ──
SYSTEM_PROMPT = """You are a food science expert. You will be given a batch of dishes with their names, cuisine, category, current ingredients, and current flavor scores.

Your job is to provide CORRECTED scores for 3 specific flavor dimensions, and ENRICHED ingredients.

## Scoring Rules (1-10 scale):

### bitter_score (1-10):
- 1: No bitterness at all (plain rice, bread, milk-based sweets)
- 2-3: Trace bitterness (most cooked vegetables, mild cheese)
- 4-5: Noticeable bitterness (coffee-based desserts, dark leafy greens like kale/radicchio, beer-battered items, eggplant/aubergine dishes, bitter gourd mild prep)
- 6-7: Prominent bitterness (espresso-forward dishes, amaro-based cocktails, charred/blackened items, fenugreek-heavy dishes, strong dark chocolate)
- 8-10: Intensely bitter (karela/bitter melon dishes, very dark coffee, strong amaro, raw dandelion greens)

### astringency_score (1-10):
Astringency = dry/puckering mouthfeel (tannins, certain acids)
- 1: No astringency (fatty/creamy/oily dishes, deep fried items, butter-based)
- 2-3: Slight dryness (lightly tannic items, mild tea, light wine sauces, some beans)
- 4-5: Moderate astringency (red wine reductions, pomegranate-based dishes, unripe banana, persimmon, strong green tea, cranberry dishes)
- 6-7: Strong astringency (heavily tannic preparations, raw persimmon, strong black tea dishes, red wine braised without sweetness)
- 8-10: Very astringent (raw unripe fruit, extremely tannic preparations)

### funk_score (1-10):
Funk = fermented/pungent/aged aromas and flavors
- 1: No funk (fresh/clean dishes, plain grains, fresh fruits, simple baked goods)
- 2-3: Mild funk (mild yogurt, light cheese like mozzarella, soy sauce in small amounts, light pickle)
- 4-5: Moderate funk (aged cheese like parmesan/cheddar, miso, doenjang, fish sauce dishes, kimchi, sauerkraut, blue cheese dressing, fermented black beans)
- 6-7: Strong funk (stinky tofu, natto, strong blue cheese, heavily fermented shrimp paste/belacan, aged fish sauce, surströmming lite)
- 8-10: Extremely funky (surströmming, very aged/stinky cheeses, strong fermented seafood, century egg)

### ingredients enrichment:
- Provide 8-12 key ingredients for each dish
- Include: main protein/starch, key vegetables, primary spices/herbs, cooking fats, sauces/pastes
- Use common English names
- Separate with commas
- Be specific: "basmati rice" not just "rice", "coconut milk" not just "milk"

## Response Format:
Return ONLY a JSON array. Each element must have:
{
  "idx": <the index number provided>,
  "bitter_score": <1-10>,
  "astringency_score": <1-10>,
  "funk_score": <1-10>,
  "ingredients": "<comma-separated list of 8-12 ingredients>"
}

IMPORTANT: Return ONLY the JSON array, no markdown, no explanation, no code blocks."""


def load_progress():
    """Load progress from file."""
    if os.path.exists(PROGRESS_FILE):
        with open(PROGRESS_FILE, "r") as f:
            return json.load(f)
    return {"completed_indices": [], "errors": []}


def save_progress(progress):
    """Save progress to file."""
    with open(PROGRESS_FILE, "w") as f:
        json.dump(progress, f)


def build_batch_prompt(batch_df):
    """Build the user prompt for a batch of dishes."""
    lines = []
    for idx, row in batch_df.iterrows():
        lines.append(
            f"[{idx}] {row['dish_name']} | Cuisine: {row['cuisine_name']} | "
            f"Category: {row.get('category', '')} | Sub: {row.get('sub_category', '')} | "
            f"Course: {row.get('course', '')} | "
            f"Current ingredients: {row.get('ingredients', '')} | "
            f"Current scores → bitter: {row.get('bitter_score', 1)}, "
            f"astringency: {row.get('astringency_score', 1)}, "
            f"funk: {row.get('funk_score', 1)}"
        )
    return (
        "Re-score the following dishes for bitter_score, astringency_score, funk_score "
        "and enrich their ingredients (8-12 items each).\n\n"
        + "\n".join(lines)
    )


def parse_response(text):
    """Parse Claude's JSON response."""
    # Strip markdown code blocks if present
    text = text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1]  # remove first line
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()

    return json.loads(text)


def process_batch(client, batch_df, retry=0):
    """Send a batch to Claude and parse the response."""
    prompt = build_batch_prompt(batch_df)

    try:
        response = client.messages.create(
            model=MODEL,
            max_tokens=4096,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}],
        )
        result_text = response.content[0].text
        results = parse_response(result_text)

        # Validate
        if not isinstance(results, list):
            raise ValueError("Response is not a list")

        validated = []
        for item in results:
            idx = item.get("idx")
            if idx is None:
                continue
            validated.append({
                "idx": int(idx),
                "bitter_score": max(1, min(10, int(item.get("bitter_score", 1)))),
                "astringency_score": max(1, min(10, int(item.get("astringency_score", 1)))),
                "funk_score": max(1, min(10, int(item.get("funk_score", 1)))),
                "ingredients": str(item.get("ingredients", "")),
            })
        return validated

    except Exception as e:
        if retry < MAX_RETRIES:
            print(f"    ⚠ Error: {e} — retrying in {RETRY_DELAY}s ({retry+1}/{MAX_RETRIES})")
            time.sleep(RETRY_DELAY)
            return process_batch(client, batch_df, retry + 1)
        else:
            print(f"    ✗ Failed after {MAX_RETRIES} retries: {e}")
            return []


def main():
    # Check API key
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("ERROR: Set ANTHROPIC_API_KEY environment variable first.")
        print("  export ANTHROPIC_API_KEY='sk-ant-...'")
        sys.exit(1)

    client = anthropic.Anthropic(api_key=api_key)

    # Load data
    print(f"Loading {INPUT_CSV}...")
    df = pd.read_csv(INPUT_CSV)
    total = len(df)
    print(f"Total dishes: {total}")

    # Load progress
    progress = load_progress()
    completed = set(progress["completed_indices"])
    print(f"Already completed: {len(completed)} dishes")

    # If we have an enriched file already, load it as our working copy
    if os.path.exists(OUTPUT_CSV) and len(completed) > 0:
        df = pd.read_csv(OUTPUT_CSV)
        print(f"Resuming from {OUTPUT_CSV}")
    else:
        # Start fresh
        df.to_csv(OUTPUT_CSV, index=False)

    # Find remaining indices
    remaining = [i for i in range(total) if i not in completed]
    print(f"Remaining: {len(remaining)} dishes")

    if not remaining:
        print("✓ All dishes already enriched!")
        return

    # Process in batches
    batches = [remaining[i:i + BATCH_SIZE] for i in range(0, len(remaining), BATCH_SIZE)]
    total_batches = len(batches)
    start_time = time.time()

    print(f"\nProcessing {total_batches} batches of {BATCH_SIZE}...\n")

    for batch_num, batch_indices in enumerate(batches, 1):
        batch_df = df.iloc[batch_indices]
        cuisines = batch_df["cuisine_name"].unique()

        elapsed = time.time() - start_time
        rate = (batch_num - 1) / elapsed * 60 if elapsed > 0 and batch_num > 1 else 0
        eta = (total_batches - batch_num + 1) / (rate / 60) if rate > 0 else 0

        print(
            f"  [{batch_num}/{total_batches}] "
            f"Dishes {batch_indices[0]}-{batch_indices[-1]} "
            f"({', '.join(cuisines[:3])}{'...' if len(cuisines) > 3 else ''}) "
            f"{'| ETA: ' + f'{eta/60:.0f}m' if eta > 0 else ''}"
        )

        results = process_batch(client, batch_df)

        if results:
            # Apply results to dataframe
            for item in results:
                idx = item["idx"]
                if 0 <= idx < total:
                    df.at[idx, "bitter_score"] = item["bitter_score"]
                    df.at[idx, "astringency_score"] = item["astringency_score"]
                    df.at[idx, "funk_score"] = item["funk_score"]
                    if item["ingredients"] and len(item["ingredients"]) > 10:
                        df.at[idx, "ingredients"] = item["ingredients"]
                    completed.add(idx)

            # Save progress
            progress["completed_indices"] = list(completed)
            save_progress(progress)

            # Save enriched CSV
            df.to_csv(OUTPUT_CSV, index=False)
            print(f"    ✓ {len(results)} dishes updated (total: {len(completed)}/{total})")
        else:
            # Log failed batch
            progress["errors"].append({"batch": batch_indices, "time": time.time()})
            save_progress(progress)
            print(f"    ✗ Batch failed, will retry on next run")

        # Rate limiting: ~1 request per second for Haiku
        time.sleep(1.0)

    elapsed = time.time() - start_time
    print(f"\n{'='*60}")
    print(f"DONE! Enriched {len(completed)}/{total} dishes in {elapsed/60:.1f} minutes")
    print(f"Output: {OUTPUT_CSV}")

    # Print summary stats
    enriched = pd.read_csv(OUTPUT_CSV)
    for col in ["bitter_score", "astringency_score", "funk_score"]:
        vals = pd.to_numeric(enriched[col], errors="coerce")
        mode_pct = (vals == vals.mode()[0]).mean() * 100 if len(vals.mode()) > 0 else 0
        print(f"  {col}: mean={vals.mean():.1f}, std={vals.std():.1f}, mode%={mode_pct:.0f}%")
    ing_lens = enriched["ingredients"].dropna().str.split(",").apply(len)
    print(f"  ingredients: avg={ing_lens.mean():.1f} items/dish")
    print(f"\nTo use: cp data/dishes_enriched.csv data/dishes.csv")


if __name__ == "__main__":
    main()
