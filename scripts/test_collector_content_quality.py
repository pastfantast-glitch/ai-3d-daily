#!/usr/bin/env python3
from __future__ import annotations
from content_quality import admission, classify_content, normalize_title, production_summary, editorial_title, editorial_analysis, reader_language_ok, production_details, production_subject, source_title_cue, source_subject_traits
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
assert "版本更新" in summary
assert "目前簡介未列出完整改動" in summary
assert "實測" not in summary  # no invented benchmark
assert "先看它實際改變哪些操作、交換或輸出步驟" not in summary
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
assert "Blender" in fallback_title
assert "…" not in fallback_title
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


dishes_meta = meta(
    "https://80.lv/articles/learn-how-to-make-delectable-stylized-3d-dishes-in-blender",
    "Learn How to Make Delectable Stylized 3D Dishes in Blender",
    "A Blender tutorial for creating stylized 3D dishes.",
    "2026-09-30",
    True,
)
deer_meta = meta(
    "https://80.lv/articles/tutorial-learn-how-to-make-a-stylized-deer-in-3d-using-blender",
    "Tutorial: Learn How to Make a Stylized Deer in 3D Using Blender",
    "A Blender tutorial for creating a stylized deer in 3D.",
    "2026-09-30",
    True,
)
dishes_title = editorial_title(dishes_meta, "3d-production", "prop-production")
deer_title = editorial_title(deer_meta, "3d-production", "character-production")
assert dishes_title != deer_title, "source-specific title cues must survive zh-Hant fallback framing"
dishes_analysis = editorial_analysis(dishes_meta, "3d-production", "prop-production")
deer_analysis = editorial_analysis(deer_meta, "3d-production", "character-production")
assert not ({x["text"] for x in dishes_analysis} & {x["text"] for x in deer_analysis}), (
    "the 2026-09-30 80.lv dishes/deer sources must not collapse to duplicate analysis blocks"
)


marmoset_meta = meta(
    "https://80.lv/articles/marmoset-toolbag-inspired-texture-baking-add-on-released-for-blender",
    "Marmoset Toolbag-Inspired Texture Baking Add-On Released for Blender",
    "A Blender add-on brings a Marmoset Toolbag-inspired texture baking workflow to artists.",
    "2026-10-01",
    True,
)
marmoset_summary = production_summary(marmoset_meta, "blender-dcc", "blender")
marmoset_analysis = editorial_analysis(marmoset_meta, "blender-dcc", "blender")
assert "Marmoset Toolbag 式烘焙" in marmoset_summary
assert "貼圖烘焙" in marmoset_summary
assert any("Marmoset Toolbag 式烘焙" in x["text"] for x in marmoset_analysis)
assert "先看它實際改變哪些操作、交換或輸出步驟" not in marmoset_summary

grease_meta = meta(
    "https://80.lv/articles/the-long-awaited-shape-keys-for-blender-s-grease-pencil-tested-on-a-character-rig",
    "The Long-Awaited Shape Keys for Blender's Grease Pencil Tested on a Character Rig",
    "Shape Keys for Grease Pencil are demonstrated on a Blender character rig.",
    "2026-10-01",
    True,
)
grease_summary = production_summary(grease_meta, "blender-dcc", "blender")
assert "Shape Keys" in grease_summary
assert "Grease Pencil" in grease_summary
assert "角色 Rig" in grease_summary

mcp_meta = meta(
    "https://www.cgchannel.com/2026/09/maxon-releases-cinema-4d-2026-4-with-a-new-mcp-server",
    "Maxon releases Cinema 4D 2026.4 with a new MCP Server",
    "Cinema 4D 2026.4 adds a new MCP Server for production workflows.",
    "2026-10-01",
    True,
)
mcp_summary = production_summary(mcp_meta, "blender-dcc", "other-dcc")
mcp_analysis = editorial_analysis(mcp_meta, "blender-dcc", "other-dcc")
assert "Cinema 4D" in mcp_summary
assert "MCP Server" in mcp_summary
assert any("MCP Server" in x["text"] for x in mcp_analysis)

for text in [marmoset_summary, grease_summary, mcp_summary]:
    assert reader_language_ok(text, 2.5), text


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


# 2026-10-06: Houdini release headlines collided once two technical details
# caused production_subject() to discard the article identity. Use the same
# description deliberately to exercise that branch independently of live pages.
shared_houdini_description = (
    "A version update to a procedural modeling toolkit for Houdini and Cinema 4D."
)
houdini_release_cases = [
    meta(
        "https://example.invalid/houdini-direct-modeling-regression",
        "Alexey Vanzhula ships Direct Modeling HDA for Houdini",
        shared_houdini_description,
        "2018-01-08",
        True,
    ),
    meta(
        "https://example.invalid/houdini-modeler-regression",
        "Alexey Vanzhula releases Modeler 26.3 for Houdini",
        shared_houdini_description,
        "2026-10-05",
        True,
    ),
]
assert all(
    len(production_details(m) + [
        x for x in source_subject_traits(m)
        if x == "程序化"
    ]) >= 2
    for m in houdini_release_cases
), "fixture must exercise the multi-detail subject branch"
expected_houdini_cues = ["Direct Modeling HDA", "Modeler 26.3"]
houdini_analyses = []
houdini_summaries = []
for m, cue in zip(houdini_release_cases, expected_houdini_cues):
    assert source_title_cue(m) == cue
    blocks = editorial_analysis(m, "blender-dcc", "houdini")
    summary = production_summary(m, "blender-dcc", "houdini")
    assert all(cue in block["text"] for block in blocks)
    assert cue in summary
    assert all(reader_language_ok(block["text"], 3.0) for block in blocks)
    assert reader_language_ok(summary, 2.5)
    assert blocks == editorial_analysis(m, "blender-dcc", "houdini")
    houdini_analyses.append({block["text"] for block in blocks})
    houdini_summaries.append(summary)
assert not (houdini_analyses[0] & houdini_analyses[1])
assert houdini_summaries[0] != houdini_summaries[1]

# Product versions must also survive the identical author and DCC framing.
version_meta = dict(houdini_release_cases[1])
version_meta["title"] = "Alexey Vanzhula releases Modeler 26.5 for Houdini"
assert source_title_cue(version_meta) == "Modeler 26.5"
version_analysis = editorial_analysis(version_meta, "blender-dcc", "houdini")
assert all("Modeler 26.5" in block["text"] for block in version_analysis)
assert not ({block["text"] for block in version_analysis} & houdini_analyses[1])

# Same semantic details across non-release articles must retain their title cues.
detail_cases = [
    meta("https://example.com/detail-a", "Workflow A", "Grease Pencil Shape Keys workflow."),
    meta("https://example.com/detail-b", "Workflow B", "Grease Pencil Shape Keys workflow."),
]
detail_analyses = [
    {block["text"] for block in editorial_analysis(m, "blender-dcc", "blender")}
    for m in detail_cases
]
assert not (detail_analyses[0] & detail_analyses[1])


# The 9/25-and-earlier reading style is concrete, not a technical keyword list.
from content_quality import editorial_policy, reviewed_reader_copy
policy = editorial_policy()
plain_policy = policy["plain_reading"]
assert "2026-09-25" in plain_policy["reference_dates"]
reviewed_records = policy["reviewed_reader_copy"]
assert len(reviewed_records) == 13
seen_reviewed_blocks = set()
for url, record in reviewed_records.items():
    source_meta = meta(url, "Source title", "Verified source description.")
    assert editorial_title(source_meta, "blender-dcc", "houdini") == record["title"]
    assert production_summary(source_meta, "blender-dcc", "houdini") == record["summary"]
    blocks = editorial_analysis(source_meta, "blender-dcc", "houdini")
    assert reader_language_ok(record["title"], 4.0)
    assert reader_language_ok(record["summary"], 2.5)
    assert len(blocks) == 3
    for block in blocks:
        assert len(block["text"]) >= 36 and reader_language_ok(block["text"], 3.0)
        assert block["text"] not in seen_reviewed_blocks
        seen_reviewed_blocks.add(block["text"])
    visible = record["title"] + record["summary"] + "".join(x["text"] for x in blocks)
    assert "…" not in record["title"]
    assert all(phrase not in visible for phrase in plain_policy["banned_phrases"])

water_url = next(u for u in reviewed_records if "water-adhesion" in u)
water = reviewed_records[water_url]
assert "水滴附著" in water["title"]
assert "VEX" in water["summary"] and "SOP Solver" in water["summary"]
assert "關節" in water["full_analysis"][2]["text"]
modeler_url = next(u for u in reviewed_records if "releases-modeler-26" in u)
modeler = reviewed_records[modeler_url]
assert "26.5" in modeler["title"] and "SubD Proxy" in modeler["summary"]
assert "26.3" in modeler["full_analysis"][2]["text"]  # stale source headline explained
for u in reviewed_records:
    if any(x in u for x in ("/2017/", "/2018/", "/2020/", "samus-free-rig")):
        assert "歷史" in reviewed_records[u]["title"]
assert reviewed_reader_copy(meta(water_url + "?different-identity=1", "Other source")) is None
# A page cannot supply its own reviewed-copy authority.
untrusted = meta("https://example.invalid/unreviewed", "Blender 5.2 LTS Release", "Rendering advancements")
untrusted["reviewed_reader_copy"] = water
assert reviewed_reader_copy(untrusted) is None
unreviewed_summary = production_summary(untrusted, "blender-dcc", "blender")
assert "水滴附著" not in unreviewed_summary
assert not any(phrase in unreviewed_summary for phrase in plain_policy["banned_phrases"])

print("COLLECTOR CONTENT QUALITY PASS: landing/index rejection + promo rejection + production-dense source-grounded reader copy + title normalization + subject-first classification")
