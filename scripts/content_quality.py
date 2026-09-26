#!/usr/bin/env python3
"""Shared content-quality policy for autonomous Production Intelligence collection.

This module is deliberately deterministic and source-grounded. It rejects index,
product/marketing landing, governance/event, and non-production pages before ranking;
normalizes SEO titles; classifies by the subject of the item rather than incidental
keywords; and generates concise Traditional-Chinese production summaries without
inventing source claims.
"""
from __future__ import annotations

from html import unescape
from urllib.parse import urlparse
import re

WS_RE = re.compile(r"\s+")
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
    if not article_type and not published:
        if any(fragment in path for fragment in LANDING_PATH_FRAGMENTS):
            return "non-article-product-or-feature-landing"
        if leaf in GENERIC_NAV_LEAVES and len(segments) <= 3:
            return "generic-navigation-or-resource-index"
        if title in GENERIC_NAV_TITLE_EXACT:
            return "generic-navigation-or-resource-index"
        if any(fragment in title for fragment in GENERIC_NAV_TITLE_FRAGMENTS):
            return "generic-navigation-or-resource-index"
        if path.rstrip("/").endswith("/roadmap") or title == "roadmap":
            return "roadmap-index-page"
        if title.endswith(" manual") and ("manual" in segments or leaf == "latest"):
            return "documentation-root-index"
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
    if any(k in t for k in ("animation", "animator", "keyframe", "locomotion")):
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


def production_focus(meta: dict) -> list[str]:
    text = f"{normalize_title(meta.get('title'))} {clean(meta.get('description'), 900)}".casefold()
    out: list[str] = []
    for needle, label in FOCUS_TERMS:
        if has_term(text, needle) and label not in out:
            out.append(label)
        if len(out) >= 4:
            break
    return out


def production_summary(meta: dict, category: str, subcategory: str) -> str:
    title = normalize_title(meta.get("title"))
    text = f"{title} {clean(meta.get('description'), 600)}".casefold()
    label = SUBCATEGORY_LABELS.get(subcategory) or CATEGORY_LABELS.get(category) or category
    focus = production_focus(meta)
    focus_clause = (
        "來源可驗證的製作重點包含「" + "、".join(focus) + "」。"
        if focus
        else f"來源可驗證的主題落在「{label}」。"
    )

    if has_any(text, ("release", "update", "version", "beta", "alpha", "preview")):
        body = (
            f"「{title}」是版本／功能更新。{focus_clause}"
            f"對 {label} 流程可用來判斷功能差異、相容性與導入時機；"
            "效能、品質與穩定性仍需以實際專案資產驗證。"
        )
    elif has_any(text, ("breakdown", "tutorial", "how to", "guide", "case study", "behind", "making-of")):
        body = (
            f"「{title}」是可供製作參考的拆解／教學。{focus_clause}"
            "適合把來源明確展示的方法拆成測試步驟，與團隊現行流程比較，再驗證品質、時間成本與限制。"
        )
    elif has_any(text, ("plugin", "addon", "add-on", "tool", "software")):
        body = (
            f"「{title}」是工具／工作流情報。{focus_clause}"
            "導入前應確認版本相容、輸出格式、授權與是否真的減少既有流程中的重複操作。"
        )
    else:
        body = (
            f"「{title}」具有直接 Production 參考價值。{focus_clause}"
            "目前以來源能明確支持的方法、功能或案例為準，不延伸未公開的效能或品質結論。"
        )
    return clean(body, 420)
