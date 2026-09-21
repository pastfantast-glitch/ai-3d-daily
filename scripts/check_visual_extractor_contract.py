#!/usr/bin/env python3
"""Regression guard for representative visual extraction resilience.

This is intentionally network-free. It validates the candidate semantics that
previously caused real 3DNchu/SideFX media to be missed: affiliate filtering,
WordPress mShots acceptance, YouTube iframe thumbnails, modern lazy/background
selectors, and deterministic fallback source cards.
"""
from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from extract_visual_assets import (  # noqa: E402
    blocked_candidate,
    collect_candidates,
    min_dimensions,
    mshots_target,
    source_card_svg,
)

errors: list[str] = []


def fail(msg: str) -> None:
    errors.append(msg)


page = "https://3dnchu.com/archives/fixture/"
mshot = (
    "https://s0.wp.com/mshots/v1/"
    "https%3A%2F%2Fexample-tool.dev%2Fdemo?w=600&h=450"
)
affiliate = "https://m.media-amazon.com/images/I/51kpUjlvRuL._SL500_.jpg"
html = f"""
<!doctype html>
<html>
<head>
  <meta property="og:image" content="https://cdn.example.com/project-hero.jpg">
  <meta itemprop="image" content="https://cdn.example.com/itemprop-shot.jpg">
  <link rel="image_src" href="https://cdn.example.com/link-shot.jpg">
</head>
<body>
  <img src="{affiliate}" alt="book ad">
  <img src="{mshot}" alt="N-Gone Pro tool preview">
  <video poster="https://cdn.example.com/tutorial-poster.jpg"></video>
  <iframe src="https://www.youtube.com/embed/orN8H41hNDE" title="Baking with Copernicus"></iframe>
  <picture><source srcset="https://cdn.example.com/a.jpg 640w, https://cdn.example.com/b.jpg 1280w"></picture>
  <div style="background-image:url('https://cdn.example.com/background-demo.jpg')"></div>
</body>
</html>
"""

cands = collect_candidates(page, html, ["N-Gone", "Copernicus"])
urls = {x["url"]: x for x in cands}

if affiliate in urls:
    fail("affiliate Amazon image must be filtered before fetch")
if not blocked_candidate(affiliate):
    fail("affiliate host guard did not recognize Amazon image")
if mshot not in urls:
    fail("valid WordPress mShots link preview missing")
else:
    rec = urls[mshot]
    if rec["reason"] != "wp-mshots:link-preview":
        fail(f"mShots reason mismatch: {rec['reason']}")
    if min_dimensions(rec) != (560, 280, 160_000):
        fail(f"mShots strong-media floor regressed: {min_dimensions(rec)}")

target = mshots_target(mshot)
if target != "https://example-tool.dev/demo":
    fail(f"mShots target decode mismatch: {target!r}")

yt = "https://i.ytimg.com/vi/orN8H41hNDE/maxresdefault.jpg"
if yt not in urls or urls[yt]["reason"] != "youtube:thumbnail":
    fail("YouTube iframe thumbnail fallback missing")

expected = {
    "https://cdn.example.com/project-hero.jpg": "og:image",
    "https://cdn.example.com/itemprop-shot.jpg": "meta:itemprop:image",
    "https://cdn.example.com/link-shot.jpg": "link:image_src",
    "https://cdn.example.com/tutorial-poster.jpg": "video:poster",
    "https://cdn.example.com/b.jpg": "source:srcset",
    "https://cdn.example.com/background-demo.jpg": "background:style",
}
for url, reason in expected.items():
    if url not in urls:
        fail(f"candidate selector missing: {url}")
    elif urls[url]["reason"] != reason:
        fail(f"candidate reason mismatch for {url}: {urls[url]['reason']} != {reason}")

svg = source_card_svg("角色 <測試> & UV", "https://experienceleague.adobe.com/docs/test")
if "<svg" not in svg or "experienceleague.adobe.com" not in svg:
    fail("fallback source card missing SVG/domain")
if "角色 &lt;測試&gt; &amp; UV" not in svg:
    fail("fallback source card title must be XML/HTML escaped")

# Generic inline media remains stricter than strong metadata/link-preview media.
if min_dimensions({"reason": "img:src"}) != (640, 320, 220_000):
    fail("generic inline image floor must remain strict")
if min_dimensions({"reason": "youtube:thumbnail"}) != (560, 280, 160_000):
    fail("strong video thumbnail floor mismatch")

if errors:
    print("VISUAL EXTRACTOR CONTRACT FAILED")
    for error in errors:
        print("-", error)
    raise SystemExit(1)

print(
    "VISUAL EXTRACTOR CONTRACT PASS: affiliate filtering + 600px strong previews + "
    "video/metadata/background discovery + deterministic source-card fallback"
)
