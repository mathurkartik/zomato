from __future__ import annotations

import math
from typing import Any, Optional

from src.phase3.scenario_config import SCENARIO_CONFIG
from src.utils import cuisine_tokens_equivalent as _cuisine_tokens_equivalent


def _is_nan(v: Any) -> bool:
    try:
        return isinstance(v, float) and math.isnan(v)
    except Exception:
        return False


def _shortlist_cuisines_to_list(cuisines_val: Any) -> list[str]:
    if cuisines_val is None:
        return []
    if isinstance(cuisines_val, str):
        return [cuisines_val]
    if isinstance(cuisines_val, list):
        return [str(x) for x in cuisines_val]
    # pandas / numpy often store array-like columns
    try:
        return [str(x) for x in list(cuisines_val)]
    except Exception:
        return [str(cuisines_val)]


def _contains_any_preferred_cuisine(cuisines_val: Any, preferred_cuisines: list[str]) -> bool:
    row_cuisines = _shortlist_cuisines_to_list(cuisines_val)
    for pref in preferred_cuisines:
        for row in row_cuisines:
            if _cuisine_tokens_equivalent(row, pref):
                return True
    return False


def _apply_single_config(shortlist_items: list[dict[str, Any]], config: dict[str, Any]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for item in shortlist_items:
        rating = item.get("rating")
        cost = item.get("cost_for_two")
        votes = item.get("votes")
        cuisines = item.get("cuisines")

        # Strict checks: missing values do not satisfy thresholds.
        if "min_rating" in config:
            if rating is None or _is_nan(rating):
                continue
            if float(rating) < float(config["min_rating"]):
                continue

        if "max_cost" in config:
            if cost is None or _is_nan(cost):
                continue
            if float(cost) > float(config["max_cost"]):
                continue

        if "min_cost" in config:
            if cost is None or _is_nan(cost):
                continue
            if float(cost) < float(config["min_cost"]):
                continue

        if "min_votes" in config:
            if votes is None or _is_nan(votes):
                continue
            try:
                if int(votes) < int(config["min_votes"]):
                    continue
            except Exception:
                continue

        if "preferred_cuisines" in config:
            if not _contains_any_preferred_cuisine(cuisines, list(config["preferred_cuisines"])):
                continue

        out.append(item)

    return out


def apply_scenario_filters_to_shortlist(
    shortlist_items: list[dict[str, Any]],
    scenario: Optional[str],
    *,
    min_rating_floor: Optional[float] = None,
    budget_max_inr: Optional[int] = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """
    Apply scenario constraints on the already-filtered shortlist.

    Because the shortlist already respects the user's structured filters
    (locality, cuisine, min_rating, budget), this function should only
    further narrow results (and safely fall back to the original shortlist
    if constraints become too strict).
    """
    if not scenario:
        return shortlist_items, {"scenario": None, "attempts": [], "final_relaxed": []}

    config = SCENARIO_CONFIG.get(scenario)
    if not config:
        return shortlist_items, {"scenario": scenario, "attempts": [], "final_relaxed": []}

    attempts: list[dict[str, Any]] = []

    # Attempt 1: full config
    attempt_configs: list[tuple[dict[str, Any], list[str]]] = [(dict(config), [])]

    # Attempt 2: relax rating threshold down to the user's min_rating (if the config is stricter).
    if "min_rating" in config and min_rating_floor is not None:
        relaxed = dict(config)
        try:
            if float(relaxed["min_rating"]) > float(min_rating_floor):
                relaxed["min_rating"] = float(min_rating_floor)
                attempt_configs.append((relaxed, ["min_rating_relaxed_to_user_floor"]))
        except Exception:
            pass

    # Attempt 3: relax cost ceilings down to the user's budget max (if config is stricter).
    if budget_max_inr is not None:
        if "max_cost" in config:
            relaxed = dict(config)
            try:
                if float(relaxed["max_cost"]) < float(budget_max_inr):
                    relaxed["max_cost"] = float(budget_max_inr)
                    attempt_configs.append((relaxed, ["max_cost_relaxed_to_user_budget"]))
            except Exception:
                pass
        if "min_cost" in config:
            # Expanding a min_cost means removing it (shortlist may include costs >= user budget).
            relaxed = dict(config)
            relaxed.pop("min_cost", None)
            attempt_configs.append((relaxed, ["min_cost_removed"]))

    # Attempt 4: remove preferred cuisines filter.
    if "preferred_cuisines" in config:
        relaxed = dict(config)
        relaxed.pop("preferred_cuisines", None)
        attempt_configs.append((relaxed, ["preferred_cuisines_ignored"]))

    # Attempt 5: remove min_votes if present.
    if "min_votes" in config:
        relaxed = dict(config)
        relaxed.pop("min_votes", None)
        attempt_configs.append((relaxed, ["min_votes_removed"]))

    # Apply attempts in order; first non-empty wins.
    final_relaxed: list[str] = []
    for idx, (cfg_try, relaxed_keys) in enumerate(attempt_configs, start=1):
        filtered = _apply_single_config(shortlist_items, cfg_try)
        attempts.append(
            {
                "attempt": idx,
                "relaxed": relaxed_keys,
                "result_size": len(filtered),
            }
        )
        if filtered:
            final_relaxed = relaxed_keys
            return filtered, {"scenario": scenario, "attempts": attempts, "final_relaxed": final_relaxed}

    # Safety fallback: return the original shortlist unchanged.
    return shortlist_items, {"scenario": scenario, "attempts": attempts, "final_relaxed": final_relaxed}

