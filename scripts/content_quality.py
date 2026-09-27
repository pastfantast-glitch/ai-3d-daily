#!/usr/bin/env python3
"""Shared content-quality policy for autonomous Production Intelligence collection.
Policy revision: 2026-09-27 navigation-index rejection v2.

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
        if re.search(r"[\u3400-\u9fff]", value):
            return value
        category_label = CATEGORY_LABELS.get(category) or "製作情報"
        return clean(f"{category_label}：{value}", 180)

    if re.search(r"[\u3400-\u9fff]", raw):
        return raw

    label = friendly_label(category, subcategory)
    if not re.search(r"[\u3400-\u9fff]", label):
        label = CATEGORY_LABELS.get(category) or "製作情報"

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
    return framed(f"{label}：{raw}")

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
    title = editorial_title(meta, category, subcategory)
    raw = f"{normalize_title(meta.get('title'))} {clean(meta.get('description'), 600)}".casefold()
    label = friendly_label(category, subcategory)
    focus = production_focus(meta)
    focus_text = "、".join(focus) if focus else label

    if has_any(raw, ("release", "update", "version", "beta", "alpha", "preview")):
        return clean(
            f"「{title}」整理這次版本／功能變更，已知重點落在 {focus_text}。"
            f"對 {label} 流程可先用來判斷升級與測試優先順序，再回原始來源確認版本限制與相容性。",
            380,
        )
    if has_any(raw, ("breakdown", "tutorial", "how to", "guide", "case study", "behind", "making-of")):
        return clean(
            f"「{title}」提供可供製作參考的流程／案例，重點落在 {focus_text}。"
            "適合先拆出來源明確展示的方法與視覺判斷，再用自己的資產規格驗證是否可轉移到 Production。",
            380,
        )
    if has_any(raw, ("plugin", "addon", "add-on", "tool", "software")):
        return clean(
            f"「{title}」屬於工具與工作流更新，已知關聯重點為 {focus_text}。"
            "評估時應優先確認它改善哪個既有步驟，再檢查版本相容、輸出格式、授權與實際導入成本。",
            380,
        )
    return clean(
        f"「{title}」提供 {label} 的近期製作參考，來源可確認的重點集中在 {focus_text}。"
        "閱讀時應以公開來源能支持的方法、功能或案例為準，再決定是否值得進一步實測。",
        380,
    )


def editorial_analysis(meta: dict, category: str, subcategory: str) -> list[dict]:
    title = editorial_title(meta, category, subcategory)
    raw = f"{normalize_title(meta.get('title'))} {clean(meta.get('description'), 600)}".casefold()
    label = friendly_label(category, subcategory)
    focus = production_focus(meta)
    focus_text = "、".join(focus) if focus else label

    if has_any(raw, ("release", "update", "version", "beta", "alpha", "preview")):
        technical = f"「{title}」屬於版本／功能更新；目前可確認的製作重點集中在 {focus_text}。評估時應先把新功能與現有 {label} 流程逐項對照，而不是只看版本號或功能數量。"
        impact = f"對 Production 的價值在於用「{title}」建立升級優先順序：哪些 {focus_text} 變更會直接影響日常製作、資產交換或最終輸出，應先用代表性專案做回歸。"
    elif has_any(raw, ("breakdown", "tutorial", "how to", "guide", "case study", "behind", "making-of")):
        technical = f"「{title}」屬於製作拆解／教學，核心觀察點落在 {focus_text}。可先把來源明確展示的步驟、視覺判斷與工具使用拆開，再對照自己現有流程。"
        impact = f"「{title}」對 {label} Production 的價值是提供可比較的實作案例；適合拿來做 Review Reference 或小型 A/B Test，而不是直接把單一案例視為通用標準。"
    else:
        technical = f"「{title}」目前可確認的技術／製作焦點集中在 {focus_text}。應優先理解它改變的是工具能力、製作方法還是輸出結果，再判斷與現有流程的關聯。"
        impact = f"對 {label} 團隊而言，「{title}」可作為近期參考項目，用來決定是否值得深入閱讀、建立測試檔或更新內部 Review Checklist。"

    limit = (
        f"「{title}」目前的證據深度仍以公開來源為主；正式導入前應用團隊實際 DCC／引擎版本、資產規格與輸出條件驗證相容性、"
        "可重現性與品質，且不得把來源未公開的效能、工時或品質提升當成既知結果。"
    )
    return [
        {"label": "技術／流程變更", "text": clean(technical, 520)},
        {"label": "Production 影響", "text": clean(impact, 520)},
        {"label": "導入測試與限制", "text": clean(limit, 520)},
    ]
