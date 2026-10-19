from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from typing import Any

import yaml

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_PROJECT_ROOT))

from src.core.feature_flags import set_flag
from src.phase2.catalog_loader import load_catalog
from src.phase2.preferences import UserPreferences
from src.phase3.intent_parser import detect_intent
from src.phase3.orchestrator import recommend
from src.phase3.query_parser import cuisine_for_dish, extract_dish, extract_locality
from src.phase4.schemas import RecommendationRequest, RecommendationResponse

_GOLDEN_SET_PATH = Path(__file__).resolve().parent / "golden_set.yaml"
_RESULTS_PATH = Path(__file__).resolve().parent / "results.json"


def _load_golden_set() -> list[dict[str, Any]]:
    with open(_GOLDEN_SET_PATH, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return data.get("test_cases", [])


def _build_prefs_from_test(tc: dict[str, Any], known_localities: list[str]) -> RecommendationRequest:
    query = tc["query"]
    locality = tc.get("expected_locality", "any")
    cuisine = tc.get("expected_cuisine", "North Indian")
    budget_max = tc.get("expected_budget_max", 2000)
    min_rating = tc.get("expected_min_rating", 3.5)

    return RecommendationRequest(
        locality=locality,
        budget_min_inr=0,
        budget_max_inr=budget_max,
        cuisine=cuisine,
        min_rating=min_rating,
        specific_cravings=query,
        scenario=tc.get("expected_scenario"),
    )


def _run_single_test(
    tc: dict[str, Any],
    catalog: Any,
    known_localities: list[str],
    use_llm: bool,
) -> dict[str, Any]:
    query = tc["query"]

    detected_scenario = detect_intent(query)
    detected_dish = extract_dish(query)
    mapped_cuisine = cuisine_for_dish(detected_dish)
    detected_locality = extract_locality(query, known_localities)

    parse_results: dict[str, Any] = {
        "detected_scenario": detected_scenario,
        "detected_dish": detected_dish,
        "mapped_cuisine": mapped_cuisine,
        "detected_locality": detected_locality,
    }

    parse_checks: dict[str, bool] = {}
    if "expected_scenario" in tc:
        parse_checks["scenario_match"] = detected_scenario == tc["expected_scenario"]
    if "expected_cuisine" in tc and mapped_cuisine:
        parse_checks["cuisine_from_dish_match"] = mapped_cuisine.lower() == tc["expected_cuisine"].lower()
    if "expected_locality" in tc and detected_locality:
        parse_checks["locality_match"] = tc["expected_locality"].lower() in detected_locality.lower()

    try:
        prefs = _build_prefs_from_test(tc, known_localities)
    except Exception as e:
        return {
            "query": query,
            "error": f"prefs_build_failed: {e}",
            "parse_results": parse_results,
            "parse_checks": parse_checks,
        }

    flag_overrides = {"llm_reranking": use_llm, "cache_enabled": False}

    t0 = time.perf_counter()
    try:
        resp = recommend(
            prefs=prefs,
            catalog=catalog,
            flag_overrides=flag_overrides,
        )
    except Exception as e:
        return {
            "query": query,
            "error": str(e),
            "parse_results": parse_results,
            "parse_checks": parse_checks,
        }
    elapsed_ms = int((time.perf_counter() - t0) * 1000)

    num_results = len(resp.items)
    ratings = [it.rating for it in resp.items if it.rating is not None]
    avg_rating = round(sum(ratings) / len(ratings), 2) if ratings else None

    filter_checks: dict[str, bool] = {}
    if "expected_min_results" in tc:
        filter_checks["min_results_met"] = num_results >= tc["expected_min_results"]
    if "expected_budget_max" in tc:
        budget_ok = all(
            (it.cost_for_two is not None and it.cost_for_two <= tc["expected_budget_max"])
            for it in resp.items
            if it.cost_for_two is not None
        )
        filter_checks["budget_respected"] = budget_ok

    name_counts: dict[str, int] = {}
    for it in resp.items:
        name_counts[it.name] = name_counts.get(it.name, 0) + 1
    max_chain_count = max(name_counts.values()) if name_counts else 0
    chain_cap_ok = True
    if "should_not_contain_chains_over" in tc:
        chain_cap_ok = max_chain_count <= tc["should_not_contain_chains_over"]
        filter_checks["chain_cap_respected"] = chain_cap_ok

    unique_cuisines: set[str] = set()
    for it in resp.items:
        for c in it.cuisines:
            unique_cuisines.add(c.lower())

    return {
        "query": query,
        "num_results": num_results,
        "avg_rating": avg_rating,
        "unique_cuisines": len(unique_cuisines),
        "max_chain_count": max_chain_count,
        "llm_used": resp.meta.llm_used,
        "fallback_used": resp.meta.fallback_used,
        "relaxed_rating": resp.meta.relaxed_rating,
        "elapsed_ms": elapsed_ms,
        "parse_results": parse_results,
        "parse_checks": parse_checks,
        "filter_checks": filter_checks,
        "result_ids": [it.id for it in resp.items[:5]],
    }


def _compute_ranking_overlap(ids_a: list[str], ids_b: list[str]) -> float:
    if not ids_a or not ids_b:
        return 0.0
    set_a = set(ids_a)
    set_b = set(ids_b)
    union = set_a | set_b
    if not union:
        return 0.0
    return round(len(set_a & set_b) / len(union), 4)


def run_evaluation() -> dict[str, Any]:
    print("Loading catalog...")
    catalog = load_catalog()
    known_localities = sorted(
        {str(x).strip().lower() for x in catalog.get("locality", []).tolist() if str(x).strip()}
    )
    test_cases = _load_golden_set()
    print(f"Loaded {len(test_cases)} test cases from golden set.\n")

    per_test: list[dict[str, Any]] = []
    total_parse_checks = 0
    passed_parse_checks = 0
    total_filter_checks = 0
    passed_filter_checks = 0
    fallback_count = 0
    relaxed_count = 0
    overlap_scores: list[float] = []

    for i, tc in enumerate(test_cases, 1):
        print(f"[{i}/{len(test_cases)}] {tc['query']}")

        det_result = _run_single_test(tc, catalog, known_localities, use_llm=False)

        llm_result = _run_single_test(tc, catalog, known_localities, use_llm=True)

        for k, v in det_result.get("parse_checks", {}).items():
            total_parse_checks += 1
            if v:
                passed_parse_checks += 1

        for k, v in det_result.get("filter_checks", {}).items():
            total_filter_checks += 1
            if v:
                passed_filter_checks += 1

        if det_result.get("fallback_used") or det_result.get("relaxed_rating"):
            fallback_count += 1
        if det_result.get("relaxed_rating"):
            relaxed_count += 1

        det_ids = det_result.get("result_ids", [])
        llm_ids = llm_result.get("result_ids", [])
        overlap = _compute_ranking_overlap(det_ids, llm_ids)
        overlap_scores.append(overlap)

        test_entry = {
            "query": tc["query"],
            "deterministic": det_result,
            "llm": llm_result,
            "ranking_overlap": overlap,
        }
        per_test.append(test_entry)

        status = "PASS" if all(det_result.get("filter_checks", {}).values()) else "WARN"
        print(f"  [{status}] det={det_result.get('num_results', 0)} results, "
              f"llm={llm_result.get('num_results', 0)} results, overlap={overlap}")

    avg_overlap = round(sum(overlap_scores) / len(overlap_scores), 4) if overlap_scores else 0.0
    parse_accuracy = round(passed_parse_checks / total_parse_checks, 4) if total_parse_checks else None
    filter_accuracy = round(passed_filter_checks / total_filter_checks, 4) if total_filter_checks else None
    fallback_rate = round(fallback_count / len(test_cases), 4) if test_cases else 0.0

    aggregate = {
        "total_tests": len(test_cases),
        "parse_accuracy": parse_accuracy,
        "total_parse_checks": total_parse_checks,
        "passed_parse_checks": passed_parse_checks,
        "filter_accuracy": filter_accuracy,
        "total_filter_checks": total_filter_checks,
        "passed_filter_checks": passed_filter_checks,
        "fallback_rate": fallback_rate,
        "relaxation_rate": round(relaxed_count / len(test_cases), 4) if test_cases else 0.0,
        "avg_ranking_overlap_det_vs_llm": avg_overlap,
    }

    report = {
        "aggregate": aggregate,
        "per_test": per_test,
    }

    _RESULTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(_RESULTS_PATH, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, default=str)

    print("\n" + "=" * 70)
    print("EVALUATION SUMMARY")
    print("=" * 70)
    print(f"  Total test cases:              {aggregate['total_tests']}")
    print(f"  Parse accuracy:                {aggregate['parse_accuracy']}")
    print(f"  Filter accuracy:               {aggregate['filter_accuracy']}")
    print(f"  Fallback rate:                 {aggregate['fallback_rate']}")
    print(f"  Relaxation rate:               {aggregate['relaxation_rate']}")
    print(f"  Avg ranking overlap (det/llm): {aggregate['avg_ranking_overlap_det_vs_llm']}")
    print(f"\nResults written to: {_RESULTS_PATH}")

    return report


if __name__ == "__main__":
    run_evaluation()
