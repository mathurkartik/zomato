# improvements 2.md

## Goal

Upgrade the recommender from simple filter-only behavior to intent-aware recommendations while keeping retrieval deterministic.

## Implemented scope

### 1) Scenario-aware recommendations

Supported scenarios:

- `date_night`
- `family_dinner`
- `quick_bite`
- `budget_eating`
- `food_exploration`
- `group_hangout`

Implemented in:

- `src/phase3/scenario_config.py`
- `src/phase3/scenario_filter.py`
- `src/phase3/orchestrator.py`

### 2) Free-text intent parsing

Free-text query is parsed to infer:

- scenario
- budget hints
- optional locality mention

Implemented in:

- `src/phase3/intent_parser.py`
- `src/phase3/orchestrator.py`

### 3) LLM ranking with deterministic fallback

- Deterministic shortlist is always produced first.
- LLM ranks/explains shortlist.
- If LLM fails or returns invalid output, deterministic fallback ranking is used.

Implemented in:

- `src/phase3/prompt_builder.py`
- `src/phase3/groq_client.py`
- `src/phase3/orchestrator.py`

### 4) Monitoring/trace fields

Recommendation trace includes:

- detected scenario
- dish mapping context (if any)
- budget extracted
- candidate sizes before/after scenario filtering
- fallback and error state

## Verification checklist

- [ ] Query with explicit scenario text changes candidate behavior.
- [ ] LLM failure still returns deterministic recommendations.
- [ ] Empty results still return reason codes and valid API shape.
- [ ] `meta` fields are populated for diagnostics.

Enhance the system to support **scenario-based recommendations** and **free‑text intent input**, consistently across **frontend**, **backend**, and **business logic**, with a clear architecture.

## High‑Level Goal

Upgrade from a purely filter-based system → **intent‑driven recommendation system** that:

- **Accepts** both structured filters (location, cuisine, rating, cost, etc.) **and** natural language queries.
- **Maps** free text to a high‑level **scenario** (e.g. `date_night`, `family_dinner`).
- **Applies** scenario‑specific filter logic in the backend.
- **Uses** the LLM for ranking + explanation, not raw filtering.

---

## Architecture Overview

- **Frontend (UI + Client)**
  - Single search bar for free‑text queries plus optional filter controls (sliders, checkboxes).
  - Sends a single request payload to the backend: `query`, `scenario` (optional), `budget` (optional), and `filters`.
  - Displays returned recommendations with scenario‑aware explanations.

- **Backend API Layer**
  - `POST /recommendations` (or equivalent endpoint) accepts the combined payload.
  - Orchestrates the flow: intent detection → scenario filter application → core filtering → LLM re‑ranking → response shaping.

- **Business Logic / Orchestration Layer**
  - `intent_parser` module: maps free text → scenario and budget.
  - `scenario_config` module: central configuration of scenario rules.
  - `scenario_filter` module: applies scenario rules to the candidate restaurants dataset.
  - `ranking` / `llm_client` module: builds the LLM prompt including scenario context and parses the result.

- **Data Layer**
  - Works on a `pandas` `DataFrame` (or equivalent abstraction) containing restaurant records with `aggregate_rating`, `average_cost_for_two`, `votes`, `cuisines`, etc.

---

## FEATURE 1: Scenario Engine (6 Scenarios)

Support the following scenarios end‑to‑end (frontend + backend):

1. `date_night`
2. `family_dinner`
3. `quick_bite`
4. `budget_eating`
5. `food_exploration`
6. `group_hangout`

On the **frontend**, expose these as:

- A **scenario dropdown** (recommended), or
- **Suggested chips** below the search bar (e.g. “Date night”, “Family dinner”), or
- Both – chips that select the scenario in the dropdown.

On the **backend**, treat `scenario` as a **first‑class field** in the recommendation request:

```json
{
  "query": "date night under 1000",
  "scenario": "date_night",          // optional – set by frontend or backend
  "budget": 1000,                    // optional
  "filters": {
    "location": "indiranagar",
    "cuisine": ["Italian", "Continental"]
  }
}
```

---

## STEP 1 (Backend): Scenario Config

Create a new backend module `scenario_config.py` in the business‑logic layer (e.g. `backend/recommendation/scenario_config.py`):

```python
SCENARIO_CONFIG = {
    "date_night": {
        "min_rating": 4.2,
        "min_cost": 800,
        "preferred_cuisines": ["Italian", "Continental", "Cafe", "Desserts"],
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
        "diversity_boost": True,
    },
    "group_hangout": {
        "min_votes": 300,
        "max_cost": 1000,
    },
}
```

This lives strictly in the **business logic layer**, not in views/controllers, so that:

- Frontend changes do not require editing this file.
- You can easily tune scenario behaviour without touching API contracts.

---

## STEP 2 (Backend): Scenario → Filter Translator

In the filtering/orchestrator layer (e.g. `backend/recommendation/filters.py`), create:

```python
from .scenario_config import SCENARIO_CONFIG
import pandas as pd


def apply_scenario_filters(df: pd.DataFrame, scenario: str | None) -> pd.DataFrame:
    """
    Apply scenario-specific constraints to the candidate restaurant dataframe.
    If scenario is None or unknown, the original df is returned.
    """
    if not scenario:
        return df

    config = SCENARIO_CONFIG.get(scenario)
    if not config:
        return df

    if "min_rating" in config:
        df = df[df["aggregate_rating"] >= config["min_rating"]]

    if "max_cost" in config:
        df = df[df["average_cost_for_two"] <= config["max_cost"]]

    if "min_cost" in config:
        df = df[df["average_cost_for_two"] >= config["min_cost"]]

    if "min_votes" in config:
        df = df[df["votes"] >= config["min_votes"]]

    if "preferred_cuisines" in config:
        df = df[
            df["cuisines"].str.contains(
                "|".join(config["preferred_cuisines"]), case=False, na=False
            )
        ]

    # Example hook for diversity-based exploration
    if config.get("diversity_boost"):
        df = _boost_cuisine_diversity(df)

    return df


def _boost_cuisine_diversity(df: pd.DataFrame) -> pd.DataFrame:
    """
    Optional helper to re-order / sample for more cuisine diversity.
    Implementation can be as simple or sophisticated as needed.
    """
    return df
```

**Where this sits in the architecture:**

- Called from the central **recommendation orchestrator** *before* generic filters (distance, open_now, etc.) or *immediately after* them, depending on preference.
- Lives purely in the **business logic layer** and is agnostic of HTTP frameworks and UI.

---

## STEP 3 (Full Stack): Integrate Scenario into the Pipeline

End‑to‑end pipeline (conceptually):

**Frontend**

1. Capture `query` from the text bar.
2. Capture optional `scenario` (user‑selected chip/dropdown).
3. Send payload to backend as shown earlier.

**Backend Orchestrator**

1. If `scenario` is not passed by the frontend, derive it from `query` using `detect_intent` (see below).
2. Extract optional `budget` from the query.
3. Fetch baseline candidates (e.g. by location / base filters).
4. Call `apply_scenario_filters(candidates, scenario)`.
5. Apply any additional structured filters.
6. Take top‑N candidates and call LLM for ranking + explanation.
7. Return ranked list to frontend.

Overall flow:

> User Input → Intent Detection → Scenario Filters → Core Filters → Top‑N → LLM Ranking → Response

---

## FEATURE 2: Free‑Text Intent Detection (Backend Business Logic)

Use the existing text bar as the **single source of truth** for user intent. Structured UI elements (scenario chips, sliders) should simply help construct a richer intent but not replace it.

---

## STEP 4 (Backend): Intent Detection Function

Create `intent_parser.py` in the business logic layer (e.g. `backend/recommendation/intent_parser.py`):

```python
def detect_intent(user_query: str | None) -> str | None:
    if not user_query:
        return None

    query = user_query.lower()

    if "date" in query or "romantic" in query:
        return "date_night"

    if "family" in query:
        return "family_dinner"

    if "quick" in query or "fast" in query or "lunch" in query:
        return "quick_bite"

    if "cheap" in query or "budget" in query:
        return "budget_eating"

    if "explore" in query or "try new" in query:
        return "food_exploration"

    if "group" in query or "friends" in query:
        return "group_hangout"

    return None
```

**Usage in API / Orchestrator:**

```python
from .intent_parser import detect_intent, extract_budget
from .filters import apply_scenario_filters


def get_recommendations(request_payload: dict) -> list[dict]:
    query: str | None = request_payload.get("query")
    scenario: str | None = request_payload.get("scenario")
    budget: int | None = request_payload.get("budget")

    if not scenario:
        scenario = detect_intent(query)

    if not budget:
        budget = extract_budget(query or "")

    candidates = load_candidate_dataframe(request_payload)  # implementation specific
    candidates = apply_scenario_filters(candidates, scenario)

    if budget is not None:
        candidates = candidates[candidates["average_cost_for_two"] <= budget]

    # ... apply other filters, call LLM, shape response ...
    return []
```

---

## STEP 5 (Backend): Extract Budget from Text (Optional but Strong)

Add to `intent_parser.py`:

```python
import re


def extract_budget(query: str) -> int | None:
    match = re.search(r"\d+", query)
    if match:
        return int(match.group())
    return None
```

This function belongs in **business logic**, not in controllers or UI. It should be reused by any endpoint that needs budget extraction from text.

---

## STEP 6 (Backend API): Modify API Layer

Update your API handler (e.g. FastAPI view, Django view, Flask route) to:

1. Accept a JSON body with `query`, optional `scenario`, optional `budget`, and structured filters.
2. Call the orchestrator (`get_recommendations`) rather than performing filtering inline.
3. Log `user_query`, `detected_scenario`, `filters_applied` for observability.

Pseudo‑example:

```python
@router.post("/recommendations")
def recommendations_endpoint(payload: RecommendationRequest) -> RecommendationResponse:
    results = get_recommendations(payload.dict())
    return RecommendationResponse(results=results)
```

---

## STEP 7 (Backend LLM Layer): Prompt Update

When sending candidates to the LLM, include **scenario** and **budget context**:

- **Inputs into prompt**
  - Top‑N candidate restaurants with core attributes.
  - Detected `scenario` (if any).
  - Approximate `budget` (if any).
  - Any additional preferences derived from filters.

- **LLM instructions**
  - “Rank these restaurants based on how suitable they are for `<scenario>`.”
  - “Explain in 1–2 sentences why each option is a good fit for `<scenario>`.”

Ensure this logic is isolated in a dedicated `llm_client` or `prompt_builder` module, not spread across controllers.

---

## STEP 8 (Frontend + Backend): Response Enhancement

Each recommendation item returned from the backend should contain at least:

- `name`
- `rating`
- `average_cost_for_two`
- `scenario` (if applied)
- `explanation` – e.g. `"This is a great choice for date night because..."`

Frontend responsibility:

- Display explanation text **inline with each card**, clearly tied to the selected or detected scenario.

Backend responsibility:

- Guarantee that `explanation` is always present when LLM is used, and define a simple fallback message when LLM is unavailable.

---

## STEP 9 (Backend Business Logic): Fallback Safety

If scenario filtering becomes too strict and returns zero results:

1. **Relax rating**: gradually decrease `min_rating` (e.g. 4.2 → 4.0 → 3.8).
2. **Expand cost range**: widen `min_cost`/`max_cost` constraints.
3. Optionally ignore `preferred_cuisines` while keeping other constraints.

Implement this in the business logic layer so that the API surface stays stable and the frontend does not need to handle this complexity.

---

## STEP 10 (Cross‑Cutting): Logging & Observability

Log the following per request (ideally in a structured log or analytics pipeline):

- `user_query`
- `detected_scenario`
- `budget_extracted`
- `filters_applied` (including which scenario rules fired)
- number of candidates before and after scenario filtering

This enables debugging of mis‑detected intents and tuning of `SCENARIO_CONFIG`.

---

## Final Behavioural Goal

The system should:

- **Accept** both structured filters and natural language.
- **Automatically detect** user intent and scenario.
- **Apply** scenario‑based business logic in a reusable layer.
- **Keep frontend simple**, delegating logic to backend orchestrators.
- **Use the LLM** primarily for ranking and explanations, not raw filtering.

---

## Test Cases (End‑to‑End)

Use these queries and verify for each:

1. `"date night under 1000"` → scenario `date_night`, budget ≈ 1000, mid‑to‑high rating, slightly premium places.
2. `"cheap lunch"` → scenario `quick_bite` or `budget_eating`, low `average_cost_for_two`.
3. `"family dinner in indiranagar"` → scenario `family_dinner`, family‑friendly cuisines, Indiranagar location.
4. `"good place to explore food"` → scenario `food_exploration`, diverse cuisines.
5. `"hangout with friends"` → scenario `group_hangout`, good votes count, suitable for groups.

For each test:

- Confirm the **detected scenario** and **budget**.
- Inspect the **filters applied** (via logs or debug output).
- Validate that UI shows the **scenario explanation** for each recommendation.
