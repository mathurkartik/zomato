from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


@dataclass(frozen=True)
class DataConfig:
    processed_catalog: Path
    cost_min_valid: int


@dataclass(frozen=True)
class FilterConfig:
    max_shortlist_candidates: int
    chain_max_per_name: int
    relax_rating_by: float
    thin_locality_threshold: int


@dataclass(frozen=True)
class LlmConfig:
    model: str
    temperature: float
    max_tokens: int
    top_k_results: int
    timeout_seconds: int
    prompt_version: str


@dataclass(frozen=True)
class AppConfig:
    data: DataConfig
    filter: FilterConfig
    llm: LlmConfig


def _resolve_paths(base: Path, raw: dict[str, Any]) -> dict[str, Any]:
    data = dict(raw.get("data", {}))
    if "processed_catalog" in data and isinstance(data["processed_catalog"], str):
        p = Path(data["processed_catalog"])
        data["processed_catalog"] = p if p.is_absolute() else (base / p).resolve()
    return {**raw, "data": data}


def load_config(path: str | Path | None = None) -> AppConfig:
    base = Path(__file__).resolve().parent.parent
    cfg_path = Path(path) if path else base / "config.yaml"
    with open(cfg_path, encoding="utf-8") as f:
        raw = yaml.safe_load(f)
    raw = _resolve_paths(base, raw)
    d = raw["data"]
    f = raw["filter"]
    l = raw["llm"]
    return AppConfig(
        data=DataConfig(
            processed_catalog=d["processed_catalog"],
            cost_min_valid=int(d["cost_min_valid"]),
        ),
        filter=FilterConfig(
            max_shortlist_candidates=int(f["max_shortlist_candidates"]),
            chain_max_per_name=int(f["chain_max_per_name"]),
            relax_rating_by=float(f["relax_rating_by"]),
            thin_locality_threshold=int(f["thin_locality_threshold"]),
        ),
        llm=LlmConfig(
            model=str(l["model"]),
            temperature=float(l["temperature"]),
            max_tokens=int(l["max_tokens"]),
            top_k_results=int(l["top_k_results"]),
            timeout_seconds=int(l["timeout_seconds"]),
            prompt_version=str(l["prompt_version"]),
        ),
    )
