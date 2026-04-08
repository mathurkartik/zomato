from __future__ import annotations

import re
from typing import Optional

from src.phase3.dish_mapping import DISH_TO_CUISINE


def extract_dish(query: Optional[str]) -> Optional[str]:
    """
    Detect a dish phrase from free text.

    If multiple dishes are present, we pick the strongest phrase by:
    1) earliest position in text
    2) longer phrase first (helps "spring roll" beat "roll")
    """
    if not query:
        return None

    q = query.lower()
    candidates: list[tuple[int, int, str]] = []
    for dish in DISH_TO_CUISINE:
        pos = q.find(dish)
        if pos != -1:
            candidates.append((pos, -len(dish), dish))

    if not candidates:
        return None

    candidates.sort()
    return candidates[0][2]


def cuisine_for_dish(dish: Optional[str]) -> Optional[str]:
    if not dish:
        return None
    return DISH_TO_CUISINE.get(dish)


def extract_locality(query: Optional[str], known_localities: list[str]) -> Optional[str]:
    """
    Detect locality phrase in free text using known locality values from catalog.
    Longest locality phrases are checked first to avoid partial conflicts.
    """
    if not query:
        return None
    q = query.lower()
    ordered = sorted({str(x).strip().lower() for x in known_localities if str(x).strip()}, key=len, reverse=True)
    for loc in ordered:
        pattern = r"\b" + re.escape(loc) + r"\b"
        if re.search(pattern, q):
            return loc
    return None

