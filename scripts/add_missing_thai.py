#!/usr/bin/env python3
"""Add missing Thai dishes to dishes.csv."""

import csv
import os

CSV_PATH = os.path.join(os.path.dirname(__file__), '..', 'data', 'dishes.csv')

COLUMNS = [
    'dish_name', 'alternate_alias', 'cuisine_name', 'region', 'category',
    'sub_category', 'main_ingredient_category', 'dietary_type', 'course',
    'primary_protein', 'dish_importance_score', 'spice_level', 'sweet_score',
    'salt_score', 'sour_score', 'bitter_score', 'umami_score', 'spicy_score',
    'rich_fat_score', 'astringency_score', 'viscosity_score', 'crunchy_score',
    'chewy_score', 'aromatic_score', 'funk_score', 'rating', 'ingredients',
    'description', 'serving_temperature'
]

NEW_DISHES = [
    {
        'dish_name': 'Pad Priew Wan',
        'alternate_alias': 'Sweet and Sour Stir Fry',
        'cuisine_name': 'Thai',
        'region': 'Central Thailand',
        'category': 'Main Dish',
        'sub_category': 'Stir-Fry',
        'main_ingredient_category': 'Vegetable Dish',
        'dietary_type': 'Veg',
        'course': 'Main',
        'primary_protein': 'Vegetables',
        'dish_importance_score': '7.5',
        'spice_level': 'Mild',
        'sweet_score': '7', 'salt_score': '4', 'sour_score': '6',
        'bitter_score': '1', 'umami_score': '5', 'spicy_score': '2',
        'rich_fat_score': '4', 'astringency_score': '1', 'viscosity_score': '4',
        'crunchy_score': '5', 'chewy_score': '2', 'aromatic_score': '5',
        'funk_score': '1',
        'rating': '',
        'ingredients': 'bell peppers, onion, tomato, pineapple, cucumber, sugar, vinegar, soy sauce, ketchup, garlic, vegetable oil, cornstarch',
        'description': 'Pad Priew Wan is a Thai sweet and sour stir-fry with colorful vegetables and pineapple in a tangy-sweet sauce.',
        'serving_temperature': 'hot',
    },
    {
        'dish_name': 'Pad Pak Ruam',
        'alternate_alias': 'Thai Mixed Vegetable Stir-Fry',
        'cuisine_name': 'Thai',
        'region': 'Central Thailand',
        'category': 'Main Dish',
        'sub_category': 'Stir-Fry',
        'main_ingredient_category': 'Vegetable Dish',
        'dietary_type': 'Vegan',
        'course': 'Main',
        'primary_protein': 'Vegetables',
        'dish_importance_score': '5.5',
        'spice_level': 'Mild',
        'sweet_score': '1', 'salt_score': '5', 'sour_score': '1',
        'bitter_score': '2', 'umami_score': '5', 'spicy_score': '3',
        'rich_fat_score': '3', 'astringency_score': '1', 'viscosity_score': '2',
        'crunchy_score': '6', 'chewy_score': '2', 'aromatic_score': '5',
        'funk_score': '2',
        'rating': '',
        'ingredients': 'broccoli, baby corn, mushrooms, carrots, snap peas, garlic, soy sauce, oyster sauce substitute, vegetable oil, white pepper',
        'description': 'Pad Pak Ruam is a quick Thai stir-fry of mixed vegetables in savory sauce.',
        'serving_temperature': 'hot',
    },
    {
        'dish_name': 'Phak Thot',
        'alternate_alias': 'Thai Vegetable Tempura',
        'cuisine_name': 'Thai',
        'region': 'Central Thailand',
        'category': 'Appetizer',
        'sub_category': 'Fried Dish',
        'main_ingredient_category': 'Vegetable Dish',
        'dietary_type': 'Veg',
        'course': 'Appetizer',
        'primary_protein': 'Vegetables',
        'dish_importance_score': '5.0',
        'spice_level': 'Mild',
        'sweet_score': '1', 'salt_score': '4', 'sour_score': '1',
        'bitter_score': '1', 'umami_score': '4', 'spicy_score': '1',
        'rich_fat_score': '6', 'astringency_score': '1', 'viscosity_score': '2',
        'crunchy_score': '8', 'chewy_score': '2', 'aromatic_score': '3',
        'funk_score': '1',
        'rating': '',
        'ingredients': 'mixed vegetables, rice flour, wheat flour, baking powder, water, salt, vegetable oil, sweet chili sauce',
        'description': 'Phak Thot are crispy Thai vegetable fritters, deep-fried in a light batter and served with sweet chili sauce.',
        'serving_temperature': 'hot',
    },
    {
        'dish_name': 'Tod Man Khao Phot',
        'alternate_alias': 'Thai Corn Cakes',
        'cuisine_name': 'Thai',
        'region': 'Central Thailand',
        'category': 'Appetizer',
        'sub_category': 'Fritter',
        'main_ingredient_category': 'Corn Dish',
        'dietary_type': 'Veg',
        'course': 'Appetizer',
        'primary_protein': 'Corn',
        'dish_importance_score': '5.5',
        'spice_level': 'Medium',
        'sweet_score': '3', 'salt_score': '4', 'sour_score': '1',
        'bitter_score': '1', 'umami_score': '4', 'spicy_score': '3',
        'rich_fat_score': '5', 'astringency_score': '1', 'viscosity_score': '3',
        'crunchy_score': '7', 'chewy_score': '3', 'aromatic_score': '4',
        'funk_score': '1',
        'rating': '',
        'ingredients': 'corn kernels, red curry paste, kaffir lime leaves, long beans, rice flour, egg, sugar, salt, vegetable oil',
        'description': 'Tod Man Khao Phot are golden Thai corn fritters seasoned with curry paste and kaffir lime, crispy outside and tender inside.',
        'serving_temperature': 'hot',
    },
    {
        'dish_name': 'Poh Pia Thot',
        'alternate_alias': 'Thai Fried Spring Rolls',
        'cuisine_name': 'Thai',
        'region': 'Central Thailand',
        'category': 'Appetizer',
        'sub_category': 'Fried Roll',
        'main_ingredient_category': 'Vegetable Dish',
        'dietary_type': 'Veg',
        'course': 'Appetizer',
        'primary_protein': 'Vegetables',
        'dish_importance_score': '6.5',
        'spice_level': 'Mild',
        'sweet_score': '1', 'salt_score': '4', 'sour_score': '1',
        'bitter_score': '1', 'umami_score': '4', 'spicy_score': '1',
        'rich_fat_score': '5', 'astringency_score': '1', 'viscosity_score': '2',
        'crunchy_score': '8', 'chewy_score': '2', 'aromatic_score': '3',
        'funk_score': '1',
        'rating': '',
        'ingredients': 'spring roll wrappers, glass noodles, cabbage, carrots, mushrooms, garlic, soy sauce, white pepper, vegetable oil, sweet chili sauce',
        'description': 'Poh Pia Thot are crispy Thai fried spring rolls stuffed with vegetables and glass noodles.',
        'serving_temperature': 'hot',
    },
    {
        'dish_name': 'Poh Pia Sot',
        'alternate_alias': 'Thai Fresh Rolls',
        'cuisine_name': 'Thai',
        'region': 'Central Thailand',
        'category': 'Appetizer',
        'sub_category': 'Fresh Roll',
        'main_ingredient_category': 'Vegetable Dish',
        'dietary_type': 'Vegan',
        'course': 'Appetizer',
        'primary_protein': 'Vegetables',
        'dish_importance_score': '5.5',
        'spice_level': 'Mild',
        'sweet_score': '2', 'salt_score': '3', 'sour_score': '2',
        'bitter_score': '1', 'umami_score': '3', 'spicy_score': '1',
        'rich_fat_score': '1', 'astringency_score': '1', 'viscosity_score': '1',
        'crunchy_score': '5', 'chewy_score': '2', 'aromatic_score': '4',
        'funk_score': '1',
        'rating': '',
        'ingredients': 'rice paper, lettuce, cucumber, carrots, mint, cilantro, rice noodles, tofu, sweet chili dipping sauce',
        'description': 'Poh Pia Sot are fresh Thai spring rolls with raw vegetables and herbs wrapped in rice paper.',
        'serving_temperature': 'cold',
    },
    {
        'dish_name': 'Pad Phak Bung Fai Daeng',
        'alternate_alias': 'Thai Stir-Fried Water Spinach',
        'cuisine_name': 'Thai',
        'region': 'Central Thailand',
        'category': 'Side Dish',
        'sub_category': 'Stir-Fry',
        'main_ingredient_category': 'Vegetable Dish',
        'dietary_type': 'Vegan',
        'course': 'Side',
        'primary_protein': 'Vegetables',
        'dish_importance_score': '6.0',
        'spice_level': 'Medium',
        'sweet_score': '1', 'salt_score': '5', 'sour_score': '1',
        'bitter_score': '2', 'umami_score': '6', 'spicy_score': '5',
        'rich_fat_score': '3', 'astringency_score': '1', 'viscosity_score': '2',
        'crunchy_score': '5', 'chewy_score': '2', 'aromatic_score': '6',
        'funk_score': '3',
        'rating': '',
        'ingredients': 'morning glory (water spinach), garlic, thai chili, soybean paste, soy sauce, oyster sauce, vegetable oil',
        'description': 'Pad Phak Bung Fai Daeng is a fast-fired wok dish of morning glory with garlic and chili, a beloved Thai street food classic.',
        'serving_temperature': 'hot',
    },
    {
        'dish_name': 'Yam Wun Sen',
        'alternate_alias': 'Thai Glass Noodle Salad',
        'cuisine_name': 'Thai',
        'region': 'Central Thailand',
        'category': 'Salad',
        'sub_category': 'Salad',
        'main_ingredient_category': 'Noodle Dish',
        'dietary_type': 'Veg',
        'course': 'Salad',
        'primary_protein': 'Noodles',
        'dish_importance_score': '5.5',
        'spice_level': 'Medium',
        'sweet_score': '2', 'salt_score': '4', 'sour_score': '5',
        'bitter_score': '1', 'umami_score': '4', 'spicy_score': '4',
        'rich_fat_score': '1', 'astringency_score': '1', 'viscosity_score': '2',
        'crunchy_score': '3', 'chewy_score': '4', 'aromatic_score': '5',
        'funk_score': '2',
        'rating': '',
        'ingredients': 'glass noodles, onion, tomato, celery, lime juice, fish sauce substitute, sugar, chili flakes, cilantro, peanuts',
        'description': 'Yam Wun Sen is a tangy Thai glass noodle salad tossed with fresh vegetables in a spicy lime dressing.',
        'serving_temperature': 'room_temp',
    },
]


def main():
    # Read existing rows
    with open(CSV_PATH, 'r', newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        existing_rows = list(reader)

    existing_names = {row['dish_name'].strip().lower() for row in existing_rows}
    before_count = len(existing_rows)
    print(f"Before: {before_count} rows")

    added = []
    skipped = []
    for dish in NEW_DISHES:
        name_lower = dish['dish_name'].strip().lower()
        if name_lower in existing_names:
            skipped.append(dish['dish_name'])
        else:
            existing_rows.append(dish)
            existing_names.add(name_lower)
            added.append(dish['dish_name'])

    # Write back
    with open(CSV_PATH, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows(existing_rows)

    after_count = len(existing_rows)
    print(f"After:  {after_count} rows")
    print(f"Added {len(added)} dishes: {', '.join(added)}")
    if skipped:
        print(f"Skipped {len(skipped)} (already exist): {', '.join(skipped)}")

    # Verify
    with open(CSV_PATH, 'r', newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        all_rows = list(reader)
    thai_new = [r for r in all_rows if r['dish_name'] in {d['dish_name'] for d in NEW_DISHES}]
    print(f"\nVerification - found {len(thai_new)} of {len(NEW_DISHES)} target dishes:")
    for r in thai_new:
        print(f"  {r['dish_name']} | {r['cuisine_name']} | {r['category']} | {r['dietary_type']}")


if __name__ == '__main__':
    main()
