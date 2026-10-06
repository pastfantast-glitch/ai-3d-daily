#!/usr/bin/env python3
"""Shared content-quality policy for autonomous Production Intelligence collection.
Policy revision: 2026-10-06 concrete zh-Hant reader copy modeled on 2026-09-23/24/25.
Reviewed source copy takes precedence; unreviewed sources keep a concise, conservative brief.

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
    # Release headlines often share an author prefix and a DCC suffix.
    # Keep the product and version between them instead of shortening those away.
    release = re.match(r"^.+?\s+(?:releases?|ships?)\s+(.+)$", raw, flags=re.I)
    if release:
        raw = re.sub(
            r"\s+for\s+(?:Houdini|Blender|Maya|Cinema 4D|3ds Max)\b.*$",
            "",
            release.group(1),
            flags=re.I,
        ).strip()
    if len(raw) <= (40 if release else 18):
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
    """Prefer concrete source subjects; keep semantic traits before falling back to a title cue."""
    details = production_details(meta)
    specific_traits = [
        x for x in source_subject_traits(meta)
        if x not in {"可下載素材", "測試展示", "教學", "製作拆解", "版本更新"}
    ]
    for trait in specific_traits:
        if trait not in details:
            details.append(trait)
        if len(details) >= 4:
            break
    cue = source_title_cue(meta)
    if len(details) >= 2:
        subject = "、".join(details[:4])
        return f"{subject}（{cue}）" if cue else subject
    if details and cue:
        return f"{details[0]}（{cue}）"
    if details:
        return details[0]
    if cue:
        return f"{focus_text}（{cue}）"
    return focus_text


def source_content_kind(raw: str) -> str:
    if has_any(raw, ("release", "releases", "released", "update", "version", "beta", "alpha", "preview", "roadmap", "ships", "launches", "launched")):
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



# Reader copy follows the concrete 2026-09-23/24/25 examples. Discovery,
# Admission, scoring and publication ownership are deliberately unchanged.
def reviewed_reader_copy(meta: dict) -> dict | None:
    records = editorial_policy().get("reviewed_reader_copy") or {}
    url = str(meta.get("url") or "").split("#", 1)[0].rstrip("/")
    record = records.get(url)
    if not isinstance(record, dict) or record.get("source_reviewed") is not True:
        return None
    return record


def plain_subject(meta: dict, category: str, subcategory: str) -> str:
    raw = normalize_title(meta.get("title"))
    if reader_language_ok(raw, 4.0):
        return raw
    text = f"{raw} {clean(meta.get('description'), 650)}".casefold()
    release = re.match(r"^.+?\s+(?:releases?|ships?|launches?|just released)\s+(.+)$", raw, re.I)
    if release:
        product = re.split(r"\s+(?:for|with)\s+", release.group(1), maxsplit=1, flags=re.I)[0]
        if len(product) <= 40:
            detail = "、".join(production_details(meta)[:2])
            return f"{product}：{detail + '與' if detail else ''}版本更新"
    blender = re.match(r"^Blender\s+(.+?)\s+Release$", raw, re.I)
    if blender:
        return f"Blender {blender.group(1)}：版本更新"

    # Translate concrete subjects, rather than clipping an English headline.
    nouns = (
        (("water adhesion",), "動態角色表面的水滴附著"),
        (("space colonization",), "分枝路徑與煙霧模擬"),
        (("bubble",), "水中氣泡運動"),
        (("forest stream",), "森林溪流模擬"),
        (("wristwatch", "möbius"), "手錶與莫比烏斯環"),
        (("deer",), "麋鹿建模"),
        (("dishes",), "餐具建模"),
        (("facial", "lip sync"), "臉部表演與綁定"),
        (("everyday", "daily action"), "日常動作素材"),
        (("combat", "attack animation"), "戰鬥動作素材"),
        (("locomotion", "walk", "run cycle"), "行走與跑步循環"),
        (("hard surface", "hard-surface"), "硬表面建模"),
        (("character", "creature"), "角色製作"),
        (("environment", "terrain"), "場景與地形製作"),
    )
    subjects = [label for terms, label in nouns if has_any(text, terms)]
    traits = [x for x in source_subject_traits(meta) if x in {"風格化", "寫實", "程序化"}]
    details = production_details(meta)
    focus = production_focus(meta)
    translated_focus = {"Rigging": "骨架綁定", "Retarget": "動作重定向", "Rendering": "渲染",
                        "Displacement": "置換細節", "Mocap": "動作捕捉"}
    terms = subjects[:1] or details[:2] or [translated_focus.get(x, x) for x in focus[:2]]
    label = friendly_label(category, subcategory)
    if not HAN_RE.search(label):
        label += " 製作"
    topic = "、".join(terms) if terms else label
    trait = "、".join(traits[:1])
    if trait and trait not in topic:
        topic = trait + topic
    # Short proper tool names and fixture titles remain whole. No middle ellipsis.
    if len(raw) <= 36 and not KANA_RE.search(raw):
        raw = re.sub(r"\bWorkflow\b", "流程", raw, flags=re.I)
        if reader_language_ok(raw, 4.0):
            return f"{raw}：{topic}"
        if len(LATIN_RE.findall(raw)) <= 24:
            return f"{raw}：{topic}製作介紹"
    suffix = {"update": "版本更新", "tutorial": "製作教學", "breakdown": "製作拆解",
              "download": "下載介紹", "demo": "效果展示", "tool": "工具介紹",
              "reference": "案例介紹"}[source_content_kind(text)]
    return clean(f"{label}：{topic}{suffix}", 180)


def editorial_title(meta: dict, category: str, subcategory: str) -> str:
    reviewed = reviewed_reader_copy(meta)
    return reviewed["title"] if reviewed else plain_subject(meta, category, subcategory)


def plain_reader_context(meta: dict, category: str, subcategory: str) -> tuple[str, str, str]:
    title = editorial_title(meta, category, subcategory)
    raw = f"{normalize_title(meta.get('title'))} {clean(meta.get('description'), 650)}".casefold()
    kind = source_content_kind(raw)
    detail = "、".join(production_details(meta))
    focus = "、".join(production_focus(meta)) or friendly_label(category, subcategory)
    if reader_language_ok(source_fact(meta), 2.5):
        fact = source_fact(meta)
    elif has_any(raw, ("marmoset toolbag",)) and has_any(raw, ("baking", "bake")):
        fact = "這個 Blender 外掛提供 Marmoset Toolbag 式烘焙操作，讓美術在 Blender 中進行貼圖烘焙。"
    elif has_any(raw, ("shape keys",)) and has_any(raw, ("grease pencil",)):
        fact = "內容展示 Grease Pencil 的 Shape Keys 在角色 Rig 上的使用方式，讓美術觀察繪製形狀如何配合角色變形。"
    elif has_any(raw, ("mcp server",)):
        fact = f"{title.split('：')[0]} 加入 MCP Server，提供軟體與外部工具連接的新入口；實際可用指令仍需查對文件。"
    elif kind == "update":
        fact = f"{title}。本文介紹{detail or focus}的更新；目前簡介未列出完整改動，不能據此推定所有新增功能。"
    elif kind == "download":
        fact = f"{title}。內容提供與{detail or focus}有關的素材；檔案格式、控制器與授權需查下載頁面的說明。"
    elif kind == "tutorial":
        fact = f"{title}。這篇教學介紹{detail or focus}的做法，可先跟著範例操作，再用自己的資產重做。"
    else:
        fact = f"{title}。內容展示{detail or focus}的作品或工具；可先看具體結果，再確認作者公開了哪些操作步驟。"
    return title, clean(fact, 460), raw


def production_summary(meta: dict, category: str, subcategory: str) -> str:
    reviewed = reviewed_reader_copy(meta)
    if reviewed:
        return reviewed["summary"]
    return plain_reader_context(meta, category, subcategory)[1]


def editorial_analysis(meta: dict, category: str, subcategory: str) -> list[dict]:
    reviewed = reviewed_reader_copy(meta)
    if reviewed:
        return [dict(x) for x in reviewed["full_analysis"]]
    title, fact, raw = plain_reader_context(meta, category, subcategory)
    if has_any(raw, ("mocap", "animation", "rigging", "rig", "facial")):
        use = "可用自己的角色試做姿勢與動作，觀察關節變形、腳底滑動和表情幅度，判斷是否能減少人工修正。"
        test = "需確認骨架、控制器與軟體版本，再測極端姿勢、動作重定向與引擎匯入；介紹本身不能證明所有角色都適用。"
    elif has_any(raw, ("baking", "texture", "material", "shader", "grease pencil")):
        use = "可選一個角色或道具測試貼圖與材質，對照原設定的分色、光影和細節，記錄哪些地方仍要人工修改。"
        test = "需在實際引擎檢查色彩空間、透明通道、貼圖尺寸與不同光向；工具預覽和最終遊戲畫面可能有差異。"
    elif has_any(raw, ("modeling", "sculpt", "retopo", "geometry")):
        use = "可拿一個現有模型試做，比較輪廓、拓樸、UV 和烘焙結果，再記錄操作與清理時間，判斷是否比原方法省工。"
        test = "需檢查複雜造型、細分曲面與舊檔相容性；單一示範不能保證所有資產都能得到相同品質。"
    else:
        use = "可挑與目前作品相近的鏡頭或素材做小型比較，觀察形狀、動態和畫面差異，先判斷哪些結果能重現。"
        test = "目前簡介不足以確認完整實作與效能。測試時需記錄軟體版本、資產規模和輸出結果，再決定能否使用。"
    technical = fact if fact.startswith(title) else f"{title}。{fact}"
    return [
        {"label": "技術／流程變更", "text": clean(technical, 620)},
        {"label": "Production 影響", "text": clean(f"以{title}為例，{use}", 620)},
        {"label": "導入測試與限制", "text": clean(f"使用{title}前，{test}", 620)},
    ]
