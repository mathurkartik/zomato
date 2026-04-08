from __future__ import annotations

import json
from typing import Any


def build_messages(*, top_k: int, prefs: dict[str, Any], shortlist: list[dict[str, Any]], prompt_version: str) -> list[dict[str, str]]:
    """
    Build OpenAI-compatible chat messages for Groq (OpenAI schema).
    """
    extras_joined = ", ".join(prefs.get("extras") or [])
    persona = prefs.get("persona") or "premium"
    scenario = prefs.get("scenario")
    user_query = prefs.get("specific_cravings") or prefs.get("query")
    dish = prefs.get("detected_dish")
    dish_cuisine = prefs.get("mapped_cuisine_from_dish")
    if persona == "budget":
        persona_line = (
            "Persona: BUDGET — prioritise value for money; favour lower cost_for_two among comparable ratings.\n"
        )
    else:
        persona_line = (
            "Persona: PREMIUM — prioritise quality and popularity (weighted_score); use rest_type for ambience cues.\n"
        )

    scenario_instruction = (
        "If scenario intent is provided, tailor the ranking and explanation to why each option suits that scenario.\n"
        if scenario
        else ""
    )

    system_message = (
        "You are an expert restaurant recommender for Bangalore, India.\n"
        "You will be given a JSON list of restaurants and a user's preferences.\n"
        f"Recommend the top {top_k} restaurants FROM THE PROVIDED LIST ONLY.\n"
        "Do not invent, hallucinate, or reference any restaurant not present in the list.\n"
        "Prefer highly-rated local restaurants over chain brands where ratings are comparable.\n"
        "Each explanation MUST cite the restaurant's actual rating, cost_for_two, and at least one\n"
        "cuisine from the provided data. Do not invent numeric values.\n"
        + scenario_instruction
        + "Respond ONLY with valid JSON — no markdown fences, no text before or after the object.\n"
    )

    user_message = (
        persona_line
        + "\nUser preferences:\n"
        f"- Locality: {prefs['locality']}\n"
        f"- Maximum budget: ₹{prefs['budget_max_inr']} for two people\n"
        f"- Cuisine preference: {prefs['cuisine']}\n"
        + (f"- Detected dish: {dish}\n" if dish else "")
        + (f"- Dish mapped cuisine: {dish_cuisine}\n" if dish_cuisine else "")
        + f"- Minimum rating: {prefs['min_rating']}\n"
        + (f"- Scenario intent: {scenario}\n" if scenario else "")
        + (f"- User query: {user_query}\n" if user_query else "")
        + f"- Additional preferences (hints only — not guaranteed by data): {extras_joined}\n\n"
        "Restaurant shortlist (recommend ONLY from restaurant_id values below):\n"
        f"{json.dumps(shortlist, ensure_ascii=False)}\n\n"
        "shortlist_json contains only: id, name, rating, cost_for_two, cuisines, rest_type\n"
        "Do not reference fields not present in this data.\n\n"
        "Respond with this exact JSON structure:\n"
        "{\n"
        '  "summary": "2-3 sentences summarising your picks for this user",\n'
        '  "recommendations": [\n'
        "    {\n"
        '      "restaurant_id": "string — must be an id from the shortlist",\n'
        '      "rank": 1,\n'
        '      "explanation": "1-2 sentences citing actual rating, cost, and cuisine from the data"\n'
        "    }\n"
        "  ]\n"
        "}\n"
    )

    # prompt_version is currently informational.
    _ = prompt_version
    return [
        {"role": "system", "content": system_message},
        {"role": "user", "content": user_message},
    ]
