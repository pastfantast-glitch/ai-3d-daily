#!/usr/bin/env python3
"""Fail-closed editorial quality contract for Production Intelligence reader copy."""
from __future__ import annotations

from pathlib import Path
from collections import Counter
import json
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
EDITORIAL_CFG = ROOT / "config" / "editorial-quality.json"
DATE_RE = re.compile(r"^20\d{2}-\d{2}-\d{2}$")
CJK_RE = re.compile(r"[\u3400-\u9fff]")
KANA_RE = re.compile(r"[\u3040-\u30ff]")
LATIN_RE = re.compile(r"[A-Za-z]")
EFFECTIVE_DATE = "2026-09-26"
BANNED = (
    "來源頁面顯示",
    "頁面內容指出：",
    "Collector 因此",
    "具有直接 Production 參考價值",
    "來源可驗證的製作重點包含",
    "來源可驗證的主題落在",
    "近期工具、流程或案例參考",
)
INTERNAL_TOKENS = (
    "3d-animation", "3d-production", "engine-art",
    "blender-dcc", "emerging-case", "ai-generation",
)

def load_editorial_config():
    try:
        return json.loads(EDITORIAL_CFG.read_text("utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def copy_signature(text):
    text = re.sub(r"「[^」]{1,220}」", "「TITLE」", str(text or ""))
    text = re.sub(r"https?://\S+", "URL", text)
    text = re.sub(r"\b[A-Za-z][A-Za-z0-9._+/#-]*\b", "TERM", text)
    text = re.sub(r"\d+(?:\.\d+)?", "NUM", text)
    return re.sub(r"\s+", " ", text).strip().casefold()


def language_balance_ok(text, max_latin_per_han):
    text = str(text or "")
    if KANA_RE.search(text):
        return False
    han = len(CJK_RE.findall(text))
    latin = len(LATIN_RE.findall(text))
    return han >= 2 and latin <= max(8, int(han * float(max_latin_per_han)))


def pending_editorial_override(date, data):
    done_path = ROOT / "data" / "publish" / f"{date}.done.json"
    override_path = ROOT / "data" / "editorial-overrides" / f"{date}.json"
    if not done_path.exists() or not override_path.exists():
        return None
    try:
        done = json.loads(done_path.read_text("utf-8"))
        override = json.loads(override_path.read_text("utf-8"))
    except Exception:
        return None
    if str(done.get("state", "")).upper() != "DONE":
        return None
    if override.get("preserve_selection") is not True or override.get("date") != date:
        return None
    canonical_ids = {str(x.get("id") or "") for x in (data.get("items") or [])}
    override_items = override.get("items") or {}
    if set(override_items) != canonical_ids:
        return None
    return override_items


def fail(errors):
    print("EDITORIAL QUALITY FAILED")
    for error in errors:
        print("-", error)
    raise SystemExit(1)

def main():
    if len(sys.argv) > 2:
        raise SystemExit("usage: check_editorial_quality.py [YYYY-MM-DD]")
    if len(sys.argv) == 2:
        date = sys.argv[1]
    else:
        dates = sorted(p.stem for p in (ROOT / "data" / "daily").glob("20??-??-??.json"))
        if not dates:
            raise SystemExit("EDITORIAL QUALITY FAILED: no daily datasets")
        date = dates[-1]
    if not DATE_RE.fullmatch(date):
        raise SystemExit("usage: check_editorial_quality.py [YYYY-MM-DD]")
    if date < EFFECTIVE_DATE:
        print(f"EDITORIAL QUALITY SKIP: {date} before {EFFECTIVE_DATE}")
        return

    data = json.loads((ROOT / "data" / "daily" / f"{date}.json").read_text("utf-8"))
    items = data.get("items") or []
    pending_override = pending_editorial_override(date, data)
    cfg = load_editorial_config()
    qa_cfg = cfg.get("qa") or {}
    banned = tuple(qa_cfg.get("banned_phrases") or BANNED)
    title_patterns = [re.compile(x) for x in (qa_cfg.get("banned_title_patterns") or [])]
    plain = cfg.get("plain_reading") or {}
    if date >= str(plain.get("effective_date") or "9999-12-31"):
        banned += tuple(plain.get("banned_phrases") or [])
        title_patterns += [re.compile(x) for x in (plain.get("banned_title_patterns") or [])]
    min_summary_chars = int(qa_cfg.get("min_summary_chars", 28) or 28)
    min_analysis_chars = int(qa_cfg.get("min_analysis_block_chars", 36) or 36)
    max_signature_occurrences = int(qa_cfg.get("max_cross_item_signature_occurrences", 2) or 2)
    language_cfg = cfg.get("language_quality") or {}
    language_effective = str(language_cfg.get("effective_date") or "9999-12-31")
    strict_language = date >= language_effective
    title_ratio = float(language_cfg.get("title_max_latin_letters_per_han", 4.0) or 4.0)
    summary_ratio = float(language_cfg.get("summary_max_latin_letters_per_han", 2.5) or 2.5)
    analysis_ratio = float(language_cfg.get("analysis_max_latin_letters_per_han", 3.0) or 3.0)
    errors = []
    seen_blocks = {}
    summary_signatures = Counter()
    summary_signature_owner = {}

    if not items:
        errors.append("no canonical items")

    for index, item in enumerate(items, 1):
        rid = str(item.get("id") or index)
        reader = (pending_override or {}).get(rid) or item
        title = str(reader.get("title") or "").strip()
        summary = str(reader.get("summary") or "").strip()
        analysis = reader.get("full_analysis") or []

        if not CJK_RE.search(title):
            errors.append(f"{rid}: title must contain zh-Hant editorial framing")
        if len(summary) < min_summary_chars or not CJK_RE.search(summary):
            errors.append(f"{rid}: summary must be a concrete zh-Hant production summary")

        if strict_language:
            if not language_balance_ok(title, title_ratio):
                errors.append(f"{rid}: title must be predominantly zh-Hant and contain no Japanese kana")
            if not language_balance_ok(summary, summary_ratio):
                errors.append(f"{rid}: summary must be predominantly zh-Hant and contain no Japanese kana")

        visible = "\n".join([title, summary] + [str(x.get("text") or "") for x in analysis])
        for pattern in title_patterns:
            if pattern.search(title):
                errors.append(f"{rid}: title matches banned repetitive framing: {pattern.pattern}")

        signature = copy_signature(summary)
        if signature:
            summary_signatures[signature] += 1
            summary_signature_owner.setdefault(signature, rid)

        for phrase in banned:
            if phrase in visible:
                errors.append(f"{rid}: banned mechanical phrase: {phrase}")
        for token in INTERNAL_TOKENS:
            if token in visible:
                errors.append(f"{rid}: internal taxonomy leaked into reader copy: {token}")

        if len(analysis) < 3:
            errors.append(f"{rid}: full_analysis requires three reader-facing angles")
        for block in analysis:
            text = str(block.get("text") or "").strip()
            if len(text) < min_analysis_chars:
                errors.append(f"{rid}: analysis block too shallow")
            if strict_language and not language_balance_ok(text, analysis_ratio):
                errors.append(f"{rid}: analysis block must be predominantly zh-Hant and contain no Japanese kana")
            if text:
                if text in seen_blocks:
                    errors.append(f"{rid}: exact duplicate analysis block also used by {seen_blocks[text]}")
                else:
                    seen_blocks[text] = rid

    for signature, count in summary_signatures.items():
        if count > max_signature_occurrences:
            errors.append(
                f"cross-item summary boilerplate repeated {count} times; "
                f"first={summary_signature_owner.get(signature)}"
            )

    metadata = data.get("metadata") or {}
    editorial = metadata.get("editorial") or {}
    effective = str(cfg.get("effective_date") or "9999-12-31")
    if date >= effective:
        expected_contract = str(cfg.get("contract") or "").strip()
        expected_style = str(cfg.get("style_reference") or "").strip()
        if expected_contract and editorial.get("contract") != expected_contract:
            errors.append(f"editorial.contract must be {expected_contract}")
        if expected_style and editorial.get("style_reference") != expected_style:
            errors.append(f"editorial.style_reference must be {expected_style}")
        if editorial.get("factual_fallback_allowed") is not True:
            errors.append("editorial.factual_fallback_allowed must be true")
    if date == "2026-09-26":
        if editorial.get("style_reference") != "2026-09-25":
            errors.append("2026-09-26 must record style_reference=2026-09-25")
        if editorial.get("selection_changed") is not False:
            errors.append("2026-09-26 editorial repair must preserve selection")

    if errors:
        fail(errors)
    pending = " pending-editorial-override" if pending_override else ""
    print(f"EDITORIAL QUALITY PASS: {date} items={len(items)}{pending}")

if __name__ == "__main__":
    main()
