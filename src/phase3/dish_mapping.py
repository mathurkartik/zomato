from __future__ import annotations

# Internal values are normalized to lowercase cuisine labels, matching
# phase2 preference normalization and deterministic filters.
DISH_TO_CUISINE: dict[str, str] = {
    # North Indian
    "butter chicken": "north indian",
    "paneer tikka": "north indian",
    "dal makhani": "north indian",
    "naan": "north indian",
    "roti": "north indian",
    "kebab": "north indian",
    "tandoori": "north indian",
    "biryani": "north indian",
    "thali": "north indian",
    # South Indian
    "dosa": "south indian",
    "idli": "south indian",
    "vada": "south indian",
    "sambar": "south indian",
    "uttapam": "south indian",
    # Chinese
    "noodles": "chinese",
    "fried rice": "chinese",
    "manchurian": "chinese",
    "spring roll": "chinese",
    # Italian
    "pizza": "italian",
    "pasta": "italian",
    "lasagna": "italian",
    "spaghetti": "italian",
    "risotto": "italian",
    # Fast Food
    "burger": "fast food",
    "sandwich": "fast food",
    "fries": "fast food",
    "wrap": "fast food",
    "roll": "fast food",
    "combo": "fast food",
    # Cafe / Beverages
    "coffee": "cafe",
    "latte": "cafe",
    "cappuccino": "cafe",
    "tea": "cafe",
    "shake": "cafe",
    # Desserts
    "cheesecake": "desserts",
    "cake": "desserts",
    "ice cream": "desserts",
    "brownie": "desserts",
    "pastry": "desserts",
    "waffle": "desserts",
    "donut": "desserts",
    # Street Food
    "pani puri": "street food",
    "golgappa": "street food",
    "chaat": "street food",
    "samosa": "street food",
    "kachori": "street food",
    # Mughlai
    "korma": "mughlai",
    "nihari": "mughlai",
    # Continental
    "steak": "continental",
    "grill": "continental",
}

