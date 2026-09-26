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
    (
        meta("https://80.lv/articles/animation", "Animation Tutorials and Breakdowns",
             "Animation tutorials, breakdowns and production articles.", "2026-09-26", True),
        False, "generic-navigation-or-resource-index",
    ),
    (
        meta("https://studio.blender.org/tools", "Blender Studio",
             "Tools and production resources."),
        False, "generic-navigation-or-resource-index",
    ),
    (
        meta("https://unity.com/games", "Game Development Software: Create 2D & 3D Games",
             "Create games with Unity."),
        False, "generic-navigation-or-resource-index",
    ),
    (
        meta("https://unity.com/industry", "Create Real-Time 3D Experiences | Industry Solutions from Unity",
             "Industry solutions for real-time 3D."),
        False, "generic-navigation-or-resource-index",
    ),
    (
        meta("https://80.lv/partners", "3D software, drawing tablets, and online art schools",
             "Partners and services for artists.", "2026-09-26", True),
        False, "generic-navigation-or-resource-index",
    ),
    (
        meta("https://docs.blender.org/manual/en/latest", "Blender 5.2 LTS Manual",
             "Blender manual."),
        False, "generic-navigation-or-resource-index",
    ),
    (
        meta("https://studio.blender.org/training", "Training - Blender Studio",
             "Training resources for Blender artists."),
        False, "generic-navigation-or-resource-index",
    ),
    (
        meta("https://www.blender.org/download/demo-files", "Demo Files",
             "Download Blender demo files."),
        False, "generic-navigation-or-resource-index",
    ),
    (
        meta("https://www.blender.org/support", "Support",
             "Blender support resources."),
        False, "generic-navigation-or-resource-index",
    ),
    (
        meta("https://www.blender.org/news/show-your-support-for-blender-projects",
             "Show your support for Blender projects",
             "Support Blender projects and development.", "2026-09-20", True),
        False, "governance-or-funding-page-no-production-method",
    ),
    (
        meta("https://www.blender.org/news/upcoming-blender-development-fund-and-ai-policies",
             "Upcoming Blender Development Fund and AI Policies",
             "Upcoming policy changes.", "2026-09-20", True),
        False, "governance-or-funding-page-no-production-method",
    ),
    (
        meta("https://www.cgchannel.com/2026/09/vfx-portfolio-and-recruitment-site-zerply-is-closing-later-this-month",
             "VFX portfolio and recruitment site Zerply is closing later this month",
             "A VFX portfolio and recruitment platform is shutting down.", "2026-09-26", True),
        False, "recruitment-or-portfolio-news-no-production-method",
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

assert classify_content(
    "New CG software you may have missed: 13 September 2026",
    "A roundup including animation and rigging utilities.",
) == ("blender-dcc", "other-dcc")

assert classify_content(
    "Breakdown: Animating Tiny Character With Massive Two-Handed Weapon",
    "Character animation breakdown.",
) == ("3d-animation", "animation")

summary = production_summary(
    meta("https://example.com/x", "Blender 5.2 LTS Release", "Rendering advancements", "2026-09-26", True),
    "blender-dcc",
    "blender",
)
assert "來源頁面顯示" not in summary
assert "Collector 僅依" not in summary
assert "Blender 5.2 LTS Release" in summary
assert any(x in summary for x in ("流程", "導入", "製作"))
assert "Rendering" in summary

print("COLLECTOR CONTENT QUALITY PASS: landing/index rejection + scope admission + title normalization + subject-first classification + zh-Hant production summary")
