from __future__ import annotations

import hashlib
import json
import logging
import time
from pathlib import Path
from typing import Any

try:
    import yaml
except ModuleNotFoundError:
    yaml = None

_logger = logging.getLogger("biteai.ab_testing")

_CONFIG_PATH = Path(__file__).resolve().parent.parent.parent / "config" / "ab_tests.yaml"
_LOG_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "ab_test_log.jsonl"


class Experiment:
    def __init__(self, name: str, enabled: bool, variants: dict[str, dict[str, Any]]):
        self.name = name
        self.enabled = enabled
        self.variants = variants

    def variant_names(self) -> list[str]:
        return list(self.variants.keys())

    def total_weight(self) -> int:
        return sum(int(v.get("weight", 0)) for v in self.variants.values())


class ABTestManager:
    def __init__(self, config_path: Path | None = None, log_path: Path | None = None):
        self.config_path = config_path or _CONFIG_PATH
        self.log_path = log_path or _LOG_PATH
        self.experiments: dict[str, Experiment] = {}
        self._load_config()

    def _load_config(self) -> None:
        if yaml is None or not self.config_path.exists():
            return
        with open(self.config_path, encoding="utf-8") as f:
            raw = yaml.safe_load(f) or {}
        for name, cfg in raw.get("experiments", {}).items():
            self.experiments[name] = Experiment(
                name=name,
                enabled=bool(cfg.get("enabled", False)),
                variants=cfg.get("variants", {}),
            )

    def assign_variant(self, session_id: str, experiment_name: str) -> str | None:
        exp = self.experiments.get(experiment_name)
        if exp is None or not exp.enabled:
            return None
        total = exp.total_weight()
        if total <= 0:
            return None
        bucket = int(hashlib.md5(f"{session_id}:{experiment_name}".encode()).hexdigest(), 16) % total
        cumulative = 0
        for variant_name, variant_cfg in exp.variants.items():
            cumulative += int(variant_cfg.get("weight", 0))
            if bucket < cumulative:
                return variant_name
        return list(exp.variants.keys())[-1]

    def get_flag_overrides(self, session_id: str) -> dict[str, bool]:
        overrides: dict[str, bool] = {}
        for exp_name, exp in self.experiments.items():
            if not exp.enabled:
                continue
            variant = self.assign_variant(session_id, exp_name)
            if variant is None:
                continue
            flags = exp.variants.get(variant, {}).get("flags", {})
            for flag_name, flag_val in flags.items():
                overrides[flag_name] = bool(flag_val)
        return overrides

    def log_assignment(self, session_id: str, experiment: str, variant: str, flags_applied: dict[str, bool]) -> None:
        entry = {
            "timestamp": time.time(),
            "session_id": session_id,
            "experiment": experiment,
            "variant": variant,
            "feature_flags_applied": flags_applied,
        }
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")

    def log_all_assignments(self, session_id: str) -> dict[str, str]:
        assignments: dict[str, str] = {}
        for exp_name, exp in self.experiments.items():
            if not exp.enabled:
                continue
            variant = self.assign_variant(session_id, exp_name)
            if variant is None:
                continue
            flags = exp.variants.get(variant, {}).get("flags", {})
            self.log_assignment(session_id, exp_name, variant, {k: bool(v) for k, v in flags.items()})
            assignments[exp_name] = variant
        return assignments

    def read_results(self) -> dict[str, dict[str, int]]:
        results: dict[str, dict[str, int]] = {}
        if not self.log_path.exists():
            return results
        with open(self.log_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue
                exp = entry.get("experiment", "")
                var = entry.get("variant", "")
                if exp not in results:
                    results[exp] = {}
                results[exp][var] = results[exp].get(var, 0) + 1
        return results


_manager: ABTestManager | None = None


def get_ab_manager() -> ABTestManager:
    global _manager
    if _manager is None:
        _manager = ABTestManager()
    return _manager
