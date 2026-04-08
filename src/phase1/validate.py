from __future__ import annotations

import json
from typing import Any

import pandas as pd


REQUIRED_COLUMNS: tuple[str, ...] = (
    "id",
    "name",
    "name_normalized",
    "locality",
    "cuisines",
    "rating",
    "votes",
    "cost_for_two",
    "weighted_score",
    "rest_type",
    "online_order",
    "book_table",
)


def validate_schema(df: pd.DataFrame) -> None:
    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(f"Catalog missing columns: {missing}")


def _json_default(o: Any) -> Any:
    if o is True or o is False:
        return o
    if hasattr(o, "item"):
        try:
            return o.item()
        except Exception:
            pass
    if isinstance(o, float):
        return o
    raise TypeError(f"Object of type {type(o)} is not JSON serializable")


def sample_row_as_dict(df: pd.DataFrame, index: int = 0) -> dict[str, Any]:
    row = df.iloc[index]
    out: dict[str, Any] = {}
    for k in REQUIRED_COLUMNS:
        v = row[k]
        if k == "cuisines" and isinstance(v, (list, tuple)):
            out[k] = list(v)
        elif pd.isna(v):
            out[k] = None
        else:
            out[k] = v
    return out


def print_sample_json(df: pd.DataFrame, index: int = 0) -> None:
    d = sample_row_as_dict(df, index=index)
    print(json.dumps(d, indent=2, default=_json_default, ensure_ascii=False))


def count_unmapped_alias_source_tokens(df: pd.DataFrame) -> dict[str, int]:
    """Counts of raw tokens that should have been replaced by CUISINE_ALIASES (expect zeros)."""
    from src.phase1.transform import CUISINE_ALIASES

    counts: dict[str, int] = {k: 0 for k in CUISINE_ALIASES}
    for cuisines in df["cuisines"]:
        if not isinstance(cuisines, list):
            continue
        for c in cuisines:
            if c in counts:
                counts[c] += 1
    return counts


def verify_weighted_score_ordering(df: pd.DataFrame) -> str:
    """Return a short human-readable check for weighted_score vs rating/votes."""
    if df.empty:
        return "(empty dataframe)"
    high_vote = df.nlargest(1, "votes").iloc[0]
    low_vote = df.nsmallest(1, "votes").iloc[0]
    return (
        f"Example: max votes row has votes={int(high_vote['votes'])}, "
        f"rating={high_vote['rating']}, weighted_score={float(high_vote['weighted_score']):.3f}; "
        f"min votes row: votes={int(low_vote['votes'])}, "
        f"rating={low_vote['rating']}, weighted_score={float(low_vote['weighted_score']):.3f}"
    )
