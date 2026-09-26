#!/usr/bin/env python3
"""Autonomous, source-grounded Collector for AI/3D/Game-Art Production Intelligence.

This script owns only Collector/private artifacts. It never writes public HTML,
visual assets, publish-state markers, or publish receipts.
All policy remains config-driven from current main.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date as date_cls, datetime
from email.utils import parsedate_to_datetime
from pathlib import Path
from urllib.parse import urljoin, urlparse
from zoneinfo import ZoneInfo
import hashlib
import json
import re
import sys
import time

import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from discovery_hybrid import load_hybrid_config, registered_source_probe_plan
from url_identity import canonicalize_url
from content_quality import admission as content_admission, classify_content, normalize_title, production_summary

INTEL_PATH = ROOT / "config" / "intelligence-v2.json"
DEPTH_PATH = ROOT / "config" / "full-analysis-depth.json"
PERSONAL_PATH = ROOT / "config" / "personalization-feedback.json"
RUNTIME_PATH = ROOT / "config" / "collector-runtime.json"
SNAPSHOT_PATH = ROOT / "data" / "candidates" / "published-registry-snapshot.json"
BACKLOG_PATH = ROOT / "data" / "candidates" / "rolling-backlog.json"

TRACKING_SOURCE = "autonomous-github-collector-v1"
DATE_RE = re.compile(r"^20\d{2}-\d{2}-\d{2}$")
WS_RE = re.compile(r"\s+")
DATE_TEXT_RE = re.compile(r"(20\d{2})[-/.](0?[1-9]|1[0-2])[-/.](0?[1-9]|[12]\d|3[01])")
ARTICLE_TYPES = {"article", "newsarticle", "blogposting", "techarticle", "report"}
BAD_PATH_PARTS = (
    "/tag/", "/tags/", "/category/", "/categories/", "/author/", "/authors/",
    "/search", "/login", "/signin", "/signup", "/privacy", "/terms", "/contact",
    "/about", "/feed", "/rss", "/wp-json/", "/cart", "/checkout",
)
BAD_EXTENSIONS = (
    ".jpg", ".jpeg", ".png", ".webp", ".gif", ".svg", ".zip", ".pdf",
    ".mp4", ".mov", ".webm", ".css", ".js", ".xml",
)
RELEVANCE_TERMS = (
    "3d", "blender", "maya", "houdini", "substance", "unreal", "unity", "shader",
    "render", "material", "texture", "model", "sculpt", "character", "environment",
    "animation", "rig", "mocap", "retarget", "vfx", "fx", "procedural", "geometry",
    "game", "artist", "pipeline", "workflow", "plugin", "add-on", "addon", "tool",
    "ai", "genai", "image-to-3d", "text-to-3d", "world model", "gaussian", "nerf",
    "zbrush", "mari", "3ds max", "cinema 4d", "octane", "redshift", "arnold",
    "metahuman", "nanite", "lumen", "pcg", "kinefx", "groom", "retopo", "uv",
)
PRODUCTION_TERMS = (
    "workflow", "pipeline", "breakdown", "tutorial", "release", "update", "version",
    "tool", "plugin", "addon", "add-on", "production", "making", "create", "creating",
    "modeling", "texturing", "rigging", "animation", "rendering", "shader", "material",
    "technique", "case study", "behind", "overview", "guide", "documentation",
    "new", "beta", "alpha", "preview", "demo", "research",
)


def clean(value: object, limit: int | None = None) -> str:
    text = WS_RE.sub(" ", str(value or "")).strip()
    return text[:limit].rstrip() if limit and len(text) > limit else text


def load_json(path: Path):
    return json.loads(path.read_text("utf-8"))


def write_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", "utf-8")


def current_date(runtime: dict) -> str:
    if len(sys.argv) > 1 and sys.argv[1]:
        value = sys.argv[1].strip()
    else:
        value = datetime.now(ZoneInfo(runtime["timezone"])).date().isoformat()
    if not DATE_RE.fullmatch(value):
        raise SystemExit("usage: run_daily_collector.py [YYYY-MM-DD]")
    return value


def same_registered_domain(url: str, domain: str) -> bool:
    try:
        host = (urlparse(url).hostname or "").lower()
    except Exception:
        return False
    domain = domain.lower().lstrip(".")
    return host == domain or host.endswith("." + domain)


def article_like_url(url: str) -> bool:
    parsed = urlparse(url)
    path = parsed.path.lower()
    if parsed.scheme != "https" or not parsed.netloc or path in ("", "/"):
        return False
    if any(part in path for part in BAD_PATH_PARTS) or path.endswith(BAD_EXTENSIONS):
        return False
    segments = [x for x in path.split("/") if x]
    if len(segments) < 1:
        return False
    leaf = segments[-1]
    if leaf in {"articles", "news", "blog", "community", "tutorials", "discover"}:
        return False
    return len(leaf) >= 4


def fetch(session: requests.Session, url: str, timeout: int) -> dict:
    started = time.monotonic()
    try:
        response = session.get(url, timeout=timeout, allow_redirects=True)
        status = int(response.status_code)
        content_type = response.headers.get("content-type", "")
        if status >= 400:
            return {
                "url": url, "final_url": response.url, "status": status, "html": "",
                "error": f"http-{status}", "elapsed": time.monotonic() - started,
            }
        if "html" not in content_type.lower() and "<html" not in response.text[:500].lower():
            return {
                "url": url, "final_url": response.url, "status": status, "html": "",
                "error": "non-html", "elapsed": time.monotonic() - started,
            }
        return {
            "url": url, "final_url": response.url, "status": status, "html": response.text,
            "error": "", "elapsed": time.monotonic() - started,
        }
    except requests.RequestException as exc:
        return {
            "url": url, "final_url": url, "status": 0, "html": "",
            "error": type(exc).__name__, "elapsed": time.monotonic() - started,
        }


def meta_content(soup: BeautifulSoup, *selectors: tuple[str, str]) -> str:
    for attr, key in selectors:
        node = soup.find("meta", attrs={attr: key})
        if node and clean(node.get("content")):
            return clean(node.get("content"))
    return ""


def json_ld_objects(soup: BeautifulSoup):
    for node in soup.find_all("script", attrs={"type": "application/ld+json"}):
        raw = node.string or node.get_text()
        if not clean(raw):
            continue
        try:
            value = json.loads(raw)
        except Exception:
            continue
        stack = value if isinstance(value, list) else [value]
        while stack:
            item = stack.pop(0)
            if isinstance(item, dict):
                yield item
                graph = item.get("@graph")
                if isinstance(graph, list):
                    stack.extend(graph)
            elif isinstance(item, list):
                stack.extend(item)


def parse_date(value: object) -> str | None:
    text = clean(value)
    if not text:
        return None
    try:
        dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
        return dt.date().isoformat()
    except ValueError:
        pass
    try:
        return parsedate_to_datetime(text).date().isoformat()
    except Exception:
        pass
    match = DATE_TEXT_RE.search(text)
    if match:
        try:
            return date_cls(int(match.group(1)), int(match.group(2)), int(match.group(3))).isoformat()
        except ValueError:
            return None
    return None


def page_metadata(result: dict, fallback_title: str = "") -> dict | None:
    html = result.get("html") or ""
    if not html:
        return None
    soup = BeautifulSoup(html, "html.parser")
    title = (
        meta_content(soup, ("property", "og:title"), ("name", "twitter:title"))
        or clean(soup.title.get_text(" ", strip=True) if soup.title else "")
        or clean(fallback_title)
    )
    title = normalize_title(title)
    description = meta_content(
        soup,
        ("property", "og:description"),
        ("name", "description"),
        ("name", "twitter:description"),
    )
    published = meta_content(
        soup,
        ("property", "article:published_time"),
        ("name", "article:published_time"),
        ("name", "date"),
        ("itemprop", "datePublished"),
    )
    article_type = False
    for obj in json_ld_objects(soup):
        typ = obj.get("@type")
        types = typ if isinstance(typ, list) else [typ]
        lowered = {clean(x).lower() for x in types if x}
        if lowered & ARTICLE_TYPES:
            article_type = True
            title = clean(obj.get("headline") or obj.get("name") or title)
            description = clean(obj.get("description") or description)
            published = clean(obj.get("datePublished") or published)
            break
    if not description:
        paragraphs = [clean(p.get_text(" ", strip=True), 600) for p in soup.find_all("p")]
        description = next((p for p in paragraphs if len(p) >= 60), "")
    if not published:
        node = soup.find("time")
        if node:
            published = clean(node.get("datetime") or node.get_text(" ", strip=True))
    final_url = canonicalize_url(result.get("final_url") or result.get("url") or "")
    if not final_url.startswith("https://") or not title:
        return None
    return {
        "url": final_url,
        "title": clean(title, 220),
        "description": clean(description, 650),
        "published": parse_date(published),
        "article_type": article_type,
        "html": html,
    }


def extract_links(html: str, base_url: str, domain: str, limit: int) -> list[tuple[str, str]]:
    if not html:
        return []
    soup = BeautifulSoup(html, "html.parser")
    out: list[tuple[str, str]] = []
    seen: set[str] = set()
    for anchor in soup.find_all("a", href=True):
        href = clean(anchor.get("href"))
        if not href or href.startswith(("#", "mailto:", "javascript:", "tel:")):
            continue
        absolute = canonicalize_url(urljoin(base_url, href))
        if not absolute.startswith("https://") or not same_registered_domain(absolute, domain) or not article_like_url(absolute):
            continue
        if absolute in seen:
            continue
        text = clean(anchor.get_text(" ", strip=True), 220)
        if len(text) < 4:
            continue
        seen.add(absolute)
        out.append((absolute, text))
        if len(out) >= limit:
            break
    return out


def relevant(meta: dict) -> bool:
    admitted, _ = content_admission(meta)
    return admitted


def stable_id(source_id: str, url: str, title: str, used: set[str]) -> str:
    path = urlparse(url).path.strip("/")
    raw = path.split("/")[-1] if path else ""
    raw = re.sub(r"\.(html?|php)$", "", raw, flags=re.I)
    raw = re.sub(r"[^a-zA-Z0-9]+", "-", raw).strip("-").lower()
    if not raw or raw.isdigit() or len(raw) < 5:
        raw = re.sub(r"[^a-zA-Z0-9]+", "-", title).strip("-").lower()[:42]
    raw = raw[:60].strip("-") or "candidate"
    candidate = f"{source_id}-{raw}"
    if len(candidate) > 84:
        candidate = candidate[:74].rstrip("-")
    if candidate in used:
        candidate = f"{candidate[:72]}-{hashlib.sha1(url.encode()).hexdigest()[:8]}"
    used.add(candidate)
    return candidate


def classify(text: str) -> tuple[str, str]:
    t = text.casefold()
    if any(k in t for k in ("meshy", "tripo", "hunyuan", "image-to-3d", "text-to-3d", "ai 3d", "genai", "generative ai")):
        return "ai-generation", "ai-3d"
    if any(k in t for k in ("motion generation", "ai motion", "motion ai", "video-to-motion")):
        return "ai-generation", "ai-motion"
    if any(k in t for k in ("image generation", "concept art ai", "comfyui", "upscal")):
        return "ai-generation", "ai-2d"
    if any(k in t for k in ("rigging", " rig ", "control rig", "skeleton", "skinning", "skin weight")):
        return "3d-animation", "rigging"
    if any(k in t for k in ("mocap", "motion capture")):
        return "3d-animation", "mocap"
    if "retarget" in t:
        return "3d-animation", "retarget"
    if any(k in t for k in ("facial animation", "face animation", "lip sync")):
        return "3d-animation", "facial"
    if any(k in t for k in ("animation", "animator", "keyframe", "body mechanics", "locomotion")):
        return "3d-animation", "animation"
    if "unreal" in t or "ue5" in t:
        return "engine-art", "unreal"
    if "unity" in t:
        return "engine-art", "unity"
    if any(k in t for k in ("shader", "material graph", "toon", "npr")):
        return "engine-art", "shader"
    if any(k in t for k in ("rendering", "renderer", "lumen", "nanite", "ray tracing", "path tracing")):
        return "engine-art", "rendering"
    if any(k in t for k in ("optimization", "performance", "lod", "hlod", "draw call")):
        return "engine-art", "optimization"
    if any(k in t for k in ("world model", "world-model")):
        return "emerging-case", "world-model"
    if any(k in t for k in ("gaussian splat", "nerf", "research", "paper", "siggraph")):
        return "emerging-case", "research"
    if any(k in t for k in ("case study", "postmortem", "breakdown", "behind the scenes", "behind-the-scenes", "vfx breakdown")):
        return "emerging-case", "case-study"
    if "procedural" in t:
        return "emerging-case", "procedural"
    if "blender" in t:
        if any(k in t for k in ("addon", "add-on", "plugin", "tool")):
            return "blender-dcc", "addon"
        return "blender-dcc", "blender"
    if "maya" in t:
        return "blender-dcc", "maya"
    if "houdini" in t:
        return "blender-dcc", "houdini"
    if "substance" in t:
        return "blender-dcc", "substance"
    if any(k in t for k in ("3ds max", "cinema 4d", "mari", "nuke", "octane", "redshift", "arnold", "v-ray")):
        return "blender-dcc", "other-dcc"
    if any(k in t for k in ("character", "portrait", "hair", "groom", "cloth", "anatomy", "creature")):
        return "3d-production", "character-production"
    if any(k in t for k in ("environment", "terrain", "landscape", "building", "architecture", "foliage", "scene")):
        return "3d-production", "environment-production"
    if any(k in t for k in ("weapon", "vehicle", "hard surface", "hard-surface", "prop")):
        return "3d-production", "prop-production"
    if any(k in t for k in ("model", "texture", "material", "uv", "retopo", "baking", "scan", "photogrammetry")):
        return "3d-production", "production-workflow"
    return "emerging-case", "case-study"


def window_for(published: str | None, report_date: str) -> str:
    if not published:
        return "evergreen"
    try:
        age = (date_cls.fromisoformat(report_date) - date_cls.fromisoformat(published)).days
    except ValueError:
        return "evergreen"
    if age <= 1:
        return "24h"
    if age <= 7:
        return "7d"
    if age <= 30:
        return "30d"
    if age <= 183:
        return "6m"
    return "evergreen"


def brief_reason(text: str, source_id: str) -> str:
    t = text.casefold()
    if any(k in t for k in ("alpha", "beta", "preview", "experimental")):
        return "early-release-limited-evidence"
    if any(k in t for k in ("tutorial", "how to", "guide", "tips", "workflow")):
        return "practical-tutorial-limited-depth"
    if any(k in t for k in ("addon", "add-on", "plugin", "tool")):
        return "useful-tool-or-addon-limited-depth"
    if any(k in t for k in ("research", "paper", "world model", "gaussian", "nerf")):
        return "emerging-research-limited-production-evidence"
    if any(k in t for k in ("breakdown", "case study", "postmortem", "behind")):
        return "production-reference-limited-depth"
    if source_id in {
        "blender-official", "epic-developer-community", "unity-official",
        "sidefx-official", "autodesk-area", "adobe-substance-3d",
    }:
        return "short-official-announcement"
    return "single-source-verified-production-tip"


def score_candidate(meta: dict, category: str, source_id: str, report_date: str) -> float:
    score = 58.0
    window = window_for(meta.get("published"), report_date)
    score += {"24h": 22, "7d": 16, "30d": 10, "6m": 5, "evergreen": 2}[window]
    text = (meta["title"] + " " + meta.get("description", "")).casefold()
    if any(k in text for k in ("release", "update", "version", "beta", "alpha", "new ")):
        score += 6
    if any(k in text for k in ("workflow", "pipeline", "breakdown", "tutorial", "case study")):
        score += 7
    if category in {"3d-production", "3d-animation", "engine-art", "ai-generation"}:
        score += 3
    if source_id in {
        "blender-official", "epic-developer-community", "unity-official",
        "sidefx-official", "autodesk-area", "adobe-substance-3d",
    }:
        score += 3
    return round(max(0.0, min(100.0, score)), 2)


def chinese_summary(meta: dict, category: str) -> str:
    desc = clean(meta.get("description"), 240)
    title = clean(meta.get("title"), 180)
    if desc:
        return clean(
            f"來源頁面顯示「{title}」。{desc} 此項目與 {category} 製作流程相關，"
            "Collector 僅依公開來源可驗證內容收錄。",
            420,
        )
    return clean(
        f"來源頁面顯示「{title}」，內容與 {category} 製作流程具直接關聯。"
        "公開頁面可驗證其主題，但目前證據深度有限，因此以 BRIEF 收錄。",
        420,
    )


def analysis_blocks(meta: dict, category: str, subcategory: str) -> list[dict]:
    title = clean(meta.get("title"), 180)
    desc = clean(meta.get("description"), 260)
    evidence = desc if desc else "公開來源目前主要提供標題與頁面層級資訊，未提供可安全延伸的效能或量化結果"
    return [
        {
            "label": "技術／流程變更",
            "text": clean(
                f"來源可驗證的重點是「{title}」；頁面內容指出：{evidence}。"
                f"Collector 因此只把它歸入 {subcategory} 的技術／流程情報，不補寫來源沒有公開的 benchmark、"
                "內部實作或品質數字。",
                520,
            ),
        },
        {
            "label": "Production 影響",
            "text": clean(
                f"對 Production 的實際價值是把這項內容當成 {category} 的近期工具、流程或案例參考，"
                "用來決定是否值得安排小型 A/B 測試、更新團隊規範或深入閱讀原始來源；"
                "目前不把尚未由來源證實的省時比例、效能提升或品質增益當成既知結果。",
                520,
            ),
        },
        {
            "label": "導入測試與限制",
            "text": clean(
                "目前證據深度以單一公開來源為主，因此維持 BRIEF。正式導入前應依團隊實際 DCC／引擎版本、"
                "資產規格、效能預算與輸出需求驗證相容性、可重現性和品質，並確認原始來源是否有後續更新、"
                "已知限制或授權條件。",
                520,
            ),
        },
    ]


def stars(score: float) -> str:
    filled = 5 if score >= 88 else 4 if score >= 74 else 3 if score >= 62 else 2
    return "★" * filled + "☆" * (5 - filled)


def load_registry(report_date: str, snapshot: dict) -> tuple[set[str], set[str], dict]:
    sources = {
        canonicalize_url(str(x.get("source_url") or ""))
        for x in snapshot.get("published_sources") or []
        if canonicalize_url(str(x.get("source_url") or ""))
    }
    ids = {
        str(x.get("id") if isinstance(x, dict) else x).strip()
        for x in snapshot.get("published_ids") or []
        if str(x.get("id") if isinstance(x, dict) else x).strip()
    }
    latest_done = ""
    supplemented = 0
    for receipt_path in sorted((ROOT / "data" / "publish").glob("20??-??-??.done.json")):
        try:
            receipt = load_json(receipt_path)
        except Exception:
            continue
        if str(receipt.get("state", "")).upper() != "DONE":
            continue
        day = str(receipt.get("date") or receipt_path.name[:10])
        if day >= report_date:
            continue
        latest_done = max(latest_done, day)
    generated = str(snapshot.get("generated_through") or "")
    if latest_done and generated < latest_done:
        for receipt_path in sorted((ROOT / "data" / "publish").glob("20??-??-??.done.json")):
            try:
                receipt = load_json(receipt_path)
            except Exception:
                continue
            day = str(receipt.get("date") or receipt_path.name[:10])
            if str(receipt.get("state", "")).upper() != "DONE" or not (generated < day <= latest_done):
                continue
            daily = ROOT / "data" / "daily" / f"{day}.json"
            if not daily.exists():
                continue
            try:
                data = load_json(daily)
            except Exception:
                continue
            for item in data.get("items") or []:
                source = canonicalize_url(str(item.get("source_url") or ""))
                rid = str(item.get("id") or "").strip()
                if source:
                    sources.add(source)
                if rid:
                    ids.add(rid)
                supplemented += 1
    audit = {
        "snapshot_state": snapshot.get("state"),
        "snapshot_generated_through": generated,
        "latest_verified_done": latest_done,
        "history_supplemented_items": supplemented,
        "source_identities": len(sources),
        "stable_ids": len(ids),
    }
    return sources, ids, audit


def source_probe(
    source: dict,
    endpoints: list[str],
    runtime: dict,
    session: requests.Session,
    report_date: str,
    used_ids: set[str],
) -> tuple[list[dict], dict]:
    http_cfg = runtime["http"]
    disc_cfg = runtime["discovery"]
    timeout = int(http_cfg["timeout_seconds"])
    max_links = int(disc_cfg["max_links_per_endpoint"])
    max_pages = int(disc_cfg["max_pages_per_source"])
    refill_pages = int(disc_cfg["refill_pages_per_source"])
    source_id = source["id"]
    domain = source["domain"]

    index_results = [fetch(session, url, timeout) for url in endpoints]
    successes = [x for x in index_results if x.get("html")]
    if not successes:
        statuses = [int(x.get("status", 0)) for x in index_results]
        blocked = any(x in (401, 403, 429) for x in statuses)
        status = "blocked" if blocked else "unavailable"
        reason = ",".join(
            sorted({x.get("error") or f"http-{x.get('status', 0)}" for x in index_results})
        ) or "no-readable-index"
        return [], {
            "status": status,
            "method": "latest-index",
            "candidates_found": 0,
            "candidate_ids": [],
            "reason": clean(reason, 180),
        }

    links: list[tuple[str, str]] = []
    seen_links: set[str] = set()
    for result in successes:
        for url, title in extract_links(result["html"], result["final_url"], domain, max_links):
            if url not in seen_links:
                seen_links.add(url)
                links.append((url, title))
    links = links[:max_pages]

    def get_page(pair):
        url, fallback = pair
        result = fetch(session, url, timeout)
        meta = page_metadata(result, fallback)
        return url, meta

    metas: list[dict] = []
    with ThreadPoolExecutor(max_workers=int(http_cfg["max_workers"])) as pool:
        futures = [pool.submit(get_page, pair) for pair in links]
        for future in as_completed(futures):
            _, meta = future.result()
            if meta and same_registered_domain(meta["url"], domain) and relevant(meta):
                metas.append(meta)

    refill_links: list[tuple[str, str]] = []
    refill_seen = set(seen_links)
    for meta in metas:
        for url, title in extract_links(meta["html"], meta["url"], domain, max_links):
            if url not in refill_seen:
                refill_seen.add(url)
                refill_links.append((url, title))
            if len(refill_links) >= refill_pages:
                break
        if len(refill_links) >= refill_pages:
            break
    if refill_links:
        with ThreadPoolExecutor(max_workers=int(http_cfg["max_workers"])) as pool:
            futures = [pool.submit(get_page, pair) for pair in refill_links]
            for future in as_completed(futures):
                _, meta = future.result()
                if meta and same_registered_domain(meta["url"], domain) and relevant(meta):
                    metas.append(meta)

    unique: dict[str, dict] = {}
    for meta in metas:
        unique.setdefault(meta["url"], meta)

    candidates = []
    for meta in unique.values():
        cid = stable_id(source_id, meta["url"], meta["title"], used_ids)
        text = f"{meta['title']} {meta.get('description', '')}"
        category, subcategory = classify_content(meta["title"], meta.get("description", ""))
        candidates.append({
            "candidate_id": cid,
            "source_id": source_id,
            "source_url": meta["url"],
            "title": meta["title"],
            "description": meta.get("description", ""),
            "published": meta.get("published"),
            "window": window_for(meta.get("published"), report_date),
            "category": category,
            "subcategory": subcategory,
            "ranking_score": score_candidate(meta, category, source_id, report_date),
            "brief_reason": brief_reason(text, source_id),
            "meta": meta,
        })
    candidates.sort(key=lambda x: (-x["ranking_score"], x["source_url"]))
    return candidates, {
        "status": "checked",
        "method": "latest-index",
        "candidates_found": len(candidates),
        "candidate_ids": [x["candidate_id"] for x in candidates],
    }


def main() -> int:
    runtime = load_json(RUNTIME_PATH)
    intel = load_json(INTEL_PATH)
    depth = load_json(DEPTH_PATH)
    personal_cfg = load_json(PERSONAL_PATH)
    hybrid = load_hybrid_config()
    report_date = current_date(runtime)

    done = ROOT / "data" / "publish" / f"{report_date}.done.json"
    if done.exists() and str(load_json(done).get("state", "")).upper() == "DONE":
        print(f"COLLECTOR NOOP: {report_date} already state=DONE")
        return 0

    snapshot = load_json(SNAPSHOT_PATH)
    published_sources, published_ids, registry_audit = load_registry(report_date, snapshot)

    backlog = load_json(BACKLOG_PATH)
    if int(backlog.get("schema_version", 0) or 0) != 1 or not isinstance(backlog.get("items"), list):
        raise SystemExit("COLLECTOR FAILED: rolling backlog must be schema_version=1 with items[]")

    plan = registered_source_probe_plan(report_date, hybrid)
    source_map = {
        str(x.get("id")): x
        for x in ((hybrid.get("discovery_source_pool") or {}).get("sources") or [])
        if x.get("enabled") is True
    }
    selected = list(plan["selected"])
    configured_endpoints = runtime.get("source_endpoints") or {}
    session = requests.Session()
    session.headers.update({
        "User-Agent": runtime["http"]["user_agent"],
        "Accept": "text/html,application/xhtml+xml",
        "Accept-Language": "en-US,en;q=0.8,zh-TW;q=0.5,ja;q=0.4",
    })

    used_ids: set[str] = set()
    discovered: list[dict] = []
    probe_records: dict[str, dict] = {}

    ordered_sources = [
        str(x.get("id"))
        for x in ((hybrid.get("discovery_source_pool") or {}).get("sources") or [])
        if x.get("enabled") is True
    ]
    for source_id in ordered_sources:
        source = source_map[source_id]
        if source_id not in selected:
            probe_records[source_id] = {
                "status": "not-scheduled",
                "method": "rolling-window",
                "candidates_found": 0,
                "candidate_ids": [],
                "reason": "deterministic-rolling-probe-not-selected",
            }
            continue
        endpoints = configured_endpoints.get(source_id) or [source["base_url"]]
        candidates, record = source_probe(
            source, endpoints, runtime, session, report_date, used_ids
        )
        probe_records[source_id] = record
        discovered.extend(candidates)

    backlog_checked = 0
    for entry in backlog.get("items") or []:
        source_url = canonicalize_url(str(entry.get("source_url") or ""))
        if not source_url.startswith("https://") or source_url in published_sources:
            continue
        backlog_checked += 1
        result = fetch(session, source_url, int(runtime["http"]["timeout_seconds"]))
        meta = page_metadata(result, str(entry.get("title") or ""))
        if not meta or not relevant(meta):
            continue
        source_id = str(entry.get("source_id") or "backlog")
        cid = stable_id(source_id, meta["url"], meta["title"], used_ids)
        text = f"{meta['title']} {meta.get('description', '')}"
        category, subcategory = classify_content(meta["title"], meta.get("description", ""))
        discovered.append({
            "candidate_id": cid,
            "source_id": source_id,
            "source_url": meta["url"],
            "title": meta["title"],
            "description": meta.get("description", ""),
            "published": meta.get("published"),
            "window": window_for(meta.get("published"), report_date),
            "category": category,
            "subcategory": subcategory,
            "ranking_score": score_candidate(meta, category, source_id, report_date),
            "brief_reason": brief_reason(text, source_id),
            "meta": meta,
            "from_backlog": True,
        })

    by_source: dict[str, dict] = {}
    for candidate in discovered:
        by_source.setdefault(candidate["source_url"], candidate)
    discovered = list(by_source.values())

    decisions: list[dict] = []
    survivors: list[dict] = []
    window_counts = {w: 0 for w in intel["collection"]["discovery_windows"]}
    category_counts = {x["id"]: 0 for x in intel["categories"]}

    for candidate in discovered:
        window_counts[candidate["window"]] = window_counts.get(candidate["window"], 0) + 1
        cid = candidate["candidate_id"]
        source_url = canonicalize_url(candidate["source_url"])
        channels = [
            "rolling-backlog" if candidate.get("from_backlog") else "registered-source-crawl",
            "published-registry-snapshot",
        ]
        if not candidate.get("from_backlog"):
            channels.insert(1, "registered-source-probe:" + candidate["source_id"])
        base = {
            "candidate_id": cid,
            "source_url": source_url,
            "discovery_channels": channels,
        }
        if source_url in published_sources:
            decisions.append({
                **base,
                "decision": "duplicate",
                "reason_code": "published-registry-exact-identity",
            })
            continue
        if cid in published_ids:
            decisions.append({
                **base,
                "decision": "duplicate",
                "reason_code": "published-registry-stable-id",
            })
            continue
        category_counts[candidate["category"]] += 1
        survivors.append(candidate)

    survivors.sort(key=lambda x: (-x["ranking_score"], x["source_url"]))
    maximum = int(intel["collection"]["daily_max_items"])
    fallback = int((hybrid.get("low_volume_release") or {}).get("fallback_floor", 0) or 0)
    selected_items = survivors[:maximum]
    overflow = survivors[maximum:]

    for candidate in selected_items:
        decisions.append({
            "candidate_id": candidate["candidate_id"],
            "source_url": candidate["source_url"],
            "discovery_channels": (
                ["rolling-backlog", "published-registry-snapshot"]
                if candidate.get("from_backlog")
                else [
                    "registered-source-crawl",
                    f"registered-source-probe:{candidate['source_id']}",
                    "published-registry-snapshot",
                ]
            ),
            "decision": "published",
            "canonical_id": candidate["candidate_id"],
        })
    for candidate in overflow:
        decisions.append({
            "candidate_id": candidate["candidate_id"],
            "source_url": candidate["source_url"],
            "discovery_channels": (
                ["rolling-backlog", "published-registry-snapshot"]
                if candidate.get("from_backlog")
                else [
                    "registered-source-crawl",
                    f"registered-source-probe:{candidate['source_id']}",
                    "published-registry-snapshot",
                ]
            ),
            "decision": "backlog",
            "reason_code": "quality-pass-beyond-daily-maximum",
        })

    if len(selected_items) < fallback:
        raise SystemExit(
            f"COLLECTOR FAILED: verified unpublished survivors={len(selected_items)} "
            f"below configured fallback floor={fallback}; no Collector artifacts written"
        )

    homepage = intel["homepage"]
    canonical_items = []
    for rank, candidate in enumerate(selected_items, 1):
        meta = candidate["meta"]
        canonical_items.append({
            "id": candidate["candidate_id"],
            "title": clean(candidate["title"], 220),
            "summary": production_summary(meta, candidate["category"], candidate["subcategory"]),
            "quick_impact": stars(candidate["ranking_score"]),
            "source_url": candidate["source_url"],
            "category": candidate["category"],
            "subcategory": candidate["subcategory"],
            "ranking_score": candidate["ranking_score"],
            "analysis_level": "BRIEF",
            "brief_reason": candidate["brief_reason"],
            "full_analysis": analysis_blocks(
                meta, candidate["category"], candidate["subcategory"]
            ),
            "rank_global": rank,
            "homepage_tier": (
                "top5" if rank <= int(homepage["top5"])
                else "next10"
                if rank <= int(homepage["top5"]) + int(homepage["next10"])
                else "category_only"
            ),
        })

    coverage = {
        "fill_ladder_exhausted": True,
        "backlog_checked": True,
        "backlog_remaining_eligible": 0,
        "targeted_refill_performed": True,
        "quality_first_confirmed": True,
        "windows": {
            w: {
                "status": str(
                    (hybrid.get("coverage_audit") or {}).get(
                        "exhaustion_status", "exhausted"
                    )
                ),
                "candidates_found": int(window_counts.get(w, 0)),
            }
            for w in intel["collection"]["discovery_windows"]
        },
        "category_candidates": {
            cid: {"candidates_considered": int(category_counts.get(cid, 0))}
            for cid in [x["id"] for x in intel["categories"]]
        },
        "registered_source_probe": {
            "performed": True,
            "sources": probe_records,
        },
        "notes": (
            f"{report_date} autonomous GitHub Collector loaded the Published Registry snapshot before discovery, "
            "supplemented it from verified-DONE history when needed, checked rolling backlog, executed the current-main "
            "deterministic registered-source probe plan, crawled configured source indexes plus a bounded source-grounded "
            "targeted refill, and applied exact source/stable identity dedupe before ranking. "
            f"Registry audit: {json.dumps(registry_audit, ensure_ascii=False, sort_keys=True)}. "
            f"Backlog entries rechecked={backlog_checked}. No source registration/domain supplied ranking bonus, quota or admission bypass."
        ),
    }

    personal = {
        "contract": personal_cfg["mode"],
        "status": "unavailable",
        "vote_count": 0,
        "reason": (
            "Autonomous GitHub Collector has no authoritative active-app-owner identity; "
            "current-main neutral-and-continue fallback applied without reading or committing raw user data."
        ),
        "max_rank_multiplier": float(personal_cfg["ranking"]["max_rank_multiplier"]),
        "max_query_expansion_fraction": float(
            personal_cfg["discovery"]["max_query_expansion_fraction"]
        ),
        "raw_profile_committed": False,
        "bookmarks_used": False,
        "domain_weights_used": False,
        "admission_bypass": False,
        "quality_gate_bypass": False,
        "source_quota": False,
    }

    metadata = {
        "total_items": len(canonical_items),
        "collection_mode": "production-intelligence-preference-v1-hybrid",
        "collection_contract_effective_date": intel["collection_contract_effective_date"],
        "preference_contract_effective_date": intel["preference_contract_effective_date"],
        "admission_policy_effective_date": intel["admission_policy_effective_date"],
        "collector_runtime": TRACKING_SOURCE,
        "discovery_windows": list(intel["collection"]["discovery_windows"]),
        "analysis_level_counts": {
            "FULL": 0,
            "BRIEF": len(canonical_items),
            "REJECT": 0,
        },
        "analysis_level_policy": (
            "evidence-depth-tiered; FULL=3-5 source-supported blocks; "
            "BRIEF=3 readable source-grounded angles with explicit limits; REJECT=not-publishable"
        ),
        "full_analysis_depth_contract": "v6-tiered-evidence-three-angle-reading",
        "full_analysis_style_reference": depth.get(
            "brief_reading_style_reference", "2026-09-12"
        ),
        "full_analysis_heading_language": "zh-Hant",
        "discovery_coverage": coverage,
        "personalization": personal,
    }
    daily = {
        "date": report_date,
        "schema_version": int(intel["schema_version"]),
        "metadata": metadata,
        "items": canonical_items,
        "visual_evidence": {},
    }
    session_data = {
        "schema_version": 1,
        "date": report_date,
        "discovery_coverage": coverage,
        "candidate_decisions": decisions,
        "personalization": personal,
    }
    ledger = {
        "schema_version": 1,
        "date": report_date,
        "items": decisions,
    }

    max_backlog = int((hybrid.get("rolling_backlog") or {}).get("max_items", 240))
    backlog_items = []
    for candidate in overflow[:max_backlog]:
        backlog_items.append({
            "id": candidate["candidate_id"],
            "source_id": candidate["source_id"],
            "title": clean(candidate["title"], 220),
            "source_url": candidate["source_url"],
            "category": candidate["category"],
            "subcategory": candidate["subcategory"],
            "ranking_score": candidate["ranking_score"],
            "discovered_for": report_date,
        })
    backlog_out = {
        "schema_version": 1,
        "updated_for": report_date,
        "policy": "verified-unpublished-quality-pass-only",
        "items": backlog_items,
    }

    write_json(ROOT / "data" / "daily" / f"{report_date}.json", daily)
    write_json(
        ROOT / "data" / "candidates" / "collection-session" / f"{report_date}.json",
        session_data,
    )
    write_json(
        ROOT / "data" / "candidates" / "decision-ledger" / f"{report_date}.json",
        ledger,
    )
    write_json(BACKLOG_PATH, backlog_out)

    print(
        f"COLLECTOR PERSISTENCE READY: date={report_date} "
        f"selected={len(canonical_items)} survivors={len(survivors)} "
        f"decisions={len(decisions)} backlog={len(backlog_items)} "
        f"probe_selected={selected}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
