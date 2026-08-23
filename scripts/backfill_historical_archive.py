#!/usr/bin/env python3
"""One-time canonical backfill for legacy historical archive pages.

The legacy HTML is treated as source evidence. This script does not invent news;
it extracts existing title/summary/source/analysis, assigns deterministic stable IDs,
normalizes Full Analysis into structured h4+p blocks, and writes canonical JSON.
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path
from urllib.parse import urlparse

from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]


def norm(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def stable_id(date: str, title: str, source: str) -> str:
    digest = hashlib.sha1(f"{source}|{title}".encode("utf-8")).hexdigest()[:10]
    host = re.sub(r"[^a-z0-9]+", "-", urlparse(source).netloc.lower().replace("www.", "")).strip("-")
    host = host[:24] or "source"
    return f"hist-{date.replace('-', '')}-{host}-{digest}"


def keywords(title: str) -> list[str]:
    parts = [norm(x) for x in re.split(r"[：:｜|／/、，,。()（）\[\]·\-]+", title)]
    out = []
    for part in parts:
        if len(part) >= 2 and part not in out:
            out.append(part[:40])
    return out[:8]


def extract_blocks(card) -> list[dict[str, str]]:
    details = card.find("details")
    body = details.find("div", class_="detail-body") if details else None
    blocks: list[dict[str, str]] = []
    current = "完整分析"
    if body:
        for child in body.find_all(["h4", "p"], recursive=False):
            text = norm(child.get_text(" ", strip=True))
            if not text:
                continue
            if child.name == "h4":
                current = text
            else:
                blocks.append({"label": current, "text": text})
    # Preserve existing information to satisfy the modern structured contract.
    summary = card.find("p", class_="summary") or card.find("p")
    summary_text = norm(summary.get_text(" ", strip=True)) if summary else ""
    impact = card.find("div", class_="quick-impact")
    impact_text = norm(impact.get_text(" ", strip=True)) if impact else ""
    meta = card.find(class_="meta") or card.find(class_="item-meta")
    meta_text = norm(meta.get_text(" ", strip=True)) if meta else ""

    def prepend_unique(label: str, text: str):
        if text and all(norm(b["text"]) != text for b in blocks):
            blocks.insert(0, {"label": label, "text": text})

    if len(blocks) < 3:
        prepend_unique("摘要脈絡", summary_text)
    if len(blocks) < 3:
        prepend_unique("Production 指標", impact_text)
    if len(blocks) < 3:
        prepend_unique("原始標記", meta_text)
    if len(blocks) < 3:
        source = card.find("a", class_="source")
        source_text = norm(source.get_text(" ", strip=True)) if source else "原始來源"
        source_url = source.get("href", "") if source else ""
        prepend_unique("來源脈絡", norm(f"{source_text} {source_url}"))
    if len(blocks) < 3:
        raise RuntimeError("cannot derive >=3 structured Full Analysis blocks from legacy card")
    return blocks


def render_details(soup, blocks):
    details = soup.new_tag("details")
    summary = soup.new_tag("summary")
    summary.string = "完整分析"
    details.append(summary)
    body = soup.new_tag("div")
    body["class"] = ["detail-body"]
    for block in blocks:
        h4 = soup.new_tag("h4")
        h4.string = block["label"]
        p = soup.new_tag("p")
        p.string = block["text"]
        body.append(h4)
        body.append(p)
    details.append(body)
    return details


def main() -> int:
    if len(sys.argv) != 2:
        raise SystemExit("usage: backfill_historical_archive.py YYYY-MM-DD")
    date = sys.argv[1]
    page = ROOT / date / "index.html"
    if not page.exists():
        raise SystemExit(f"archive missing: {page}")
    soup = BeautifulSoup(page.read_text("utf-8"), "html.parser")
    cards = soup.select("article.news")
    if not cards:
        raise SystemExit(f"no legacy archive cards found for {date}")

    records: dict[str, dict] = {}
    visuals: dict[str, dict] = {}
    order: list[str] = []

    for card in cards:
        heading = card.find(["h3", "h4", "h2"])
        source = card.find("a", class_="source")
        if not heading or not source or not source.get("href"):
            continue
        title = norm(heading.get_text(" ", strip=True))
        source_url = source.get("href", "").strip()
        rid = stable_id(date, title, source_url)
        in_top = card.find_parent("section", id="top") is not None
        blocks = extract_blocks(card)

        card["data-intel-id"] = rid
        card["data-intel-role"] = "card"
        source["rel"] = "noopener noreferrer"
        source["target"] = "_blank"
        old = card.find("details")
        new = render_details(soup, blocks)
        if old:
            old.replace_with(new)
        else:
            source.insert_before(new)

        if rid not in records:
            records[rid] = {"id": rid, "slot": "top" if in_top else "more", "full_analysis": blocks}
            order.append(rid)
            visuals[rid] = {
                "enabled": True,
                "source_url": source_url,
                "label": "HISTORICAL SOURCE VISUAL",
                "confidence": "medium",
                "keywords": keywords(title),
            }
        elif in_top:
            records[rid]["slot"] = "top"

    top_ids = []
    for card in soup.select("#top article.news[data-intel-id]"):
        rid = card.get("data-intel-id")
        if rid not in top_ids:
            top_ids.append(rid)
    if len(top_ids) != 5:
        raise SystemExit(f"{date}: expected 5 unique TOP cards, got {len(top_ids)}")

    # Canonical order: TOP 5 first, then first appearance of remaining intelligence.
    canonical_ids = top_ids + [rid for rid in order if rid not in top_ids]
    data = {
        "date": date,
        "schema_version": 2,
        "render_revision": 1,
        "backfilled_from": f"{date}/index.html",
        "visual_evidence": {rid: visuals[rid] for rid in canonical_ids},
        "items": [records[rid] for rid in canonical_ids],
    }
    out = ROOT / "data" / "daily" / f"{date}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", "utf-8")

    # Modern daily shell cache token, without touching the current homepage.
    token = f"{date.replace('-', '')}-r1"
    text = soup.prettify()
    for asset in ("../styles.css", "../daily.css", "../daily.js"):
        text = re.sub(rf"({re.escape(asset)})\?v=[^\"']+", rf"\1?v={token}", text)
    page.write_text(text, "utf-8")
    print(f"backfilled {date}: {len(canonical_ids)} canonical intelligence IDs; TOP={len(top_ids)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
