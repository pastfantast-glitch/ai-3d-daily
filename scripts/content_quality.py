#!/usr/bin/env python3
"""Shared content-quality policy for autonomous Production Intelligence collection.
Policy revision: 2026-09-27 source-grounded editorial v1.\nEditorial contract: source-grounded factual fallback; 2026-09-25 style baseline.

This module is deliberately deterministic and source-grounded. It rejects index,
product/marketing landing, governance/event, and non-production pages before ranking;
normalizes SEO titles; classifies by the subject of the item rather than incidental
keywords; and generates concise Traditional-Chinese production summaries without
inventing source claims.
"""
from __future__ import annotations

from html import unescape
from pathlib import Path
import json
from urllib.parse import urlparse
import re

EDITORIAL_CONFIG_PATH = Path(__file__).resolve().parents[1] / "config" / "editorial-quality.json"


def editorial_policy() -> dict:
    try:
        return json.loads(EDITORIAL_CONFIG_PATH.read_text("utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


WS_RE = re.compile(r"\s+")
KANA_RE = re.compile(r"[\u3040-\u30ff]")
HAN_RE = re.compile(r"[\u3400-\u9fff]")
LATIN_RE = re.compile(r"[A-Za-z]")
SITE_SUFFIX_RE = re.compile(
    r"\s*(?:\||—|–)\s*(?:CG Channel|SideFX|Unity|Blender|80 Level|80\.lv)\s*$",
    re.I,
)
GENERIC_TITLE_FRAGMENTS = (
    "articles and tutorials for 2d/3d artists",
    "latest news and articles",
    "all articles",
    "all tutorials",
    "news and articles",
)
GENERIC_NAV_TITLE_FRAGMENTS = (
    "tutorials and breakdowns",
    "industry solutions from",
    "online art schools",
)
GENERIC_NAV_TITLE_EXACT = {
    "blender studio",
    "demo files",
    "support",
}
GENERIC_NAV_LEAVES = {
    "games", "industry", "partners", "latest", "training",
    "demo-files", "support", "tools",
}
LANDING_PATH_FRAGMENTS = (
    "/products/", "/features/", "/pricing/", "/solutions/", "/services/",
)
BUSINESS_NOISE = (
    "player retention", "user acquisition", "growth opportunity", "churn",
    "monetization", "marketing campaign", "revenue growth", "mobile players",
)
RECRUITMENT_NOISE = (
    "recruitment site", "portfolio site", "job board", "jobs site",
    "hiring platform", "recruitment platform",
)
EVENT_NOISE = (
    "film festival", "festival", "meet-up", "meetup", "conference booth",
)
GOVERNANCE_NOISE = (
    "annual report", "development fund", "support for blender projects",
    "fundraising", "governance", "policy announcement", "policies",
)
TECHNICAL_ANCHORS = (
    "3d", "blender", "maya", "houdini", "substance", "zbrush", "3ds max",
    "cinema 4d", "keyshot", "unreal engine", "ue5", "ue6", "unity",
    "shader", "render", "material", "texture", "svbrdf", "model", "sculpt",
    "character", "creature", "groom", "animation", "rig", "mocap", "retarget",
    "vfx", "procedural", "geometry", "photogrammetry", "retopo", "uv",
    "metahuman", "nanite", "lumen", "pcg", "kinefx", "gaussian", "nerf",
    "image-to-3d", "text-to-3d", "meshy", "tripo", "hunyuan", "comfyui",
)
PRODUCTION_SIGNALS = (
    "workflow", "pipeline", "breakdown", "tutorial", "release", "update",
    "version", "feature", "tool", "plugin", "addon", "add-on", "production",
    "modeling", "texturing", "rigging", "animation", "rendering", "shader",
    "material", "texture", "sculpt", "retopo", "baking", "mocap", "retarget",
    "case study", "behind the scenes", "overview", "guide", "research",
)
METHOD_SIGNALS = (
    "workflow", "pipeline", "breakdown", "tutorial", "release", "update",
    "feature", "tool", "plugin", "addon", "add-on", "production", "modeling",
    "texturing", "rigging", "rendering", "shader", "material", "sculpt",
    "retopo", "baking", "mocap", "retarget", "case study",
)
CATEGORY_LABELS = {
    "ai-generation": "AI 生成",
    "3d-production": "3D 資產製作",
    "3d-animation": "3D 動作／Rig",
    "engine-art": "遊戲引擎美術",
    "emerging-case": "新技術／Production Case",
    "blender-dcc": "Blender／DCC",
}
FOCUS_TERMS = (
    ("metahuman", "MetaHuman"),
    ("mesh terrain", "Mesh Terrain"),
    ("control rig", "Control Rig"),
    ("rigging", "Rigging"),
    ("retarget", "Retarget"),
    ("motion capture", "Mocap"),
    ("mocap", "Mocap"),
    ("animation", "動畫"),
    ("skin texture", "皮膚材質"),
    ("texture", "貼圖／材質"),
    ("material", "材質"),
    ("displacement", "Displacement"),
    ("lighting", "燈光"),
    ("shader", "Shader"),
    ("rendering", "Rendering"),
    ("ray tracing", "Ray Tracing"),
    ("path tracing", "Path Tracing"),
    ("procedural", "程序化"),
    ("geometry nodes", "Geometry Nodes"),
    ("modeling", "建模"),
    ("sculpt", "雕刻"),
    ("retopo", "拓撲"),
    ("baking", "烘焙"),
    ("uv", "UV"),
    ("vfx", "VFX"),
    ("unreal engine", "Unreal Engine"),
    ("unity", "Unity"),
    ("blender", "Blender"),
    ("houdini", "Houdini"),
    ("maya", "Maya"),
    ("substance", "Substance"),
    ("octane", "OctaneRender"),
    ("mari", "Mari"),
)

SUBCATEGORY_LABELS = {
    "ai-3d": "AI 3D 生成",
    "ai-2d": "AI 2D／影像工作流",
    "ai-motion": "AI 動作生成",
    "character-production": "角色製作",
    "prop-production": "物件／硬表面製作",
    "environment-production": "場景製作",
    "production-workflow": "跨資產製作流程",
    "rigging": "Rigging",
    "animation": "Animation",
    "mocap": "Mocap",
    "retarget": "Retarget",
    "cleanup": "動畫 Cleanup",
    "facial": "Facial",
    "unreal": "Unreal Engine",
    "unity": "Unity",
    "shader": "Shader／材質",
    "rendering": "Rendering",
    "tools": "引擎工具",
    "optimization": "效能最佳化",
    "research": "研究／原型",
    "case-study": "Production Case",
    "procedural": "程序化流程",
    "world-model": "World Model",
    "4d": "4D／動態 3D",
    "blender": "Blender",
    "blender-tip": "Blender Tip",
    "addon": "DCC Add-on",
    "maya": "Maya",
    "houdini": "Houdini",
    "substance": "Substance",
    "other-dcc": "其他 DCC",
}


def clean(value: object, limit: int | None = None) -> str:
    text = WS_RE.sub(" ", unescape(str(value or ""))).strip()
    if limit and len(text) > limit:
        text = text[:limit].rstrip(" ,.;:：，。；、-—–")
    return text


def reader_language_ok(value: object, max_latin_per_han: float = 3.0) -> bool:
    text = clean(value)
    if not text or KANA_RE.search(text):
        return False
    han = len(HAN_RE.findall(text))
    latin = len(LATIN_RE.findall(text))
    if han < 2:
        return False
    return latin <= max(8, int(han * max_latin_per_han))


def source_title_cue(meta: dict) -> str:
    """Keep a short source-grounded title cue so different sources cannot collapse to identical fallback copy."""
    raw = clean(KANA_RE.sub("", normalize_title(meta.get("title"))))
    if not raw:
        return ""
    if len(raw) <= 18:
        return raw
    return clean(f"{raw[:9].rstrip()}…{raw[-9:].lstrip()}", 24)


def source_subject_traits(meta: dict) -> list[str]:
    """Return concise zh-Hant semantic traits grounded in the source title/description."""
    text = f"{normalize_title(meta.get('title'))} {clean(meta.get('description'), 600)}".casefold()
    rules = (
        (("everyday", "daily action", "daily motion"), "日常動作"),
        (("combat", "fight", "attack animation", "battle"), "戰鬥動作"),
        (("walk", "run cycle", "locomotion"), "移動循環"),
        (("facial", "lip sync", "expression"), "臉部表演"),
        (("hand animation", "finger", "hand pose"), "手部動作"),
        (("dance", "dancing"), "舞蹈動作"),
        (("storyboard", "storyboarding", "pre-production"), "分鏡前期"),
        (("stylized", "toon", "cartoon"), "風格化"),
        (("realistic", "photoreal", "photorealistic"), "寫實"),
        (("procedural", "geometry nodes", "pcg"), "程序化"),
        (("free pack", "free asset", "download", "free mocap"), "可下載素材"),
        (("test", "demo", "showcase"), "測試展示"),
        (("tutorial", "guide", "course", "training"), "教學"),
        (("breakdown", "behind the scenes", "making-of", "case study"), "製作拆解"),
        (("release", "update", "version", "beta", "alpha", "preview"), "版本更新"),
    )
    out: list[str] = []
    for terms, label in rules:
        if has_any(text, terms) and label not in out:
            out.append(label)
        if len(out) >= 2:
            break
    return out


def reader_source_fact(meta: dict, title: str, focus_text: str) -> str:
    raw = source_fact(meta)
    if reader_language_ok(raw, 2.5):
        return raw
    lowered = f"{normalize_title(meta.get('title'))} {clean(meta.get('description'), 600)}".casefold()
    cue = source_title_cue(meta)
    cue_suffix = f"；來源題名線索「{cue}」" if cue else ""
    if has_any(lowered, ("tutorial", "guide", "course", "training", "workflow")):
        return f"來源介紹一套以 {focus_text} 為主的教學／製作流程，讀者標題為「{title}」{cue_suffix}"
    if has_any(lowered, ("release", "update", "version", "beta", "alpha", "roadmap")):
        return f"來源整理「{title}」的版本／開發更新，重點涉及 {focus_text}{cue_suffix}"
    if has_any(lowered, ("plugin", "addon", "add-on", "tool", "software")):
        return f"來源介紹「{title}」這項工具，公開重點涉及 {focus_text}{cue_suffix}"
    return f"來源主題為「{title}」，目前可確認的製作面向包含 {focus_text}{cue_suffix}"


def has_term(text: str, term: str) -> bool:
    """Match standalone ASCII tokens safely; keep phrase matching for multi-word signals."""
    term = term.casefold()
    if re.fullmatch(r"[a-z0-9][a-z0-9.+#-]*", term):
        return re.search(rf"(?<![a-z0-9]){re.escape(term)}(?![a-z0-9])", text) is not None
    return term in text


def has_any(text: str, terms) -> bool:
    return any(has_term(text, term) for term in terms)


def normalize_title(title: object) -> str:
    text = clean(title, 220)
    previous = None
    while previous != text:
        previous = text
        text = SITE_SUFFIX_RE.sub("", text).strip()
    return clean(text, 180)


def landing_reason(meta: dict) -> str | None:
    title = normalize_title(meta.get("title")).casefold()
    url = str(meta.get("url") or "")
    path = urlparse(url).path.casefold()
    article_type = bool(meta.get("article_type"))
    published = bool(meta.get("published"))

    segments = [segment for segment in path.split("/") if segment]
    leaf = segments[-1] if segments else ""

    if any(fragment in title for fragment in GENERIC_TITLE_FRAGMENTS):
        return "generic-index-title"

    # Navigation/index identity is stronger evidence than unreliable Article/Published metadata.
    # Some source sites mark category/partner/resource hubs as Article, so reject these page
    # shapes before considering metadata.
    if leaf in GENERIC_NAV_LEAVES and len(segments) <= 3:
        return "generic-navigation-or-resource-index"
    if title in GENERIC_NAV_TITLE_EXACT:
        return "generic-navigation-or-resource-index"
    if any(fragment in title for fragment in GENERIC_NAV_TITLE_FRAGMENTS):
        return "generic-navigation-or-resource-index"
    if title.endswith(" manual") and ("manual" in segments or leaf == "latest"):
        return "documentation-root-index"

    if not article_type and not published:
        if any(fragment in path for fragment in LANDING_PATH_FRAGMENTS):
            return "non-article-product-or-feature-landing"
        if path.rstrip("/").endswith("/roadmap") or title == "roadmap":
            return "roadmap-index-page"
    return None


def admission(meta: dict) -> tuple[bool, str]:
    reason = landing_reason(meta)
    if reason:
        return False, reason

    title = normalize_title(meta.get("title"))
    desc = clean(meta.get("description"), 800)
    text = f"{title} {desc}".casefold()
    technical = sum(1 for term in TECHNICAL_ANCHORS if has_term(text, term))
    production = sum(1 for term in PRODUCTION_SIGNALS if has_term(text, term))
    title_text = title.casefold()

    if has_any(title_text, GOVERNANCE_NOISE):
        return False, "governance-or-funding-page-no-production-method"
    if has_any(title_text, RECRUITMENT_NOISE):
        return False, "recruitment-or-portfolio-news-no-production-method"
    if has_any(text, BUSINESS_NOISE) and technical == 0:
        return False, "business-or-player-growth-no-art-production-takeaway"
    if has_any(text, EVENT_NOISE) and not has_any(text, METHOD_SIGNALS):
        return False, "event-or-community-page-no-production-method"
    if has_any(text, GOVERNANCE_NOISE) and not has_any(text, METHOD_SIGNALS):
        return False, "governance-or-funding-page-no-production-method"
    if technical == 0:
        return False, "no-3d-game-art-technical-anchor"
    if production == 0 and technical < 2:
        return False, "insufficient-production-takeaway"
    if "2d vector animation" in text and not any(
        term in text for term in ("3d", "unreal", "unity", "blender", "maya", "houdini", "game art")
    ):
        return False, "2d-only-outside-current-production-scope"
    return True, "admitted-source-grounded-production-content"


def classify_content(title: object, description: object = "") -> tuple[str, str]:
    t = normalize_title(title).casefold()
    d = clean(description, 900).casefold()
    all_text = f"{t} {d}"

    if any(k in all_text for k in ("meshy", "tripo", "hunyuan", "image-to-3d", "text-to-3d", "ai 3d", "generative 3d")):
        return "ai-generation", "ai-3d"
    if any(k in all_text for k in ("motion generation", "ai motion", "motion ai", "video-to-motion")):
        return "ai-generation", "ai-motion"
    if any(k in all_text for k in ("concept art ai", "comfyui", "image generation", "upscal")):
        return "ai-generation", "ai-2d"

    # Product/version/roundup subject in the title beats incidental feature words in the description.
    if "cg software" in t or "software you may have missed" in t:
        return "blender-dcc", "other-dcc"
    if "blender" in t:
        return "blender-dcc", "blender"
    if "houdini" in t:
        return "blender-dcc", "houdini"
    if "maya" in t:
        return "blender-dcc", "maya"
    if "substance" in t:
        return "blender-dcc", "substance"
    if any(k in t for k in ("3ds max", "cinema 4d", "keyshot", "mari", "nuke", "octane", "redshift", "arnold", "v-ray")):
        return "blender-dcc", "other-dcc"
    if "unreal engine" in t or re.search(r"\bue[56](?:\.\d+)?\b", t):
        return "engine-art", "unreal"
    if re.search(r"\bunity\b", t):
        return "engine-art", "unity"

    if any(k in t for k in ("mocap", "motion capture")):
        return "3d-animation", "mocap"
    if "retarget" in t:
        return "3d-animation", "retarget"
    if any(k in t for k in ("facial animation", "face animation", "lip sync")):
        return "3d-animation", "facial"
    if any(k in t for k in ("rigging", " rig ", "skeleton", "skinning", "skin weight")):
        return "3d-animation", "rigging"
    if any(k in t for k in ("animation", "animating", "animator", "keyframe", "locomotion")):
        return "3d-animation", "animation"

    if any(k in all_text for k in ("skin texture", "character", "portrait", "hair", "groom", "cloth", "anatomy", "creature")):
        return "3d-production", "character-production"
    if any(k in all_text for k in ("weapon", "vehicle", "hard surface", "hard-surface", " prop ")):
        return "3d-production", "prop-production"
    if any(k in all_text for k in ("environment", "terrain", "landscape", "building", "architecture", "foliage")):
        return "3d-production", "environment-production"

    if has_any(all_text, ("unreal", "ue5", "ue6")):
        return "engine-art", "unreal"
    if has_term(all_text, "unity"):
        return "engine-art", "unity"
    if any(k in all_text for k in ("shader", "material graph", "toon", "npr")):
        return "engine-art", "shader"
    if any(k in all_text for k in ("ray tracing", "path tracing", "renderer", "rendering", "lumen", "nanite")):
        return "engine-art", "rendering"
    if any(k in all_text for k in ("optimization", "performance", "lod", "hlod", "draw call")):
        return "engine-art", "optimization"

    if any(k in all_text for k in ("mocap", "motion capture")):
        return "3d-animation", "mocap"
    if "retarget" in all_text:
        return "3d-animation", "retarget"
    if any(k in all_text for k in ("rigging", "control rig", "skeleton", "skinning")):
        return "3d-animation", "rigging"
    if "animation" in all_text:
        return "3d-animation", "animation"

    if "blender" in all_text:
        return "blender-dcc", "blender"
    if "houdini" in all_text:
        return "blender-dcc", "houdini"
    if "maya" in all_text:
        return "blender-dcc", "maya"
    if "substance" in all_text:
        return "blender-dcc", "substance"
    if any(k in all_text for k in ("3ds max", "cinema 4d", "keyshot", "mari", "nuke", "octane", "redshift", "arnold", "v-ray")):
        return "blender-dcc", "other-dcc"

    if any(k in all_text for k in ("world model", "world-model")):
        return "emerging-case", "world-model"
    if any(k in all_text for k in ("gaussian splat", "nerf", "research", "paper", "siggraph")):
        return "emerging-case", "research"
    if "procedural" in all_text:
        return "emerging-case", "procedural"
    if any(k in all_text for k in ("case study", "postmortem", "breakdown", "behind the scenes", "vfx breakdown")):
        return "emerging-case", "case-study"

    if any(k in all_text for k in ("model", "texture", "material", "uv", "retopo", "baking", "scan", "photogrammetry")):
        return "3d-production", "production-workflow"
    return "emerging-case", "case-study"


def friendly_label(category: str, subcategory: str) -> str:
    return SUBCATEGORY_LABELS.get(subcategory) or CATEGORY_LABELS.get(category) or "Production"


def editorial_title(meta: dict, category: str, subcategory: str) -> str:
    raw = normalize_title(meta.get("title"))

    def framed(value: str) -> str:
        value = clean(value, 180)
        if reader_language_ok(value, 4.0):
            return value
        category_label = CATEGORY_LABELS.get(category) or "製作重點"
        if not HAN_RE.search(category_label):
            category_label = clean(f"{category_label} 製作", 40)
        subject = re.split(r"\s*[|｜—–-]\s*", value, maxsplit=1)[0]
        subject = clean(subject, 32)
        if subject:
            candidate = clean(f"{category_label}：{subject} 的製作重點", 180)
            if reader_language_ok(candidate, 4.0):
                return candidate
        focus = production_focus(meta)
        focus_text = "、".join(focus[:2]) if focus else "製作流程"
        return clean(f"{category_label}：{focus_text} 技術與製作重點", 180)

    if reader_language_ok(raw, 4.0):
        return raw

    label = friendly_label(category, subcategory)
    if not re.search(r"[\u3400-\u9fff]", label):
        label = CATEGORY_LABELS.get(category) or "製作情報"
    if not re.search(r"[\u3400-\u9fff]", label):
        label = "製作情報"

    patterns = (
        (r"^Blender\s+(.+?)\s+Release$", lambda m: f"Blender {m.group(1)}：版本更新"),
        (r"^Tutorial:\s*(.+)$", lambda m: f"{m.group(1)}：製作教學"),
        (r"^Breakdown:\s*(.+)$", lambda m: f"{m.group(1)}：製作拆解"),
        (r"^(.+?)\s+is out$", lambda m: f"{m.group(1)}：版本更新"),
        (r"^(.+?)\s+releases\s+(.+)$", lambda m: f"{m.group(2)}：{m.group(1)} 發布更新"),
        (r"^10 things CG artists need to know about\s+(.+)$", lambda m: f"{m.group(1)}：CG 藝術家需關注的 10 項重點"),
        (r"^(.+?)\s+is here:\s*discover its\s+(\d+)\s+key features.*$", lambda m: f"{m.group(1)}：{m.group(2)} 項重點功能"),
        (r"^New CG software you may have missed:\s*(.+)$", lambda m: f"本週 CG 工具更新：{m.group(1)}"),
        (r"^How\s+(.+?)\s+created\s+(.+)$", lambda m: f"{m.group(2)}：{m.group(1)} 製作拆解"),
        (r"^Get free\s+(.+)$", lambda m: f"免費工具：{m.group(1)}"),
    )
    for pattern, render in patterns:
        match = re.match(pattern, raw, flags=re.I)
        if match:
            return framed(render(match))
    return framed(raw)

def production_focus(meta: dict) -> list[str]:
    text = f"{normalize_title(meta.get('title'))} {clean(meta.get('description'), 900)}".casefold()
    out: list[str] = []
    for needle, label in FOCUS_TERMS:
        if has_term(text, needle) and label not in out:
            out.append(label)
        if len(out) >= 4:
            break
    return out


def source_fact(meta: dict) -> str:
    cfg = editorial_policy()
    fallback = cfg.get("factual_fallback") or {}
    limit = int(fallback.get("max_source_description_chars", 280) or 280)
    description = clean(meta.get("description"), limit)
    return description or normalize_title(meta.get("title"))


def production_summary(meta: dict, category: str, subcategory: str) -> str:
    title = editorial_title(meta, category, subcategory)
    raw = f"{normalize_title(meta.get('title'))} {clean(meta.get('description'), 600)}".casefold()
    label = friendly_label(category, subcategory)
    focus = production_focus(meta)
    focus_text = "、".join(focus) if focus else label
    fact = reader_source_fact(meta, title, focus_text)
    traits = source_subject_traits(meta)
    trait_text = "、".join(traits)

    if has_any(raw, ("release", "update", "version", "beta", "alpha", "preview")):
        lead = "版本重點"
    elif has_any(raw, ("breakdown", "tutorial", "how to", "guide", "case study", "behind", "making-of", "workflow")):
        lead = "流程重點"
    elif has_any(raw, ("plugin", "addon", "add-on", "tool", "software")):
        lead = "工具重點"
    else:
        lead = "技術重點"

    if clean(meta.get("description")):
        trait_clause = f" 可驗證的內容型態包含 {trait_text}；" if trait_text else ""
        return clean(
            f"{lead}：{fact}{trait_clause} Production 檢查點為 {focus_text}；"
            "先以來源已公開的功能、流程與限制為準，不補寫未公開的效能或工時數字。",
            420,
        )
    return clean(
        f"「{title}」目前公開頁面只提供標題層級資訊，可確認主題與 {focus_text} 有關。"
        "因此以較短的 BRIEF 呈現，保留來源事實，不延伸未公開的結果。",
        420,
    )


def editorial_analysis(meta: dict, category: str, subcategory: str) -> list[dict]:
    title = editorial_title(meta, category, subcategory)
    raw = f"{normalize_title(meta.get('title'))} {clean(meta.get('description'), 600)}".casefold()
    label = friendly_label(category, subcategory)
    focus = production_focus(meta)
    focus_text = "、".join(focus) if focus else label
    fact = reader_source_fact(meta, title, focus_text)
    source_anchor = title
    evidence_anchor = clean(fact, 180)

    technical = (
        f"「{title}」的公開資訊明確涉及 {focus_text}。來源描述為：{fact} "
        "技術判讀以這些已公開內容為界，不把標題之外的功能或結果自行補成既定事實。"
    )
    if has_any(raw, ("release", "update", "version", "beta", "alpha", "preview")):
        impact = (
            f"來源主題 {source_anchor} 的可驗證內容提到 {evidence_anchor}。對 {label}，"
            f"可直接檢查 {focus_text} 是否改變現有的資產交換、authoring 或輸出步驟；"
            "先用代表性工程做升版回歸，再決定是否更新團隊基線。"
        )
    elif has_any(raw, ("breakdown", "tutorial", "how to", "guide", "case study", "behind", "making-of", "workflow")):
        impact = (
            f"來源主題 {source_anchor} 的可驗證內容提到 {evidence_anchor}。對 {label}，"
            f"可把來源展示的 {focus_text} 拆成實際步驟，與既有流程逐段比較輸入、人工修正與最終輸出；"
            "這比只看完成圖更適合作為 Production review 依據。"
        )
    else:
        impact = (
            f"來源主題 {source_anchor} 的可驗證內容提到 {evidence_anchor}。對 {label}，"
            f"可把 {focus_text} 放進目前相同製作環節做小規模對照，確認它實際解決的是 authoring、交換、"
            "品質控制還是 runtime 問題，再決定導入範圍。"
        )

    limit = (
        f"「{title}」目前可驗證的來源內容為 {evidence_anchor}。"
        "來源沒有提供的 benchmark、工時節省或品質提升不做推定；正式導入前仍要用目標 DCC／引擎版本、"
        "代表性資產與實際輸出格式驗證相容性與可重現性。"
    )
    return [
        {"label": "技術／流程變更", "text": clean(technical, 560)},
        {"label": "Production 影響", "text": clean(impact, 560)},
        {"label": "導入測試與限制", "text": clean(limit, 560)},
    ]

