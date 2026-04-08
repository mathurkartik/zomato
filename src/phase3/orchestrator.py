from __future__ import annotations

import hashlib
import json
import logging
import re as _re
import time
from typing import Any

import pandas as pd

from src.config import load_config
from src.phase2.filter import FilterMeta, FilterResult, filter_restaurants
from src.phase2.preferences import UserPreferences
from src.phase3.intent_parser import detect_intent
from src.phase3.query_parser import cuisine_for_dish, extract_dish, extract_locality
from src.phase3.groq_client import (
    DEFAULT_MODEL,
    call_groq_chat_completions,
    get_groq_api_key,
    validate_or_fallback_model,
)
from src.phase3.prompt_builder import build_messages
from src.phase3.scenario_filter import apply_scenario_filters_to_shortlist
from src.phase4.schemas import (
    RecommendationItem,
    RecommendationMeta,
    RecommendationResponse,
)
from src.utils import cuisine_tokens_equivalent as _cuisine_tokens_equivalent


_cache: dict[str, RecommendationResponse] = {}
CACHE_SCHEMA_VERSION = "2026-04-08-primary-cuisine-priority-v1"

_monitor_logger = logging.getLogger("biteai.monitor")

_BUDGET_PATTERN = _re.compile(
    r"(?:under|below|within|around|budget|upto|up to|₹|rs\.?)\s*(\d+)",
    _re.IGNORECASE,
)


def _cache_key(
    prefs: UserPreferences,
    *,
    scenario: str | None,
    user_query: str | None,
) -> str:
    query_norm = (user_query or "").strip().lower()
    query_fp = hashlib.md5(query_norm.encode()).hexdigest() if query_norm else None
    payload = {
        "cache_schema_version": CACHE_SCHEMA_VERSION,
        "locality": prefs.locality,
        "budget_min_inr": prefs.budget_min_inr,
        "budget_max_inr": prefs.budget_max_inr,
        "cuisine": prefs.cuisine,
        "min_rating": prefs.min_rating,
        "extras": sorted(prefs.extras),
        "online_order": prefs.online_order,
        "book_table": prefs.book_table,
        "persona": prefs.persona,
        "scenario": scenario,
        "query_fp": query_fp,
    }
    return hashlib.md5(json.dumps(payload, sort_keys=True).encode()).hexdigest()


def _none_if_nan(v: Any) -> Any:
    try:
        if pd.isna(v):
            return None
    except Exception:
        pass
    return v


def _primary_cuisine(cuisines_val: Any) -> str | None:
    if cuisines_val is None:
        return None
    if isinstance(cuisines_val, list):
        if not cuisines_val:
            return None
        return str(cuisines_val[0]).strip().lower()
    try:
        items = list(cuisines_val)
        if not items:
            return None
        return str(items[0]).strip().lower()
    except Exception:
        s = str(cuisines_val).strip().lower()
        return s or None


def _primary_cuisine_matches_target(row: dict[str, Any], target_cuisine: str) -> bool:
    primary = _primary_cuisine(row.get("cuisines"))
    if not primary:
        return False
    t = target_cuisine.strip().lower()
    return _cuisine_tokens_equivalent(primary, t)


def _cost_display(cost_for_two: int | None) -> str | None:
    if cost_for_two is None:
        return None
    return f"₹{int(cost_for_two)} for two"


def _fallback_recommendations(shortlist: list[dict[str, Any]], top_n: int) -> list[dict[str, Any]]:
    """
    Deterministic fallback:
    sort by (aggregate_rating DESC, votes DESC)
    """
    def sort_key(item: dict[str, Any]) -> tuple[float, int]:
        rating = item.get("rating")
        rating_val = -1.0
        if rating is not None:
            try:
                rating_val = float(rating)
                # Treat NaN as missing rating.
                if pd.isna(rating_val):
                    rating_val = -1.0
            except Exception:
                rating_val = -1.0
        votes = item.get("votes") if "votes" in item else 0
        try:
            votes_val = int(votes)
        except Exception:
            votes_val = 0
        return (rating_val, votes_val)

    sorted_items = sorted(shortlist, key=sort_key, reverse=True)
    picked = sorted_items[:top_n]
    out: list[dict[str, Any]] = []
    for i, it in enumerate(picked, start=1):
        out.append(
            {
                "restaurant_id": it["id"],
                "rank": i,
                "explanation": "Recommended based on rating and popularity (fallback mode)",
            }
        )
    return out


def _build_rejected_list(
    shortlist_items: list[dict[str, Any]],
    accepted_items: list["RecommendationItem"],
) -> list[Any]:
    """Build rejected list: shortlisted restaurants not in the final recommendations."""
    from src.phase4.schemas import RejectedItem

    accepted_ids = {item.id for item in accepted_items}
    top_rating = max(
        (float(it.get("rating") or 0) for it in shortlist_items if it.get("rating")),
        default=0.0,
    )
    rejected = []
    for row in shortlist_items:
        if row["id"] in accepted_ids:
            continue
        rating = _none_if_nan(row.get("rating"))
        cost = _none_if_nan(row.get("cost_for_two"))

        if rating is not None and float(rating) < top_rating - 0.5:
            reason = f"Rating {rating} is below the top picks in this area"
        else:
            reason = "Not ranked highly enough for your specific preferences"

        rejected.append(
            RejectedItem(
                id=row["id"],
                name=str(row.get("name")),
                rating=float(rating) if rating is not None else None,
                cost_for_two=int(cost) if cost is not None else None,
                cost_display=_cost_display(int(cost) if cost is not None else None),
                rejection_reason=reason,
            )
        )
    return rejected


def _meta_from_filter(meta: FilterMeta, *, reason: str) -> RecommendationMeta:
    # Keep API meta stable even for empty results.
    return RecommendationMeta(
        shortlist_size=meta.shortlist_size,
        relaxed_rating=meta.relaxed_rating,
        reason=meta.reason,
        min_cost_in_locality=meta.min_cost_in_locality,
        latency_ms=meta.elapsed_ms,
        suggest_localities=list(meta.suggest_localities or []),
    )


def _persona_sort_shortlist(items: list[dict[str, Any]], persona: str) -> list[dict[str, Any]]:
    """Reorder shortlist before LLM: budget = cost ASC; premium = weighted_score DESC."""
    if not items:
        return items
    if persona == "budget":

        def cost_key(it: dict[str, Any]) -> tuple[int, float]:
            c = it.get("cost_for_two")
            if c is None or (isinstance(c, float) and pd.isna(c)):
                return (1, 999999.0)
            try:
                return (0, float(int(c)))
            except Exception:
                return (1, 999999.0)

        return sorted(items, key=cost_key)

    return sorted(
        items,
        key=lambda it: (
            -float(_none_if_nan(it.get("weighted_score")) or 0.0),
            -int(it.get("votes") or 0),
        ),
    )


def _prioritize_primary_cuisine_then_rating(
    items: list[dict[str, Any]], target_cuisine: str
) -> list[dict[str, Any]]:
    def key(row: dict[str, Any]) -> tuple[int, float, int]:
        primary_match = 1 if _primary_cuisine_matches_target(row, target_cuisine) else 0
        r = row.get("rating")
        try:
            rating = float(r) if r is not None and not pd.isna(r) else -1.0
        except Exception:
            rating = -1.0
        v = row.get("votes") or 0
        try:
            votes = int(v)
        except Exception:
            votes = 0
        return (-primary_match, -rating, -votes)

    return sorted(items, key=key)


def recommend(*, prefs: UserPreferences, catalog: pd.DataFrame) -> RecommendationResponse:
    """
    Phase 2 filter → (Phase 3 LLM) → merge → safe fallback.
    This function must never raise for Groq failures.
    """
    t0 = time.perf_counter()

    user_query: str | None = getattr(prefs, "specific_cravings", None) or getattr(prefs, "query", None)
    detected_scenario: str | None = getattr(prefs, "scenario", None)
    if not detected_scenario:
        detected_scenario = detect_intent(user_query)

    detected_dish: str | None = extract_dish(user_query)
    mapped_cuisine_from_dish: str | None = cuisine_for_dish(detected_dish)
    known_localities = sorted({str(x).strip().lower() for x in catalog.get("locality", []).tolist() if str(x).strip()})
    # Only extract locality from free text when the user has not already
    # selected one from the dropdown. Prevents "near Indiranagar" in the
    # cravings box from silently overriding a dropdown-selected locality.
    _locality_is_unset = not prefs.locality or prefs.locality.strip() in ("", "any")
    detected_locality: str | None = (
        extract_locality(user_query, known_localities) if _locality_is_unset else None
    )

    _budget_match = _BUDGET_PATTERN.search(user_query or "")
    budget_extracted: int | None = int(_budget_match.group(1)) if _budget_match else None

    # Optionally override structured fields from query-derived deterministic parsing.
    prefs_effective = prefs
    updates: dict[str, Any] = {}
    if detected_locality:
        updates["locality"] = detected_locality
    if mapped_cuisine_from_dish:
        updates["cuisine"] = mapped_cuisine_from_dish
    if budget_extracted is not None:
        # Respect validation bounds from UserPreferences.
        budget_extracted = max(100, min(5000, int(budget_extracted)))
        updates["budget_max_inr"] = budget_extracted

    if updates:
        try:
            prefs_effective = prefs.model_copy(update=updates)
        except Exception:
            prefs_effective = prefs  # fall back to original if copy fails

    # Phase 2 deterministic filtering
    filter_result: FilterResult = filter_restaurants(catalog, prefs_effective)
    # Edge-case fallback for dish mapping:
    # if mapped cuisine produced zero results, relax cuisine filter by retrying
    # with the user's original cuisine choice.
    if mapped_cuisine_from_dish and filter_result.reason != "OK":
        fallback_filter_result = filter_restaurants(catalog, prefs)
        if fallback_filter_result.reason == "OK":
            filter_result = fallback_filter_result
            prefs_effective = prefs
            mapped_cuisine_from_dish = None
            detected_dish = None

    if filter_result.reason != "OK":
        base = _meta_from_filter(filter_result.meta, reason=filter_result.reason)
        # Ensure safe defaults for the API meta (no LLM attempted).
        meta = base.model_copy(
            update={
                "model": None,
                "prompt_version": None,
                "cache_hit": False,
                "llm_used": False,
                "fallback_used": False,
                "tokens_used": None,
                "error": None,
                "persona": prefs.persona,
            }
        )
        return RecommendationResponse(
            summary="No restaurants matched your filters.",
            items=[],
            rejected=[],
            meta=meta,
        )

    # Cache
    key = _cache_key(prefs_effective, scenario=detected_scenario, user_query=user_query)
    if key in _cache:
        cached = _cache[key]
        # Ensure cache_hit is correct on repeated calls.
        elapsed = int((time.perf_counter() - t0) * 1000)
        return cached.model_copy(update={"meta": cached.meta.model_copy(update={"cache_hit": True, "latency_ms": elapsed})})

    cache_hit = False

    cfg = load_config()
    llm_cfg = cfg.llm

    candidates_before_scenario = len(filter_result.items)
    # Apply scenario constraints on top of the deterministic shortlist.
    shortlist_items, scenario_filter_info = apply_scenario_filters_to_shortlist(
        filter_result.items,
        detected_scenario,
        min_rating_floor=prefs_effective.min_rating,
        budget_max_inr=prefs_effective.budget_max_inr,
    )
    candidates_after_scenario = len(shortlist_items)
    # Enrich shortlist_items with votes for fallback sorting if needed.
    # Phase2 items already include votes, but keep a safe default.
    for it in shortlist_items:
        it["votes"] = it.get("votes", 0)

    shortlist_items = _persona_sort_shortlist(shortlist_items, prefs_effective.persona)
    shortlist_items = _prioritize_primary_cuisine_then_rating(shortlist_items, prefs_effective.cuisine)

    # Rank the full shortlist; do not hard-limit response size to top_k.
    top_k = len(shortlist_items)

    # Build prompt payload with only 6 fields as per architecture.
    shortlist_for_prompt: list[dict[str, Any]] = []
    allowed_fields = {"id", "name", "rating", "cost_for_two", "cuisines", "rest_type", "votes"}
    for it in shortlist_items:
        # Convert NaNs to None to keep JSON serialization valid.
        payload_item = {k: _none_if_nan(v) for k, v in it.items() if k in allowed_fields}
        # The prompt spec includes only these 6 fields (votes is extra used only internally).
        cuisines_val = payload_item.get("cuisines")
        if cuisines_val is None:
            cuisines_json: list[Any] = []
        elif isinstance(cuisines_val, list):
            cuisines_json = cuisines_val
        else:
            # Parquet -> pandas often produces numpy arrays for list columns.
            try:
                cuisines_json = list(cuisines_val)
            except Exception:
                cuisines_json = [cuisines_val]

        shortlist_for_prompt.append(
            {
                "id": payload_item.get("id"),
                "name": payload_item.get("name"),
                "rating": payload_item.get("rating"),
                "cost_for_two": payload_item.get("cost_for_two"),
                "cuisines": cuisines_json,
                "rest_type": payload_item.get("rest_type"),
            }
        )

    prefs_payload = prefs_effective.model_dump()
    # Ensure prompt has scenario + user query even when caller is plain UserPreferences.
    prefs_payload["scenario"] = detected_scenario
    prefs_payload["specific_cravings"] = user_query
    prefs_payload["detected_dish"] = detected_dish
    prefs_payload["mapped_cuisine_from_dish"] = mapped_cuisine_from_dish
    messages = build_messages(
        top_k=top_k,
        prefs=prefs_payload,
        shortlist=shortlist_for_prompt,
        prompt_version=llm_cfg.prompt_version,
    )

    # Prepare model and api key
    error: str | None = None
    llm_used = False
    fallback_used = False
    tokens_used: int | None = None
    latency_ms: int = 0

    api_key = ""
    try:
        api_key = get_groq_api_key()
    except Exception as e:  # noqa: BLE001
        # If API key missing, skip LLM and fallback.
        error = str(e)
        fallback_used = True
        llm_used = False
        api_key = ""

    accepted_recommendations: list[dict[str, Any]] = []
    summary_text = ""

    if api_key:
        model_to_use = validate_or_fallback_model(llm_cfg.model)

        # Retry once for any Groq-level failure.
        groq_result = call_groq_chat_completions(
            api_key=api_key,
            model=model_to_use,
            messages=messages,
            temperature=llm_cfg.temperature,
            max_tokens=llm_cfg.max_tokens,
            timeout_seconds=llm_cfg.timeout_seconds,
            extra_debug_context="first_attempt",
        )
        if not groq_result.ok:
            groq_result = call_groq_chat_completions(
                api_key=api_key,
                model=model_to_use,
                messages=messages,
                temperature=llm_cfg.temperature,
                max_tokens=llm_cfg.max_tokens,
                timeout_seconds=llm_cfg.timeout_seconds,
                extra_debug_context="second_attempt_after_failure",
            )

        if not groq_result.ok:
            error = groq_result.error or error or "Groq call failed"
            fallback_used = True
        else:
            latency_ms = groq_result.latency_ms
            tokens_used = groq_result.tokens_used

            # Extract assistant content (OpenAI-compatible response)
            body = groq_result.json_body or {}
            choices = body.get("choices") if isinstance(body, dict) else None
            content = None
            if isinstance(choices, list) and choices:
                msg = choices[0].get("message") if isinstance(choices[0], dict) else None
                if isinstance(msg, dict):
                    content = msg.get("content")
            content = content if isinstance(content, str) else ""

            def parse_json_from_content(s: str) -> dict[str, Any] | None:
                try:
                    parsed = json.loads(s)
                except Exception:
                    return None
                if not isinstance(parsed, dict):
                    return None
                if "recommendations" not in parsed:
                    return None
                return parsed

            parsed = parse_json_from_content(content.strip())
            if parsed is None:
                # Invalid JSON: retry once with stricter instruction.
                fallback_used = True  # tentative; may flip if retry succeeds
                strict_messages = list(messages)
                strict_messages[-1] = {
                    "role": "user",
                    "content": strict_messages[-1]["content"]
                    + "\nIMPORTANT: Respond ONLY with valid JSON. No markdown. No extra text.",
                }
                groq_retry = call_groq_chat_completions(
                    api_key=api_key,
                    model=model_to_use,
                    messages=strict_messages,
                    temperature=llm_cfg.temperature,
                    max_tokens=llm_cfg.max_tokens,
                    timeout_seconds=llm_cfg.timeout_seconds,
                    extra_debug_context="json_retry",
                )
                if groq_retry.ok:
                    latency_ms = groq_retry.latency_ms
                    tokens_used = groq_retry.tokens_used
                    body2 = groq_retry.json_body or {}
                    choices2 = body2.get("choices") if isinstance(body2, dict) else None
                    content2 = ""
                    if isinstance(choices2, list) and choices2:
                        msg2 = choices2[0].get("message") if isinstance(choices2[0], dict) else None
                        if isinstance(msg2, dict):
                            content2 = msg2.get("content") or ""
                    parsed = parse_json_from_content(str(content2).strip())

            if parsed is not None:
                candidate_summary = parsed.get("summary")
                summary_text = candidate_summary if isinstance(candidate_summary, str) else ""
                recs = parsed.get("recommendations")
                if isinstance(recs, list):
                    shortlist_ids = {it["id"] for it in shortlist_items}
                    validated: list[dict[str, Any]] = []
                    for r in recs:
                        if not isinstance(r, dict):
                            continue
                        rid = r.get("restaurant_id")
                        if rid in shortlist_ids:
                            validated.append(
                                {
                                    "restaurant_id": rid,
                                    "rank": int(r.get("rank") or (len(validated) + 1)),
                                    "explanation": str(r.get("explanation") or "").strip(),
                                }
                            )
                    accepted_recommendations = sorted(validated, key=lambda x: x["rank"])
                    # If the LLM returns fewer items than available shortlist,
                    # append deterministic remainder so output is not capped.
                    if len(accepted_recommendations) < len(shortlist_items):
                        used_ids = {r["restaurant_id"] for r in accepted_recommendations}
                        remainder = _fallback_recommendations(shortlist_items, len(shortlist_items))
                        next_rank = len(accepted_recommendations) + 1
                        for rec in remainder:
                            rid = rec["restaurant_id"]
                            if rid in used_ids:
                                continue
                            accepted_recommendations.append(
                                {
                                    "restaurant_id": rid,
                                    "rank": next_rank,
                                    "explanation": rec["explanation"],
                                }
                            )
                            used_ids.add(rid)
                            next_rank += 1
                    llm_used = len(accepted_recommendations) > 0
                    fallback_used = not llm_used
            if llm_used is False:
                error = error or "LLM returned invalid JSON or no valid shortlist IDs"

    if fallback_used:
        # Deterministic fallback: full shortlist ordered by rating then votes.
        fallback_top = len(shortlist_items)
        accepted_recommendations = _fallback_recommendations(shortlist_items, fallback_top)
        summary_text = summary_text or "Recommended based on rating and popularity."

    # Merge into API items
    by_id: dict[str, dict[str, Any]] = {it["id"]: it for it in shortlist_items}
    items: list[RecommendationItem] = []
    for rec in accepted_recommendations:
        rid = rec["restaurant_id"]
        row = by_id.get(rid)
        if not row:
            continue
        cost = _none_if_nan(row.get("cost_for_two"))
        rating = _none_if_nan(row.get("rating"))
        cuisines_val = row.get("cuisines")
        if cuisines_val is None:
            cuisines_list: list[Any] = []
        elif isinstance(cuisines_val, list):
            cuisines_list = cuisines_val
        else:
            try:
                cuisines_list = list(cuisines_val)
            except Exception:
                cuisines_list = [cuisines_val]
        ws = row.get("weighted_score")
        v_raw = row.get("votes") or 0
        try:
            votes_i = int(v_raw)
        except Exception:
            votes_i = 0
        items.append(
            RecommendationItem(
                id=rid,
                rank=int(rec.get("rank") or (len(items) + 1)),
                name=str(row.get("name")),
                locality=str(row.get("locality")),
                cuisines=[str(x) for x in cuisines_list],
                rating=float(rating) if rating is not None else None,
                cost_for_two=int(cost) if cost is not None else None,
                cost_display=_cost_display(int(cost) if cost is not None else None),
                rest_type=str(row.get("rest_type")) if row.get("rest_type") is not None else None,
                weighted_score=float(ws) if ws is not None and not pd.isna(ws) else None,
                votes=votes_i,
                explanation=str(rec.get("explanation") or "").strip()
                or "Recommended based on rating and popularity (fallback mode)",
            )
        )

    latency_ms = latency_ms or int((time.perf_counter() - t0) * 1000)
    if api_key and not error and not llm_used:
        error = error or "LLM did not provide valid results; fallback used."

    # Renumber ranks sequentially only — do not re-sort.
    # The LLM ranking is preserved. The pre-sort before the LLM call already
    # gave primary-cuisine items priority as input to the model.
    reranked_items: list[RecommendationItem] = []
    for idx, row in enumerate([it.model_dump() for it in items], start=1):
        row["rank"] = idx
        reranked_items.append(RecommendationItem(**row))

    rejected_items = _build_rejected_list(shortlist_items, reranked_items)

    resp = RecommendationResponse(
        summary=summary_text,
        items=reranked_items,
        rejected=rejected_items,
        meta=RecommendationMeta(
            shortlist_size=len(shortlist_items),
            model=llm_cfg.model,
            prompt_version=llm_cfg.prompt_version,
            relaxed_rating=filter_result.meta.relaxed_rating,
            cache_hit=False,
            llm_used=bool(llm_used),
            fallback_used=bool(fallback_used),
            latency_ms=latency_ms,
            tokens_used=tokens_used,
            reason=None,
            min_cost_in_locality=None,
            error=error,
            persona=prefs_effective.persona,
            suggest_localities=list(filter_result.meta.suggest_localities or []),
        ),
    )

    _cache[key] = resp

    try:
        _monitor_logger.info(
            "recommendation_trace=%s",
            {
                "user_query": user_query,
                "detected_scenario": detected_scenario,
                "detected_dish": detected_dish,
                "mapped_cuisine_from_dish": mapped_cuisine_from_dish,
                "budget_extracted": budget_extracted,
                "candidates_before_scenario": candidates_before_scenario,
                "candidates_after_scenario": candidates_after_scenario,
                "scenario_filter_info": scenario_filter_info,
                "llm_used": bool(llm_used),
                "fallback_used": bool(fallback_used),
                "error": error,
            },
        )
    except Exception:
        pass
    return resp
