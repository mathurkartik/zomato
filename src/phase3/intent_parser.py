from __future__ import annotations

import re
from typing import Optional

# Simple keyword-based intent -> scenario mapping.
# This is intentionally conservative and deterministic so it is testable.


def detect_intent(user_query: Optional[str]) -> Optional[str]:
    if not user_query:
        return None

    query = user_query.lower()

    if "date" in query or "romantic" in query:
        return "date_night"

    if "family" in query or "kids" in query:
        return "family_dinner"

    if "quick" in query or "fast" in query or "lunch" in query or "grab" in query:
        return "quick_bite"

    if "cheap" in query or "budget" in query or "affordable" in query:
        return "budget_eating"

    if "explore" in query or "try new" in query or "new place" in query:
        return "food_exploration"

    if "group" in query or "friends" in query or "hangout" in query:
        return "group_hangout"

    return None


def extract_budget(query: str) -> Optional[int]:
    # Extract first integer number from the query (e.g. "under 1000").
    match = re.search(r"\d+", query)
    if match:
        try:
            return int(match.group())
        except Exception:
            return None
    return None

