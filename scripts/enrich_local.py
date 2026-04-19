#!/usr/bin/env python3
"""
TasteMate Local Data Enrichment — No API needed
=================================================
Uses food science heuristics + keyword matching to:
1. Re-score bitter_score, astringency_score, funk_score
2. Enrich ingredients from ~4.3 to 8-12 per dish
"""

import os
import re
import pandas as pd
import numpy as np

INPUT_CSV = os.path.join(os.path.dirname(__file__), "..", "data", "dishes.csv")
OUTPUT_CSV = os.path.join(os.path.dirname(__file__), "..", "data", "dishes_enriched.csv")


# ══════════════════════════════════════════════════════════════════════════════
#  BITTER SCORE RULES
# ══════════════════════════════════════════════════════════════════════════════

# Keywords in dish name or ingredients → bitter score
BITTER_KEYWORDS = {
    # Very bitter (7-9)
    "bitter gourd": 9, "karela": 9, "bitter melon": 9, "pare": 8,
    "amaro": 8, "campari": 8, "angostura": 7,
    # Moderately bitter (5-7)
    "espresso": 7, "dark chocolate": 6, "cocoa": 6, "cacao": 6,
    "coffee": 5, "mocha": 5, "tiramisu": 5,
    "fenugreek": 5, "methi": 5, "kasoori methi": 4,
    "broccoli rabe": 6, "rapini": 6, "dandelion": 6,
    "radicchio": 5, "endive": 5, "chicory": 5,
    "kale": 4, "arugula": 4, "rocket": 4, "mustard green": 4,
    "brussels sprout": 4, "broccoli": 3,
    "tonic water": 5, "tonic": 4,
    "grapefruit": 4, "citrus peel": 4, "orange peel": 4, "lemon zest": 3,
    "beer": 4, "stout": 5, "ale": 4, "hops": 5,
    "dark beer": 5, "porter": 5,
    # Mildly bitter (2-3)
    "eggplant": 3, "aubergine": 3, "baingan": 3, "brinjal": 3,
    "turmeric": 2, "haldi": 2,
    "olive": 2, "walnut": 2, "pecan": 2, "almond": 2,
    "spinach": 2, "turnip": 2, "radish": 2, "daikon": 2,
    "gourd": 2, "squash": 2, "zucchini": 2,
    "artichoke": 4, "asparagus": 3,
    "celery": 2, "parsley": 2,
    "matcha": 5, "green tea": 4, "black tea": 3, "tea": 3,
}

# Sub-category adjustments
BITTER_SUBCAT = {
    "charred": 3, "blackened": 3, "grilled dish": 2, "grill": 2,
    "roast": 2, "smoked": 2,
}


def score_bitter(row):
    name = str(row.get("dish_name", "")).lower()
    ing = str(row.get("ingredients", "")).lower()
    subcat = str(row.get("sub_category", "")).lower()
    combined = f"{name} {ing}"

    scores = []
    for keyword, val in BITTER_KEYWORDS.items():
        if keyword in combined:
            scores.append(val)

    # Sub-category bonus
    for keyword, val in BITTER_SUBCAT.items():
        if keyword in subcat or keyword in name:
            scores.append(val)

    if not scores:
        # Desserts tend to have minimal bitterness unless chocolate
        cat = str(row.get("category", "")).lower()
        if cat == "dessert":
            if any(w in combined for w in ["chocolate", "cocoa", "coffee", "matcha"]):
                return max(scores) if scores else 4
            return 1
        return 1

    return min(max(scores), 10)


# ══════════════════════════════════════════════════════════════════════════════
#  ASTRINGENCY SCORE RULES
# ══════════════════════════════════════════════════════════════════════════════

ASTRINGENCY_KEYWORDS = {
    # High astringency (5-8)
    "persimmon": 7, "unripe banana": 7, "raw banana": 6, "green banana": 5,
    "red wine": 5, "wine reduction": 5, "wine sauce": 5,
    "pomegranate": 5, "anardana": 5, "pomegranate molasses": 4,
    "cranberry": 5, "cranberries": 5,
    "tannin": 6,
    "green tea": 5, "matcha": 5, "black tea": 4, "tea": 3,
    "strong tea": 5, "chai": 3,
    "grape leaves": 4, "vine leaves": 4,
    "red grape": 4,
    "acorn": 5, "oak": 3,
    # Moderate (3-4)
    "lentil": 3, "dal": 3, "daal": 3, "toor": 3, "masoor": 3, "urad": 3, "chana": 3,
    "chickpea": 3, "garbanzo": 3,
    "kidney bean": 3, "rajma": 3, "black bean": 3, "pinto bean": 3,
    "dried bean": 3, "bean": 2,
    "walnut": 3, "pecan": 3, "chestnut": 3,
    "spinach": 3, "kale": 3, "chard": 3,
    "eggplant": 3, "aubergine": 3,
    "tamarind": 3, "imli": 3,
    "turmeric": 2,
    "red cabbage": 3,
    "artichoke": 4,
    "rhubarb": 4,
    "cinnamon": 2, "clove": 2, "star anise": 2,
    # Slight (2)
    "tomato": 2,  # raw tomatoes slightly astringent
    "potato": 1,  # basically none
}

# Reduce astringency for fatty/creamy dishes
ASTRINGENCY_REDUCERS = [
    "cream", "butter", "ghee", "oil", "coconut milk", "coconut cream",
    "lard", "fried", "deep fried", "cheese", "mascarpone", "ricotta",
    "mayo", "mayonnaise", "avocado", "fatty",
]


def score_astringency(row):
    name = str(row.get("dish_name", "")).lower()
    ing = str(row.get("ingredients", "")).lower()
    subcat = str(row.get("sub_category", "")).lower()
    combined = f"{name} {ing}"

    scores = []
    for keyword, val in ASTRINGENCY_KEYWORDS.items():
        if keyword in combined:
            scores.append(val)

    if not scores:
        base = 1
    else:
        base = max(scores)

    # Fatty/creamy dishes reduce astringency
    reducer_count = sum(1 for r in ASTRINGENCY_REDUCERS if r in combined)
    if reducer_count >= 2:
        base = max(1, base - 2)
    elif reducer_count == 1:
        base = max(1, base - 1)

    # Fried dishes are low astringency
    if any(w in subcat for w in ["fried", "fritter", "deep"]):
        base = max(1, base - 1)

    # Salads with raw veg have slight astringency
    if subcat in ("salad", "herb salad", "raw"):
        base = max(base, 2)

    return min(base, 10)


# ══════════════════════════════════════════════════════════════════════════════
#  FUNK SCORE RULES
# ══════════════════════════════════════════════════════════════════════════════

FUNK_KEYWORDS = {
    # Extremely funky (7-9)
    "stinky tofu": 9, "chou doufu": 9, "natto": 8,
    "century egg": 8, "pidan": 8,
    "surströmming": 10,
    "blue cheese": 7, "roquefort": 7, "gorgonzola": 7, "stilton": 7,
    "belacan": 7, "terasi": 7, "shrimp paste": 7, "kapi": 6,
    "fermented shrimp": 7, "bagoong": 7,
    "doenjang": 6, "cheonggukjang": 8, "fermented soybean": 6,
    "dried shrimp": 5, "dried fish": 5,
    # Strongly funky (5-6)
    "fish sauce": 5, "nam pla": 5, "nuoc mam": 5, "patis": 5,
    "miso": 5, "red miso": 6, "white miso": 4,
    "kimchi": 6, "gochujang": 4, "doenjang jjigae": 6,
    "sauerkraut": 5, "fermented cabbage": 5,
    "anchovy": 5, "anchovies": 5,
    "oyster sauce": 4, "fermented black bean": 5,
    "tempeh": 5, "tapai": 5,
    "aged cheese": 5, "parmesan": 4, "parmigiano": 4, "pecorino": 4,
    "gruyère": 4, "gruyere": 4, "comté": 4, "comte": 4,
    "cheddar": 3, "aged cheddar": 4,
    "fermented": 5, "pickled": 3,
    "preserved": 4, "cured": 3,
    "salami": 4, "prosciutto": 3, "chorizo": 3, "nduja": 5,
    "garum": 6,
    "stinky": 7, "pungent": 5,
    "worcestershire": 4,
    "umeboshi": 4, "narezushi": 6,
    # Moderately funky (3-4)
    "yogurt": 3, "dahi": 3, "curd": 3, "lassi": 2,
    "kefir": 4, "buttermilk": 3, "chaas": 3,
    "soy sauce": 3, "shoyu": 3, "tamari": 3,
    "vinegar": 2, "rice vinegar": 2,
    "pickle": 3, "achar": 3, "achaar": 3,
    "tamarind": 2, "fermented rice": 4,
    "tripe": 4, "offal": 4, "intestine": 4, "liver": 3,
    "blood sausage": 4, "blood": 3, "sundae": 4,
    "dried squid": 5, "squid paste": 5, "bonito": 4, "katsuobushi": 4, "dashi": 3,
    # Slight (2)
    "cheese": 2, "cream cheese": 2, "mozzarella": 2,
    "butter": 1, "cream": 1,
}

# Cuisine-specific funk baseline
CUISINE_FUNK_BOOST = {
    "korean": 2,     # fermented ingredients in many dishes
    "japanese": 1,   # soy, miso, dashi common
    "thai": 1,       # fish sauce common
    "vietnamese": 1, # fish sauce, shrimp paste
    "indonesian": 1, # shrimp paste, fermented
    "chinese": 1,    # fermented black beans, soy sauce
}


def score_funk(row):
    name = str(row.get("dish_name", "")).lower()
    ing = str(row.get("ingredients", "")).lower()
    cuisine = str(row.get("cuisine_name", "")).lower()
    subcat = str(row.get("sub_category", "")).lower()
    combined = f"{name} {ing}"

    scores = []
    for keyword, val in FUNK_KEYWORDS.items():
        if keyword in combined:
            scores.append(val)

    if not scores:
        base = 1
    else:
        base = max(scores)

    # Cuisine baseline boost
    boost = CUISINE_FUNK_BOOST.get(cuisine, 0)
    if base <= 2 and boost > 0:
        # Only apply cuisine boost if dish likely uses fermented ingredients
        # Check for common dishes in these cuisines that always have fermented elements
        if cuisine == "korean" and subcat in ("jjigae", "stew", "soup", "kimchi dish",
                                               "bibimbap", "fried rice", "stir-fry",
                                               "noodle dish", "noodle soup", "savory pancake"):
            base = max(base, 3)
        elif cuisine in ("thai", "vietnamese") and subcat in ("curry", "stir-fry",
                                                               "noodle soup", "soup",
                                                               "salad", "minced meat salad",
                                                               "pounded salad", "noodle dish"):
            base = max(base, 3)
        elif cuisine == "japanese" and subcat in ("noodle soup", "soup", "rice dish",
                                                   "noodle dish", "stew"):
            base = max(base, 3)
        elif cuisine == "indonesian" and subcat in ("curry", "stir-fry", "soup",
                                                     "noodle soup", "satay", "rice dish"):
            base = max(base, 3)

    # Fresh/baked items are low funk
    cat = str(row.get("category", "")).lower()
    if cat == "dessert" and base <= 2:
        base = 1
    if cat == "bread" and base <= 2:
        base = 1
    if "drink" in cat and base <= 2:
        base = 1

    return min(base, 10)


# ══════════════════════════════════════════════════════════════════════════════
#  INGREDIENTS ENRICHMENT
# ══════════════════════════════════════════════════════════════════════════════

# Base ingredients by cuisine that are commonly used
CUISINE_BASE_INGREDIENTS = {
    "indian": {
        "curry": ["onion", "garlic", "ginger", "turmeric", "cumin seeds", "coriander powder", "garam masala", "oil", "tomato", "green chili"],
        "flatbread": ["whole wheat flour", "salt", "water", "ghee"],
        "rice dish": ["basmati rice", "ghee", "cumin seeds", "bay leaf", "whole spices"],
        "sweet": ["sugar", "ghee", "cardamom", "milk"],
        "chaat": ["chaat masala", "tamarind chutney", "mint chutney", "yogurt", "sev"],
        "dal": ["toor dal", "turmeric", "cumin seeds", "mustard seeds", "onion", "tomato", "garlic", "green chili"],
        "biryani": ["basmati rice", "saffron", "yogurt", "fried onions", "whole spices", "ghee", "mint", "coriander leaves"],
        "_default": ["oil", "onion", "garlic", "ginger", "turmeric", "salt", "cumin"],
    },
    "thai": {
        "curry": ["coconut milk", "thai basil", "kaffir lime leaves", "fish sauce", "palm sugar", "galangal", "lemongrass", "thai chili"],
        "stir-fry": ["vegetable oil", "garlic", "fish sauce", "oyster sauce", "soy sauce", "sugar", "thai chili"],
        "soup": ["lemongrass", "galangal", "kaffir lime leaves", "fish sauce", "lime juice", "thai chili"],
        "noodle soup": ["rice noodles", "broth", "fish sauce", "bean sprouts", "scallions", "lime", "thai basil"],
        "salad": ["fish sauce", "lime juice", "palm sugar", "thai chili", "shallot", "cilantro"],
        "sweet": ["coconut milk", "palm sugar", "rice flour", "pandan leaves"],
        "_default": ["fish sauce", "garlic", "thai chili", "lime juice", "palm sugar", "vegetable oil"],
    },
    "italian": {
        "pasta": ["pasta", "olive oil", "garlic", "parmesan cheese", "salt", "black pepper"],
        "flatbread": ["bread flour", "olive oil", "salt", "yeast", "water"],
        "soup": ["olive oil", "garlic", "onion", "celery", "carrot", "broth", "parmesan rind"],
        "risotto": ["arborio rice", "broth", "onion", "white wine", "butter", "parmesan"],
        "stew": ["olive oil", "onion", "garlic", "tomato", "white wine", "parsley"],
        "sweet": ["sugar", "eggs", "butter", "flour", "vanilla"],
        "_default": ["olive oil", "garlic", "salt", "black pepper", "parmesan"],
    },
    "japanese": {
        "sushi": ["sushi rice", "rice vinegar", "nori seaweed", "wasabi", "soy sauce"],
        "noodle soup": ["dashi broth", "soy sauce", "mirin", "scallions", "nori"],
        "noodle dish": ["soy sauce", "mirin", "dashi", "sesame oil", "scallions"],
        "rice dish": ["japanese rice", "soy sauce", "mirin", "dashi", "sesame seeds"],
        "grilled dish": ["soy sauce", "mirin", "sake", "ginger"],
        "sweet": ["rice flour", "red bean paste", "sugar", "matcha"],
        "_default": ["soy sauce", "mirin", "dashi", "rice vinegar", "sesame oil"],
    },
    "korean": {
        "jjigae": ["gochugaru", "gochujang", "garlic", "soy sauce", "sesame oil", "scallions", "tofu"],
        "stew": ["gochugaru", "doenjang", "garlic", "scallions", "sesame oil"],
        "rice dish": ["korean rice", "sesame oil", "soy sauce", "garlic", "gochugaru"],
        "noodle dish": ["gochugaru", "soy sauce", "sesame oil", "garlic", "scallions"],
        "savory pancake": ["flour", "scallions", "egg", "soy sauce", "sesame oil"],
        "grilled dish": ["soy sauce", "sesame oil", "garlic", "sugar", "pear juice", "scallions"],
        "kimchi dish": ["kimchi", "gochugaru", "garlic", "sesame oil", "scallions"],
        "sweet": ["rice flour", "sugar", "sesame seeds", "red bean paste"],
        "_default": ["garlic", "soy sauce", "sesame oil", "gochugaru", "scallions"],
    },
    "chinese": {
        "stir-fry": ["vegetable oil", "garlic", "ginger", "soy sauce", "shaoxing wine", "cornstarch", "scallions"],
        "soup": ["broth", "ginger", "scallions", "soy sauce", "sesame oil", "white pepper"],
        "noodle dish": ["noodles", "soy sauce", "sesame oil", "garlic", "scallions", "chili oil"],
        "noodle soup": ["broth", "noodles", "soy sauce", "scallions", "ginger", "star anise"],
        "rice dish": ["jasmine rice", "soy sauce", "sesame oil", "scallions", "egg"],
        "dumpling": ["flour wrapper", "pork", "ginger", "scallions", "soy sauce", "sesame oil"],
        "sweet": ["sugar", "red bean paste", "glutinous rice flour"],
        "_default": ["soy sauce", "ginger", "garlic", "scallions", "sesame oil", "vegetable oil"],
    },
    "mexican": {
        "taco": ["corn tortilla", "onion", "cilantro", "lime", "salsa", "chili"],
        "stew": ["dried chili", "onion", "garlic", "tomato", "cumin", "oregano", "broth"],
        "bean dish": ["pinto beans", "onion", "garlic", "cumin", "oregano", "chili"],
        "rice dish": ["rice", "tomato", "onion", "garlic", "chicken broth", "cumin"],
        "soup": ["onion", "garlic", "tomato", "chili", "cumin", "oregano", "cilantro", "lime"],
        "sweet": ["sugar", "cinnamon", "vanilla", "milk", "eggs"],
        "_default": ["onion", "garlic", "chili", "cumin", "cilantro", "lime", "salt"],
    },
    "french": {
        "soup": ["butter", "onion", "leek", "broth", "cream", "thyme", "bay leaf"],
        "stew": ["butter", "onion", "carrot", "celery", "wine", "broth", "thyme", "bay leaf"],
        "sauté": ["butter", "shallot", "white wine", "cream", "thyme", "parsley"],
        "pastry": ["butter", "flour", "eggs", "sugar", "vanilla"],
        "sweet": ["butter", "sugar", "flour", "eggs", "cream", "vanilla"],
        "flatbread": ["flour", "butter", "salt", "yeast"],
        "_default": ["butter", "shallot", "garlic", "thyme", "cream", "white wine", "salt", "black pepper"],
    },
    "lebanese": {
        "dip": ["olive oil", "lemon juice", "garlic", "salt", "cumin"],
        "stew": ["olive oil", "onion", "garlic", "tomato", "lemon juice", "cumin", "coriander"],
        "grilled dish": ["olive oil", "garlic", "lemon juice", "sumac", "seven spice"],
        "flatbread": ["flour", "yeast", "olive oil", "salt", "water"],
        "salad": ["olive oil", "lemon juice", "garlic", "mint", "parsley", "sumac"],
        "sweet": ["sugar", "rose water", "orange blossom water", "pistachio", "phyllo"],
        "_default": ["olive oil", "garlic", "lemon juice", "salt", "cumin", "parsley"],
    },
    "turkish": {
        "kebab": ["onion", "garlic", "cumin", "paprika", "salt", "black pepper", "sumac", "olive oil"],
        "stew": ["onion", "garlic", "tomato paste", "pepper paste", "butter", "cumin"],
        "flatbread": ["flour", "yeast", "salt", "olive oil", "butter"],
        "sweet": ["sugar", "butter", "phyllo", "pistachio", "rose water", "syrup"],
        "soup": ["onion", "butter", "red lentils", "tomato paste", "cumin", "paprika", "lemon"],
        "_default": ["onion", "garlic", "tomato paste", "butter", "cumin", "paprika", "salt"],
    },
    "greek": {
        "stew": ["olive oil", "onion", "garlic", "tomato", "oregano", "cinnamon", "bay leaf"],
        "grilled dish": ["olive oil", "lemon juice", "oregano", "garlic", "salt"],
        "salad": ["olive oil", "red wine vinegar", "oregano", "feta cheese", "tomato", "cucumber"],
        "sweet": ["phyllo", "honey", "walnuts", "cinnamon", "butter"],
        "dip": ["olive oil", "garlic", "lemon juice", "yogurt"],
        "_default": ["olive oil", "garlic", "lemon juice", "oregano", "feta cheese", "salt"],
    },
    "spanish": {
        "stew": ["olive oil", "onion", "garlic", "tomato", "paprika", "saffron", "bay leaf"],
        "grilled dish": ["olive oil", "garlic", "sea salt", "paprika", "lemon"],
        "rice dish": ["bomba rice", "olive oil", "saffron", "garlic", "broth", "paprika"],
        "sweet": ["sugar", "eggs", "flour", "olive oil", "cinnamon", "lemon zest"],
        "_default": ["olive oil", "garlic", "onion", "paprika", "salt", "black pepper"],
    },
    "vietnamese": {
        "soup": ["fish sauce", "star anise", "cinnamon", "ginger", "scallions", "bean sprouts", "lime", "thai basil"],
        "noodle soup": ["rice noodles", "broth", "fish sauce", "star anise", "ginger", "bean sprouts", "lime", "herbs"],
        "stir-fry": ["fish sauce", "garlic", "shallot", "lemongrass", "sugar", "vegetable oil"],
        "roll": ["rice paper", "vermicelli", "lettuce", "herbs", "fish sauce", "peanuts"],
        "salad": ["fish sauce", "lime juice", "sugar", "garlic", "chili", "herbs"],
        "sweet": ["coconut milk", "sugar", "tapioca", "pandan"],
        "_default": ["fish sauce", "garlic", "shallot", "sugar", "lime juice", "vegetable oil"],
    },
    "indonesian": {
        "curry": ["coconut milk", "shallot", "garlic", "galangal", "lemongrass", "turmeric", "chili", "shrimp paste"],
        "stir-fry": ["sweet soy sauce", "garlic", "shallot", "chili", "vegetable oil"],
        "soup": ["broth", "shallot", "garlic", "turmeric", "lemongrass", "lime leaves"],
        "grilled dish": ["sweet soy sauce", "shallot", "garlic", "coriander", "cumin", "lime"],
        "fried dish": ["vegetable oil", "shallot", "garlic", "turmeric", "salt"],
        "sweet": ["coconut milk", "palm sugar", "rice flour", "pandan"],
        "_default": ["shallot", "garlic", "chili", "sweet soy sauce", "vegetable oil", "salt"],
    },
    "brazilian": {
        "stew": ["onion", "garlic", "tomato", "bay leaf", "cumin", "coconut milk", "palm oil"],
        "grilled dish": ["coarse salt", "garlic", "lime", "black pepper"],
        "rice dish": ["rice", "garlic", "onion", "oil", "salt", "bay leaf"],
        "sweet": ["sugar", "condensed milk", "coconut", "eggs", "butter"],
        "_default": ["garlic", "onion", "salt", "lime", "oil", "black pepper"],
    },
    "colombian": {
        "soup": ["potato", "onion", "garlic", "cilantro", "cumin", "broth", "corn"],
        "stew": ["onion", "garlic", "tomato", "cumin", "cilantro", "potato"],
        "fried dish": ["corn flour", "cheese", "salt", "oil"],
        "_default": ["onion", "garlic", "cumin", "cilantro", "salt", "oil"],
    },
    "peruvian": {
        "stew": ["onion", "garlic", "aji amarillo", "cumin", "potato", "cilantro"],
        "grilled dish": ["aji panca", "garlic", "cumin", "lime", "oil"],
        "rice dish": ["rice", "garlic", "onion", "oil", "cilantro"],
        "sweet": ["condensed milk", "sugar", "vanilla", "cinnamon"],
        "_default": ["garlic", "onion", "aji amarillo", "lime", "cumin", "cilantro", "salt"],
    },
    "hungarian": {
        "stew": ["onion", "paprika", "garlic", "caraway seeds", "tomato", "sour cream", "lard"],
        "soup": ["onion", "paprika", "garlic", "caraway seeds", "potato", "egg noodles"],
        "sweet": ["sugar", "flour", "eggs", "butter", "walnut", "poppy seed"],
        "_default": ["onion", "paprika", "garlic", "caraway seeds", "sour cream", "lard", "salt"],
    },
    "polish": {
        "soup": ["onion", "garlic", "dill", "sour cream", "potato", "broth"],
        "stew": ["onion", "garlic", "bay leaf", "allspice", "butter", "sour cream"],
        "sweet": ["flour", "sugar", "eggs", "butter", "poppy seed", "vanilla"],
        "dumpling": ["flour", "potato", "onion", "butter", "salt", "egg"],
        "_default": ["onion", "garlic", "dill", "butter", "sour cream", "salt", "black pepper"],
    },
    "portuguese": {
        "stew": ["olive oil", "onion", "garlic", "bay leaf", "paprika", "white wine", "tomato"],
        "grilled dish": ["olive oil", "garlic", "sea salt", "lemon", "parsley"],
        "sweet": ["sugar", "eggs", "cinnamon", "butter", "flour"],
        "_default": ["olive oil", "garlic", "onion", "bay leaf", "salt", "parsley"],
    },
    "croatian": {
        "stew": ["olive oil", "onion", "garlic", "tomato", "red wine", "bay leaf", "rosemary"],
        "grilled dish": ["olive oil", "garlic", "rosemary", "sea salt", "lemon"],
        "sweet": ["sugar", "eggs", "flour", "butter", "walnut", "lemon zest"],
        "_default": ["olive oil", "garlic", "onion", "salt", "black pepper", "parsley"],
    },
    "serbian": {
        "grilled dish": ["salt", "black pepper", "onion", "paprika", "oil"],
        "stew": ["onion", "garlic", "paprika", "tomato", "oil", "bay leaf"],
        "sweet": ["sugar", "flour", "eggs", "walnut", "vanilla"],
        "_default": ["onion", "garlic", "paprika", "salt", "oil", "black pepper"],
    },
    "georgian": {
        "stew": ["onion", "garlic", "walnut", "coriander", "fenugreek", "marigold", "vinegar"],
        "grilled dish": ["salt", "black pepper", "adjika", "tkemali sauce"],
        "dumpling": ["flour", "beef", "onion", "cumin", "coriander", "chili flakes"],
        "sweet": ["walnut", "honey", "grape must", "flour", "sugar"],
        "_default": ["garlic", "walnut", "coriander", "fenugreek", "onion", "salt"],
    },
    "american": {
        "grilled dish": ["salt", "black pepper", "garlic powder", "onion powder", "paprika", "oil"],
        "stew": ["onion", "garlic", "broth", "potato", "carrot", "celery", "thyme", "bay leaf"],
        "sandwich": ["bread", "butter", "lettuce", "tomato", "mayonnaise"],
        "sweet": ["sugar", "butter", "flour", "eggs", "vanilla", "baking powder"],
        "_default": ["salt", "black pepper", "garlic", "onion", "butter", "oil"],
    },
}


def enrich_ingredients(row):
    """Enrich ingredients to 8-12 items."""
    name = str(row.get("dish_name", "")).lower()
    current = str(row.get("ingredients", ""))
    cuisine = str(row.get("cuisine_name", "")).lower()
    subcat = str(row.get("sub_category", "")).lower()
    cat = str(row.get("category", "")).lower()

    # Parse current ingredients
    current_items = [i.strip() for i in current.split(",") if i.strip()]
    current_lower = set(i.lower() for i in current_items)

    # Already has enough
    if len(current_items) >= 8:
        return current

    # Get cuisine-specific additions
    cuisine_map = CUISINE_BASE_INGREDIENTS.get(cuisine, {})

    # Try sub_category first, then category, then default
    additions = []
    if subcat in cuisine_map:
        additions = cuisine_map[subcat]
    elif cat in cuisine_map:
        additions = cuisine_map[cat]

    # Also check broader sub_category matches
    if not additions:
        for key in cuisine_map:
            if key != "_default" and key in subcat:
                additions = cuisine_map[key]
                break

    if not additions:
        additions = cuisine_map.get("_default", [])

    # Add items that aren't already present
    for item in additions:
        if item.lower() not in current_lower and len(current_items) < 12:
            # Check it's not a near-duplicate
            is_dup = False
            for existing in current_lower:
                if item.lower() in existing or existing in item.lower():
                    is_dup = True
                    break
            if not is_dup:
                current_items.append(item)
                current_lower.add(item.lower())

    return ", ".join(current_items)


# ══════════════════════════════════════════════════════════════════════════════
#  MAIN
# ══════════════════════════════════════════════════════════════════════════════

def main():
    print(f"Loading {INPUT_CSV}...")
    df = pd.read_csv(INPUT_CSV)
    total = len(df)
    print(f"Total dishes: {total}")

    # Store original stats
    print("\n── BEFORE ──")
    for col in ["bitter_score", "astringency_score", "funk_score"]:
        vals = pd.to_numeric(df[col], errors="coerce")
        mode = vals.mode()[0] if len(vals.mode()) > 0 else 0
        mode_pct = (vals == mode).mean() * 100
        print(f"  {col:22s}: mean={vals.mean():.1f}, std={vals.std():.1f}, {mode_pct:.0f}% are {mode:.0f}")
    ing_lens = df["ingredients"].dropna().str.split(",").apply(len)
    print(f"  {'ingredients':22s}: avg={ing_lens.mean():.1f} items/dish, {(ing_lens < 3).sum()} dishes < 3")

    # Apply enrichment
    print("\nEnriching...")
    df["bitter_score"] = df.apply(score_bitter, axis=1)
    df["astringency_score"] = df.apply(score_astringency, axis=1)
    df["funk_score"] = df.apply(score_funk, axis=1)
    df["ingredients"] = df.apply(enrich_ingredients, axis=1)

    # Stats after
    print("\n── AFTER ──")
    for col in ["bitter_score", "astringency_score", "funk_score"]:
        vals = pd.to_numeric(df[col], errors="coerce")
        mode = vals.mode()[0] if len(vals.mode()) > 0 else 0
        mode_pct = (vals == mode).mean() * 100
        unique = vals.nunique()
        print(f"  {col:22s}: mean={vals.mean():.1f}, std={vals.std():.1f}, {unique} unique values, {mode_pct:.0f}% mode={mode:.0f}")
    ing_lens = df["ingredients"].dropna().str.split(",").apply(len)
    print(f"  {'ingredients':22s}: avg={ing_lens.mean():.1f} items/dish, {(ing_lens < 3).sum()} dishes < 3")

    # Save
    df.to_csv(OUTPUT_CSV, index=False)
    print(f"\nSaved to {OUTPUT_CSV}")

    # Show some examples
    print("\n── SAMPLE ENRICHED DISHES ──")
    samples = [
        ("Indian", "Rajma Masala"), ("Indian", "Methi Paratha"),
        ("Thai", "Green Curry"), ("Thai", "Som Tam"),
        ("Korean", "Kimchi Jjigae"), ("Korean", "Bibimbap"),
        ("Japanese", "Miso Soup"), ("Italian", "Tiramisu"),
        ("French", "Coq au Vin"), ("Indonesian", "Nasi Goreng"),
    ]
    for cuisine, dish in samples:
        row = df[(df["cuisine_name"] == cuisine) & (df["dish_name"].str.contains(dish, case=False, na=False))]
        if not row.empty:
            r = row.iloc[0]
            print(f"\n  {r['dish_name']} ({cuisine}):")
            print(f"    bitter={r['bitter_score']}, astringency={r['astringency_score']}, funk={r['funk_score']}")
            print(f"    ingredients: {r['ingredients']}")

    print(f"\n✓ Done! To use: cp data/dishes_enriched.csv data/dishes.csv")


if __name__ == "__main__":
    main()
