#!/usr/bin/env python3
"""Shared content-quality policy for autonomous Production Intelligence collection.
Policy revision: 2026-09-29 concise source-grounded reader copy.\nEditorial contract: verification stays in QA/metadata; reader copy follows the concise style while retaining the 2026-09-25 contract baseline.

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
PROMOTION_NOISE = (
    "discount", "promo code", "coupon", "exclusive offer", "limited-time offer",
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

PRODUCTION_DETAIL_TERMS = (
    (("marmoset toolbag", "toolbag"), "Marmoset Toolbag 式烘焙"),
    (("texture baking", "baking add-on", "bake textures"), "貼圖烘焙"),
    (("shape keys", "shape key"), "Shape Keys"),
    (("grease pencil",), "Grease Pencil"),
    (("character rig", "rigged character"), "角色 Rig"),
    (("ayon",), "AYON"),
    (("pipeline platform", "pipeline management"), "Pipeline 管理"),
    (("substance designer",), "Substance Designer"),
    (("complex pattern", "procedural pattern"), "程序化圖樣"),
    (("battlefield",), "戰場環境"),
    (("vfx breakdown",), "VFX 拆解"),
    (("ipad",), "iPad 工作流"),
    (("generative ai", "gen ai"), "生成式 AI"),
    (("mcp server", "model context protocol"), "MCP Server"),
    (("free rig", "rig of"), "可下載 Rig"),
    (("four colors", "four-colors", "4 colors", "four-colour"), "四色限制"),
    (("comic book", "comic-book"), "漫畫風格"),
    (("previous versions",), "舊版本取得"),
    (("resolve 21.1",), "Resolve 21.1"),
    (("modo 14.2",), "Modo 14.2"),
    (("airport",), "機場視覺化"),
    (("animation reel",), "動畫作品集"),
    (("cinema 4d",), "Cinema 4D"),
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
    """Return concise reader-facing copy; verification details stay in metadata/QA."""
    raw = source_fact(meta)
    if reader_language_ok(raw, 2.5):
        return raw
    lowered = f"{normalize_title(meta.get('title'))} {clean(meta.get('description'), 600)}".casefold()
    traits = source_subject_traits(meta)
    trait = "、".join(traits[:2])

    if has_any(lowered, ("download", "free pack", "free asset")):
        base = f"這項內容提供與 {focus_text} 有關的可下載素材"
    elif has_any(lowered, ("tutorial", "guide", "course", "training", "workflow")):
        base = f"這篇內容聚焦 {focus_text} 的教學／製作流程"
    elif has_any(lowered, ("release", "update", "version", "beta", "alpha", "preview", "roadmap")):
        base = f"這次內容整理 {focus_text} 的版本／功能更新"
    elif has_any(lowered, ("breakdown", "making-of", "behind the scenes", "case study")):
        base = f"這篇案例拆解聚焦 {focus_text} 的實際製作"
    elif has_any(lowered, ("test", "showcase", "demo")):
        base = f"這個展示案例聚焦 {focus_text} 的實作表現"
    elif has_any(lowered, ("plugin", "addon", "add-on", "tool", "software")):
        base = f"這項工具聚焦 {focus_text} 的製作應用"
    else:
        base = f"這則內容聚焦 {focus_text} 的製作應用"

    if trait:
        return f"{base}，內容型態包含 {trait}"
    return base

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
    if leaf == "category":
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
    if has_any(title_text, PROMOTION_NOISE):
        return False, "promotion-or-discount-no-production-method"
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
        subject = source_title_cue(meta)
        if not subject:
            subject = re.split(r"\s*[|｜—–-]\s*", value, maxsplit=1)[0]
            subject = clean(subject, 18)
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


def production_details(meta: dict) -> list[str]:
    """Extract concrete reader-facing technical subjects without inventing source claims."""
    text = f"{normalize_title(meta.get('title'))} {clean(meta.get('description'), 900)}".casefold()
    out: list[str] = []
    for needles, label in PRODUCTION_DETAIL_TERMS:
        if has_any(text, needles) and label not in out:
            out.append(label)
        if len(out) >= 4:
            break
    return out


def production_subject(meta: dict, focus_text: str) -> str:
    """Prefer concrete source subjects; keep a short title cue only when semantics are sparse."""
    details = production_details(meta)
    cue = source_title_cue(meta)
    if len(details) >= 2:
        return "、".join(details[:4])
    if details and cue:
        return f"{details[0]}（{cue}）"
    if details:
        return details[0]
    if cue:
        return f"{focus_text}（{cue}）"
    return focus_text


def source_content_kind(raw: str) -> str:
    if has_any(raw, ("release", "update", "version", "beta", "alpha", "preview", "roadmap", "ships")):
        return "update"
    if has_any(raw, ("tutorial", "guide", "course", "training", "workflow", "learn how", "learn to")):
        return "tutorial"
    if has_any(raw, ("breakdown", "making-of", "behind the scenes", "case study")):
        return "breakdown"
    if has_any(raw, ("download", "free pack", "free asset", "free rig")):
        return "download"
    if has_any(raw, ("test", "showcase", "demo")):
        return "demo"
    if has_any(raw, ("plugin", "addon", "add-on", "tool", "platform", "server")):
        return "tool"
    return "reference"


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
    subject = production_subject(meta, focus_text)
    kind = source_content_kind(raw)

    if not clean(meta.get("description")):
        return clean(
            f"{title} 與 {subject} 有關，但目前可讀資訊有限；先保留為精簡 BRIEF，只描述來源能直接支持的製作面向。",
            360,
        )

    if kind == "update":
        text = (
            f"這次更新聚焦 {subject}，涉及 {focus_text}。對 {label} 而言，重點是新增能力實際介入 "
            "authoring、資產交換或輸出的哪一段，以及升版後是否會改變既有設定與相容性。"
        )
    elif kind == "tutorial":
        text = (
            f"這篇教學主要拆解 {subject}，並把 {focus_text} 放進可跟著操作的製作流程。"
            f"對 {label} 而言，比單看成果更重要的是素材前置、主要操作、人工修正與輸出如何銜接，能否轉成現有 SOP 的具體步驟。"
        )
    elif kind == "breakdown":
        text = (
            f"這篇案例把 {subject} 放回實際 production 中拆解，涉及 {focus_text}。"
            "可從中觀察素材準備、製作決策與最終畫面之間的關係，適合拿來對照團隊現有做法，而不是只看成品展示。"
        )
    elif kind == "download":
        text = (
            f"這項內容提供 {subject}，並與 {focus_text} 的實際使用有關。"
            "真正值得評估的是資產／工具進入現有流程後的格式、可編輯性、相容性與後續維護成本，而不只是免費或可下載。"
        )
    elif kind == "demo":
        text = (
            f"這項展示聚焦 {subject}，可用來觀察 {focus_text} 的控制方式與結果表現。"
            "若要轉成 production 參考，還要確認同樣方法在自家資產、版本與輸出條件下是否能重現。"
        )
    elif kind == "tool":
        text = (
            f"這項工具的核心是 {subject}，作用範圍落在 {focus_text}。"
            f"對 {label} 流程，應直接看它減少哪些手動步驟、提供哪些控制，以及是否能和既有 DCC／引擎資料交換方式共存。"
        )
    else:
        text = (
            f"這則內容主要談 {subject}，與 {focus_text} 的製作實作直接相關。"
            "它能提供具體方法或結果作為對照，但仍要區分哪些是可複用流程、哪些只成立於單一作品或特定專案條件。"
        )
    return clean(text, 460)

def editorial_analysis(meta: dict, category: str, subcategory: str) -> list[dict]:
    raw = f"{normalize_title(meta.get('title'))} {clean(meta.get('description'), 600)}".casefold()
    label = friendly_label(category, subcategory)
    focus = production_focus(meta)
    focus_text = "、".join(focus) if focus else label
    subject = production_subject(meta, focus_text)
    kind = source_content_kind(raw)

    if kind == "update":
        technical = (
            f"更新內容集中在 {subject}，並牽涉 {focus_text}。這類變更要先釐清新增能力位於 authoring、資產交換還是輸出端，"
            "因為同樣叫「新功能」，對美術工作量與既有專案的影響可能完全不同。"
        )
        impact = (
            f"在 {label} 流程裡，可用同一份代表性資產做升版前後對照：記錄操作步驟、手動修正次數、輸出一致性與相容性，"
            f"確認 {subject} 是否真的降低成本，或只是增加另一套設定。"
        )
        limit = (
            f"目前資訊能確認 {subject} 的功能方向，但不能直接推定大型專案的穩定性、效能或插件相容性；"
            "若會改動既有資料格式或版本依賴，導入前仍需做舊檔與回退測試。"
        )
    elif kind == "tutorial":
        technical = (
            f"教學核心落在 {subject}，並透過 {focus_text} 展示一條可重現的操作路徑。"
            "閱讀時應把內容拆成素材前置、主要操作、人工修正與輸出結果，才能看出真正可複用的步驟。"
        )
        impact = (
            f"對 {label} 團隊，最有價值的是把其中明確步驟轉成 checklist，再用現有資產跑一次；"
            "若能在相同品質下減少返工，或讓新人更快到達可 review 狀態，才具有流程導入價值。"
        )
        limit = (
            "教學通常以單一案例為主，能證明方法可操作，但不代表它已覆蓋大量資產、多人協作或不同版本條件；"
            "還需要另外驗證命名、批次處理、檔案交換與例外情況。"
        )
    elif kind == "breakdown":
        technical = (
            f"案例拆解的重點是 {subject}，可從 {focus_text} 看出製作選擇如何累積到最終畫面。"
            "比單看成品更有價值的是辨認哪些步驟依賴特定素材、工具或人工判斷。"
        )
        impact = (
            f"對 {label}，可把案例中的關鍵節點對應到自家 pipeline：哪些能直接複用、哪些需要工具化、"
            "哪些只適合 hero asset 或特定鏡頭，這比照搬整套流程更實際。"
        )
        limit = (
            "案例文章通常缺少完整工時、版本矩陣與失敗樣本，因此適合作為方法參考，不適合直接換算成本或效能收益；"
            "仍需用相近資產規模做內部驗證。"
        )
    elif kind == "download":
        technical = (
            f"內容提供 {subject}，與 {focus_text} 的實際匯入與編輯有關。"
            "重點是檔案格式、結構、可修改程度，以及進入 downstream 後是否仍保留需要的控制。"
        )
        impact = (
            f"對 {label} 團隊，可直接拿代表性資產測試匯入、編輯、重定向或輸出，並記錄需要多少清理工作；"
            "如果前處理成本高，免費資產也不一定能節省 production 時間。"
        )
        limit = (
            "可下載並不等於可直接量產使用；授權、版本、命名、拓撲／Rig 結構與 downstream 相容性都要另外確認，"
            "尤其是要進共用資產庫時。"
        )
    elif kind == "demo":
        technical = (
            f"展示內容聚焦 {subject}，可直接觀察 {focus_text} 的控制粒度、結果品質與可重現性。"
            "這類素材適合拿來建立假設，但還不能只靠展示畫面判斷它是否能進入正式流程。"
        )
        impact = (
            f"對 {label}，可把展示條件重建成小型 A/B test，用相同資產比較操作時間、可控性與輸出差異；"
            "能否在自家版本與資料上穩定重現，比單次效果漂亮更重要。"
        )
        limit = (
            "展示通常會挑選成功案例，未必涵蓋失敗條件、邊界案例與效能成本；導入前需要補測不同資產複雜度與輸出需求。"
        )
    elif kind == "tool":
        technical = (
            f"工具主題是 {subject}，主要作用在 {focus_text}。需要看清楚它是取代既有手動步驟、補一個缺口，"
            "還是只是把原本功能換成另一個介面。"
        )
        impact = (
            f"對 {label}，可用一個真實任務比較導入前後的操作步驟、人工修正、輸出結果與交接成本；"
            "若工具能減少重複操作但增加資料轉換或版本依賴，總成本未必下降。"
        )
        limit = (
            "工具介紹通常不會涵蓋所有 production 邊界條件；部署前仍需確認版本支援、檔案相容、批次處理、例外錯誤與團隊維護責任。"
        )
    else:
        technical = (
            f"內容重點落在 {subject}，並涉及 {focus_text}。先辨認文章實際展示的是方法、工具能力還是單一作品結果，"
            "才能避免把展示效果誤當成可直接複製的流程。"
        )
        impact = (
            f"對 {label}，可以把內容中的做法或結果對照目前 pipeline，找出它可能影響的操作、交接或品質檢查點；"
            "只有能對應到真實工作步驟的部分，才值得進一步投入測試。"
        )
        limit = (
            "單一來源能提供方向與實例，但通常不足以證明跨專案穩定性；若要正式導入，仍需補做版本、資產規模與輸出條件的驗證。"
        )

    return [
        {"label": "技術／流程變更", "text": clean(technical, 620)},
        {"label": "Production 影響", "text": clean(impact, 620)},
        {"label": "導入測試與限制", "text": clean(limit, 620)},
    ]


