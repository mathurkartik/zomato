from __future__ import annotations

import logging
from typing import Any, Optional


_logger = logging.getLogger("biteai.monitor")


def log_recommendation(
    *,
    user_query: Optional[str],
    detected_scenario: Optional[str],
    detected_dish: Optional[str],
    mapped_cuisine_from_dish: Optional[str],
    budget_extracted: Optional[int],
    candidates_before_scenario: int,
    candidates_after_scenario: int,
    scenario_filter_info: dict[str, Any] | None = None,
    llm_used: bool | None = None,
    fallback_used: bool | None = None,
    error: Optional[str] = None,
) -> None:
    """
    Lightweight structured logging to support the architecture diagram's
    "Monitor" stage.
    """
    payload: dict[str, Any] = {
        "user_query": user_query,
        "detected_scenario": detected_scenario,
        "detected_dish": detected_dish,
        "mapped_cuisine_from_dish": mapped_cuisine_from_dish,
        "budget_extracted": budget_extracted,
        "candidates_before_scenario": candidates_before_scenario,
        "candidates_after_scenario": candidates_after_scenario,
        "scenario_filter_info": scenario_filter_info,
        "llm_used": llm_used,
        "fallback_used": fallback_used,
        "error": error,
    }
    try:
        _logger.info("recommendation_trace=%s", payload)
    except Exception:
        # Never let monitoring break the recommendation path.
        return

