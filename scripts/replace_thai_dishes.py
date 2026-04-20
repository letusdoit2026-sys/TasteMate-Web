#!/usr/bin/env python3
"""
Replace all Thai cuisine dishes in dishes.csv with a curated set of 68 dishes.
"""

import csv
import shutil
from pathlib import Path
from collections import Counter

DATA_DIR = Path("/Users/praveengiri/Documents/TasteAltlas/TasteMate-Web/data")
SRC = DATA_DIR / "dishes.csv"
BACKUP = DATA_DIR / "dishes_backup_before_thai_replace.csv"

# ── 1. Read original ──────────────────────────────────────────────────────────
with open(SRC, newline="", encoding="utf-8") as f:
    reader = csv.DictReader(f)
    fieldnames = reader.fieldnames
    all_rows = list(reader)

original_count = len(all_rows)
thai_before = sum(1 for r in all_rows if r["cuisine_name"] == "Thai")
print(f"Original total rows: {original_count}")
print(f"Existing Thai rows:  {thai_before}")

# ── 2. Backup ─────────────────────────────────────────────────────────────────
shutil.copy2(SRC, BACKUP)
print(f"Backup saved to:     {BACKUP}")

# ── 3. Remove old Thai rows ───────────────────────────────────────────────────
non_thai = [r for r in all_rows if r["cuisine_name"] != "Thai"]

# ── 4. Define new Thai dishes ─────────────────────────────────────────────────
def dish(
    dish_name, alternate_alias, region, category, sub_category,
    main_ingredient_category, dietary_type, course, primary_protein,
    dish_importance_score, spice_level,
    sweet, salt, sour, bitter, umami, spicy, rich_fat,
    astringency, viscosity, crunchy, chewy, aromatic, funk,
    ingredients, description, serving_temperature
):
    return {
        "dish_name": dish_name,
        "alternate_alias": alternate_alias,
        "cuisine_name": "Thai",
        "region": region,
        "category": category,
        "sub_category": sub_category,
        "main_ingredient_category": main_ingredient_category,
        "dietary_type": dietary_type,
        "course": course,
        "primary_protein": primary_protein,
        "dish_importance_score": str(dish_importance_score),
        "spice_level": spice_level,
        "sweet_score": str(sweet),
        "salt_score": str(salt),
        "sour_score": str(sour),
        "bitter_score": str(bitter),
        "umami_score": str(umami),
        "spicy_score": str(spicy),
        "rich_fat_score": str(rich_fat),
        "astringency_score": str(astringency),
        "viscosity_score": str(viscosity),
        "crunchy_score": str(crunchy),
        "chewy_score": str(chewy),
        "aromatic_score": str(aromatic),
        "funk_score": str(funk),
        "rating": "",
        "ingredients": ingredients,
        "description": description,
        "serving_temperature": serving_temperature,
    }

CT = "Central Thailand"
NT = "Northern Thailand"
ST = "Southern Thailand"

new_thai = [
    # ── APPETIZERS ─────────────────────────────────────────────────────────
    dish("Thai Spring Rolls", "Por Pia Tod", CT, "Appetizer", "Fried Roll",
         "Vegetable Dish", "Veg", "Appetizer", "Vegetables", 8.0, "Mild",
         2,4,1,1,4,1,6,1,2,9,2,3,1,
         "spring roll wrappers, glass noodles, cabbage, carrots, mushrooms, garlic, soy sauce, white pepper, vegetable oil, sweet chili sauce",
         "Deep-fried golden rolls filled with vegetables and glass noodles, served with sweet chili sauce.",
         "hot"),

    dish("Chicken Satay", "Sate Gai", CT, "Appetizer", "Skewer",
         "Chicken Dish", "Non-Veg", "Appetizer", "Chicken", 8.5, "Medium",
         3,4,1,1,7,2,5,1,3,2,4,7,2,
         "chicken breast, coconut milk, turmeric, lemongrass, peanut sauce, cucumber relish, cumin, coriander root, palm sugar, fish sauce, vegetable oil",
         "Marinated chicken skewers grilled and served with rich peanut dipping sauce and vinegary cucumber salad.",
         "hot"),

    dish("Fresh Summer Rolls", "Por Pia Sod", CT, "Appetizer", "Fresh Roll",
         "Vegetable Dish", "Veg", "Appetizer", "Vegetables", 7.0, "Mild",
         2,3,2,1,3,1,2,1,1,5,2,5,1,
         "rice paper, lettuce, cucumber, carrots, mint, cilantro, rice noodles, tofu, peanut sauce",
         "Fresh herbs, lettuce, and tofu wrapped in delicate rice paper, served with peanut sauce.",
         "cold"),

    dish("Thai Fried Calamari", "Pla Muk Tod", CT, "Appetizer", "Fried Dish",
         "Seafood Dish", "Pescatarian", "Appetizer", "Squid", 6.5, "Mild",
         2,4,1,1,5,2,6,1,2,8,5,3,2,
         "squid rings, rice flour, wheat flour, garlic, white pepper, salt, vegetable oil, sweet chili sauce, Sriracha, lime",
         "Lightly battered and deep-fried squid rings paired with sweet Sriracha or chili dipping sauce.",
         "hot"),

    dish("Thai Fish Cakes", "Tod Mun Pla", CT, "Appetizer", "Fritter",
         "Fish Dish", "Pescatarian", "Appetizer", "Fish", 8.0, "Medium",
         1,5,1,1,7,4,5,1,4,5,6,7,4,
         "white fish paste, red curry paste, kaffir lime leaves, long beans, fish sauce, egg, palm sugar, vegetable oil, cucumber relish, peanuts",
         "Savory patties made from fish paste and red curry, offering distinct chewy texture and herbal aroma.",
         "hot"),

    dish("Green Papaya Salad", "Som Tum", CT, "Appetizer", "Salad",
         "Vegetable Dish", "Pescatarian", "Appetizer", "Vegetables", 9.0, "Hot",
         3,5,7,1,6,7,1,2,1,8,2,5,5,
         "green papaya, lime juice, fish sauce, palm sugar, thai chilies, peanuts, dried shrimp, tomatoes, long beans, garlic",
         "Refreshing, spicy starter featuring shredded unripe papaya, lime juice, chilies, peanuts, and fish sauce.",
         "cold"),

    dish("Thai Chicken Wings", "Kai Tod", CT, "Appetizer", "Fried Dish",
         "Chicken Dish", "Non-Veg", "Appetizer", "Chicken", 7.0, "Medium",
         3,5,1,1,6,3,7,1,2,8,3,5,3,
         "chicken wings, fish sauce, garlic, cilantro root, white pepper, rice flour, vegetable oil, sweet chili sauce, lime",
         "Crispy wings marinated in fish sauce, garlic, and cilantro, or tossed in sticky sweet and spicy glaze.",
         "hot"),

    dish("Thai Shrimp Cakes", "Tod Mun Goong", CT, "Appetizer", "Fritter",
         "Shrimp Dish", "Pescatarian", "Appetizer", "Shrimp", 7.0, "Medium",
         1,5,1,1,7,3,5,1,3,7,4,5,3,
         "shrimp, garlic, white pepper, cilantro root, fish sauce, egg, breadcrumbs, vegetable oil, sweet chili sauce, lime",
         "Deep-fried breaded shrimp patties with crunchy exterior and succulent interior.",
         "hot"),

    dish("Fried Wontons", "Giew Tod", CT, "Appetizer", "Fried Pastry",
         "Pork Dish", "Non-Veg", "Appetizer", "Pork", 6.5, "Mild",
         1,4,1,1,6,1,6,1,2,8,3,3,2,
         "wonton wrappers, minced pork, shrimp, cream cheese, garlic, soy sauce, white pepper, vegetable oil, sweet chili sauce",
         "Crispy wrappers filled with seasoned minced pork, shrimp, or crab and cream cheese mixture.",
         "hot"),

    dish("Fried Tofu", "Tau Hu Tod", CT, "Appetizer", "Fried Dish",
         "Tofu Dish", "Vegan", "Appetizer", "Tofu", 6.0, "Mild",
         3,3,1,1,4,2,5,1,2,7,3,2,2,
         "firm tofu, rice flour, garlic, salt, white pepper, vegetable oil, sweet chili sauce, peanuts, cilantro",
         "Golden cubes of deep-fried tofu served with sweet chili sauce topped with crushed peanuts.",
         "hot"),

    dish("Golden Bags", "Tung Tong", CT, "Appetizer", "Fried Pastry",
         "Chicken Dish", "Non-Veg", "Appetizer", "Chicken", 6.0, "Mild",
         1,4,1,1,5,1,5,1,2,7,3,3,2,
         "wonton wrappers, minced chicken, shrimp, water chestnuts, garlic, soy sauce, white pepper, vegetable oil, sweet chili sauce, cilantro",
         "Crispy wonton purses filled with savory mixture of minced chicken, shrimp, and vegetables.",
         "hot"),

    dish("Thai Curry Puffs", "Karipap", CT, "Appetizer", "Fried Pastry",
         "Potato Dish", "Veg", "Appetizer", "Potatoes", 6.5, "Mild",
         2,4,1,1,4,2,6,1,3,7,2,5,1,
         "pastry dough, potatoes, onions, yellow curry powder, turmeric, sugar, salt, vegetable oil, butter",
         "Flaky pastry shells filled with mild yellow curry mixture of potatoes, onions, and vegetables.",
         "hot"),

    dish("Chicken Lettuce Wraps", "", CT, "Appetizer", "Stir-Fry",
         "Chicken Dish", "Non-Veg", "Appetizer", "Chicken", 6.0, "Medium",
         2,5,2,1,7,3,3,1,2,5,3,5,3,
         "minced chicken, lettuce leaves, ginger, mushrooms, soy sauce, oyster sauce, garlic, water chestnuts, sesame oil, Thai chilies",
         "Healthy DIY starter featuring minced chicken stir-fried with ginger and mushrooms, served with cool lettuce leaves.",
         "hot"),

    dish("Steamed Dumplings", "Kanom Jeeb", CT, "Appetizer", "Dumpling",
         "Pork Dish", "Non-Veg", "Appetizer", "Pork", 6.5, "Mild",
         1,4,1,1,6,1,4,1,3,1,4,3,2,
         "wonton wrappers, minced pork, shrimp, water chestnuts, garlic, soy sauce, sesame oil, white pepper, fried garlic, sweet soy sauce",
         "Thai-style shumai filled with minced pork and shrimp, served with tangy soy-based dipping sauce.",
         "hot"),

    dish("Thai Corn Fritters", "Tod Man Khao Pod", CT, "Appetizer", "Fritter",
         "Corn Dish", "Veg", "Appetizer", "Corn", 6.0, "Medium",
         3,4,1,1,4,3,5,1,3,7,3,4,1,
         "corn kernels, red curry paste, kaffir lime leaves, long beans, rice flour, egg, sugar, salt, vegetable oil",
         "Crispy, sweet, and savory patties made from fresh corn kernels mixed with red curry paste and lime leaves.",
         "hot"),

    dish("Larb Gai", "", CT, "Appetizer", "Salad",
         "Chicken Dish", "Non-Veg", "Appetizer", "Chicken", 8.0, "Hot",
         1,5,6,1,6,6,2,1,1,3,3,7,4,
         "minced chicken, lime juice, fish sauce, toasted rice powder, shallots, cilantro, mint, Thai chilies, scallions, lettuce",
         "Zesty minced chicken salad seasoned with lime, fish sauce, chilies, and toasted rice powder, often served as lettuce wrap.",
         "room_temp"),

    dish("Shrimp in a Blanket", "Goong Hom Pha", CT, "Appetizer", "Fried Dish",
         "Shrimp Dish", "Pescatarian", "Appetizer", "Shrimp", 6.5, "Mild",
         1,4,1,1,5,1,5,1,2,8,3,3,2,
         "whole prawns, spring roll wrappers, garlic, white pepper, sesame oil, vegetable oil, sweet chili sauce, plum sauce",
         "Whole prawns wrapped in spring roll pastry and deep-fried until shatteringly crisp.",
         "hot"),

    dish("Sun-Dried Beef", "Neua Dad Deow", CT, "Appetizer", "Fried Dish",
         "Beef Dish", "Non-Veg", "Appetizer", "Beef", 6.5, "Medium",
         2,5,1,1,7,3,5,1,1,5,7,4,3,
         "beef strips, fish sauce, oyster sauce, palm sugar, garlic, white pepper, sesame seeds, vegetable oil, sticky rice, nam jim jaew",
         "Deep-fried marinated beef strips, similar to jerky but tender, served with sticky rice and spicy sauce.",
         "hot"),

    dish("Waterfall Beef Salad", "Nam Tok", CT, "Appetizer", "Salad",
         "Beef Dish", "Non-Veg", "Appetizer", "Beef", 7.5, "Hot",
         1,5,6,1,7,6,3,1,1,2,5,7,4,
         "grilled beef, lime juice, fish sauce, toasted rice powder, shallots, cilantro, mint, Thai chilies, scallions, dried chili flakes",
         "Slices of grilled beef tossed in spicy and herbaceous dressing with toasted rice powder.",
         "room_temp"),

    dish("Coconut Shrimp", "", CT, "Appetizer", "Fried Dish",
         "Shrimp Dish", "Pescatarian", "Appetizer", "Shrimp", 6.5, "Mild",
         4,3,1,1,5,1,6,1,2,8,3,4,1,
         "butterfly shrimp, shredded coconut, coconut milk, rice flour, egg, panko breadcrumbs, vegetable oil, pineapple sauce, plum sauce",
         "Butterfly shrimp coated in coconut-infused batter and fried until golden, served with pineapple or plum sauce.",
         "hot"),

    # ── MAIN COURSES ───────────────────────────────────────────────────────
    # Noodles
    dish("Pad Thai", "", CT, "Main Dish", "Stir-Fry",
         "Noodle Dish", "Non-Veg", "Main", "Shrimp", 10.0, "Medium",
         4,5,4,1,7,3,4,1,2,5,4,5,4,
         "rice noodles, shrimp, egg, tamarind paste, fish sauce, palm sugar, bean sprouts, peanuts, garlic, scallions, lime, dried shrimp",
         "Stir-fried thin rice noodles with tamarind sauce, sprouts, and peanuts.",
         "hot"),

    dish("Pad See Ew", "", CT, "Main Dish", "Stir-Fry",
         "Noodle Dish", "Non-Veg", "Main", "Chicken", 9.0, "Mild",
         3,6,1,1,8,1,5,1,3,2,5,4,3,
         "wide rice noodles, chicken, Chinese broccoli, egg, dark soy sauce, light soy sauce, oyster sauce, garlic, vegetable oil, white pepper",
         "Savory, smoky wide flat noodles with Chinese broccoli and sweet soy.",
         "hot"),

    dish("Drunken Noodles", "Pad Kee Mao", CT, "Main Dish", "Stir-Fry",
         "Noodle Dish", "Non-Veg", "Main", "Chicken", 9.0, "Hot",
         2,5,1,1,7,7,4,1,2,3,5,8,3,
         "wide rice noodles, chicken, holy basil, Thai chilies, bell peppers, garlic, fish sauce, oyster sauce, soy sauce, egg, vegetable oil",
         "Spicy wide noodles with basil, chilies, and bell peppers.",
         "hot"),

    dish("Khao Soi", "", NT, "Main Dish", "Noodle Soup",
         "Noodle Dish", "Non-Veg", "Main", "Chicken", 8.5, "Medium",
         2,5,2,1,7,4,7,1,5,4,4,8,3,
         "egg noodles, coconut milk, red curry paste, chicken, crispy noodles, shallots, pickled mustard greens, lime, turmeric, fish sauce",
         "Northern Thai coconut curry noodle soup topped with crispy noodles.",
         "hot"),

    dish("Pad Woon Sen", "", CT, "Main Dish", "Stir-Fry",
         "Noodle Dish", "Non-Veg", "Main", "Egg", 7.0, "Mild",
         2,5,1,1,6,2,3,1,2,3,3,4,2,
         "glass noodles, egg, carrots, cabbage, mushrooms, onion, garlic, soy sauce, oyster sauce, white pepper, vegetable oil",
         "Stir-fried glass (mung bean) noodles with eggs and vegetables.",
         "hot"),

    dish("Boat Noodles", "Kuay Teow Reua", CT, "Main Dish", "Noodle Soup",
         "Noodle Dish", "Non-Veg", "Main", "Beef", 7.5, "Medium",
         1,6,1,1,9,3,5,1,4,2,4,7,5,
         "rice noodles, beef, pork blood, dark soy sauce, star anise, cinnamon, garlic, bean sprouts, Chinese celery, dried chilies, fish sauce",
         "Rich, dark broth noodle soup with beef or pork.",
         "hot"),

    dish("Rad Na", "", CT, "Main Dish", "Noodle Dish",
         "Noodle Dish", "Non-Veg", "Main", "Pork", 7.0, "Mild",
         2,5,1,1,7,1,4,1,6,2,4,3,3,
         "wide rice noodles, pork, Chinese broccoli, garlic, soy sauce, oyster sauce, cornstarch, fermented soybean, white pepper, vegetable oil",
         "Wide noodles topped with thick, savory gravy and Chinese broccoli.",
         "hot"),

    dish("Kuay Teow Nua", "", CT, "Main Dish", "Noodle Soup",
         "Noodle Dish", "Non-Veg", "Main", "Beef", 7.0, "Mild",
         1,5,1,1,8,2,4,1,3,2,5,5,3,
         "rice noodles, beef slices, beef broth, bean sprouts, Chinese celery, garlic oil, soy sauce, white pepper, cilantro, fried garlic",
         "Thai-style beef noodle soup with tender slices of meat.",
         "hot"),

    # Stir-Fry Favorites
    dish("Pad Kra Pao", "", CT, "Main Dish", "Stir-Fry",
         "Pork Dish", "Non-Veg", "Main", "Pork", 9.5, "Hot",
         1,6,1,1,8,7,4,1,2,2,3,9,4,
         "minced pork, holy basil, Thai chilies, garlic, fish sauce, oyster sauce, soy sauce, sugar, fried egg, jasmine rice, vegetable oil",
         "Minced meat (often pork or chicken) with holy basil and chili.",
         "hot"),

    dish("Cashew Chicken", "Gai Pad Med Mamuang", CT, "Main Dish", "Stir-Fry",
         "Chicken Dish", "Non-Veg", "Main", "Chicken", 8.0, "Medium",
         3,5,1,1,7,3,5,1,2,6,3,5,2,
         "chicken, roasted cashews, dried chilies, onion, bell peppers, soy sauce, oyster sauce, fish sauce, sugar, garlic, vegetable oil",
         "Stir-fry with roasted cashews and chili paste.",
         "hot"),

    dish("Pad Priew Wan", "Sweet and Sour Stir-Fry", CT, "Main Dish", "Stir-Fry",
         "Vegetable Dish", "Veg", "Main", "Vegetables", 7.5, "Mild",
         7,4,6,1,5,2,3,1,4,5,2,4,1,
         "bell peppers, onion, tomato, pineapple, cucumber, sugar, vinegar, soy sauce, ketchup, garlic, vegetable oil, cornstarch",
         "Sweet and sour stir-fry with colorful vegetables and pineapple in tangy-sweet sauce.",
         "hot"),

    dish("Pad Ginger", "Gai Pad Khing", CT, "Main Dish", "Stir-Fry",
         "Chicken Dish", "Non-Veg", "Main", "Chicken", 7.0, "Medium",
         2,5,1,1,6,3,3,1,2,4,3,7,2,
         "chicken, fresh ginger, mushrooms, onion, bell peppers, soy sauce, oyster sauce, sesame oil, garlic, scallions, vegetable oil",
         "Sliced chicken or beef stir-fried with heavy amounts of fresh ginger.",
         "hot"),

    dish("Pad Prik Khing", "", CT, "Main Dish", "Stir-Fry",
         "Pork Dish", "Non-Veg", "Main", "Pork", 7.5, "Hot",
         2,5,1,1,7,6,4,1,2,5,3,7,4,
         "pork, red curry paste, long beans, kaffir lime leaves, fish sauce, palm sugar, vegetable oil, garlic",
         "A dry curry stir-fry featuring string beans and red curry paste.",
         "hot"),

    dish("Garlic Pepper Stir-Fry", "Moo Gratiem / Gai Gratiem", CT, "Main Dish", "Stir-Fry",
         "Pork Dish", "Non-Veg", "Main", "Pork", 7.0, "Medium",
         1,5,1,1,7,3,4,1,2,3,4,6,2,
         "pork or chicken, fried garlic, black pepper, white pepper, soy sauce, oyster sauce, cilantro root, vegetable oil, jasmine rice",
         "Simple, savory stir-fry focused on fried garlic and black pepper.",
         "hot"),

    dish("Kana Moo Krob", "", CT, "Main Dish", "Stir-Fry",
         "Pork Dish", "Non-Veg", "Main", "Pork", 7.0, "Medium",
         2,5,1,2,7,3,7,1,2,7,3,5,3,
         "Chinese broccoli, crispy pork belly, garlic, oyster sauce, soy sauce, fish sauce, sugar, Thai chilies, vegetable oil",
         "Stir-fried Chinese broccoli with crispy pork belly.",
         "hot"),

    dish("Mixed Vegetable Stir-Fry", "Pad Pak Ruam Mit", CT, "Main Dish", "Stir-Fry",
         "Vegetable Dish", "Vegan", "Main", "Vegetables", 6.0, "Mild",
         1,5,1,2,5,2,3,1,2,6,2,4,2,
         "broccoli, baby corn, mushrooms, carrots, snap peas, garlic, soy sauce, oyster sauce, vegetable oil, white pepper",
         "Healthy assortment of seasonal greens in oyster sauce.",
         "hot"),

    # Classic Curries
    dish("Green Curry", "Kaeng Khiao Wan", CT, "Main Dish", "Curry",
         "Chicken Dish", "Non-Veg", "Main", "Chicken", 9.5, "Hot",
         3,5,1,1,7,7,7,1,5,2,3,9,3,
         "green curry paste, coconut milk, chicken, Thai eggplant, bamboo shoots, Thai basil, kaffir lime leaves, fish sauce, palm sugar, Thai chilies",
         "Creamy coconut curry with green chilies and Thai basil.",
         "hot"),

    dish("Red Curry", "Gaeng Daeng", CT, "Main Dish", "Curry",
         "Chicken Dish", "Non-Veg", "Main", "Chicken", 9.0, "Hot",
         3,5,1,1,7,6,7,1,5,2,3,8,3,
         "red curry paste, coconut milk, chicken, bamboo shoots, bell peppers, Thai basil, kaffir lime leaves, fish sauce, palm sugar",
         "Bolder, spicy curry based on red chili paste.",
         "hot"),

    dish("Yellow Curry", "Kaeng Kari", CT, "Main Dish", "Curry",
         "Chicken Dish", "Non-Veg", "Main", "Chicken", 8.0, "Medium",
         3,4,1,1,6,3,7,1,5,2,3,7,2,
         "yellow curry paste, coconut milk, chicken, potatoes, onions, turmeric, cinnamon, fish sauce, palm sugar, bay leaves",
         "Milder, turmeric-based curry often featuring potatoes.",
         "hot"),

    dish("Massaman Curry", "", CT, "Main Dish", "Curry",
         "Beef Dish", "Non-Veg", "Main", "Beef", 9.0, "Medium",
         4,4,2,1,7,3,7,1,5,3,4,8,3,
         "massaman curry paste, coconut milk, beef, potatoes, peanuts, onions, cinnamon, cardamom, tamarind, fish sauce, palm sugar, bay leaves",
         "Rich, peanut-inflected curry with warm spices like cinnamon and cardamom.",
         "hot"),

    dish("Panang Curry", "", CT, "Main Dish", "Curry",
         "Chicken Dish", "Non-Veg", "Main", "Chicken", 8.5, "Medium",
         3,5,1,1,7,4,7,1,6,2,3,8,3,
         "panang curry paste, coconut milk, chicken, kaffir lime leaves, crushed peanuts, Thai basil, fish sauce, palm sugar, red chilies",
         "Thicker, saltier red curry with lime leaf and crushed peanuts.",
         "hot"),

    dish("Jungle Curry", "Gaeng Pa", CT, "Main Dish", "Curry",
         "Chicken Dish", "Non-Veg", "Main", "Chicken", 7.0, "Hot",
         1,5,1,2,6,9,2,1,3,3,3,8,4,
         "jungle curry paste, chicken, bamboo shoots, green peppercorns, Thai eggplant, krachai (fingerroot), holy basil, fish sauce, long beans, Thai chilies",
         "Watery, highly spicy curry made without coconut milk.",
         "hot"),

    dish("Pineapple Curry", "", CT, "Main Dish", "Curry",
         "Shrimp Dish", "Pescatarian", "Main", "Shrimp", 7.0, "Medium",
         5,4,2,1,6,4,6,1,4,2,3,7,3,
         "red curry paste, coconut milk, shrimp, pineapple chunks, cherry tomatoes, Thai basil, kaffir lime leaves, fish sauce, palm sugar",
         "Red curry base with sweet pineapple chunks and cherry tomatoes.",
         "hot"),

    dish("Duck Curry", "", CT, "Main Dish", "Curry",
         "Duck Dish", "Non-Veg", "Main", "Duck", 7.5, "Medium",
         4,5,1,1,8,4,8,1,5,2,4,8,3,
         "red curry paste, coconut milk, roasted duck, grapes, pineapple, cherry tomatoes, Thai basil, kaffir lime leaves, fish sauce, palm sugar",
         "Roasted duck in red curry with grapes, pineapple, and tomatoes.",
         "hot"),

    # Rice & Specialist Dishes
    dish("Thai Fried Rice", "Khao Pad", CT, "Main Dish", "Rice Dish",
         "Rice Dish", "Non-Veg", "Main", "Egg", 8.5, "Mild",
         2,5,1,1,6,2,4,1,2,3,3,4,2,
         "jasmine rice, egg, onion, tomato, garlic, soy sauce, fish sauce, white pepper, scallions, vegetable oil, lime, cucumber",
         "Classic fried rice with egg, onions, and tomato.",
         "hot"),

    dish("Pineapple Fried Rice", "Khao Pad Sapparod", CT, "Main Dish", "Rice Dish",
         "Rice Dish", "Non-Veg", "Main", "Shrimp", 7.5, "Mild",
         4,4,1,1,5,1,4,1,2,4,3,4,2,
         "jasmine rice, pineapple, shrimp, cashews, raisins, egg, curry powder, soy sauce, fish sauce, scallions, vegetable oil",
         "Visually striking rice often served in a pineapple shell.",
         "hot"),

    dish("Basil Fried Rice", "Khao Pad Krapao", CT, "Main Dish", "Rice Dish",
         "Rice Dish", "Non-Veg", "Main", "Chicken", 7.5, "Hot",
         1,5,1,1,7,6,4,1,2,3,3,8,3,
         "jasmine rice, chicken, holy basil, Thai chilies, garlic, fish sauce, soy sauce, oyster sauce, egg, vegetable oil",
         "Spicy variation of fried rice using holy basil and chilies.",
         "hot"),

    dish("Crab Fried Rice", "Khao Pad Pu", CT, "Main Dish", "Rice Dish",
         "Seafood Dish", "Pescatarian", "Main", "Crab", 7.5, "Mild",
         2,5,1,1,7,1,4,1,2,3,3,4,2,
         "jasmine rice, crab meat, egg, garlic, soy sauce, fish sauce, white pepper, scallions, lime, vegetable oil, cilantro",
         "Premium fried rice featuring lumps of sweet crab meat.",
         "hot"),

    dish("Crying Tiger", "Suea Rong Hai", CT, "Main Dish", "Grilled Dish",
         "Beef Dish", "Non-Veg", "Main", "Beef", 7.5, "Hot",
         1,5,4,1,8,6,5,1,1,2,6,6,4,
         "grilled beef steak, nam jim jaew, toasted rice powder, fish sauce, lime juice, dried chili flakes, shallots, cilantro, sticky rice",
         "Marinated grilled steak served with spicy jaew dipping sauce.",
         "hot"),

    dish("Larb", "", CT, "Main Dish", "Salad",
         "Pork Dish", "Non-Veg", "Main", "Pork", 8.0, "Hot",
         1,5,6,1,6,6,3,1,1,3,3,7,4,
         "minced pork, lime juice, fish sauce, toasted rice powder, shallots, cilantro, mint, Thai chilies, scallions, sticky rice",
         "Zesty minced meat salad (chicken or pork) with lime and toasted rice.",
         "room_temp"),

    dish("Gai Yang", "", CT, "Main Dish", "Grilled Dish",
         "Chicken Dish", "Non-Veg", "Main", "Chicken", 8.0, "Medium",
         2,5,2,1,7,3,5,1,1,4,4,7,3,
         "whole chicken, lemongrass, fish sauce, garlic, cilantro root, white pepper, soy sauce, sticky rice, som tum, nam jim jaew",
         "Thai-style grilled chicken, marinated in lemongrass and fish sauce.",
         "hot"),

    dish("Steam Ginger Fish", "Pla Neung Khing", CT, "Main Dish", "Steamed Dish",
         "Fish Dish", "Pescatarian", "Main", "Fish", 7.0, "Mild",
         2,5,2,1,7,2,4,1,3,1,3,6,3,
         "whole fish, fresh ginger, scallions, soy sauce, sesame oil, cilantro, dried mushrooms, Chinese celery, garlic",
         "Whole fish or fillets steamed with ginger, scallions, and soy.",
         "hot"),

    dish("Pla Rad Prik", "", CT, "Main Dish", "Fried Dish",
         "Fish Dish", "Pescatarian", "Main", "Fish", 7.5, "Hot",
         4,5,3,1,7,6,6,1,4,6,3,7,4,
         "whole fish, garlic, Thai chilies, fish sauce, tamarind, palm sugar, shallots, vegetable oil, cilantro, rice flour",
         "Deep-fried whole fish topped with spicy three-flavored chili sauce.",
         "hot"),

    dish("Khao Kha Moo", "", CT, "Main Dish", "Braised Dish",
         "Pork Dish", "Non-Veg", "Main", "Pork", 7.5, "Mild",
         3,5,1,1,8,2,8,1,4,1,5,6,3,
         "pork leg, five-spice powder, dark soy sauce, garlic, cilantro root, star anise, cinnamon, palm sugar, hard-boiled egg, pickled mustard greens, jasmine rice",
         "Slow-braised pork leg served over rice with pickled greens.",
         "hot"),

    dish("Khao Mok Gai", "", CT, "Main Dish", "Rice Dish",
         "Rice Dish", "Non-Veg", "Main", "Chicken", 7.0, "Mild",
         2,4,1,1,6,2,5,1,3,2,4,7,2,
         "jasmine rice, chicken, turmeric, cumin, cinnamon, cardamom, bay leaves, onion, garlic, sweet chili sauce, cucumber, cilantro",
         "Thai-style chicken biryani (yellow rice) served with sweet chili sauce.",
         "hot"),

    dish("Yum Woon Sen", "", CT, "Main Dish", "Salad",
         "Noodle Dish", "Non-Veg", "Main", "Shrimp", 7.0, "Hot",
         2,5,5,1,6,5,2,1,2,3,3,5,4,
         "glass noodles, shrimp, minced pork, celery, onion, tomato, lime juice, fish sauce, sugar, Thai chilies, cilantro, peanuts",
         "Spicy glass noodle salad with shrimp and minced pork.",
         "room_temp"),

    dish("Tom Yum Soup", "Tom Yum Goong", CT, "Main Dish", "Soup",
         "Shrimp Dish", "Pescatarian", "Main", "Shrimp", 10.0, "Hot",
         1,5,7,1,8,7,3,1,3,1,3,9,4,
         "shrimp, lemongrass, galangal, kaffir lime leaves, Thai chilies, mushrooms, fish sauce, lime juice, cilantro, tom yum paste, coconut milk",
         "Hot and sour soup served in large fire pot as an entree.",
         "hot"),

    dish("Tom Kha Soup", "Tom Kha Gai", CT, "Main Dish", "Soup",
         "Chicken Dish", "Non-Veg", "Main", "Chicken", 9.0, "Medium",
         2,5,5,1,7,3,7,1,4,1,3,9,3,
         "chicken, coconut milk, galangal, lemongrass, kaffir lime leaves, mushrooms, fish sauce, lime juice, Thai chilies, cilantro",
         "Creamy coconut soup served as primary dish with rice.",
         "hot"),

    dish("Khua Kling", "", ST, "Main Dish", "Stir-Fry",
         "Pork Dish", "Non-Veg", "Main", "Pork", 7.0, "Hot",
         1,5,1,1,7,9,4,1,2,2,4,8,5,
         "minced pork, southern curry paste, kaffir lime leaves, lemongrass, turmeric, shrimp paste, Thai chilies, fish sauce, palm sugar",
         "Southern Thai dry-fried minced meat curry that is extremely spicy.",
         "hot"),

    # ── DESSERTS ────────────────────────────────────────────────────────────
    dish("Mango Sticky Rice", "Khao Niew Mamuang", CT, "Dessert", "Sweet",
         "Rice Dish", "Vegan", "Dessert", "Rice", 9.5, "Low",
         9,1,1,1,1,1,5,1,4,1,5,4,1,
         "sticky rice, coconut milk, ripe mango, palm sugar, salt, sesame seeds, mung beans",
         "The king of Thai desserts -- warm sweet glutinous rice soaked in coconut milk with ripe mango.",
         "room_temp"),

    dish("Fried Bananas", "Kluay Tod", CT, "Dessert", "Fried Pastry",
         "Fruit Dish", "Vegan", "Dessert", "Banana", 7.0, "Low",
         8,1,1,1,1,1,6,1,3,7,3,3,1,
         "bananas, rice flour, shredded coconut, sugar, salt, baking powder, sesame seeds, vegetable oil, honey",
         "Sliced bananas battered in rice flour and coconut, deep-fried until crunchy, drizzled with honey.",
         "hot"),

    dish("Thai Coconut Custard", "Khanom Tuay", CT, "Dessert", "Custard",
         "Coconut Dish", "Vegan", "Dessert", "Coconut", 6.5, "Low",
         8,1,1,1,1,1,6,1,6,1,2,4,1,
         "coconut milk, rice flour, sugar, pandan extract, salt, tapioca starch, water",
         "Two-layered steamed pudding with sweet green pandan jelly bottom and thick coconut cream top.",
         "room_temp"),

    dish("Sweet Sticky Rice with Custard", "Khao Niew Sang Kaya", CT, "Dessert", "Sweet",
         "Rice Dish", "Veg", "Dessert", "Rice", 6.5, "Low",
         9,1,1,1,1,1,5,1,5,1,5,3,1,
         "sticky rice, coconut milk, egg, palm sugar, salt, pandan leaves",
         "Similar to mango sticky rice but topped with firm steamed egg and coconut milk custard.",
         "room_temp"),

    dish("Roti with Condensed Milk", "Roti Gluay", CT, "Dessert", "Flatbread",
         "Wheat Dish", "Veg", "Dessert", "Wheat", 7.0, "Low",
         8,1,1,1,1,1,7,1,3,4,3,3,1,
         "wheat flour, butter, egg, condensed milk, sugar, salt, vegetable oil, banana (optional)",
         "Flaky, buttery flatbread pan-fried and drizzled with sweetened condensed milk and sugar.",
         "hot"),

    # ── BEVERAGES ──────────────────────────────────────────────────────────
    dish("Thai Iced Tea", "Cha Yen", CT, "Drink", "Beverage",
         "Milk Dish", "Veg", "Drink", "Milk", 9.0, "Low",
         8,1,1,2,1,1,5,3,3,1,1,5,1,
         "Thai tea mix, star anise, orange blossom water, half-and-half, condensed milk, sugar, ice",
         "Strong black tea brewed with star anise and orange blossom, topped with condensed milk.",
         "cold"),

    dish("Thai Iced Coffee", "Oliang", CT, "Drink", "Beverage",
         "Milk Dish", "Veg", "Drink", "Milk", 7.0, "Low",
         7,1,1,4,1,1,4,2,3,1,1,5,1,
         "Thai coffee blend, condensed milk, evaporated milk, sugar, corn, soy, ice",
         "Dark roasted coffee blend served over ice with thick layer of cream.",
         "cold"),

    dish("Pink Milk", "Nom Yen", CT, "Drink", "Beverage",
         "Milk Dish", "Veg", "Drink", "Milk", 5.0, "Low",
         9,1,1,1,1,1,4,1,3,1,1,2,1,
         "sala fruit syrup, evaporated milk, condensed milk, sugar, ice, water",
         "Bright pink sweet drink made from Sala fruit syrup and evaporated milk.",
         "cold"),

    dish("Fresh Whole Coconut", "Nam Maprao", CT, "Drink", "Beverage",
         "Coconut Dish", "Vegan", "Drink", "Coconut", 6.0, "Low",
         5,1,1,1,1,1,3,1,2,1,2,2,1,
         "young coconut, coconut water, coconut meat",
         "Young coconut with top hacked off to drink the water and scoop out the meat.",
         "cold"),
]

# ── 5. Combine and write ──────────────────────────────────────────────────────
final_rows = non_thai + new_thai
final_count = len(final_rows)

with open(SRC, "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(final_rows)

# ── 6. Report ──────────────────────────────────────────────────────────────────
thai_added = len(new_thai)
print(f"\n{'='*50}")
print(f"BEFORE: {original_count} total rows ({thai_before} Thai)")
print(f"AFTER:  {final_count} total rows ({thai_added} Thai)")
print(f"Thai dishes added: {thai_added}")

# Breakdown by course
print(f"\nBreakdown by course:")
course_counts = Counter(d["course"] for d in new_thai)
for course, count in sorted(course_counts.items()):
    print(f"  {course}: {count}")

# Breakdown by dietary_type
print(f"\nBreakdown by dietary_type:")
diet_counts = Counter(d["dietary_type"] for d in new_thai)
for diet, count in sorted(diet_counts.items()):
    print(f"  {diet}: {count}")

# Check for duplicates
names = [d["dish_name"] for d in new_thai]
dupes = [name for name, cnt in Counter(names).items() if cnt > 1]
if dupes:
    print(f"\nWARNING: Duplicate dish names found: {dupes}")
else:
    print(f"\nNo duplicate dish names within Thai cuisine.")

print(f"\nDone! Saved to {SRC}")
