#!/usr/bin/env python3
from __future__ import annotations
from content_quality import admission, classify_content, normalize_title, production_summary


def meta(url, title, description="", published=None, article_type=False):
    return {
        "url": url,
        "title": title,
        "description": description,
        "published": published,
        "article_type": article_type,
    }


cases = [
    (
        meta("https://80.lv/articles/business", "Articles and tutorials for 2D/3D Artists",
             "Workflow breakdowns and tutorials for Unreal Engine, 3ds Max, Substance Painter, Houdini, and more."),
        False, "generic-index-title",
    ),
    (
        meta("https://unity.com/features/collaboration", "Unity Collaboration Tools for Teams | Version Control & Builds",
             "Version control and builds for teams."),
        False, "non-article-product-or-feature-landing",
    ),
    (
        meta("https://www.sidefx.com/products/houdini", "Houdini | Procedural Content Creation Tools for Film/TV, Gamedev and more | SideFX",
             "Procedural content creation.", None, False),
        False, "non-article-product-or-feature-landing",
    ),
    (
        meta("https://80.lv/articles/the-players-you-already-have-are-your-biggest-growth-opportunity",
             "The Players You Already Have Are Your Biggest Growth Opportunity",
             "Learn to spot churn early and win mobile players back for good.", "2026-09-26", True),
        False, "business-or-player-growth-no-art-production-takeaway",
    ),
]

for m, expected, reason in cases:
    got, got_reason = admission(m)
    assert got is expected, (m["url"], got, got_reason)
    assert got_reason == reason, (m["url"], got_reason, reason)

assert normalize_title("IKinema releases Action for MotionBuilder | CG Channel") == "IKinema releases Action for MotionBuilder"
assert normalize_title("Houdini Engine | SideFX") == "Houdini Engine"

assert classify_content(
    "Exploring Thin, Pale, Slimy Skin Texture by Recreating The Demogorgon From Stranger Things",
    "lookdev, displacement and lighting for the creature skin texture",
) == ("3d-production", "character-production")
assert classify_content(
    "Blender 5.2 LTS Release",
    "node-powered physics, rendering advancements and asset libraries",
) == ("blender-dcc", "blender")
assert classify_content(
    "Unreal Engine 5.8 is here: discover its 5 key features for CG artists",
    "Mesh Terrain, MetaHuman Crowds, rigging and animation tools",
) == ("engine-art", "unreal")

summary = production_summary(
    meta("https://example.com/x", "Blender 5.2 LTS Release", "Rendering advancements", "2026-09-26", True),
    "blender-dcc",
    "blender",
)
assert "來源頁面顯示" not in summary
assert "Collector 僅依" not in summary
assert "Blender 5.2 LTS Release" in summary
assert any(x in summary for x in ("流程", "導入", "製作"))

print("COLLECTOR CONTENT QUALITY PASS: landing/index rejection + scope admission + title normalization + subject-first classification + zh-Hant production summary")
