#!/usr/bin/env python3
"""Replace ALL Indian dishes in dishes.csv with curated 120 dishes from PDF."""

import pandas as pd
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CSV_PATH = os.path.join(BASE_DIR, "data", "dishes.csv")

# ══════════════════════════════════════════════════════════════════════════════
#  40 APPETIZERS
# ══════════════════════════════════════════════════════════════════════════════
appetizers = [
    # dish_name, alternate_alias, region, category, sub_category, main_ingredient_category, dietary_type, primary_protein, dish_importance_score, spice_level, sweet, salt, sour, bitter, umami, spicy, rich_fat, astringency, viscosity, crunchy, chewy, aromatic, funk, ingredients, description, serving_temperature
    ("Vegetable Samosa", "", "North Indian", "Appetizer", "Fried Snack", "Vegetable Dish", "Veg", "", 9.0, "Medium", 1, 5, 2, 1, 3, 4, 6, 1, 3, 8, 2, 6, 1, "potatoes, peas, cumin, coriander, green chilies, flour, oil", "Crispy pastry shells stuffed with spiced potatoes and peas.", "hot"),
    ("Paneer Tikka", "", "North Indian", "Appetizer", "Tandoori", "Dairy Dish", "Veg", "Paneer", 8.5, "Medium", 1, 5, 2, 1, 4, 5, 6, 1, 3, 3, 5, 7, 1, "paneer, yogurt, bell peppers, onions, tandoori masala, lemon", "Marinated cottage cheese cubes grilled in a tandoor oven.", "hot"),
    ("Chicken Tikka", "", "North Indian", "Appetizer", "Tandoori", "Poultry Dish", "Non-Veg", "Chicken", 8.5, "Medium", 1, 5, 2, 1, 6, 5, 5, 1, 3, 3, 5, 7, 1, "chicken, yogurt, ginger, garlic, tandoori masala, lemon", "Boneless chicken pieces marinated in yogurt and spices.", "hot"),
    ("Gobi Manchurian", "", "Indo-Chinese", "Appetizer", "Indo-Chinese", "Vegetable Dish", "Veg", "", 8.0, "Medium", 3, 5, 3, 1, 5, 5, 5, 1, 4, 6, 3, 5, 1, "cauliflower, soy sauce, vinegar, garlic, ginger, cornstarch, green onions", "Cauliflower florets tossed in a spicy, tangy Indo-Chinese sauce.", "hot"),
    ("Vegetable Pakora", "", "North Indian", "Appetizer", "Fried Snack", "Vegetable Dish", "Veg", "", 7.5, "Medium", 1, 5, 1, 1, 3, 4, 6, 1, 3, 8, 2, 5, 1, "onions, potatoes, spinach, gram flour, cumin, chili powder, oil", "Assorted vegetable fritters dipped in gram flour batter.", "hot"),
    ("Samosa Chaat", "", "North Indian", "Appetizer", "Street Food", "Vegetable Dish", "Veg", "", 7.5, "Medium", 3, 5, 4, 1, 3, 4, 4, 1, 4, 6, 2, 6, 1, "samosas, chickpeas, yogurt, tamarind chutney, mint chutney, onions", "Smashed samosas topped with chickpeas, yogurt, and chutneys.", "room_temp"),
    ("Chicken 65", "", "South Indian", "Appetizer", "Fried Snack", "Poultry Dish", "Non-Veg", "Chicken", 8.0, "Hot", 1, 5, 1, 1, 6, 7, 6, 1, 3, 7, 4, 6, 1, "chicken, red chilies, curry leaves, ginger, garlic, yogurt, oil", "Spicy, deep-fried chicken bites originating from South India.", "hot"),
    ("Papdi Chaat", "", "North Indian", "Appetizer", "Street Food", "Grain Dish", "Veg", "", 7.0, "Mild", 3, 5, 4, 1, 2, 3, 3, 1, 3, 7, 2, 5, 1, "papdi, potatoes, chickpeas, yogurt, tamarind chutney, mint chutney, sev", "Crisp flour crackers topped with potatoes, chickpeas, and tangy sauces.", "room_temp"),
    ("Aloo Tikki", "", "North Indian", "Appetizer", "Street Food", "Vegetable Dish", "Veg", "", 7.5, "Medium", 2, 5, 2, 1, 3, 4, 5, 1, 4, 6, 3, 5, 1, "potatoes, peas, bread crumbs, cumin, coriander, tamarind chutney", "Spiced potato patties, often served with tamarind chutney.", "hot"),
    ("Onion Bhaji", "Onion Pakora", "North Indian", "Appetizer", "Fried Snack", "Vegetable Dish", "Veg", "", 7.0, "Medium", 2, 5, 1, 1, 3, 4, 6, 1, 3, 8, 2, 5, 1, "onions, gram flour, cumin, chili powder, coriander, oil", "Crispy onion fritters made with chickpea flour.", "hot"),
    ("Pani Puri", "Gol Gappa", "North Indian", "Appetizer", "Street Food", "Grain Dish", "Veg", "", 8.0, "Hot", 2, 4, 5, 1, 2, 6, 2, 1, 2, 7, 1, 6, 1, "semolina puri, tamarind water, mint water, potatoes, chickpeas, chili", "Hollow crispy balls filled with spiced water and potatoes.", "room_temp"),
    ("Chicken Lollipop", "", "Indo-Chinese", "Appetizer", "Indo-Chinese", "Poultry Dish", "Non-Veg", "Chicken", 7.5, "Medium", 2, 5, 2, 1, 6, 5, 5, 1, 4, 6, 4, 5, 1, "chicken wings, soy sauce, chili sauce, ginger, garlic, cornstarch", "Spiced chicken wings or drumettes served with chili sauce.", "hot"),
    ("Seekh Kebab", "", "North Indian", "Appetizer", "Kebab", "Red Meat Dish", "Non-Veg", "Lamb", 8.0, "Medium", 1, 5, 1, 1, 7, 5, 6, 1, 4, 3, 5, 7, 2, "minced lamb, onions, ginger, garlic, cumin, coriander, mint, garam masala", "Minced meat skewers seasoned with herbs and grilled.", "hot"),
    ("Chilli Paneer", "", "Indo-Chinese", "Appetizer", "Indo-Chinese", "Dairy Dish", "Veg", "Paneer", 7.5, "Hot", 2, 5, 2, 1, 4, 6, 5, 1, 4, 5, 5, 5, 1, "paneer, bell peppers, soy sauce, vinegar, green chilies, garlic", "Indo-Chinese appetizer with paneer and bell peppers.", "hot"),
    ("Hara Bhara Kabab", "", "North Indian", "Appetizer", "Kebab", "Vegetable Dish", "Veg", "", 6.5, "Mild", 1, 4, 1, 2, 3, 3, 4, 1, 4, 4, 4, 5, 1, "spinach, peas, potatoes, gram flour, ginger, green chilies", "Healthy spinach, pea, and potato patties.", "hot"),
    ("Tandoori Chicken", "", "North Indian", "Appetizer", "Tandoori", "Poultry Dish", "Non-Veg", "Chicken", 9.0, "Medium", 1, 5, 2, 1, 6, 5, 5, 1, 3, 4, 5, 8, 2, "chicken, yogurt, tandoori masala, lemon, ginger, garlic, kashmiri chili", "Bone-in chicken marinated and roasted in a clay oven.", "hot"),
    ("Dahi Puri", "", "North Indian", "Appetizer", "Street Food", "Grain Dish", "Veg", "", 6.5, "Mild", 3, 4, 3, 1, 2, 2, 4, 1, 4, 6, 2, 4, 1, "puri, potatoes, yogurt, tamarind chutney, sev, chaat masala", "Crispy puris stuffed with potatoes and topped with sweetened yogurt.", "room_temp"),
    ("Bhel Puri", "", "West Indian", "Appetizer", "Street Food", "Grain Dish", "Veg", "", 7.0, "Mild", 2, 5, 4, 1, 2, 3, 3, 1, 2, 8, 1, 5, 1, "puffed rice, sev, onions, tomatoes, tamarind sauce, mint chutney", "Savory snack of puffed rice, vegetables, and tamarind sauce.", "room_temp"),
    ("Vada Pav", "", "West Indian", "Appetizer", "Street Food", "Vegetable Dish", "Veg", "", 7.5, "Medium", 1, 5, 1, 1, 3, 5, 5, 1, 4, 5, 4, 5, 1, "potato vada, pav bread, garlic chutney, green chutney, fried chilies", "Spiced potato dumpling served in a bread roll with chutney.", "hot"),
    ("Paneer Pakora", "", "North Indian", "Appetizer", "Fried Snack", "Dairy Dish", "Veg", "Paneer", 6.5, "Medium", 1, 5, 1, 1, 4, 4, 6, 1, 3, 7, 4, 5, 1, "paneer, gram flour, spices, green chilies, oil", "Deep-fried cottage cheese fritters.", "hot"),
    ("Chilli Chicken", "", "Indo-Chinese", "Appetizer", "Indo-Chinese", "Poultry Dish", "Non-Veg", "Chicken", 8.0, "Hot", 2, 5, 2, 1, 5, 7, 5, 1, 4, 5, 4, 5, 1, "chicken, soy sauce, vinegar, green chilies, bell peppers, garlic", "Spicy Indo-Chinese stir-fry with chicken and green chilies.", "hot"),
    ("Medhu Vada", "", "South Indian", "Appetizer", "Fried Snack", "Legume Dish", "Vegan", "", 6.5, "Mild", 1, 4, 1, 1, 4, 2, 4, 1, 3, 7, 3, 4, 2, "urad dal, curry leaves, ginger, black pepper, cumin", "Savory lentil donuts often served with sambar and coconut chutney.", "hot"),
    ("Idli", "", "South Indian", "Appetizer", "Steamed", "Grain Dish", "Vegan", "", 7.0, "Mild", 1, 3, 2, 1, 3, 1, 2, 1, 3, 1, 3, 3, 3, "rice, urad dal, fenugreek seeds, salt", "Steamed rice cakes, often served with chutney as a light starter.", "hot"),
    ("Fish Tikka", "Tawa Fish", "North Indian", "Appetizer", "Tandoori", "Seafood Dish", "Non-Veg", "Fish", 7.0, "Medium", 1, 5, 2, 1, 6, 5, 5, 1, 3, 3, 4, 7, 3, "fish fillets, yogurt, ajwain, turmeric, chili powder, lemon", "Spiced fish fillets grilled or pan-fried.", "hot"),
    ("Lamb Boti Kebab", "", "North Indian", "Appetizer", "Kebab", "Red Meat Dish", "Non-Veg", "Lamb", 7.0, "Medium", 1, 5, 2, 1, 7, 5, 6, 1, 4, 3, 6, 7, 2, "lamb, yogurt, ginger, garlic, garam masala, lemon", "Chunks of lamb marinated in yogurt and grilled on skewers.", "hot"),
    ("Malai Kofta", "Appetizer Version", "North Indian", "Appetizer", "Fried Snack", "Dairy Dish", "Veg", "Paneer", 6.5, "Mild", 2, 4, 1, 1, 4, 2, 7, 1, 5, 4, 4, 5, 1, "paneer, potatoes, cashews, cream, raisins, cardamom", "Fried veggie/cheese balls in a creamy sauce.", "hot"),
    ("Masala Papad", "", "North Indian", "Appetizer", "Snack", "Legume Dish", "Veg", "", 5.0, "Mild", 1, 5, 2, 1, 2, 3, 2, 1, 1, 8, 1, 4, 1, "papad, onions, tomatoes, coriander, chaat masala, lemon", "Crispy lentil crackers topped with chopped onions and tomatoes.", "room_temp"),
    ("Kachori", "Dal or Pyaaz", "North Indian", "Appetizer", "Fried Snack", "Legume Dish", "Veg", "", 7.0, "Medium", 1, 5, 1, 1, 4, 4, 6, 1, 4, 7, 3, 6, 1, "flour, moong dal, fennel, cumin, chili powder, oil", "Flaky pastries filled with spiced lentils or onions.", "hot"),
    ("Sabudana Vada", "", "West Indian", "Appetizer", "Fried Snack", "Grain Dish", "Vegan", "", 5.5, "Mild", 1, 4, 2, 1, 3, 3, 5, 1, 3, 7, 3, 4, 1, "tapioca pearls, peanuts, potatoes, cumin, green chilies", "Vegan patties made from tapioca pearls and peanuts.", "hot"),
    ("Bharwan Mushroom", "", "North Indian", "Appetizer", "Tandoori", "Vegetable Dish", "Veg", "", 5.5, "Mild", 1, 4, 1, 1, 5, 3, 5, 1, 3, 3, 4, 6, 2, "mushrooms, paneer, cream cheese, spices, herbs", "Stuffed mushrooms grilled in the tandoor.", "hot"),
    ("Amritsari Fish Fry", "", "North Indian", "Appetizer", "Fried Snack", "Seafood Dish", "Non-Veg", "Fish", 7.0, "Medium", 1, 5, 2, 1, 6, 5, 6, 1, 3, 7, 4, 6, 3, "fish, gram flour, ajwain, chili powder, lemon, oil", "Gram flour coated fried fish originating from Punjab.", "hot"),
    ("Dahi Bhalla", "Dahi Vada", "North Indian", "Appetizer", "Street Food", "Legume Dish", "Veg", "", 6.5, "Mild", 3, 4, 3, 1, 3, 2, 4, 1, 5, 2, 4, 4, 1, "urad dal, yogurt, tamarind chutney, cumin, chili powder", "Lentil dumplings soaked in thick seasoned yogurt.", "cold"),
    ("Chicken Chapli Kebab", "", "North Indian", "Appetizer", "Kebab", "Poultry Dish", "Non-Veg", "Chicken", 6.5, "Hot", 1, 5, 1, 1, 6, 6, 6, 1, 4, 4, 5, 7, 2, "minced chicken, onions, tomatoes, pomegranate seeds, cumin, coriander", "Pan-fried minced chicken patties with heavy spices.", "hot"),
    ("Gobi 65", "", "South Indian", "Appetizer", "Fried Snack", "Vegetable Dish", "Veg", "", 7.0, "Hot", 1, 5, 1, 1, 4, 7, 5, 1, 3, 7, 3, 6, 1, "cauliflower, red chilies, curry leaves, ginger, garlic, yogurt, rice flour", "Spicy fried cauliflower, a vegetarian take on Chicken 65.", "hot"),
    ("Moong Dal Halwa Kachumber", "", "North Indian", "Appetizer", "Salad", "Vegetable Dish", "Vegan", "", 4.5, "Mild", 1, 4, 3, 1, 2, 2, 1, 1, 1, 5, 1, 3, 1, "cucumber, onions, tomatoes, lemon, salt, chili powder", "Fresh cucumber and onion salad often served as a light start.", "cold"),
    ("Mogo Chips", "", "East African-Indian", "Appetizer", "Fried Snack", "Vegetable Dish", "Vegan", "", 5.0, "Medium", 1, 5, 1, 1, 3, 4, 5, 1, 2, 8, 2, 4, 1, "cassava, oil, salt, chili powder, lemon", "Fried cassava chips, a popular East African-Indian fusion snack.", "hot"),
    ("Khandvi", "", "West Indian", "Appetizer", "Steamed", "Legume Dish", "Veg", "", 5.5, "Mild", 2, 4, 2, 1, 3, 2, 3, 2, 3, 2, 3, 4, 1, "gram flour, yogurt, turmeric, mustard seeds, sesame seeds, coconut", "Rolled, savory snacks made from gram flour and yogurt.", "room_temp"),
    ("Chicken Malai Kebab", "", "North Indian", "Appetizer", "Kebab", "Poultry Dish", "Non-Veg", "Chicken", 7.5, "Mild", 1, 4, 1, 1, 5, 2, 7, 1, 4, 3, 5, 6, 1, "chicken, cream, cheese, cashew paste, cardamom, white pepper", "Creamy, mild chicken skewers marinated in cheese and cream.", "hot"),
    ("Shrimp Tandoori", "", "North Indian", "Appetizer", "Tandoori", "Seafood Dish", "Non-Veg", "Shrimp", 7.0, "Medium", 1, 5, 2, 1, 6, 5, 5, 1, 3, 3, 4, 7, 3, "shrimp, yogurt, tandoori masala, lemon, ginger, garlic", "Jumbo shrimp marinated in tandoori spices and grilled.", "hot"),
    ("Veg Spring Rolls", "", "Indo-Chinese", "Appetizer", "Indo-Chinese", "Vegetable Dish", "Veg", "", 6.0, "Mild", 1, 4, 1, 1, 3, 3, 4, 1, 2, 8, 2, 3, 1, "cabbage, carrots, flour wrappers, soy sauce, oil", "Indo-Chinese rolls filled with cabbage and carrots.", "hot"),
]

# ══════════════════════════════════════════════════════════════════════════════
#  60 MAIN COURSES
# ══════════════════════════════════════════════════════════════════════════════
mains = [
    ("Chicken Tikka Masala", "", "North Indian", "Main Dish", "Curry", "Poultry Dish", "Non-Veg", "Chicken", 9.5, "Medium", 3, 5, 3, 1, 6, 5, 7, 1, 5, 2, 4, 7, 1, "chicken, tomatoes, cream, butter, garam masala, kashmiri chili, fenugreek", "Marinated grilled chicken chunks in a creamy, spiced tomato sauce.", "hot"),
    ("Butter Chicken", "Murgh Makhani", "North Indian", "Main Dish", "Curry", "Poultry Dish", "Non-Veg", "Chicken", 9.5, "Mild", 3, 5, 2, 1, 6, 3, 8, 1, 6, 2, 4, 7, 1, "chicken, butter, tomatoes, cream, cashews, fenugreek, garam masala", "Tender chicken in a rich, mild, buttery tomato gravy.", "hot"),
    ("Chicken Biryani", "", "South Indian", "Main Dish", "Rice Dish", "Poultry Dish", "Non-Veg", "Chicken", 9.0, "Medium", 2, 5, 1, 1, 6, 4, 6, 1, 3, 2, 3, 9, 2, "basmati rice, chicken, saffron, whole spices, onions, yogurt, mint", "A fragrant, layered rice dish cooked with aromatic spices and chicken.", "hot"),
    ("Palak Paneer", "Saag Paneer", "North Indian", "Main Dish", "Curry", "Dairy Dish", "Veg", "Paneer", 8.5, "Mild", 1, 5, 1, 3, 4, 3, 6, 2, 5, 2, 4, 6, 1, "spinach, paneer, cream, onions, garlic, garam masala", "Indian cottage cheese cubes in a thick, pureed spinach gravy.", "hot"),
    ("Lamb Rogan Josh", "", "North Indian", "Main Dish", "Curry", "Red Meat Dish", "Non-Veg", "Lamb", 8.5, "Hot", 1, 5, 1, 1, 7, 6, 6, 1, 5, 2, 6, 8, 2, "lamb, yogurt, ginger, kashmiri chili, fennel, cardamom, cloves", "An aromatic Kashmiri lamb curry flavored with ginger and red chilies.", "hot"),
    ("Chana Masala", "Chole", "North Indian", "Main Dish", "Curry", "Legume Dish", "Vegan", "", 8.0, "Medium", 1, 5, 2, 1, 5, 5, 4, 1, 4, 2, 3, 7, 1, "chickpeas, onions, tomatoes, cumin, ginger, turmeric, amchur", "A savory chickpea stew flavored with cumin, ginger, and turmeric.", "hot"),
    ("Tandoori Chicken Main", "", "North Indian", "Main Dish", "Tandoori", "Poultry Dish", "Non-Veg", "Chicken", 8.5, "Medium", 1, 5, 2, 1, 6, 5, 5, 1, 3, 4, 5, 8, 2, "chicken, yogurt, tandoori masala, lemon, ginger, garlic", "Bone-in chicken marinated in yogurt and spices, roasted in a clay oven.", "hot"),
    ("Masala Dosa", "", "South Indian", "Main Dish", "Crepe", "Grain Dish", "Veg", "", 8.5, "Medium", 1, 4, 2, 1, 4, 3, 5, 1, 3, 7, 2, 5, 3, "rice batter, urad dal, potatoes, mustard seeds, curry leaves, turmeric", "A crispy fermented rice and lentil crepe filled with spiced potato masala.", "hot"),
    ("Lamb Vindaloo", "", "West Indian", "Main Dish", "Curry", "Red Meat Dish", "Non-Veg", "Lamb", 8.0, "Very Hot", 1, 5, 3, 1, 6, 8, 5, 1, 5, 2, 6, 7, 2, "lamb, vinegar, red chilies, garlic, ginger, mustard seeds", "A fiery, tangy Goan curry made with vinegar, garlic, and red chilies.", "hot"),
    ("Aloo Gobi", "", "North Indian", "Main Dish", "Dry Curry", "Vegetable Dish", "Vegan", "", 7.5, "Medium", 1, 5, 1, 1, 3, 4, 3, 1, 3, 4, 3, 6, 1, "cauliflower, potatoes, turmeric, cumin, coriander, ginger", "A dry vegetarian dish featuring cauliflower and potatoes cooked with turmeric.", "hot"),
    ("Dal Makhani", "", "North Indian", "Main Dish", "Lentil Dish", "Legume Dish", "Veg", "", 8.5, "Mild", 2, 5, 1, 1, 6, 3, 8, 1, 6, 1, 3, 7, 2, "black lentils, kidney beans, butter, cream, tomatoes, ginger, garlic", "Slow-cooked black lentils and kidney beans in a creamy, buttery sauce.", "hot"),
    ("Chicken Korma", "", "North Indian", "Main Dish", "Curry", "Poultry Dish", "Non-Veg", "Chicken", 8.0, "Mild", 2, 4, 1, 1, 5, 2, 7, 1, 5, 2, 4, 7, 1, "chicken, yogurt, cashews, almonds, cream, cardamom, saffron", "A mild, nutty curry thickened with yogurt and ground cashews or almonds.", "hot"),
    ("Paneer Tikka Masala", "", "North Indian", "Main Dish", "Curry", "Dairy Dish", "Veg", "Paneer", 8.0, "Medium", 3, 5, 3, 1, 5, 5, 7, 1, 5, 2, 5, 7, 1, "paneer, tomatoes, cream, butter, garam masala, kashmiri chili", "Grilled paneer cubes served in the same creamy tomato sauce as Chicken Tikka Masala.", "hot"),
    ("Chicken Jalfrezi", "", "North Indian", "Main Dish", "Stir-Fry", "Poultry Dish", "Non-Veg", "Chicken", 7.5, "Hot", 1, 5, 2, 1, 5, 6, 5, 1, 4, 4, 4, 6, 1, "chicken, bell peppers, onions, tomatoes, cumin, coriander, green chilies", "A spicy stir-fry of marinated chicken, bell peppers, onions, and tomatoes.", "hot"),
    ("Malai Kofta Main", "", "North Indian", "Main Dish", "Curry", "Dairy Dish", "Veg", "Paneer", 7.5, "Mild", 2, 4, 1, 1, 4, 2, 8, 1, 6, 3, 4, 6, 1, "paneer, potatoes, cashews, cream, tomatoes, cardamom, saffron", "Deep-fried vegetable or paneer balls served in a rich, creamy gravy.", "hot"),
    ("Baingan Bharta", "", "North Indian", "Main Dish", "Dry Curry", "Vegetable Dish", "Vegan", "", 7.0, "Medium", 1, 5, 2, 2, 4, 4, 4, 1, 4, 2, 3, 7, 2, "eggplant, onions, tomatoes, peas, garlic, green chilies", "Smoky, roasted eggplant mashed and cooked with onions, tomatoes, and peas.", "hot"),
    ("Shahi Paneer", "", "North Indian", "Main Dish", "Curry", "Dairy Dish", "Veg", "Paneer", 7.5, "Mild", 2, 4, 2, 1, 4, 2, 7, 1, 5, 2, 5, 6, 1, "paneer, cream, tomatoes, cashews, cardamom, saffron", "A royal paneer dish in a thick gravy of cream, tomatoes, and spices.", "hot"),
    ("Chicken Curry", "Traditional", "North Indian", "Main Dish", "Curry", "Poultry Dish", "Non-Veg", "Chicken", 8.0, "Medium", 1, 5, 2, 1, 6, 5, 5, 1, 5, 2, 5, 7, 1, "chicken, onions, tomatoes, ginger, garlic, turmeric, garam masala", "Home-style chicken stew with a base of onions, ginger, and garlic.", "hot"),
    ("Lamb Curry", "Goat Curry", "North Indian", "Main Dish", "Curry", "Red Meat Dish", "Non-Veg", "Lamb", 8.0, "Medium", 1, 5, 2, 1, 7, 5, 6, 1, 5, 2, 6, 7, 2, "lamb, onions, tomatoes, yogurt, ginger, garlic, garam masala", "Tender meat slow-cooked in a classic onion and tomato gravy.", "hot"),
    ("Matar Paneer", "", "North Indian", "Main Dish", "Curry", "Dairy Dish", "Veg", "Paneer", 7.5, "Medium", 2, 5, 2, 1, 4, 4, 5, 1, 5, 2, 4, 6, 1, "paneer, peas, tomatoes, onions, cumin, garam masala, cream", "A popular North Indian dish of peas and paneer in a tomato-based sauce.", "hot"),
    ("Kadai Paneer", "", "North Indian", "Main Dish", "Curry", "Dairy Dish", "Veg", "Paneer", 7.5, "Medium", 1, 5, 2, 1, 4, 5, 5, 1, 4, 3, 5, 7, 1, "paneer, bell peppers, tomatoes, kadai masala, coriander seeds", "Paneer cooked with bell peppers and freshly ground kadai masala spices.", "hot"),
    ("Saag Chicken", "Saag Lamb", "North Indian", "Main Dish", "Curry", "Poultry Dish", "Non-Veg", "Chicken", 7.0, "Medium", 1, 5, 1, 3, 5, 4, 5, 2, 5, 2, 5, 6, 1, "chicken, spinach, cream, onions, ginger, garlic, garam masala", "Meat cooked in a spiced spinach puree, similar to Palak Paneer.", "hot"),
    ("Shrimp Tandoori Main", "", "North Indian", "Main Dish", "Tandoori", "Seafood Dish", "Non-Veg", "Shrimp", 7.0, "Medium", 1, 5, 2, 1, 6, 5, 5, 1, 3, 3, 4, 7, 3, "large shrimp, yogurt, tandoori masala, lemon, butter", "Large shrimp marinated in tandoori spices and grilled.", "hot"),
    ("Bhindi Masala", "", "North Indian", "Main Dish", "Dry Curry", "Vegetable Dish", "Vegan", "", 6.5, "Medium", 1, 5, 2, 1, 3, 4, 3, 1, 3, 4, 3, 5, 1, "okra, onions, tomatoes, turmeric, cumin, coriander, amchur", "Okra (ladyfingers) stir-fried with onions, tomatoes, and dry spices.", "hot"),
    ("Chole Bhature", "", "North Indian", "Main Dish", "Curry", "Legume Dish", "Veg", "", 8.0, "Medium", 1, 5, 2, 1, 5, 5, 6, 1, 4, 6, 3, 7, 1, "chickpeas, flour, yogurt, cumin, coriander, amchur, oil", "Spiced chickpeas served with a large, deep-fried leavened bread.", "hot"),
    ("Fish Curry Goan", "", "West Indian", "Main Dish", "Curry", "Seafood Dish", "Non-Veg", "Fish", 7.5, "Medium", 1, 5, 3, 1, 6, 5, 5, 1, 5, 2, 4, 7, 3, "fish, coconut milk, tamarind, red chilies, curry leaves, kokum", "Seafood cooked in a tangy coconut milk base with curry leaves.", "hot"),
    ("Lamb Madras", "", "South Indian", "Main Dish", "Curry", "Red Meat Dish", "Non-Veg", "Lamb", 7.0, "Very Hot", 1, 5, 2, 1, 6, 8, 5, 1, 5, 2, 6, 7, 2, "lamb, coconut, red chilies, tamarind, mustard seeds, curry leaves", "A hot South Indian-style curry with coconut and a strong hit of chili.", "hot"),
    ("Navratan Korma", "", "North Indian", "Main Dish", "Curry", "Vegetable Dish", "Veg", "", 7.0, "Mild", 3, 4, 1, 1, 4, 2, 6, 1, 5, 3, 3, 6, 1, "mixed vegetables, fruits, cashews, cream, saffron, cardamom", "A nine-gem vegetarian curry with mixed vegetables, fruits, and nuts.", "hot"),
    ("Yellow Dal Tadka", "", "North Indian", "Main Dish", "Lentil Dish", "Legume Dish", "Veg", "", 7.5, "Medium", 1, 5, 2, 1, 5, 4, 5, 1, 5, 1, 3, 7, 1, "yellow lentils, ghee, cumin, garlic, red chilies, turmeric", "Yellow lentils tempered with ghee, cumin, garlic, and red chilies.", "hot"),
    ("Paneer Bhurji", "", "North Indian", "Main Dish", "Dry Curry", "Dairy Dish", "Veg", "Paneer", 6.5, "Medium", 1, 5, 2, 1, 4, 4, 5, 1, 3, 3, 4, 6, 1, "paneer, onions, tomatoes, green chilies, turmeric, cumin", "Scrambled paneer sauteed with chopped onions, tomatoes, and spices.", "hot"),
    ("Chicken 65 Main", "", "South Indian", "Main Dish", "Dry Curry", "Poultry Dish", "Non-Veg", "Chicken", 7.5, "Hot", 1, 5, 1, 1, 6, 7, 5, 1, 3, 6, 4, 6, 1, "chicken, red chilies, curry leaves, ginger, garlic, yogurt", "Spicy, deep-fried chicken pieces often served as a dry main or with sauce.", "hot"),
    ("Goat Biryani", "", "South Indian", "Main Dish", "Rice Dish", "Red Meat Dish", "Non-Veg", "Goat", 8.5, "Medium", 2, 5, 1, 1, 7, 5, 6, 1, 3, 2, 5, 9, 3, "basmati rice, goat, saffron, whole spices, onions, yogurt, mint", "Flavorful long-grain rice layered with tender goat meat and saffron.", "hot"),
    ("Vegetable Pulao", "", "North Indian", "Main Dish", "Rice Dish", "Vegetable Dish", "Veg", "", 6.5, "Mild", 1, 4, 1, 1, 3, 2, 3, 1, 3, 2, 2, 6, 1, "basmati rice, mixed vegetables, whole spices, cumin, bay leaf", "A mild, one-pot rice dish with assorted vegetables and whole spices.", "hot"),
    ("Chicken Do Pyaza", "", "North Indian", "Main Dish", "Curry", "Poultry Dish", "Non-Veg", "Chicken", 7.0, "Medium", 2, 5, 2, 1, 5, 5, 5, 1, 5, 3, 4, 6, 1, "chicken, onions, tomatoes, yogurt, garam masala, cumin", "A chicken dish featuring onions added at two different stages of cooking.", "hot"),
    ("Kadhai Chicken", "", "North Indian", "Main Dish", "Curry", "Poultry Dish", "Non-Veg", "Chicken", 7.5, "Medium", 1, 5, 2, 1, 6, 5, 5, 1, 4, 3, 5, 7, 1, "chicken, bell peppers, tomatoes, kadai masala, coriander seeds, ginger", "Chicken cooked in a wok-like pot with bell peppers and thick gravy.", "hot"),
    ("Tandoori Mixed Grill", "", "North Indian", "Main Dish", "Tandoori", "Poultry Dish", "Non-Veg", "Mixed", 8.0, "Medium", 1, 5, 2, 1, 7, 5, 5, 1, 3, 4, 5, 8, 2, "tandoori chicken, seekh kebab, shrimp, fish tikka, yogurt, spices", "A platter featuring tandoori chicken, seekh kebabs, shrimp, and fish.", "hot"),
    ("Lamb Boti Kabab Main", "", "North Indian", "Main Dish", "Kebab", "Red Meat Dish", "Non-Veg", "Lamb", 7.0, "Medium", 1, 5, 2, 1, 7, 5, 6, 1, 4, 3, 6, 7, 2, "lamb, yogurt, ginger, garlic, garam masala, lemon", "Cubes of lamb marinated in yogurt and spices, grilled on skewers.", "hot"),
    ("Paneer Makhani", "", "North Indian", "Main Dish", "Curry", "Dairy Dish", "Veg", "Paneer", 7.5, "Mild", 3, 5, 2, 1, 4, 3, 8, 1, 6, 2, 5, 7, 1, "paneer, butter, tomatoes, cream, cashews, fenugreek, garam masala", "Paneer cubes in the same mild, buttery tomato gravy used for butter chicken.", "hot"),
    ("Shrimp Curry", "", "South Indian", "Main Dish", "Curry", "Seafood Dish", "Non-Veg", "Shrimp", 7.0, "Medium", 1, 5, 3, 1, 6, 5, 5, 1, 5, 2, 4, 7, 3, "shrimp, coconut milk, tomatoes, onions, curry leaves, red chilies", "Prawns or shrimp simmered in a spiced tomato or coconut-based sauce.", "hot"),
    ("Dal Fry", "", "North Indian", "Main Dish", "Lentil Dish", "Legume Dish", "Veg", "", 7.0, "Medium", 1, 5, 2, 1, 5, 4, 4, 1, 5, 1, 2, 6, 1, "lentils, onions, tomatoes, cumin, turmeric, garlic, ghee", "Boiled lentils sauteed with spices, onions, and tomatoes.", "hot"),
    ("Keema Matar", "", "North Indian", "Main Dish", "Curry", "Red Meat Dish", "Non-Veg", "Lamb", 7.0, "Medium", 1, 5, 2, 1, 7, 5, 5, 1, 4, 2, 4, 6, 2, "minced lamb, peas, onions, tomatoes, ginger, garlic, garam masala", "Minced lamb or goat cooked with peas and traditional spices.", "hot"),
    ("Mushroom Masala", "", "North Indian", "Main Dish", "Curry", "Vegetable Dish", "Veg", "", 6.5, "Medium", 1, 5, 2, 1, 5, 4, 5, 1, 5, 2, 4, 6, 2, "mushrooms, onions, tomatoes, cream, garam masala, cumin", "Fresh mushrooms cooked in a spiced onion-tomato gravy.", "hot"),
    ("Fish Tikka Main", "", "North Indian", "Main Dish", "Tandoori", "Seafood Dish", "Non-Veg", "Fish", 7.0, "Medium", 1, 5, 2, 1, 6, 5, 5, 1, 3, 3, 4, 7, 3, "fish fillets, yogurt, tandoori masala, lemon, ajwain", "Marinated fish fillets grilled in the tandoor.", "hot"),
    ("Chicken Chettinad", "", "South Indian", "Main Dish", "Curry", "Poultry Dish", "Non-Veg", "Chicken", 7.5, "Very Hot", 1, 5, 2, 1, 6, 8, 5, 1, 4, 2, 5, 8, 2, "chicken, black pepper, fennel, star anise, kalpasi, red chilies, coconut", "A fiery South Indian curry made with a unique blend of 16-23 roasted spices.", "hot"),
    ("Egg Curry", "", "North Indian", "Main Dish", "Curry", "Egg Dish", "Non-Veg", "Egg", 6.5, "Medium", 1, 5, 2, 1, 5, 5, 5, 1, 5, 2, 4, 6, 1, "eggs, onions, tomatoes, turmeric, cumin, garam masala", "Hard-boiled eggs simmered in a spicy onion-tomato gravy.", "hot"),
    ("Nihari", "", "North Indian", "Main Dish", "Stew", "Red Meat Dish", "Non-Veg", "Beef", 7.0, "Medium", 1, 5, 1, 1, 8, 4, 7, 1, 6, 1, 5, 7, 3, "beef, bone marrow, wheat flour, ginger, garam masala, fennel", "A slow-cooked beef or lamb stew, traditionally a breakfast dish but common as a main.", "hot"),
    ("Aloo Matar", "", "North Indian", "Main Dish", "Curry", "Vegetable Dish", "Vegan", "", 6.5, "Mild", 1, 5, 2, 1, 3, 3, 3, 1, 4, 2, 3, 5, 1, "potatoes, peas, tomatoes, cumin, turmeric, garam masala", "A simple, comforting potato and pea curry.", "hot"),
    ("Lamb Pasanda", "", "North Indian", "Main Dish", "Curry", "Red Meat Dish", "Non-Veg", "Lamb", 7.0, "Mild", 2, 4, 1, 1, 6, 3, 7, 1, 5, 2, 5, 7, 1, "lamb, yogurt, almonds, cream, cardamom, saffron", "A mild, creamy lamb curry made with yogurt and almond paste.", "hot"),
    ("Gobi Manchurian Main", "", "Indo-Chinese", "Main Dish", "Indo-Chinese", "Vegetable Dish", "Veg", "", 7.0, "Medium", 3, 5, 3, 1, 5, 5, 5, 1, 5, 4, 3, 5, 1, "cauliflower, soy sauce, vinegar, garlic, ginger, cornstarch, gravy", "Indo-Chinese cauliflower florets in a spicy soy-garlic sauce.", "hot"),
    ("Chilli Chicken Main", "", "Indo-Chinese", "Main Dish", "Indo-Chinese", "Poultry Dish", "Non-Veg", "Chicken", 7.5, "Hot", 2, 5, 2, 1, 5, 7, 5, 1, 4, 4, 4, 5, 1, "chicken, soy sauce, vinegar, green chilies, bell peppers, garlic", "Indo-Chinese stir-fried chicken with green chilies and bell peppers.", "hot"),
    ("Chicken Tikka Main", "", "North Indian", "Main Dish", "Tandoori", "Poultry Dish", "Non-Veg", "Chicken", 8.0, "Medium", 1, 5, 2, 1, 6, 5, 5, 1, 3, 3, 5, 7, 1, "chicken, yogurt, tandoori masala, lemon, salad, naan", "Grilled boneless chicken pieces served with salad and naan.", "hot"),
    ("Vegetable Makhanwala", "", "North Indian", "Main Dish", "Curry", "Vegetable Dish", "Veg", "", 6.5, "Mild", 3, 4, 2, 1, 3, 2, 7, 1, 5, 2, 3, 5, 1, "mixed vegetables, butter, tomatoes, cream, fenugreek, garam masala", "Mixed vegetables cooked in a rich, buttery tomato sauce.", "hot"),
    ("Pork Vindaloo", "", "West Indian", "Main Dish", "Curry", "Red Meat Dish", "Non-Veg", "Pork", 7.0, "Very Hot", 1, 5, 3, 1, 6, 8, 6, 1, 5, 2, 5, 7, 2, "pork, vinegar, red chilies, garlic, ginger, mustard seeds", "The authentic Goan version of Vindaloo (found in specialty coastal restaurants).", "hot"),
    ("Methi Chicken", "", "North Indian", "Main Dish", "Curry", "Poultry Dish", "Non-Veg", "Chicken", 6.5, "Medium", 1, 5, 1, 3, 5, 4, 5, 2, 5, 2, 4, 7, 2, "chicken, fenugreek leaves, onions, tomatoes, ginger, garlic", "Chicken cooked with fresh fenugreek leaves for a slightly bitter, earthy flavor.", "hot"),
    ("Paneer Ghee Roast", "", "South Indian", "Main Dish", "Dry Curry", "Dairy Dish", "Veg", "Paneer", 6.5, "Hot", 1, 5, 1, 1, 4, 6, 7, 1, 4, 3, 5, 7, 1, "paneer, ghee, red chilies, tamarind, garlic, curry leaves", "Spicy Mangalorean-style paneer cooked in clarified butter.", "hot"),
    ("Lemon Rice", "", "South Indian", "Main Dish", "Rice Dish", "Grain Dish", "Vegan", "", 6.0, "Mild", 1, 4, 4, 1, 3, 3, 3, 1, 2, 3, 2, 5, 1, "rice, lemon juice, peanuts, mustard seeds, curry leaves, turmeric", "South Indian tempered rice flavored with lemon juice and peanuts.", "hot"),
    ("Bisi Bele Bath", "", "South Indian", "Main Dish", "Rice Dish", "Legume Dish", "Veg", "", 6.5, "Medium", 2, 5, 3, 1, 5, 4, 5, 1, 5, 2, 3, 7, 1, "rice, toor dal, tamarind, bisi bele bath powder, vegetables, ghee", "A spicy, lentil-based rice dish from Karnataka.", "hot"),
    ("Tandoori Salmon", "", "North Indian", "Main Dish", "Tandoori", "Seafood Dish", "Non-Veg", "Fish", 7.0, "Medium", 1, 5, 2, 1, 6, 5, 6, 1, 4, 3, 4, 7, 3, "salmon, yogurt, tandoori masala, lemon, ginger, garlic", "Salmon fillets marinated in Indian spices and roasted in the clay oven.", "hot"),
    ("Chilli Paneer Main", "", "Indo-Chinese", "Main Dish", "Indo-Chinese", "Dairy Dish", "Veg", "Paneer", 7.0, "Hot", 2, 5, 2, 1, 4, 6, 5, 1, 4, 4, 5, 5, 1, "paneer, soy sauce, vinegar, green chilies, bell peppers, garlic", "Paneer cubes tossed in a spicy Indo-Chinese sauce.", "hot"),
    ("Puri Bhaji", "", "North Indian", "Main Dish", "Curry", "Vegetable Dish", "Veg", "", 7.0, "Medium", 1, 5, 1, 1, 3, 4, 5, 1, 4, 6, 3, 5, 1, "whole wheat flour, potatoes, onions, cumin, turmeric, oil", "Deep-fried whole wheat bread served with a spiced potato curry.", "hot"),
]

# ══════════════════════════════════════════════════════════════════════════════
#  20 DESSERTS (includes drinks that double as desserts)
# ══════════════════════════════════════════════════════════════════════════════
desserts = [
    ("Gulab Jamun", "", "North Indian", "Dessert", "Sweet", "Dairy Dish", "Veg", "", 9.0, "Mild", 9, 2, 1, 1, 1, 1, 8, 1, 7, 2, 5, 7, 1, "milk solids, flour, sugar, rose water, cardamom, saffron, ghee", "Soft, spongy milk-solid dumplings fried and soaked in rose-flavored sugar syrup.", "hot"),
    ("Rasmalai", "", "East Indian", "Dessert", "Sweet", "Dairy Dish", "Veg", "", 8.5, "Mild", 8, 1, 1, 1, 1, 1, 7, 1, 6, 1, 5, 8, 1, "chhena, milk, sugar, cardamom, saffron, pistachios", "Soft cheese patties soaked in chilled, sweetened, and thickened milk flavored with cardamom and saffron.", "cold"),
    ("Kheer", "Rice Pudding", "North Indian", "Dessert", "Sweet", "Dairy Dish", "Veg", "", 8.5, "Mild", 8, 1, 1, 1, 1, 1, 7, 1, 6, 1, 3, 7, 1, "rice, milk, sugar, cardamom, pistachios, saffron", "A creamy rice pudding simmered with milk and sugar, flavored with cardamom and garnished with nuts.", "cold"),
    ("Gajar Ka Halwa", "", "North Indian", "Dessert", "Sweet", "Vegetable Dish", "Veg", "", 8.0, "Mild", 8, 1, 1, 1, 1, 1, 7, 1, 5, 1, 4, 7, 1, "carrots, milk, ghee, sugar, cardamom, cashews, raisins", "A warm, carrot-based dessert made by slow-cooking grated carrots with milk, ghee, and sugar.", "hot"),
    ("Rasgulla", "", "East Indian", "Dessert", "Sweet", "Dairy Dish", "Veg", "", 8.0, "Mild", 9, 1, 1, 1, 1, 1, 5, 1, 7, 1, 5, 4, 1, "chhena, semolina, sugar, rose water", "Spongy white balls made from cottage cheese and semolina, cooked in a light, clear sugar syrup.", "cold"),
    ("Kulfi", "", "North Indian", "Dessert", "Frozen", "Dairy Dish", "Veg", "", 8.0, "Mild", 8, 1, 1, 1, 1, 1, 8, 1, 5, 1, 3, 7, 1, "milk, sugar, cardamom, pistachios, saffron, almonds", "Traditional Indian ice cream that is denser and creamier than Western versions.", "cold"),
    ("Jalebi", "", "North Indian", "Dessert", "Sweet", "Grain Dish", "Veg", "", 8.0, "Mild", 9, 1, 1, 1, 1, 1, 6, 1, 6, 7, 2, 5, 1, "flour, sugar, saffron, cardamom, oil, yogurt", "Deep-fried, pretzel-shaped batter soaked in sugar syrup, known for its bright orange color.", "hot"),
    ("Laddu", "Ladoo", "North Indian", "Dessert", "Sweet", "Grain Dish", "Veg", "", 7.5, "Mild", 8, 1, 1, 1, 1, 1, 6, 1, 5, 3, 4, 6, 1, "gram flour, ghee, sugar, cardamom, pistachios", "Round, sweet balls made from various flours; Motichoor Ladoo and Besan Ladoo are the most common.", "room_temp"),
    ("Kaju Katli", "", "North Indian", "Dessert", "Sweet", "Nut Dish", "Veg", "", 7.5, "Mild", 8, 1, 1, 1, 1, 1, 5, 1, 4, 2, 3, 5, 1, "cashew nuts, sugar, ghee, silver leaf", "A rich, diamond-shaped fudge made from cashew nuts, sugar, and ghee.", "room_temp"),
    ("Mango Lassi", "Dessert Version", "North Indian", "Dessert", "Beverage", "Dairy Dish", "Veg", "", 7.5, "Mild", 7, 1, 2, 1, 1, 1, 5, 1, 5, 1, 2, 5, 1, "mango, yogurt, sugar, cardamom, milk", "A thick, sweet yogurt-mango drink popular as a refreshing end to a spicy meal.", "cold"),
    ("Falooda", "", "North Indian", "Dessert", "Beverage", "Dairy Dish", "Veg", "", 7.0, "Mild", 8, 1, 1, 1, 1, 1, 5, 1, 5, 2, 3, 6, 1, "rose syrup, vermicelli, basil seeds, kulfi, ice cream, milk", "A cold dessert-drink made with rose syrup, vermicelli, basil seeds, and a scoop of kulfi or ice cream.", "cold"),
    ("Shrikhand", "Amrakhand", "West Indian", "Dessert", "Sweet", "Dairy Dish", "Veg", "", 6.5, "Mild", 7, 1, 2, 1, 1, 1, 5, 1, 5, 1, 3, 6, 1, "strained yogurt, sugar, saffron, cardamom, mango pulp", "A thick, creamy dessert made of strained yogurt, often flavored with mango pulp or saffron.", "cold"),
    ("Soan Papdi", "", "North Indian", "Dessert", "Sweet", "Grain Dish", "Veg", "", 6.0, "Mild", 7, 1, 1, 1, 1, 1, 4, 1, 3, 5, 2, 4, 1, "gram flour, sugar, ghee, cardamom, pistachios", "A light, flaky dessert with a crisp, fibrous texture made from gram flour and sugar.", "room_temp"),
    ("Kalakand", "", "North Indian", "Dessert", "Sweet", "Dairy Dish", "Veg", "", 6.0, "Mild", 8, 1, 1, 1, 1, 1, 6, 1, 5, 2, 4, 5, 1, "milk, paneer, sugar, cardamom", "A moist, grainy milk cake made from solidified sweetened milk and paneer.", "room_temp"),
    ("Barfi", "", "North Indian", "Dessert", "Sweet", "Dairy Dish", "Veg", "", 6.5, "Mild", 8, 1, 1, 1, 1, 1, 5, 1, 5, 2, 3, 5, 1, "milk solids, sugar, ghee, pistachios, coconut, cream", "A dense, fudge-like sweet available in many varieties including Pista, Malai, and Coconut.", "room_temp"),
    ("Moong Dal Halwa", "", "North Indian", "Dessert", "Sweet", "Legume Dish", "Veg", "", 6.5, "Mild", 8, 1, 1, 1, 2, 1, 7, 1, 5, 2, 4, 6, 1, "moong dal, ghee, sugar, cardamom, cashews, raisins", "A rich, heavy dessert made from mung bean paste, ghee, and sugar.", "hot"),
    ("Peda", "", "North Indian", "Dessert", "Sweet", "Dairy Dish", "Veg", "", 6.0, "Mild", 8, 1, 1, 1, 1, 1, 5, 1, 5, 2, 4, 5, 1, "khoa, sugar, cardamom, saffron, pistachios", "Small, semi-soft circular sweets made from khoa and sugar.", "room_temp"),
    ("Mysore Pak", "", "South Indian", "Dessert", "Sweet", "Grain Dish", "Veg", "", 6.5, "Mild", 7, 1, 1, 1, 1, 1, 7, 1, 5, 4, 3, 4, 1, "gram flour, ghee, sugar", "A crumbly, porous sweet from South India made of gram flour, ghee, and sugar.", "room_temp"),
    ("Sandesh", "", "East Indian", "Dessert", "Sweet", "Dairy Dish", "Veg", "", 6.0, "Mild", 7, 1, 1, 1, 1, 1, 4, 1, 4, 2, 4, 5, 1, "chhena, sugar, cardamom, saffron, pistachios", "A delicate Bengali sweet made from fresh chhena (cheese), known for its soft, melt-in-the-mouth texture.", "room_temp"),
    ("Gulab Jamun Cheesecake", "", "Fusion", "Dessert", "Fusion Sweet", "Dairy Dish", "Veg", "", 5.5, "Mild", 9, 2, 1, 1, 1, 1, 8, 1, 6, 3, 4, 6, 1, "cream cheese, gulab jamun, sugar, graham crackers, cardamom, rose water", "Modern US Indian fusion: cheesecake incorporating gulab jamun flavors.", "cold"),
]

# ══════════════════════════════════════════════════════════════════════════════
#  BUILD DATAFRAME
# ══════════════════════════════════════════════════════════════════════════════
columns = [
    "dish_name", "alternate_alias", "cuisine_name", "region", "category",
    "sub_category", "main_ingredient_category", "dietary_type", "course",
    "primary_protein", "dish_importance_score", "spice_level",
    "sweet_score", "salt_score", "sour_score", "bitter_score",
    "umami_score", "spicy_score", "rich_fat_score", "astringency_score",
    "viscosity_score", "crunchy_score", "chewy_score", "aromatic_score",
    "funk_score", "rating", "ingredients", "description", "serving_temperature",
]

rows = []
for t in appetizers:
    row = list(t[:2]) + ["Indian"] + list(t[2:4])  # name, alias, cuisine, region, category
    row.append(t[4])   # sub_category
    row.append(t[5])   # main_ingredient_category
    row.append(t[6])   # dietary_type
    row.append("Appetizer")  # course
    row.append(t[7])   # primary_protein
    row += list(t[8:25])  # scores
    row.append("")      # rating
    row += list(t[25:28])  # ingredients, description, serving_temperature
    rows.append(row)

for t in mains:
    row = list(t[:2]) + ["Indian"] + list(t[2:4])
    row.append(t[4])
    row.append(t[5])
    row.append(t[6])
    row.append("Main")
    row.append(t[7])
    row += list(t[8:25])
    row.append("")
    row += list(t[25:28])
    rows.append(row)

for t in desserts:
    row = list(t[:2]) + ["Indian"] + list(t[2:4])
    row.append(t[4])
    row.append(t[5])
    row.append(t[6])
    row.append("Dessert")
    row.append(t[7])
    row += list(t[8:25])
    row.append("")
    row += list(t[25:28])
    rows.append(row)

new_df = pd.DataFrame(rows, columns=columns)

# ══════════════════════════════════════════════════════════════════════════════
#  REPLACE IN CSV
# ══════════════════════════════════════════════════════════════════════════════
df = pd.read_csv(CSV_PATH)
print(f"Before: {len(df)} total rows, {len(df[df['cuisine_name'] == 'Indian'])} Indian")

# Remove all Indian dishes
df = df[df["cuisine_name"] != "Indian"]
print(f"After removing Indian: {len(df)} rows")

# Add new Indian dishes
df = pd.concat([df, new_df], ignore_index=True)
print(f"After adding new Indian: {len(df)} total rows, {len(df[df['cuisine_name'] == 'Indian'])} Indian")

# Save
df.to_csv(CSV_PATH, index=False)
print(f"\nSaved to {CSV_PATH}")

# Summary
indian = df[df["cuisine_name"] == "Indian"]
print(f"\n=== Indian Dish Summary ===")
print(f"Total: {len(indian)}")
print(f"\nBy course:")
print(indian["course"].value_counts().to_string())
print(f"\nBy dietary_type:")
print(indian["dietary_type"].value_counts().to_string())
print(f"\nBy main_ingredient_category:")
print(indian["main_ingredient_category"].value_counts().to_string())
