from __future__ import annotations

import hashlib
import re
from typing import Any

import numpy as np
import pandas as pd

CUISINE_ALIASES: dict[str, str] = {
    "punjabi": "north indian",
    "mughlai": "north indian",
    "awadhi": "north indian",
    "rajasthani": "north indian",
    "cantonese": "chinese",
    "szechuan": "chinese",
    "kerala": "south indian",
    "chettinad": "south indian",
    "andhra": "south indian",
    "hyderabadi": "south indian",
    "continental": "european",
    "american": "european",
}


def normalize_name(s: str) -> str:
    return re.sub(r"[^a-z0-9 ]", "", s.lower()).strip()


# Collapse "Koramangala 1St Block" → base name before title-casing (see improvements.md).
_BLOCK_SUFFIX_RE = re.compile(
    r"\s+\d+\s*(?:st|nd|rd|th)\s+block\s*$",
    re.IGNORECASE,
)


def normalize_locality(s: str) -> str:
    """Strip trailing 'N St/nd/th Block' variants; preserve remaining casing (matches catalog tokens)."""
    t = s.strip()
    if not t:
        return t
    return _BLOCK_SUFFIX_RE.sub("", t).strip()


def parse_rating(rate_val: Any) -> float | None:
    if rate_val is None or (isinstance(rate_val, float) and np.isnan(rate_val)):
        return None
    s = str(rate_val).strip()
    if s.upper() == "NEW" or s == "-" or s == "":
        return None
    s = s.replace("/5", "").strip()
    try:
        return float(s)
    except ValueError:
        return None


def parse_cost_for_two(raw: Any) -> int | None:
    if raw is None or (isinstance(raw, float) and np.isnan(raw)):
        return None
    s = str(raw).strip()
    if not s or s == "-":
        return None
    s = re.sub(r"[₹$,]", "", s)
    s = s.replace(",", "")
    try:
        return int(float(s))
    except ValueError:
        return None


def parse_bool_yn(raw: Any) -> bool | None:
    if raw is None or (isinstance(raw, float) and np.isnan(raw)):
        return None
    s = str(raw).strip().lower()
    if s == "yes":
        return True
    if s == "no":
        return False
    return None


def tokenize_cuisines(cuisines_raw: Any) -> list[str]:
    if cuisines_raw is None or (isinstance(cuisines_raw, float) and np.isnan(cuisines_raw)):
        return []
    s = str(cuisines_raw).strip()
    if not s:
        return []
    parts = [p.strip().lower() for p in s.split(",")]
    return [p for p in parts if p]


def apply_cuisine_aliases(tokens: list[str]) -> list[str]:
    out: list[str] = []
    for t in tokens:
        mapped = CUISINE_ALIASES.get(t, t)
        out.append(mapped)
    return out


def derive_id(name_normalized: str, locality: str) -> str:
    key = f"{name_normalized}{locality}"
    return hashlib.md5(key.encode("utf-8")).hexdigest()[:12]


def compute_weighted_score(rating: pd.Series, votes: pd.Series) -> pd.Series:
    r = rating.astype(float).fillna(0.0)
    v = votes.astype(float).clip(lower=0.0)
    return r * np.log1p(v)
