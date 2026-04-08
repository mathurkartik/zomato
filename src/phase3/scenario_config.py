from __future__ import annotations

from typing import Any

# Centralized scenario configuration.
# This file lives in the business-logic layer so scenario tuning does not
# require touching API handlers or frontend code.
SCENARIO_CONFIG: dict[str, dict[str, Any]] = {
    "date_night": {
        "min_rating": 4.2,
        "min_cost": 800,
        "preferred_cuisines": ["Italian", "European", "Cafe", "Desserts"],
    },
    "family_dinner": {
        "min_votes": 200,
        "max_cost": 1200,
        "preferred_cuisines": ["North Indian", "Chinese", "Multi-Cuisine"],
    },
    "quick_bite": {
        "max_cost": 500,
        "preferred_cuisines": ["Fast Food", "Cafe", "Street Food"],
    },
    "budget_eating": {
        "max_cost": 400,
        "min_rating": 3.8,
    },
    "food_exploration": {
        "min_rating": 4.2,
    },
    "group_hangout": {
        "min_votes": 300,
        "max_cost": 1000,
    },
}

