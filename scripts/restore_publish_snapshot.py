#!/usr/bin/env python3
"""Prepare a recovery commit from a previously verified publish commit.

This helper never moves branch history backwards. It restores only derived
publication surfaces from a known-good `Publish canonical intelligence ...`
commit and leaves canonical datasets/registry untouched. Default mode is dry-run;
pass --apply inside the canonical writer workflow or a controlled local checkout.
"""
from __future__ import annotations

from pathlib import Path
import argparse
import json
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def git(*args: str, capture: bool = True) -> str:
    p = subprocess.run(["git", *args], cwd=ROOT, text=True, capture_output=capture, check=True)
    return p.stdout.strip() if capture else ""


def resolve_target(explicit: str | None) -> str:
    if explicit:
        return explicit
    path = ROOT / "data" / "publish" / "latest-success.json"
    if not path.exists():
        raise SystemExit("latest-success.json missing; pass --target explicitly")
    return json.loads(path.read_text("utf-8"))["publish_commit_sha"]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--target", help="known-good Publish canonical intelligence commit SHA")
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()
    target = resolve_target(args.target)
    subject = git("show", "-s", "--format=%s", target)
    if not subject.startswith("Publish canonical intelligence "):
        raise SystemExit(f"refusing non-publish target {target}: {subject}")

    tree = git("ls-tree", "-r", "--name-only", target).splitlines()
    archive_paths = [p for p in tree if re.fullmatch(r"20\d{2}-\d{2}-\d{2}/index\.html", p)]
    restore = ["index.html", "assets/visual", *archive_paths]
    print("RECOVERY TARGET:", target, subject)
    print("RESTORE PATHS:")
    for p in restore:
        print(" -", p)
    if not args.apply:
        print("DRY RUN ONLY. Re-run with --apply to restore working tree/index.")
        return 0

    # Restore tracked derived surfaces from the known-good commit. Canonical source
    # data and registry are intentionally not touched.
    git("checkout", target, "--", *restore, capture=False)
    print("RECOVERY SNAPSHOT RESTORED TO WORKTREE/INDEX")
    print("Review git diff --cached, then commit through the canonical writer only.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
