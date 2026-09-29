#!/usr/bin/env python3
from __future__ import annotations
from content_quality import admission, classify_content, normalize_title, production_summary, editorial_title, editorial_analysis, reader_language_ok
from check_editorial_quality import copy_signature


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

editorial_meta = meta(
    "https://example.com/x",
    "Blender 5.2 LTS Release",
    "Rendering advancements",
    "2026-09-26",
    True,
)
title = editorial_title(editorial_meta, "blender-dcc", "blender")
summary = production_summary(editorial_meta, "blender-dcc", "blender")
analysis = editorial_analysis(editorial_meta, "blender-dcc", "blender")

assert title == "Blender 5.2 LTS：版本更新"
assert "來源頁面顯示" not in summary
assert "Collector 僅依" not in summary
assert "Rendering advancements" not in summary
assert reader_language_ok(summary, 2.5)
assert "Production 檢查點" not in summary
assert "近期製作參考" not in summary
assert "值得進一步實測" not in summary
assert len(analysis) == 3
assert [x["label"] for x in analysis] == ["技術／流程變更", "Production 影響", "導入測試與限制"]
assert "Rendering advancements" not in analysis[0]["text"]
assert reader_language_ok(analysis[0]["text"], 3.0)
assert "Blender 5.2 LTS：版本更新" in analysis[0]["text"]
assert "Blender 5.2 LTS：版本更新" in analysis[2]["text"]
assert len({x["text"] for x in analysis}) == 3
for block in analysis:
    assert "Collector" not in block["text"]
    assert "blender-dcc" not in block["text"]


fallback_title = editorial_title(
    meta(
        "https://www.blender.org/user-stories/example",
        "Using Blender in Game Development",
        "A studio describes its Blender game-development workflow.",
        "2026-09-27",
        True,
    ),
    "blender-dcc",
    "blender",
)
assert fallback_title.startswith("Blender／DCC 製作：")
assert reader_language_ok(fallback_title, 4.0)
assert "Blender／DCC：Blender／DCC：" not in fallback_title

analysis_a = editorial_analysis(
    meta("https://example.com/a", "Workflow A", "Blender modeling workflow A.", "2026-09-27", True),
    "blender-dcc",
    "blender",
)
analysis_b = editorial_analysis(
    meta("https://example.com/b", "Workflow B", "Blender modeling workflow B.", "2026-09-27", True),
    "blender-dcc",
    "blender",
)
assert not ({x["text"] for x in analysis_a} & {x["text"] for x in analysis_b})


assert reader_language_ok("Blender 5.1：5 項重點功能", 4.0)
assert not reader_language_ok("製作情報：Advanced Facial Rigging - Blender Studio", 4.0)
assert not reader_language_ok("Blender リギング：日本語タイトル", 4.0)

foreign_meta = meta(
    "https://example.com/foreign",
    "Advanced Facial Rigging - Blender Studio",
    "This course covers a flexible and expressive facial rigging workflow.",
    "2026-09-28",
    True,
)
foreign_title = editorial_title(foreign_meta, "blender-dcc", "blender")
foreign_summary = production_summary(foreign_meta, "blender-dcc", "blender")
foreign_analysis = editorial_analysis(foreign_meta, "blender-dcc", "blender")
assert reader_language_ok(foreign_title, 4.0)
assert reader_language_ok(foreign_summary, 2.5)
assert all(reader_language_ok(x["text"], 3.0) for x in foreign_analysis)
assert "This course covers" not in foreign_summary
assert all("This course covers" not in x["text"] for x in foreign_analysis)


collision_a = editorial_analysis(
    meta(
        "https://example.com/source-a",
        "Exclusive Fall Community Offer for Production Artists Working With Blender Rigging",
        "Blender rigging workflow tutorial.",
        "2026-09-29",
        True,
    ),
    "blender-dcc",
    "blender",
)
collision_b = editorial_analysis(
    meta(
        "https://example.com/source-b",
        "Facial Character Production Study for Artists Working With Blender Rigging",
        "Blender rigging workflow tutorial.",
        "2026-09-29",
        True,
    ),
    "blender-dcc",
    "blender",
)
assert not ({x["text"] for x in collision_a} & {x["text"] for x in collision_b}), (
    "different source titles must not collapse to exact duplicate analysis blocks"
)


summary_variants = [
    production_summary(
        meta(
            "https://example.com/mocap-everyday",
            "Download a Free Pack of Mocap Animations for Everyday Actions",
            "Free mocap animation pack for everyday character actions.",
            "2026-09-29",
            True,
        ),
        "3d-animation",
        "mocap",
    ),
    production_summary(
        meta(
            "https://example.com/mocap-combat",
            "Download a Free Mocap Pack for Combat and Attack Animations",
            "Free mocap animation pack for combat character actions.",
            "2026-09-29",
            True,
        ),
        "3d-animation",
        "mocap",
    ),
    production_summary(
        meta(
            "https://example.com/mocap-locomotion",
            "Download a Free Mocap Pack for Walk Run and Locomotion Cycles",
            "Free mocap animation pack for locomotion cycles.",
            "2026-09-29",
            True,
        ),
        "3d-animation",
        "mocap",
    ),
]
assert len({copy_signature(x) for x in summary_variants}) == 3, (
    "source-grounded semantic traits must prevent cross-item summary boilerplate collisions"
)


promo_case = meta(
    "https://80.lv/articles/level-up-this-fall-exclusive-gnomon-discount-for-the-80-level-community",
    "Level Up This Fall: Exclusive Gnomon Discount for the 80 Level Community",
    "Courses in visual effects, games, animation, modeling and rigging with a limited-time discount.",
    "2026-09-28",
    True,
)
assert admission(promo_case) == (False, "promotion-or-discount-no-production-method")

category_case = meta(
    "https://80.lv/articles/category?slug=animation",
    "Animation",
    "Animation articles.",
    "2026-09-29",
    True,
)
assert admission(category_case) == (False, "generic-navigation-or-resource-index")

reader_copy_meta = meta(
    "https://example.com/reader-copy",
    "Download a Free Mocap Pack for Everyday Actions",
    "Free mocap animation pack for everyday character actions.",
    "2026-09-29",
    True,
)
reader_summary = production_summary(reader_copy_meta, "3d-animation", "mocap")
reader_analysis = editorial_analysis(reader_copy_meta, "3d-animation", "mocap")
for banned_reader_phrase in (
    "來源主題為",
    "來源題名線索",
    "目前可確認的製作面向包含",
    "讀者標題為",
    "Production 檢查點為",
):
    assert banned_reader_phrase not in reader_summary
    assert all(banned_reader_phrase not in x["text"] for x in reader_analysis)


assert reader_language_ok("Unity Spline Architect：大量物件 GPU 實例化更新", 4.0)
assert reader_language_ok("Redchillies.vfx：Netflix 影集特效製作拆解", 4.0)

print("COLLECTOR CONTENT QUALITY PASS: landing/index rejection + promo rejection + concise source-grounded reader copy + title normalization + subject-first classification")
