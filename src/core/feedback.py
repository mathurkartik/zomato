from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field

_LOG_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "feedback_log.jsonl"


class FeedbackRequest(BaseModel):
    session_id: str
    recommendation_id: str
    rating: Literal["up", "down"]
    comment: str | None = None
    visited: bool = False


class FeedbackSummary(BaseModel):
    total: int = 0
    thumbs_up: int = 0
    thumbs_down: int = 0
    up_down_ratio: float | None = None
    visit_rate: float | None = None
    per_variant: dict[str, dict[str, Any]] = Field(default_factory=dict)


def store_feedback(feedback: FeedbackRequest, variant_info: dict[str, str] | None = None) -> dict[str, Any]:
    entry: dict[str, Any] = {
        "timestamp": time.time(),
        "session_id": feedback.session_id,
        "recommendation_id": feedback.recommendation_id,
        "rating": feedback.rating,
        "comment": feedback.comment,
        "visited": feedback.visited,
    }
    if variant_info:
        entry["ab_variants"] = variant_info
    _LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(_LOG_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")
    return entry


def compute_summary(log_path: Path | None = None) -> FeedbackSummary:
    path = log_path or _LOG_PATH
    entries: list[dict[str, Any]] = []
    if path.exists():
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entries.append(json.loads(line))
                except json.JSONDecodeError:
                    continue

    total = len(entries)
    thumbs_up = sum(1 for e in entries if e.get("rating") == "up")
    thumbs_down = sum(1 for e in entries if e.get("rating") == "down")
    visited = sum(1 for e in entries if e.get("visited"))

    up_down_ratio: float | None = None
    if thumbs_down > 0:
        up_down_ratio = round(thumbs_up / thumbs_down, 2)
    elif thumbs_up > 0:
        up_down_ratio = float("inf")

    visit_rate: float | None = None
    if total > 0:
        visit_rate = round(visited / total, 4)

    per_variant: dict[str, dict[str, Any]] = {}
    for e in entries:
        ab_variants = e.get("ab_variants", {})
        for exp_name, variant in ab_variants.items():
            key = f"{exp_name}:{variant}"
            if key not in per_variant:
                per_variant[key] = {"total": 0, "up": 0, "down": 0, "visited": 0}
            per_variant[key]["total"] += 1
            if e.get("rating") == "up":
                per_variant[key]["up"] += 1
            elif e.get("rating") == "down":
                per_variant[key]["down"] += 1
            if e.get("visited"):
                per_variant[key]["visited"] += 1

    return FeedbackSummary(
        total=total,
        thumbs_up=thumbs_up,
        thumbs_down=thumbs_down,
        up_down_ratio=up_down_ratio,
        visit_rate=visit_rate,
        per_variant=per_variant,
    )
