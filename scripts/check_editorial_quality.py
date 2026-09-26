#!/usr/bin/env python3
"""Fail-closed editorial quality contract for Production Intelligence reader copy."""
from __future__ import annotations

from pathlib import Path
import json
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
DATE_RE = re.compile(r"^20\d{2}-\d{2}-\d{2}$")
CJK_RE = re.compile(r"[\u3400-\u9fff]")
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
    errors = []
    seen_blocks = {}

    if not items:
        errors.append("no canonical items")

    for index, item in enumerate(items, 1):
        rid = str(item.get("id") or index)
        title = str(item.get("title") or "").strip()
        summary = str(item.get("summary") or "").strip()
        analysis = item.get("full_analysis") or []

        if not CJK_RE.search(title):
            errors.append(f"{rid}: title must contain zh-Hant editorial framing")
        if len(summary) < 28 or not CJK_RE.search(summary):
            errors.append(f"{rid}: summary must be a concrete zh-Hant production summary")

        visible = "\n".join([title, summary] + [str(x.get("text") or "") for x in analysis])
        for phrase in BANNED:
            if phrase in visible:
                errors.append(f"{rid}: banned mechanical phrase: {phrase}")
        for token in INTERNAL_TOKENS:
            if token in visible:
                errors.append(f"{rid}: internal taxonomy leaked into reader copy: {token}")

        if len(analysis) < 3:
            errors.append(f"{rid}: full_analysis requires three reader-facing angles")
        for block in analysis:
            text = str(block.get("text") or "").strip()
            if len(text) < 36:
                errors.append(f"{rid}: analysis block too shallow")
            if text:
                if text in seen_blocks:
                    errors.append(f"{rid}: exact duplicate analysis block also used by {seen_blocks[text]}")
                else:
                    seen_blocks[text] = rid

    editorial = (data.get("metadata") or {}).get("editorial") or {}
    if date == "2026-09-26":
        if editorial.get("style_reference") != "2026-09-25":
            errors.append("2026-09-26 must record style_reference=2026-09-25")
        if editorial.get("selection_changed") is not False:
            errors.append("2026-09-26 editorial repair must preserve selection")

    if errors:
        fail(errors)
    print(f"EDITORIAL QUALITY PASS: {date} items={len(items)}")

if __name__ == "__main__":
    main()
