#!/usr/bin/env python3
"""Replace ALL Italian dishes in dishes.csv with curated 150 dishes from PDF."""

import pandas as pd
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CSV_PATH = os.path.join(BASE_DIR, "data", "dishes.csv")

# ══════════════════════════════════════════════════════════════════════════════
#  50 APPETIZERS (Antipasti)
# ══════════════════════════════════════════════════════════════════════════════
appetizers = [
    # dish_name, alternate_alias, region, category, sub_category, main_ingredient_category, dietary_type, primary_protein, dish_importance_score, spice_level, sweet, salt, sour, bitter, umami, spicy, rich_fat, astringency, viscosity, crunchy, chewy, aromatic, funk, ingredients, description, serving_temperature
    ("Calamari Fritti", "", "Southern Italian", "Appetizer", "Fried Seafood", "Seafood Dish", "Non-Veg", "Squid", 9.0, "Mild", 1, 5, 2, 1, 5, 1, 6, 1, 2, 8, 4, 4, 2, "squid, flour, semolina, salt, lemon, marinara sauce, oil", "Lightly battered and fried calamari rings served with marinara and lemon wedges.", "hot"),
    ("Bruschetta al Pomodoro", "", "Tuscan", "Appetizer", "Bread", "Grain Dish", "Vegan", "", 9.0, "Mild", 1, 5, 3, 1, 4, 1, 4, 1, 2, 7, 3, 6, 1, "bread, tomatoes, garlic, basil, olive oil, salt", "Grilled bread rubbed with garlic and topped with diced tomatoes, basil, and olive oil.", "room_temp"),
    ("Arancini", "Sicilian Rice Balls", "Sicilian", "Appetizer", "Fried Snack", "Grain Dish", "Non-Veg", "Beef", 8.5, "Mild", 1, 5, 1, 1, 6, 1, 6, 1, 4, 7, 4, 5, 1, "arborio rice, mozzarella, peas, beef ragu, breadcrumbs, saffron, oil", "Crispy fried rice balls stuffed with ragu, mozzarella, and peas.", "hot"),
    ("Burrata with Prosciutto", "", "Southern Italian", "Appetizer", "Cheese Plate", "Dairy Dish", "Non-Veg", "Pork", 9.0, "Mild", 1, 5, 1, 1, 5, 1, 8, 1, 4, 2, 3, 5, 2, "burrata, prosciutto di Parma, olive oil, arugula, balsamic glaze", "Creamy burrata cheese paired with thinly sliced prosciutto and arugula.", "room_temp"),
    ("Caprese Salad", "Insalata Caprese", "Neapolitan", "Appetizer", "Salad", "Dairy Dish", "Veg", "", 9.0, "Mild", 1, 4, 2, 1, 4, 1, 5, 1, 2, 2, 3, 6, 1, "fresh mozzarella, tomatoes, basil, olive oil, salt, balsamic vinegar", "Fresh mozzarella, ripe tomatoes, and basil drizzled with olive oil.", "room_temp"),
    ("Beef Carpaccio", "", "Venetian", "Appetizer", "Raw Meat", "Red Meat Dish", "Non-Veg", "Beef", 8.0, "Mild", 1, 4, 2, 1, 6, 1, 4, 1, 2, 2, 3, 5, 2, "beef tenderloin, arugula, Parmigiano-Reggiano, capers, lemon, olive oil", "Paper-thin slices of raw beef dressed with arugula, Parmesan shavings, and lemon.", "cold"),
    ("Mussels Fra Diavolo", "", "Southern Italian", "Appetizer", "Spicy Seafood", "Seafood Dish", "Non-Veg", "Shellfish", 7.5, "Hot", 1, 5, 3, 1, 6, 7, 5, 1, 4, 2, 4, 7, 2, "mussels, San Marzano tomatoes, red pepper flakes, garlic, white wine, parsley", "Steamed mussels in a spicy tomato-garlic sauce with crusty bread.", "hot"),
    ("Clams Oreganata", "", "Southern Italian", "Appetizer", "Baked Seafood", "Seafood Dish", "Non-Veg", "Shellfish", 7.5, "Mild", 1, 5, 1, 1, 6, 1, 5, 1, 3, 6, 3, 6, 2, "littleneck clams, breadcrumbs, garlic, oregano, olive oil, Pecorino Romano, lemon", "Baked clams topped with seasoned breadcrumbs, oregano, and Pecorino.", "hot"),
    ("Polpette", "Italian Meatballs", "Southern Italian", "Appetizer", "Meat", "Red Meat Dish", "Non-Veg", "Beef", 8.5, "Mild", 1, 5, 2, 1, 7, 2, 6, 1, 5, 2, 5, 6, 1, "ground beef, ground pork, breadcrumbs, Parmigiano-Reggiano, egg, garlic, parsley, marinara", "Tender meatballs braised in a slow-simmered tomato sauce.", "hot"),
    ("Focaccia with Rosemary", "", "Ligurian", "Appetizer", "Bread", "Grain Dish", "Vegan", "", 8.0, "Mild", 1, 5, 1, 1, 3, 1, 5, 1, 3, 5, 5, 7, 1, "flour, olive oil, rosemary, sea salt, yeast, water", "Fluffy, olive oil-rich flatbread topped with rosemary and coarse sea salt.", "hot"),
    ("Fried Zucchini Flowers", "", "Roman", "Appetizer", "Fried Vegetable", "Vegetable Dish", "Veg", "", 7.5, "Mild", 1, 4, 1, 1, 4, 1, 6, 1, 3, 7, 3, 5, 1, "zucchini flowers, ricotta, mozzarella, anchovies, flour, sparkling water, oil", "Delicate squash blossoms stuffed with ricotta and lightly fried in a crispy batter.", "hot"),
    ("Grilled Octopus", "", "Southern Italian", "Appetizer", "Grilled Seafood", "Seafood Dish", "Non-Veg", "Octopus", 8.5, "Mild", 1, 5, 2, 1, 7, 1, 4, 1, 3, 3, 6, 6, 2, "octopus, olive oil, lemon, garlic, potatoes, capers, parsley", "Charred octopus tentacles served over warm potatoes with lemon vinaigrette.", "hot"),
    ("Tuna Tartare", "", "Sicilian", "Appetizer", "Raw Seafood", "Seafood Dish", "Non-Veg", "Tuna", 7.5, "Mild", 1, 4, 2, 1, 7, 1, 4, 1, 2, 3, 3, 5, 3, "sushi-grade tuna, capers, olive oil, lemon, avocado, shallots, chives", "Finely diced raw tuna seasoned with capers, lemon, and olive oil.", "cold"),
    ("Eggplant Rollatini", "", "Southern Italian", "Appetizer", "Baked Vegetable", "Vegetable Dish", "Veg", "", 7.0, "Mild", 1, 5, 2, 1, 5, 1, 6, 1, 5, 3, 4, 5, 1, "eggplant, ricotta, mozzarella, Parmigiano-Reggiano, marinara, basil", "Thin eggplant slices rolled around ricotta and baked in marinara sauce.", "hot"),
    ("Prosciutto e Melone", "", "Emilian", "Appetizer", "Cured Meat", "Pork Dish", "Non-Veg", "Pork", 8.0, "Mild", 4, 5, 1, 1, 5, 1, 4, 1, 2, 2, 3, 5, 2, "prosciutto di Parma, cantaloupe melon, olive oil", "Sweet ripe melon wrapped in thin slices of aged prosciutto.", "cold"),
    ("Garlic Knots", "", "Neapolitan", "Appetizer", "Bread", "Grain Dish", "Veg", "", 7.5, "Mild", 1, 5, 1, 1, 3, 1, 5, 1, 3, 5, 5, 7, 1, "pizza dough, garlic, butter, olive oil, parsley, Parmesan", "Knotted strips of pizza dough baked and tossed in garlic butter and parsley.", "hot"),
    ("Fried Smelts", "", "Southern Italian", "Appetizer", "Fried Seafood", "Seafood Dish", "Non-Veg", "Fish", 6.5, "Mild", 1, 5, 2, 1, 5, 1, 5, 1, 2, 8, 3, 4, 3, "smelts, flour, salt, lemon, oil", "Whole small fish dusted in flour and fried until golden and crispy.", "hot"),
    ("Grilled Artichokes", "", "Roman", "Appetizer", "Grilled Vegetable", "Vegetable Dish", "Vegan", "", 7.0, "Mild", 1, 4, 2, 3, 4, 1, 4, 2, 3, 4, 4, 5, 1, "artichokes, lemon, garlic, olive oil, parsley, mint", "Halved artichokes charred on the grill and dressed with lemon and olive oil.", "hot"),
    ("Crostini di Fegato", "Chicken Liver Crostini", "Tuscan", "Appetizer", "Spread", "Poultry Dish", "Non-Veg", "Chicken", 7.0, "Mild", 1, 5, 1, 2, 7, 1, 6, 1, 4, 5, 3, 6, 3, "chicken livers, onions, capers, anchovy, butter, sage, vin santo, bread", "Toasted bread spread with a rich Tuscan chicken liver pate.", "room_temp"),
    ("Stuffed Cherry Peppers", "", "Southern Italian", "Appetizer", "Stuffed Vegetable", "Pork Dish", "Non-Veg", "Pork", 7.0, "Medium", 1, 5, 2, 1, 5, 4, 5, 1, 3, 4, 4, 5, 2, "cherry peppers, prosciutto, provolone, breadcrumbs, olive oil", "Sweet-hot cherry peppers stuffed with prosciutto and provolone.", "room_temp"),
    ("Shrimp Scampi Appetizer", "", "Southern Italian", "Appetizer", "Sauteed Seafood", "Seafood Dish", "Non-Veg", "Shrimp", 8.0, "Mild", 1, 5, 2, 1, 5, 2, 6, 1, 3, 3, 4, 7, 2, "shrimp, garlic, white wine, butter, lemon, red pepper flakes, parsley, bread", "Jumbo shrimp sauteed in garlic, white wine, and butter with crusty bread.", "hot"),
    ("Mozzarella in Carrozza", "Fried Mozzarella", "Neapolitan", "Appetizer", "Fried Cheese", "Dairy Dish", "Veg", "", 7.5, "Mild", 1, 5, 1, 1, 5, 1, 7, 1, 4, 7, 5, 4, 1, "mozzarella, bread, eggs, flour, oil, anchovy (optional)", "Fried mozzarella sandwiched between bread slices, golden and stretchy.", "hot"),
    ("Roasted Peppers with Anchovies", "", "Piedmontese", "Appetizer", "Roasted Vegetable", "Seafood Dish", "Non-Veg", "Fish", 6.5, "Mild", 2, 5, 1, 1, 6, 1, 4, 1, 3, 3, 3, 5, 3, "roasted bell peppers, anchovies, garlic, olive oil, capers, parsley", "Silky roasted peppers draped with oil-cured anchovies and garlic.", "room_temp"),
    ("Panzanella Salad", "", "Tuscan", "Appetizer", "Salad", "Grain Dish", "Vegan", "", 7.0, "Mild", 1, 5, 3, 1, 4, 1, 4, 1, 2, 5, 3, 5, 1, "stale bread, tomatoes, cucumbers, red onion, basil, olive oil, red wine vinegar", "A Tuscan bread salad with ripe tomatoes, cucumbers, and red wine vinaigrette.", "room_temp"),
    ("Vitello Tonnato", "", "Piedmontese", "Appetizer", "Cold Meat", "Red Meat Dish", "Non-Veg", "Veal", 7.5, "Mild", 1, 5, 2, 1, 7, 1, 5, 1, 4, 2, 4, 5, 3, "veal loin, tuna, capers, anchovies, mayonnaise, lemon, olive oil", "Chilled sliced veal blanketed in a creamy tuna-caper sauce.", "cold"),
    ("Minestrone Soup", "", "Northern Italian", "Appetizer", "Soup", "Vegetable Dish", "Vegan", "", 8.0, "Mild", 1, 5, 2, 1, 5, 1, 3, 1, 5, 2, 3, 5, 1, "cannellini beans, zucchini, carrots, celery, tomatoes, pasta, olive oil, Parmesan", "A hearty vegetable soup with beans, pasta, and seasonal vegetables.", "hot"),
    ("Pasta e Fagioli", "", "Southern Italian", "Appetizer", "Soup", "Legume Dish", "Veg", "", 8.0, "Mild", 1, 5, 2, 1, 6, 1, 4, 1, 5, 2, 3, 5, 1, "cannellini beans, ditalini pasta, tomatoes, celery, onions, Parmesan, olive oil", "A thick, rustic soup of pasta and white beans in a tomato broth.", "hot"),
    ("Scamorza Affumicata", "", "Southern Italian", "Appetizer", "Cheese", "Dairy Dish", "Veg", "", 6.0, "Mild", 1, 5, 1, 1, 5, 1, 6, 1, 3, 3, 5, 6, 2, "smoked scamorza cheese, olive oil, bread", "Grilled smoked scamorza cheese served warm with crusty bread.", "hot"),
    ("Baccala Mantecato", "", "Venetian", "Appetizer", "Spread", "Seafood Dish", "Non-Veg", "Fish", 7.0, "Mild", 1, 5, 1, 1, 6, 1, 5, 1, 5, 4, 3, 5, 3, "salt cod, olive oil, garlic, parsley, polenta crostini", "Whipped salt cod spread served on grilled polenta crostini.", "room_temp"),
    ("Suppli al Telefono", "", "Roman", "Appetizer", "Fried Snack", "Grain Dish", "Non-Veg", "Beef", 7.5, "Mild", 1, 5, 2, 1, 6, 1, 6, 1, 4, 7, 5, 5, 1, "arborio rice, tomato sauce, mozzarella, ground beef, breadcrumbs, egg, oil", "Roman fried rice croquettes with a stretchy mozzarella center.", "hot"),
    ("Spiedini alla Romana", "", "Roman", "Appetizer", "Fried Cheese", "Dairy Dish", "Veg", "", 6.5, "Mild", 1, 5, 1, 1, 5, 1, 6, 1, 3, 6, 5, 4, 1, "mozzarella, bread, anchovy butter, flour, egg, breadcrumbs, oil", "Skewered bread and mozzarella battered, fried, and drizzled with anchovy butter.", "hot"),
    ("Escarole and Beans", "", "Southern Italian", "Appetizer", "Soup", "Legume Dish", "Vegan", "", 6.5, "Mild", 1, 5, 1, 2, 5, 1, 4, 1, 4, 2, 3, 5, 1, "escarole, cannellini beans, garlic, olive oil, red pepper flakes, chicken broth", "Braised escarole with white beans in a garlicky broth.", "hot"),
    ("Marinated Olives", "", "Southern Italian", "Appetizer", "Snack", "Vegetable Dish", "Vegan", "", 5.5, "Mild", 1, 6, 1, 2, 4, 1, 4, 1, 2, 3, 3, 6, 2, "Castelvetrano olives, Cerignola olives, garlic, orange zest, rosemary, olive oil, red pepper", "A mix of Italian olives marinated with citrus, herbs, and garlic.", "room_temp"),
    ("White Bean Dip with Crostini", "", "Tuscan", "Appetizer", "Spread", "Legume Dish", "Vegan", "", 6.0, "Mild", 1, 4, 2, 1, 4, 1, 4, 1, 4, 5, 2, 5, 1, "cannellini beans, garlic, lemon, olive oil, rosemary, bread", "Smooth white bean puree drizzled with olive oil, served with toasted crostini.", "room_temp"),
    ("Grilled Scallops with Lemon", "", "Northern Italian", "Appetizer", "Grilled Seafood", "Seafood Dish", "Non-Veg", "Shellfish", 7.5, "Mild", 1, 4, 2, 1, 6, 1, 4, 1, 3, 3, 4, 5, 2, "sea scallops, lemon, butter, garlic, white wine, parsley", "Seared diver scallops finished with lemon butter and white wine.", "hot"),
    ("Truffle Arancini", "", "Piedmontese", "Appetizer", "Fried Snack", "Grain Dish", "Veg", "", 7.5, "Mild", 1, 5, 1, 1, 7, 1, 6, 1, 4, 7, 4, 8, 2, "arborio rice, truffle oil, black truffle, fontina, breadcrumbs, Parmesan, oil", "Crispy rice balls infused with black truffle and fontina cheese.", "hot"),
    ("Culatello with Figs", "", "Emilian", "Appetizer", "Cured Meat", "Pork Dish", "Non-Veg", "Pork", 7.5, "Mild", 3, 5, 1, 1, 6, 1, 5, 1, 2, 2, 3, 6, 3, "culatello, fresh figs, honey, arugula, olive oil", "Silky slices of aged culatello served with ripe figs and a drizzle of honey.", "room_temp"),
    ("Bresaola with Arugula", "", "Lombard", "Appetizer", "Cured Meat", "Red Meat Dish", "Non-Veg", "Beef", 7.0, "Mild", 1, 5, 2, 2, 5, 1, 3, 2, 2, 3, 3, 5, 2, "bresaola, arugula, Parmigiano-Reggiano, lemon, olive oil", "Air-dried beef sliced thin, topped with arugula, Parmesan shavings, and lemon.", "cold"),
    ("Fontina Fonduta", "", "Piedmontese", "Appetizer", "Cheese Dip", "Dairy Dish", "Veg", "", 7.0, "Mild", 1, 5, 1, 1, 6, 1, 8, 1, 5, 3, 3, 6, 2, "fontina cheese, milk, butter, egg yolks, white truffle, bread", "A warm, velvety cheese fondue from the Alps, served with crusty bread.", "hot"),
    ("Fried Olives All'Ascolana", "", "Southern Italian", "Appetizer", "Fried Snack", "Pork Dish", "Non-Veg", "Pork", 7.0, "Mild", 1, 5, 1, 1, 6, 1, 6, 1, 3, 7, 4, 5, 2, "large green olives, ground pork, ground beef, breadcrumbs, egg, nutmeg, oil", "Large stuffed olives filled with seasoned meat, breaded, and deep-fried.", "hot"),
    ("Caponata Siciliana", "", "Sicilian", "Appetizer", "Stewed Vegetable", "Vegetable Dish", "Vegan", "", 7.5, "Mild", 3, 5, 4, 1, 5, 1, 4, 1, 4, 3, 3, 6, 1, "eggplant, celery, tomatoes, capers, olives, pine nuts, vinegar, sugar, olive oil", "A sweet and sour Sicilian eggplant stew with capers and olives.", "room_temp"),
    ("Panelle", "Chickpea Fritters", "Sicilian", "Appetizer", "Fried Snack", "Legume Dish", "Vegan", "", 6.5, "Mild", 1, 5, 1, 1, 4, 1, 4, 1, 3, 7, 3, 4, 1, "chickpea flour, water, parsley, salt, lemon, oil", "Thin, crispy Sicilian chickpea flour fritters served with a squeeze of lemon.", "hot"),
    ("Steamed Cockles", "", "Southern Italian", "Appetizer", "Steamed Seafood", "Seafood Dish", "Non-Veg", "Shellfish", 6.5, "Mild", 1, 5, 1, 1, 6, 1, 3, 1, 3, 2, 4, 6, 2, "cockles, garlic, white wine, parsley, olive oil, crusty bread", "Cockles steamed open in white wine and garlic, served with bread.", "hot"),
    ("Lobster Ravioli Appetizer", "", "Northern Italian", "Appetizer", "Filled Pasta", "Seafood Dish", "Non-Veg", "Lobster", 8.0, "Mild", 1, 5, 1, 1, 7, 1, 7, 1, 4, 2, 4, 6, 2, "lobster, ricotta, pasta dough, butter, sage, Parmesan", "Delicate ravioli filled with lobster and ricotta in brown butter and sage.", "hot"),
    ("Shishito Peppers with Parmesan", "", "Northern Italian", "Appetizer", "Roasted Vegetable", "Vegetable Dish", "Veg", "", 6.0, "Medium", 1, 5, 1, 1, 4, 3, 3, 1, 2, 4, 3, 4, 1, "shishito peppers, olive oil, sea salt, Parmigiano-Reggiano, lemon", "Blistered peppers showered with grated Parmesan and sea salt.", "hot"),
    ("Polenta Fries", "", "Northern Italian", "Appetizer", "Fried Snack", "Grain Dish", "Veg", "", 6.5, "Mild", 1, 5, 1, 1, 4, 1, 5, 1, 3, 7, 3, 4, 1, "polenta, Parmesan, olive oil, rosemary, marinara sauce", "Crispy fried polenta sticks served with marinara for dipping.", "hot"),
    ("Sardines in Saor", "", "Venetian", "Appetizer", "Marinated Seafood", "Seafood Dish", "Non-Veg", "Fish", 6.5, "Mild", 2, 5, 4, 1, 6, 1, 4, 1, 3, 4, 4, 5, 3, "sardines, onions, white wine vinegar, raisins, pine nuts, olive oil", "Fried sardines marinated in a sweet-sour onion, raisin, and pine nut sauce.", "room_temp"),
    ("Stracciatella Soup", "", "Roman", "Appetizer", "Soup", "Egg Dish", "Veg", "", 7.0, "Mild", 1, 5, 1, 1, 5, 1, 4, 1, 4, 1, 2, 4, 1, "chicken broth, eggs, Parmigiano-Reggiano, semolina, parsley, nutmeg, lemon", "A light Roman egg-drop soup with Parmesan and lemon.", "hot"),
    ("Roasted Garlic with Ricotta", "", "Southern Italian", "Appetizer", "Spread", "Dairy Dish", "Veg", "", 6.0, "Mild", 1, 4, 1, 1, 4, 1, 5, 1, 4, 4, 2, 6, 1, "garlic, ricotta, olive oil, herbs, crusty bread, honey", "Slow-roasted garlic spread over whipped ricotta with a honey drizzle.", "hot"),
    ("Antipasto Misto Platter", "", "Northern Italian", "Appetizer", "Charcuterie", "Pork Dish", "Non-Veg", "Pork", 8.5, "Mild", 1, 6, 2, 1, 6, 1, 6, 1, 3, 4, 4, 6, 3, "prosciutto, salami, sopressata, mozzarella, provolone, roasted peppers, olives, artichokes, breadsticks", "A grand assortment of Italian cured meats, cheeses, and marinated vegetables.", "room_temp"),
]

# ══════════════════════════════════════════════════════════════════════════════
#  50 MAIN COURSES (Primi & Secondi)
# ══════════════════════════════════════════════════════════════════════════════
mains = [
    # dish_name, alternate_alias, region, category, sub_category, main_ingredient_category, dietary_type, primary_protein, dish_importance_score, spice_level, sweet, salt, sour, bitter, umami, spicy, rich_fat, astringency, viscosity, crunchy, chewy, aromatic, funk, ingredients, description, serving_temperature
    ("Lasagna Bolognese", "", "Emilian", "Main Dish", "Baked Pasta", "Red Meat Dish", "Non-Veg", "Beef", 10.0, "Mild", 1, 5, 2, 1, 8, 1, 8, 1, 6, 2, 4, 6, 2, "pasta sheets, beef and pork ragu, bechamel, Parmigiano-Reggiano, mozzarella, tomato", "Layers of fresh pasta, rich Bolognese ragu, bechamel, and melted cheese.", "hot"),
    ("Spaghetti Carbonara", "", "Roman", "Main Dish", "Pasta", "Pork Dish", "Non-Veg", "Pork", 10.0, "Mild", 1, 5, 1, 1, 8, 2, 8, 1, 5, 2, 4, 5, 2, "spaghetti, guanciale, egg yolks, Pecorino Romano, black pepper", "A silky egg-and-cheese sauce coating spaghetti with crispy guanciale.", "hot"),
    ("Chicken Parmigiana", "", "Southern Italian", "Main Dish", "Breaded Meat", "Poultry Dish", "Non-Veg", "Chicken", 9.5, "Mild", 1, 5, 2, 1, 7, 1, 7, 1, 5, 6, 4, 5, 1, "chicken cutlet, breadcrumbs, marinara, mozzarella, Parmesan, basil", "Breaded chicken cutlet topped with marinara and melted mozzarella.", "hot"),
    ("Fettuccine Alfredo", "", "Roman", "Main Dish", "Pasta", "Dairy Dish", "Veg", "", 9.0, "Mild", 1, 5, 1, 1, 6, 1, 9, 1, 5, 2, 4, 4, 1, "fettuccine, butter, Parmigiano-Reggiano, black pepper", "Tossed fettuccine in a rich emulsion of butter and Parmesan.", "hot"),
    ("Veal Marsala", "", "Sicilian", "Main Dish", "Sauteed Meat", "Red Meat Dish", "Non-Veg", "Veal", 8.5, "Mild", 2, 5, 1, 1, 7, 1, 7, 1, 4, 2, 4, 6, 1, "veal scallopini, Marsala wine, mushrooms, butter, shallots, flour, parsley", "Tender veal scallopini in a rich Marsala wine and mushroom sauce.", "hot"),
    ("Osso Buco", "", "Lombard", "Main Dish", "Braised Meat", "Red Meat Dish", "Non-Veg", "Veal", 9.0, "Mild", 1, 5, 1, 1, 8, 1, 7, 1, 6, 2, 5, 7, 2, "veal shanks, white wine, tomatoes, carrots, celery, onion, gremolata, saffron risotto", "Cross-cut veal shanks braised until fall-off-the-bone tender, topped with gremolata.", "hot"),
    ("Eggplant Parmigiana", "", "Southern Italian", "Main Dish", "Baked Vegetable", "Vegetable Dish", "Veg", "", 8.5, "Mild", 1, 5, 2, 1, 6, 1, 7, 1, 5, 4, 4, 5, 1, "eggplant, marinara sauce, mozzarella, Parmigiano-Reggiano, basil, breadcrumbs", "Layers of fried eggplant, marinara, and melted cheese baked until bubbly.", "hot"),
    ("Penne alla Vodka", "", "Roman", "Main Dish", "Pasta", "Grain Dish", "Veg", "", 8.5, "Mild", 1, 5, 2, 1, 6, 2, 7, 1, 5, 2, 4, 5, 1, "penne, tomatoes, vodka, heavy cream, Parmigiano-Reggiano, red pepper flakes, basil", "Penne in a creamy, blush tomato-vodka sauce with a hint of heat.", "hot"),
    ("Rigatoni Amatriciana", "", "Roman", "Main Dish", "Pasta", "Pork Dish", "Non-Veg", "Pork", 8.5, "Medium", 1, 5, 2, 1, 7, 3, 6, 1, 4, 2, 4, 6, 2, "rigatoni, guanciale, San Marzano tomatoes, Pecorino Romano, red pepper flakes", "Tube pasta in a bold tomato sauce with crispy guanciale and Pecorino.", "hot"),
    ("Linguine alle Vongole", "White Clam Sauce", "Neapolitan", "Main Dish", "Pasta", "Seafood Dish", "Non-Veg", "Shellfish", 9.0, "Mild", 1, 5, 1, 1, 7, 2, 5, 1, 3, 2, 4, 7, 2, "linguine, littleneck clams, garlic, white wine, olive oil, parsley, red pepper flakes", "Linguine tossed with fresh clams in a garlicky white wine sauce.", "hot"),
    ("Chicken Piccata", "", "Northern Italian", "Main Dish", "Sauteed Meat", "Poultry Dish", "Non-Veg", "Chicken", 8.0, "Mild", 1, 5, 4, 1, 5, 1, 6, 1, 4, 2, 3, 5, 1, "chicken cutlet, lemon, capers, butter, white wine, flour, parsley", "Pan-seared chicken in a bright lemon-butter-caper sauce.", "hot"),
    ("Saltimbocca alla Romana", "", "Roman", "Main Dish", "Sauteed Meat", "Red Meat Dish", "Non-Veg", "Veal", 8.0, "Mild", 1, 5, 1, 1, 7, 1, 6, 1, 4, 3, 4, 7, 2, "veal scallopini, prosciutto, sage, butter, white wine, flour", "Veal wrapped with prosciutto and sage, pan-fried in butter and white wine.", "hot"),
    ("Risotto alla Milanese", "", "Lombard", "Main Dish", "Risotto", "Grain Dish", "Veg", "", 9.0, "Mild", 1, 5, 1, 1, 7, 1, 7, 1, 5, 1, 3, 7, 1, "arborio rice, saffron, bone marrow, butter, onion, white wine, Parmigiano-Reggiano", "A golden saffron-infused risotto finished with butter and Parmesan.", "hot"),
    ("Pappardelle with Wild Boar Ragu", "", "Tuscan", "Main Dish", "Pasta", "Red Meat Dish", "Non-Veg", "Boar", 8.0, "Mild", 1, 5, 2, 1, 8, 1, 6, 1, 5, 2, 5, 7, 2, "pappardelle, wild boar, red wine, tomatoes, rosemary, juniper, celery, onion", "Wide ribbons of pasta cloaked in a slow-cooked wild boar ragu.", "hot"),
    ("Gnocchi Sorrento", "", "Neapolitan", "Main Dish", "Pasta", "Grain Dish", "Veg", "", 8.0, "Mild", 1, 5, 2, 1, 6, 1, 7, 1, 5, 2, 5, 5, 1, "potato gnocchi, tomato sauce, mozzarella, basil, Parmigiano-Reggiano", "Pillowy potato gnocchi baked with tomato sauce and stretchy mozzarella.", "hot"),
    ("Lobster Fra Diavolo", "", "Southern Italian", "Main Dish", "Spicy Seafood", "Seafood Dish", "Non-Veg", "Lobster", 9.0, "Hot", 1, 5, 2, 1, 7, 7, 5, 1, 4, 3, 5, 7, 2, "lobster, linguine, San Marzano tomatoes, garlic, red pepper flakes, white wine, basil", "Whole lobster over linguine in a fiery tomato sauce.", "hot"),
    ("Veal Milanese", "", "Lombard", "Main Dish", "Breaded Meat", "Red Meat Dish", "Non-Veg", "Veal", 8.5, "Mild", 1, 5, 2, 1, 6, 1, 6, 1, 3, 8, 4, 5, 1, "veal cutlet, breadcrumbs, eggs, flour, arugula, cherry tomatoes, lemon", "A pounded veal cutlet breaded and fried to a golden crisp.", "hot"),
    ("Branzino al Forno", "Whole Roasted Sea Bass", "Southern Italian", "Main Dish", "Roasted Fish", "Seafood Dish", "Non-Veg", "Fish", 8.5, "Mild", 1, 4, 2, 1, 6, 1, 4, 1, 3, 3, 4, 7, 2, "whole branzino, lemon, garlic, olive oil, capers, cherry tomatoes, white wine, herbs", "Whole roasted sea bass with lemon, capers, and herbs.", "hot"),
    ("Cacio e Pepe", "", "Roman", "Main Dish", "Pasta", "Dairy Dish", "Veg", "", 9.0, "Medium", 1, 5, 1, 1, 7, 3, 7, 1, 4, 2, 4, 5, 2, "tonnarelli or spaghetti, Pecorino Romano, black pepper", "A masterful Roman pasta dressed only in Pecorino and cracked black pepper.", "hot"),
    ("Bucatini all'Amatriciana", "", "Roman", "Main Dish", "Pasta", "Pork Dish", "Non-Veg", "Pork", 8.5, "Medium", 1, 5, 2, 1, 7, 3, 6, 1, 4, 2, 5, 6, 2, "bucatini, guanciale, San Marzano tomatoes, Pecorino Romano, red pepper flakes", "Hollow spaghetti in a spicy tomato sauce with crispy guanciale.", "hot"),
    ("Chicken Marsala", "", "Sicilian", "Main Dish", "Sauteed Meat", "Poultry Dish", "Non-Veg", "Chicken", 8.5, "Mild", 2, 5, 1, 1, 6, 1, 6, 1, 4, 2, 3, 6, 1, "chicken cutlet, Marsala wine, mushrooms, butter, shallots, flour, thyme", "Pan-seared chicken cutlets in a sweet Marsala wine and mushroom sauce.", "hot"),
    ("Seafood Cioppino", "", "Northern Italian", "Main Dish", "Seafood Stew", "Seafood Dish", "Non-Veg", "Shellfish", 8.5, "Mild", 1, 5, 2, 1, 7, 2, 5, 1, 5, 3, 4, 7, 2, "shrimp, clams, mussels, calamari, fish, tomatoes, white wine, garlic, saffron, fennel", "A tomato-based seafood stew brimming with clams, mussels, shrimp, and fish.", "hot"),
    ("Pork Osso Buco", "", "Lombard", "Main Dish", "Braised Meat", "Pork Dish", "Non-Veg", "Pork", 7.5, "Mild", 1, 5, 1, 1, 7, 1, 7, 1, 6, 2, 5, 6, 2, "pork shanks, white wine, tomatoes, carrots, celery, onion, gremolata", "Slow-braised pork shanks in a wine and vegetable broth topped with gremolata.", "hot"),
    ("Tortellini in Brodo", "", "Emilian", "Main Dish", "Filled Pasta", "Pork Dish", "Non-Veg", "Pork", 8.5, "Mild", 1, 5, 1, 1, 7, 1, 5, 1, 4, 2, 4, 6, 1, "tortellini, prosciutto, mortadella, Parmigiano-Reggiano, chicken broth, nutmeg", "Delicate meat-filled tortellini floating in a clear, golden broth.", "hot"),
    ("Tagliatelle al Tartufo", "", "Piedmontese", "Main Dish", "Pasta", "Grain Dish", "Veg", "", 8.5, "Mild", 1, 4, 1, 1, 7, 1, 7, 1, 4, 2, 4, 9, 2, "fresh tagliatelle, black truffle, butter, Parmigiano-Reggiano, olive oil", "Fresh egg tagliatelle lavished with shaved truffle and butter.", "hot"),
    ("Bistecca alla Fiorentina", "", "Tuscan", "Main Dish", "Grilled Meat", "Red Meat Dish", "Non-Veg", "Beef", 9.5, "Mild", 1, 5, 1, 1, 8, 1, 6, 1, 3, 3, 6, 5, 2, "Chianina T-bone steak, sea salt, black pepper, olive oil, lemon, rosemary", "A massive T-bone steak from Chianina cattle, grilled rare over wood coals.", "hot"),
    ("Shrimp Fra Diavolo", "", "Southern Italian", "Main Dish", "Spicy Seafood", "Seafood Dish", "Non-Veg", "Shrimp", 8.0, "Hot", 1, 5, 2, 1, 6, 7, 5, 1, 4, 3, 4, 7, 2, "shrimp, linguine, tomatoes, garlic, red pepper flakes, white wine, basil", "Jumbo shrimp in a fiery tomato sauce served over linguine.", "hot"),
    ("Veal Saltimbocca", "", "Roman", "Main Dish", "Sauteed Meat", "Red Meat Dish", "Non-Veg", "Veal", 8.0, "Mild", 1, 5, 1, 1, 7, 1, 6, 1, 4, 3, 4, 7, 2, "veal, prosciutto, sage, butter, white wine, flour", "Veal cutlets topped with prosciutto and sage, seared and deglazed with wine.", "hot"),
    ("Manicotti", "", "Southern Italian", "Main Dish", "Baked Pasta", "Dairy Dish", "Veg", "", 7.5, "Mild", 1, 5, 2, 1, 6, 1, 7, 1, 5, 2, 4, 5, 1, "crepes or pasta tubes, ricotta, mozzarella, Parmesan, marinara, basil, egg", "Pasta tubes stuffed with ricotta and baked in marinara and melted cheese.", "hot"),
    ("Baked Ziti", "", "Southern Italian", "Main Dish", "Baked Pasta", "Dairy Dish", "Veg", "", 8.0, "Mild", 1, 5, 2, 1, 6, 1, 7, 1, 5, 3, 4, 5, 1, "ziti, ricotta, mozzarella, Parmesan, marinara, Italian sausage (optional)", "A crowd-pleasing baked pasta dish layered with ricotta, mozzarella, and sauce.", "hot"),
    ("Lobster Risotto", "", "Northern Italian", "Main Dish", "Risotto", "Seafood Dish", "Non-Veg", "Lobster", 9.0, "Mild", 1, 5, 1, 1, 8, 1, 7, 1, 5, 2, 3, 7, 2, "lobster, arborio rice, lobster stock, white wine, butter, shallots, Parmesan, tarragon", "Creamy risotto enriched with lobster meat and lobster-shell stock.", "hot"),
    ("Ravioli di Zucca", "Butternut Squash Ravioli", "Lombard", "Main Dish", "Filled Pasta", "Vegetable Dish", "Veg", "", 7.5, "Mild", 3, 4, 1, 1, 5, 1, 6, 1, 4, 2, 4, 6, 1, "butternut squash, amaretti, mostarda, Parmesan, pasta dough, brown butter, sage", "Squash-filled ravioli tossed in brown butter and sage.", "hot"),
    ("Spaghetti alle Vongole", "", "Neapolitan", "Main Dish", "Pasta", "Seafood Dish", "Non-Veg", "Shellfish", 8.5, "Mild", 1, 5, 1, 1, 7, 2, 5, 1, 3, 2, 4, 7, 2, "spaghetti, clams, garlic, white wine, olive oil, parsley, cherry tomatoes", "Spaghetti with fresh clams, garlic, and a splash of white wine.", "hot"),
    ("Cavatelli with Sausage & Broccoli Rabe", "", "Southern Italian", "Main Dish", "Pasta", "Pork Dish", "Non-Veg", "Pork", 8.0, "Medium", 1, 5, 1, 3, 6, 3, 6, 1, 3, 2, 5, 6, 1, "cavatelli, Italian sausage, broccoli rabe, garlic, red pepper flakes, olive oil, Pecorino", "Handmade pasta with crumbled sausage and bitter broccoli rabe.", "hot"),
    ("Salmon with Pesto", "", "Ligurian", "Main Dish", "Roasted Fish", "Seafood Dish", "Non-Veg", "Fish", 7.5, "Mild", 1, 5, 1, 1, 6, 1, 6, 1, 4, 3, 4, 8, 1, "salmon fillet, basil pesto, pine nuts, garlic, Parmesan, olive oil, lemon", "Roasted salmon glazed with a vibrant Ligurian basil pesto.", "hot"),
    ("Veal Chop Valdostana", "", "Piedmontese", "Main Dish", "Stuffed Meat", "Red Meat Dish", "Non-Veg", "Veal", 8.0, "Mild", 1, 5, 1, 1, 7, 1, 8, 1, 4, 4, 5, 5, 2, "veal rib chop, fontina cheese, prosciutto, breadcrumbs, egg, butter", "A thick veal chop stuffed with fontina and prosciutto, then breaded and pan-fried.", "hot"),
    ("Pork Milanese", "", "Lombard", "Main Dish", "Breaded Meat", "Pork Dish", "Non-Veg", "Pork", 7.5, "Mild", 1, 5, 1, 1, 6, 1, 6, 1, 3, 8, 4, 4, 1, "pork cutlet, breadcrumbs, eggs, flour, arugula, cherry tomatoes, lemon", "Pounded pork cutlet breaded and fried golden, served with arugula salad.", "hot"),
    ("Orecchiette with Sausage & Broccoli Rabe", "", "Southern Italian", "Main Dish", "Pasta", "Pork Dish", "Non-Veg", "Pork", 8.0, "Medium", 1, 5, 1, 3, 6, 3, 5, 1, 3, 2, 5, 6, 1, "orecchiette, Italian sausage, broccoli rabe, garlic, red pepper flakes, olive oil, Pecorino", "Ear-shaped pasta with crumbled sausage and broccoli rabe in olive oil.", "hot"),
    ("Chicken Francese", "", "Southern Italian", "Main Dish", "Sauteed Meat", "Poultry Dish", "Non-Veg", "Chicken", 7.5, "Mild", 1, 5, 3, 1, 5, 1, 6, 1, 4, 2, 3, 5, 1, "chicken cutlet, eggs, flour, lemon, butter, white wine, parsley", "Egg-battered chicken in a light lemon-butter-wine sauce.", "hot"),
    ("Short Rib Pappardelle", "", "Tuscan", "Main Dish", "Pasta", "Red Meat Dish", "Non-Veg", "Beef", 8.5, "Mild", 1, 5, 1, 1, 8, 1, 7, 1, 5, 2, 5, 6, 2, "short ribs, pappardelle, red wine, tomatoes, onion, carrot, celery, rosemary, Parmesan", "Wide pasta ribbons topped with a rich braised short rib ragu.", "hot"),
    ("Linguine Pescatore", "", "Southern Italian", "Main Dish", "Pasta", "Seafood Dish", "Non-Veg", "Shellfish", 8.5, "Mild", 1, 5, 2, 1, 7, 2, 5, 1, 4, 2, 4, 7, 2, "linguine, shrimp, clams, mussels, calamari, tomatoes, garlic, white wine, basil", "Linguine tossed with a medley of seafood in a light tomato sauce.", "hot"),
    ("Mushroom Risotto", "", "Northern Italian", "Main Dish", "Risotto", "Vegetable Dish", "Veg", "", 8.5, "Mild", 1, 5, 1, 1, 7, 1, 7, 1, 5, 2, 3, 7, 1, "arborio rice, mixed mushrooms, white wine, shallots, butter, Parmesan, thyme, truffle oil", "A creamy risotto loaded with mixed wild mushrooms and a drizzle of truffle oil.", "hot"),
    ("Veal Piccata", "", "Northern Italian", "Main Dish", "Sauteed Meat", "Red Meat Dish", "Non-Veg", "Veal", 7.5, "Mild", 1, 5, 4, 1, 5, 1, 6, 1, 4, 2, 3, 5, 1, "veal scallopini, lemon, capers, butter, white wine, flour, parsley", "Veal cutlets in a tangy lemon-butter-caper pan sauce.", "hot"),
    ("Rack of Lamb with Rosemary", "", "Tuscan", "Main Dish", "Roasted Meat", "Red Meat Dish", "Non-Veg", "Lamb", 8.5, "Mild", 1, 5, 1, 1, 7, 1, 6, 1, 3, 4, 5, 8, 2, "rack of lamb, rosemary, garlic, Dijon mustard, breadcrumbs, olive oil", "Herb-crusted rack of lamb roasted to a perfect medium-rare.", "hot"),
    ("Spaghetti Pomodoro", "", "Neapolitan", "Main Dish", "Pasta", "Grain Dish", "Vegan", "", 8.5, "Mild", 2, 5, 2, 1, 5, 1, 4, 1, 4, 2, 4, 6, 1, "spaghetti, San Marzano tomatoes, garlic, basil, olive oil, salt", "The simplest and most iconic pasta: spaghetti in a pure tomato-basil sauce.", "hot"),
    ("Braised Rabbit", "Coniglio", "Tuscan", "Main Dish", "Braised Meat", "Red Meat Dish", "Non-Veg", "Rabbit", 7.0, "Mild", 1, 5, 2, 1, 6, 1, 5, 1, 5, 2, 5, 7, 2, "rabbit, white wine, olives, tomatoes, rosemary, garlic, pine nuts", "Tender rabbit pieces braised in white wine with olives and herbs.", "hot"),
    ("Egg Yolk Raviolo", "Uovo in Raviolo", "Emilian", "Main Dish", "Filled Pasta", "Egg Dish", "Veg", "", 8.0, "Mild", 1, 4, 1, 1, 7, 1, 8, 1, 5, 2, 4, 6, 2, "pasta dough, egg yolk, ricotta, spinach, butter, Parmigiano-Reggiano, truffle", "A single large raviolo encasing a runny egg yolk, ricotta, and truffle.", "hot"),
    ("Mafalde with Sunday Sauce", "", "Southern Italian", "Main Dish", "Pasta", "Red Meat Dish", "Non-Veg", "Beef", 8.0, "Mild", 1, 5, 2, 1, 7, 1, 6, 1, 5, 2, 5, 6, 2, "mafalde pasta, pork ribs, beef, Italian sausage, San Marzano tomatoes, garlic, basil, Parmesan", "Ruffled-edge pasta in a rich, slow-simmered meat sauce with braised meats.", "hot"),
    ("Branzino al Cartoccio", "", "Southern Italian", "Main Dish", "Baked Fish", "Seafood Dish", "Non-Veg", "Fish", 7.5, "Mild", 1, 4, 2, 1, 6, 1, 4, 1, 3, 2, 4, 7, 2, "branzino fillet, cherry tomatoes, olives, capers, white wine, lemon, parchment", "Sea bass baked in parchment with tomatoes, olives, and capers.", "hot"),
    ("Veal Chop Parmigiana", "", "Southern Italian", "Main Dish", "Breaded Meat", "Red Meat Dish", "Non-Veg", "Veal", 8.5, "Mild", 1, 5, 2, 1, 7, 1, 7, 1, 5, 6, 5, 5, 2, "veal rib chop, breadcrumbs, marinara, mozzarella, Parmesan, basil", "A thick veal chop, breaded and fried, then topped with marinara and melted cheese.", "hot"),
]

# ══════════════════════════════════════════════════════════════════════════════
#  50 DESSERTS (Dolci)
# ══════════════════════════════════════════════════════════════════════════════
desserts = [
    # dish_name, alternate_alias, region, category, sub_category, main_ingredient_category, dietary_type, primary_protein, dish_importance_score, spice_level, sweet, salt, sour, bitter, umami, spicy, rich_fat, astringency, viscosity, crunchy, chewy, aromatic, funk, ingredients, description, serving_temperature
    ("Tiramisu", "", "Venetian", "Dessert", "Layered Dessert", "Dairy Dish", "Veg", "", 10.0, "Mild", 8, 1, 1, 3, 2, 1, 7, 1, 5, 2, 4, 7, 1, "mascarpone, espresso, ladyfingers, egg yolks, sugar, cocoa powder, Marsala", "Espresso-soaked ladyfingers layered with mascarpone cream and dusted with cocoa.", "cold"),
    ("Cannoli", "", "Sicilian", "Dessert", "Fried Pastry", "Dairy Dish", "Veg", "", 9.5, "Mild", 8, 1, 1, 1, 1, 1, 6, 1, 3, 7, 3, 5, 1, "ricotta, powdered sugar, chocolate chips, pistachios, candied fruit, cannoli shells", "Crisp fried pastry tubes filled with sweet ricotta cream.", "room_temp"),
    ("Panna Cotta", "", "Piedmontese", "Dessert", "Custard", "Dairy Dish", "Veg", "", 9.0, "Mild", 8, 1, 1, 1, 1, 1, 7, 1, 5, 1, 3, 5, 1, "heavy cream, sugar, vanilla, gelatin, berry coulis", "A silky, vanilla-scented cream custard topped with berry sauce.", "cold"),
    ("Affogato al Caffe", "", "Northern Italian", "Dessert", "Frozen Dessert", "Dairy Dish", "Veg", "", 8.5, "Mild", 7, 1, 1, 4, 1, 1, 6, 1, 4, 1, 2, 8, 1, "vanilla gelato, hot espresso, amaretto (optional)", "A scoop of vanilla gelato drowned in a shot of hot espresso.", "cold"),
    ("Gelato", "Seasonal Varieties", "Northern Italian", "Dessert", "Frozen Dessert", "Dairy Dish", "Veg", "", 9.5, "Mild", 8, 1, 1, 1, 1, 1, 6, 1, 4, 1, 2, 6, 1, "milk, cream, sugar, egg yolks, seasonal fruit or chocolate or nuts", "Italian-style ice cream with dense, intensely flavored scoops.", "cold"),
    ("Zeppole", "", "Neapolitan", "Dessert", "Fried Pastry", "Grain Dish", "Veg", "", 8.0, "Mild", 8, 1, 1, 1, 1, 1, 5, 1, 3, 6, 4, 5, 1, "flour, eggs, butter, sugar, ricotta, powdered sugar, oil", "Light, airy Italian doughnuts dusted with powdered sugar.", "hot"),
    ("Ricotta Cheesecake", "", "Southern Italian", "Dessert", "Cake", "Dairy Dish", "Veg", "", 8.0, "Mild", 8, 1, 1, 1, 1, 1, 6, 1, 5, 3, 3, 5, 1, "ricotta, cream cheese, sugar, eggs, lemon zest, vanilla, graham cracker crust", "A light, fluffy cheesecake made with ricotta for a delicate texture.", "cold"),
    ("Warm Chocolate Budino", "Lava Cake", "Northern Italian", "Dessert", "Warm Cake", "Dairy Dish", "Veg", "", 8.5, "Mild", 8, 1, 1, 2, 1, 1, 8, 1, 6, 2, 3, 6, 1, "dark chocolate, butter, eggs, sugar, flour, vanilla, whipped cream", "A warm chocolate cake with a molten center, served with whipped cream.", "hot"),
    ("Lemon Sorbetto", "", "Southern Italian", "Dessert", "Frozen Dessert", "Vegetable Dish", "Vegan", "", 7.5, "Mild", 7, 1, 5, 1, 1, 1, 1, 1, 3, 1, 1, 6, 1, "lemons, sugar, water", "A refreshing palate-cleansing sorbet made from Amalfi lemons.", "cold"),
    ("Chocolate Budino", "", "Northern Italian", "Dessert", "Custard", "Dairy Dish", "Veg", "", 7.5, "Mild", 8, 1, 1, 2, 1, 1, 7, 1, 6, 1, 3, 5, 1, "dark chocolate, milk, cream, sugar, cornstarch, vanilla, sea salt, olive oil", "A dense, rich Italian chocolate pudding topped with olive oil and sea salt.", "cold"),
    ("Biscotti", "", "Tuscan", "Dessert", "Cookie", "Grain Dish", "Veg", "", 7.5, "Mild", 6, 1, 1, 1, 1, 1, 3, 1, 2, 8, 3, 5, 1, "flour, sugar, eggs, almonds, anise, lemon zest", "Twice-baked almond cookies, perfect for dipping in espresso or vin santo.", "room_temp"),
    ("Semifreddo", "", "Northern Italian", "Dessert", "Frozen Dessert", "Dairy Dish", "Veg", "", 7.5, "Mild", 8, 1, 1, 1, 1, 1, 7, 1, 4, 2, 3, 5, 1, "egg yolks, sugar, heavy cream, vanilla, amaretti, chocolate or fruit", "A partially frozen mousse-like dessert, lighter than gelato.", "cold"),
    ("Flourless Chocolate Cake", "Torta Caprese", "Neapolitan", "Dessert", "Cake", "Nut Dish", "Veg", "", 8.0, "Mild", 8, 1, 1, 2, 1, 1, 7, 1, 5, 2, 3, 5, 1, "dark chocolate, butter, sugar, eggs, almonds, powdered sugar", "A rich, dense gluten-free chocolate-almond cake from the island of Capri.", "room_temp"),
    ("Amaretti Cookies", "", "Piedmontese", "Dessert", "Cookie", "Nut Dish", "Veg", "", 6.5, "Mild", 7, 1, 1, 2, 1, 1, 3, 1, 2, 5, 3, 6, 1, "almonds, sugar, egg whites, almond extract, apricot kernels", "Light, crisp Italian almond macaroons with a subtle bitter-almond flavor.", "room_temp"),
    ("Panettone Bread Pudding", "", "Lombard", "Dessert", "Bread Pudding", "Dairy Dish", "Veg", "", 7.0, "Mild", 8, 1, 1, 1, 1, 1, 7, 1, 5, 3, 4, 6, 1, "panettone, eggs, cream, sugar, vanilla, raisins, candied orange, creme anglaise", "Custardy bread pudding made from panettone, served with creme anglaise.", "hot"),
    ("Torrone", "", "Southern Italian", "Dessert", "Confection", "Nut Dish", "Veg", "", 6.5, "Mild", 8, 1, 1, 1, 1, 1, 3, 1, 2, 3, 6, 4, 1, "honey, sugar, egg whites, almonds, pistachios, wafer paper", "A chewy nougat confection studded with toasted almonds and pistachios.", "room_temp"),
    ("Zabaglione with Berries", "", "Piedmontese", "Dessert", "Custard", "Egg Dish", "Veg", "", 7.0, "Mild", 7, 1, 2, 1, 1, 1, 5, 1, 4, 1, 2, 6, 1, "egg yolks, sugar, Marsala wine, mixed berries", "A warm, frothy wine custard spooned over fresh mixed berries.", "hot"),
    ("Sfogliatella", "", "Neapolitan", "Dessert", "Pastry", "Grain Dish", "Veg", "", 7.5, "Mild", 7, 1, 1, 1, 1, 1, 5, 1, 3, 8, 4, 6, 1, "semolina, ricotta, candied citrus, cinnamon, pastry dough, sugar, butter", "A crisp, shell-shaped Neapolitan pastry filled with sweet ricotta and semolina.", "hot"),
    ("Crostata di Frutta", "Fruit Tart", "Northern Italian", "Dessert", "Tart", "Grain Dish", "Veg", "", 7.0, "Mild", 7, 1, 2, 1, 1, 1, 5, 1, 3, 5, 3, 5, 1, "pastry cream, shortcrust pastry, seasonal fruit, apricot glaze", "A buttery shortcrust tart filled with pastry cream and topped with glazed fruit.", "room_temp"),
    ("Espresso Martini Mousse", "", "Northern Italian", "Dessert", "Mousse", "Dairy Dish", "Veg", "", 6.5, "Mild", 7, 1, 1, 3, 1, 1, 6, 1, 4, 1, 2, 7, 1, "mascarpone, espresso, vodka, coffee liqueur, chocolate, cream", "A creamy coffee-spiked mousse inspired by the classic cocktail.", "cold"),
    ("Struffoli", "", "Neapolitan", "Dessert", "Fried Pastry", "Grain Dish", "Veg", "", 7.0, "Mild", 9, 1, 1, 1, 1, 1, 5, 1, 4, 5, 4, 5, 1, "flour, eggs, sugar, honey, sprinkles, candied fruit, orange zest, oil", "Tiny fried dough balls coated in warm honey, piled into a festive mound.", "room_temp"),
    ("Cassata Siciliana", "", "Sicilian", "Dessert", "Layered Cake", "Dairy Dish", "Veg", "", 7.5, "Mild", 9, 1, 1, 1, 1, 1, 6, 1, 5, 2, 4, 6, 1, "sponge cake, ricotta, candied fruit, marzipan, fondant icing, pistachios", "A lavish Sicilian sponge cake filled with ricotta cream and covered in marzipan.", "cold"),
    ("Bomboloni", "Italian Doughnuts", "Tuscan", "Dessert", "Fried Pastry", "Grain Dish", "Veg", "", 7.5, "Mild", 8, 1, 1, 1, 1, 1, 5, 1, 3, 4, 5, 5, 1, "flour, eggs, butter, sugar, yeast, pastry cream or Nutella, oil", "Fluffy Italian filled doughnuts with pastry cream or Nutella.", "hot"),
    ("Budino di Riso", "", "Tuscan", "Dessert", "Custard", "Grain Dish", "Veg", "", 6.0, "Mild", 7, 1, 1, 1, 1, 1, 5, 1, 4, 2, 3, 5, 1, "arborio rice, milk, eggs, sugar, vanilla, lemon zest, rum", "A creamy baked rice custard with vanilla and lemon zest.", "room_temp"),
    ("Ricotta Pie", "", "Southern Italian", "Dessert", "Pie", "Dairy Dish", "Veg", "", 7.0, "Mild", 8, 1, 1, 1, 1, 1, 6, 1, 4, 4, 3, 5, 1, "ricotta, sugar, eggs, orange zest, candied fruit, pie crust, vanilla", "An Italian Easter pie with a creamy, citrus-scented ricotta filling.", "room_temp"),
    ("Olive Oil Cake", "", "Tuscan", "Dessert", "Cake", "Grain Dish", "Veg", "", 7.0, "Mild", 7, 1, 1, 1, 1, 1, 5, 1, 4, 2, 3, 5, 1, "olive oil, flour, sugar, eggs, lemon, orange zest, yogurt", "A moist, fragrant cake made with fruity extra-virgin olive oil.", "room_temp"),
    ("Limoncello Cake", "", "Neapolitan", "Dessert", "Cake", "Grain Dish", "Veg", "", 7.5, "Mild", 8, 1, 3, 1, 1, 1, 5, 1, 4, 2, 3, 7, 1, "flour, sugar, eggs, limoncello, lemon zest, cream, mascarpone", "A moist sponge soaked in limoncello and layered with lemon mascarpone cream.", "cold"),
    ("Mascarpone Cream with Berries", "", "Lombard", "Dessert", "Cream Dessert", "Dairy Dish", "Veg", "", 6.5, "Mild", 7, 1, 2, 1, 1, 1, 6, 1, 4, 1, 2, 5, 1, "mascarpone, heavy cream, sugar, vanilla, mixed berries", "Whipped mascarpone cream spooned over fresh seasonal berries.", "cold"),
    ("Nutella Crepes", "", "Northern Italian", "Dessert", "Crepe", "Grain Dish", "Veg", "", 7.0, "Mild", 8, 1, 1, 1, 1, 1, 6, 1, 3, 3, 3, 6, 1, "crepe batter, Nutella, hazelnuts, powdered sugar, banana (optional)", "Thin crepes spread with warm Nutella and topped with toasted hazelnuts.", "hot"),
    ("Pistachio Semifreddo", "", "Sicilian", "Dessert", "Frozen Dessert", "Nut Dish", "Veg", "", 7.5, "Mild", 8, 1, 1, 1, 1, 1, 7, 1, 4, 3, 3, 6, 1, "pistachios, egg yolks, sugar, heavy cream, pistachio paste", "A frozen pistachio mousse dessert with intense nutty flavor.", "cold"),
    ("Cantucci", "", "Tuscan", "Dessert", "Cookie", "Nut Dish", "Veg", "", 6.5, "Mild", 6, 1, 1, 1, 1, 1, 3, 1, 2, 8, 3, 5, 1, "flour, sugar, eggs, almonds, orange zest, anise", "Crunchy Tuscan almond cookies meant for dipping in vin santo.", "room_temp"),
    ("Spumoni", "", "Neapolitan", "Dessert", "Frozen Dessert", "Dairy Dish", "Veg", "", 6.5, "Mild", 8, 1, 1, 1, 1, 1, 6, 1, 4, 3, 3, 5, 1, "chocolate gelato, pistachio gelato, cherry gelato, candied fruit, nuts", "A layered molded ice cream with chocolate, pistachio, and cherry.", "cold"),
    ("Chocolate Tartufo", "", "Calabrian", "Dessert", "Frozen Dessert", "Dairy Dish", "Veg", "", 7.0, "Mild", 8, 1, 1, 2, 1, 1, 7, 1, 4, 3, 3, 5, 1, "dark chocolate gelato, chocolate truffle center, cocoa powder, hazelnuts", "A ball of chocolate gelato with a molten truffle center, dusted in cocoa.", "cold"),
    ("Zuppa Inglese", "", "Emilian", "Dessert", "Trifle", "Dairy Dish", "Veg", "", 7.0, "Mild", 8, 1, 1, 1, 1, 1, 6, 1, 5, 2, 3, 5, 1, "sponge cake, pastry cream, chocolate cream, alchermes liqueur, whipped cream", "An Italian trifle of liqueur-soaked sponge layered with custard creams.", "cold"),
    ("Poached Pears in Red Wine", "", "Piedmontese", "Dessert", "Poached Fruit", "Vegetable Dish", "Vegan", "", 6.5, "Mild", 7, 1, 2, 1, 1, 1, 2, 2, 3, 1, 3, 7, 1, "pears, red wine, sugar, cinnamon, star anise, cloves, orange zest", "Whole pears slow-poached in spiced red wine until tender and ruby-colored.", "room_temp"),
    ("Fig and Walnut Tart", "", "Tuscan", "Dessert", "Tart", "Nut Dish", "Veg", "", 6.5, "Mild", 7, 1, 1, 1, 1, 1, 5, 1, 3, 5, 3, 5, 1, "figs, walnuts, honey, butter, shortcrust pastry, mascarpone", "A rustic tart filled with honey-roasted figs and toasted walnuts.", "room_temp"),
    ("Almond Cake", "", "Sicilian", "Dessert", "Cake", "Nut Dish", "Veg", "", 7.0, "Mild", 7, 1, 1, 1, 1, 1, 5, 1, 4, 3, 3, 6, 1, "almonds, sugar, eggs, butter, almond extract, lemon zest, flour", "A moist, aromatic Sicilian almond cake with a golden crust.", "room_temp"),
    ("Pizzelle", "", "Southern Italian", "Dessert", "Cookie", "Grain Dish", "Veg", "", 6.0, "Mild", 6, 1, 1, 1, 1, 1, 3, 1, 2, 7, 2, 5, 1, "flour, eggs, sugar, butter, anise extract, vanilla", "Thin, crisp waffle cookies pressed in a decorative iron.", "room_temp"),
    ("Crema di Mascarpone", "", "Lombard", "Dessert", "Cream Dessert", "Dairy Dish", "Veg", "", 6.0, "Mild", 7, 1, 1, 1, 1, 1, 7, 1, 4, 1, 2, 5, 1, "mascarpone, egg yolks, sugar, vanilla, espresso (optional)", "A simple, lush mascarpone cream served in glasses with espresso.", "cold"),
    ("Baci di Dama", "", "Piedmontese", "Dessert", "Cookie", "Nut Dish", "Veg", "", 6.0, "Mild", 7, 1, 1, 1, 1, 1, 5, 1, 2, 5, 3, 5, 1, "hazelnuts, almonds, flour, butter, sugar, dark chocolate", "Delicate hazelnut cookies sandwiched with a thin layer of dark chocolate.", "room_temp"),
    ("Mimosa Cake", "", "Northern Italian", "Dessert", "Cake", "Dairy Dish", "Veg", "", 6.5, "Mild", 8, 1, 1, 1, 1, 1, 6, 1, 4, 3, 3, 5, 1, "sponge cake, pastry cream, whipped cream, limoncello, powdered sugar", "A fluffy sponge cake covered in crumbled cake pieces, resembling mimosa flowers.", "cold"),
    ("Honey Balsamic Strawberries", "", "Emilian", "Dessert", "Fruit Dessert", "Vegetable Dish", "Vegan", "", 5.5, "Mild", 7, 1, 3, 1, 1, 1, 1, 1, 2, 1, 2, 5, 1, "strawberries, balsamic vinegar, honey, black pepper, basil", "Fresh strawberries macerated in aged balsamic and drizzled with honey.", "room_temp"),
    ("Chocolate Salame", "", "Northern Italian", "Dessert", "Confection", "Dairy Dish", "Veg", "", 6.0, "Mild", 8, 1, 1, 2, 1, 1, 6, 1, 3, 4, 4, 5, 1, "dark chocolate, butter, biscuit cookies, eggs, rum, almonds, powdered sugar", "A no-bake chocolate log studded with cookie pieces, sliced to resemble salami.", "cold"),
    ("Ciambellone", "", "Roman", "Dessert", "Cake", "Grain Dish", "Veg", "", 6.0, "Mild", 7, 1, 1, 1, 1, 1, 4, 1, 3, 3, 3, 5, 1, "flour, sugar, eggs, olive oil, milk, lemon zest, baking powder", "A simple, rustic Italian ring cake often enjoyed at breakfast.", "room_temp"),
    ("Frittelle", "", "Venetian", "Dessert", "Fried Pastry", "Grain Dish", "Veg", "", 6.5, "Mild", 8, 1, 1, 1, 1, 1, 5, 1, 3, 5, 4, 5, 1, "flour, eggs, sugar, raisins, pine nuts, grappa, lemon zest, oil", "Venetian carnival fritters studded with raisins and pine nuts.", "hot"),
    ("Peach and Amaretti Crumble", "", "Piedmontese", "Dessert", "Crumble", "Grain Dish", "Veg", "", 6.0, "Mild", 7, 1, 2, 1, 1, 1, 5, 1, 3, 6, 3, 6, 1, "peaches, amaretti cookies, butter, sugar, almonds, lemon", "Baked peaches topped with a crunchy amaretti cookie crumble.", "hot"),
    ("Hazelnut Tart", "", "Piedmontese", "Dessert", "Tart", "Nut Dish", "Veg", "", 7.0, "Mild", 7, 1, 1, 1, 1, 1, 6, 1, 3, 5, 3, 6, 1, "hazelnuts, sugar, butter, dark chocolate, eggs, shortcrust pastry", "A rich tart filled with Piedmontese hazelnuts and dark chocolate.", "room_temp"),
    ("Torta della Nonna", "", "Tuscan", "Dessert", "Tart", "Dairy Dish", "Veg", "", 7.5, "Mild", 7, 1, 1, 1, 1, 1, 6, 1, 4, 4, 3, 5, 1, "shortcrust pastry, pastry cream, pine nuts, lemon zest, powdered sugar", "Grandmother's custard tart topped with pine nuts and powdered sugar.", "room_temp"),
    ("Crema Carsolina", "", "Northern Italian", "Dessert", "Custard", "Dairy Dish", "Veg", "", 5.5, "Mild", 7, 1, 1, 1, 1, 1, 5, 1, 5, 1, 2, 4, 1, "milk, sugar, egg yolks, cornstarch, vanilla, caramel", "A delicate caramel custard from the Carso region near Trieste.", "cold"),
    ("Chocolate Budino Dark", "", "Northern Italian", "Dessert", "Custard", "Dairy Dish", "Veg", "", 6.5, "Mild", 7, 1, 1, 3, 1, 1, 7, 1, 6, 1, 3, 5, 1, "bittersweet chocolate, cream, milk, sugar, espresso, sea salt, whipped cream", "An intensely dark chocolate pudding with espresso undertones and sea salt.", "cold"),
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
    row = list(t[:2]) + ["Italian"] + list(t[2:4])  # name, alias, cuisine, region, category
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
    row = list(t[:2]) + ["Italian"] + list(t[2:4])
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
    row = list(t[:2]) + ["Italian"] + list(t[2:4])
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
print(f"Before: {len(df)} total rows, {len(df[df['cuisine_name'] == 'Italian'])} Italian")

# Remove all Italian dishes
df = df[df["cuisine_name"] != "Italian"]
print(f"After removing Italian: {len(df)} rows")

# Add new Italian dishes
df = pd.concat([df, new_df], ignore_index=True)
print(f"After adding new Italian: {len(df)} total rows, {len(df[df['cuisine_name'] == 'Italian'])} Italian")

# Save
df.to_csv(CSV_PATH, index=False)
print(f"\nSaved to {CSV_PATH}")

# Summary
italian = df[df["cuisine_name"] == "Italian"]
print(f"\n=== Italian Dish Summary ===")
print(f"Total: {len(italian)}")
print(f"\nBy course:")
print(italian["course"].value_counts().to_string())
print(f"\nBy dietary_type:")
print(italian["dietary_type"].value_counts().to_string())
print(f"\nBy main_ingredient_category:")
print(italian["main_ingredient_category"].value_counts().to_string())
