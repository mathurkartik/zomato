# improvements.md

This file captures the important implemented improvements in the current project state.

## 1) Core recommendation quality and correctness

- Added scenario-aware filtering using `src/phase3/scenario_config.py` and `src/phase3/scenario_filter.py`.
- Unified cuisine token synonym handling via `src/utils.py` (`coffee` <-> `cafe`) and removed duplicated local helpers.
- Updated scenario config:
  - `date_night` now uses `European` instead of `Continental`.
  - removed unused `diversity_boost` from `food_exploration`.
- Fixed locality extraction precedence so free-text locality does not override a structured dropdown locality.
- Reworked budget extraction to context-aware parsing in orchestrator.
- Prevented re-sort at final response stage to preserve LLM ranking, while still re-numbering rank values.

## 2) Explainability improvements

- Added rejected-restaurant output in API response:
  - `RejectedItem` schema
  - `RecommendationResponse.rejected`
  - rejected list builder in `src/phase3/orchestrator.py`
- Frontend now renders a collapsible "considered but not recommended" list.

## 3) New user filters

- Added optional request filters:
  - `online_order`
  - `book_table`
- Wired these through:
  - `src/phase2/preferences.py`
  - `src/phase2/filter.py`
  - frontend request payload (`frontend/src/lib/api.ts`, `SearchCard.tsx`)

## 4) Dynamic filter counts

- Added dynamic counts endpoint:
  - `POST /api/v1/filters/counts`
- Counts now update according to currently selected form filters
  (locality/cuisine/budget/rating and current toggle state).
- Frontend search card updates counts live using this endpoint.

## 5) API/root behavior updates

- Root endpoint (`GET /`) now returns JSON service info.
- Removed legacy static web serving from backend app.

## 6) UX enhancements

- Added confidence badge in results view based on `meta`.
- Added "Try nearby" behavior via locality callback flow.
- Added online-order and table-booking toggles to search UI.

## 7) Validation and stability

- Added cache-key fields for new filters to avoid stale response reuse.
- Replaced recommendation trace logging call with resilient inline logger block.
- Test suite passed after updates in the latest verified run.

