#!/usr/bin/env python3
"""Shared date-aware policy resolver for release, analysis, discovery and personalization.

This module is intentionally small and side-effect free. It centralizes interpretation
of current-main JSON policy so renderer/verifier/collector code can share one date
boundary instead of reimplementing effective-date logic independently.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
import json

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config"


@lru_cache(maxsize=None)
def _load(name: str) -> dict:
    return json.loads((CONFIG / name).read_text("utf-8"))


def intelligence_policy() -> dict:
    return _load("intelligence-v2.json")


def analysis_depth_policy() -> dict:
    return _load("full-analysis-depth.json")


def discovery_policy_raw() -> dict:
    return _load("discovery-hybrid.json")


def personalization_policy_raw() -> dict:
    return _load("personalization-feedback.json")


def _effective(date: str, cfg: dict, key: str = "effective_date") -> bool:
    boundary = str(cfg.get(key) or "").strip()
    return bool(boundary and date >= boundary)


def tiered_analysis_enabled(date: str) -> bool:
    return _effective(date, analysis_depth_policy(), "tiered_effective_date")


def brief_reading_enabled(date: str) -> bool:
    return _effective(date, analysis_depth_policy(), "brief_reading_contract_effective_date")


def brief_policy_for_date(date: str) -> dict:
    cfg = analysis_depth_policy()
    if brief_reading_enabled(date):
        return cfg.get("brief_reading") or cfg.get("brief") or {}
    return cfg.get("brief") or {}


def analysis_policy(date: str, item: dict, legacy_min_blocks: int = 3):
    """Return (level, min_blocks, max_blocks, error) for one public item."""
    cfg = analysis_depth_policy()
    if not tiered_analysis_enabled(date):
        return "FULL", int(legacy_min_blocks), None, None

    level = str(item.get("analysis_level") or cfg.get("default_analysis_level") or "FULL").upper()
    if level == "REJECT":
        return level, 0, 0, "REJECT item reached public Pages surface"
    if level not in ("FULL", "BRIEF"):
        return level, 0, 0, f"unknown analysis_level={level}"

    rule = brief_policy_for_date(date) if level == "BRIEF" else (cfg.get("full") or {})
    minimum = int(rule.get("min_blocks", 0) or 0)
    maximum = int(rule.get("max_blocks", 0) or 0)
    if minimum <= 0 or maximum < minimum:
        return level, minimum, maximum, f"invalid {level} depth policy min={minimum} max={maximum}"
    return level, minimum, maximum, None


def top5_policy() -> dict:
    return analysis_depth_policy().get("top5_policy") or {}


def release_policy() -> dict:
    collection = intelligence_policy().get("collection") or {}
    return {
        "daily_min_items": int(collection.get("daily_min_items", 0) or 0),
        "daily_target_items": int(collection.get("daily_target_items", 0) or 0),
        "daily_max_items": int(collection.get("daily_max_items", 0) or 0),
        "discovery_windows": list(collection.get("discovery_windows") or []),
        "admission_policy": collection.get("admission_policy") or {},
    }


def discovery_policy(date: str) -> dict:
    cfg = discovery_policy_raw()
    return cfg if _effective(date, cfg) else {}


def personalization_policy(date: str) -> dict:
    cfg = personalization_policy_raw()
    if not _effective(date, cfg):
        return {"active": False, "config": cfg}
    return {"active": True, "config": cfg}


def policy_snapshot(date: str) -> dict:
    """Compact non-sensitive snapshot for diagnostics and contract tests."""
    level, min_blocks, max_blocks, error = analysis_policy(
        date, {"analysis_level": "BRIEF"}, legacy_min_blocks=3
    )
    release = release_policy()
    personalization = personalization_policy(date)
    return {
        "date": date,
        "analysis": {
            "tiered": tiered_analysis_enabled(date),
            "brief_reading": brief_reading_enabled(date),
            "brief_level": level,
            "brief_min_blocks": min_blocks,
            "brief_max_blocks": max_blocks,
            "error": error,
        },
        "top5": top5_policy(),
        "release": release,
        "discovery_active": bool(discovery_policy(date)),
        "personalization_active": bool(personalization.get("active")),
    }
