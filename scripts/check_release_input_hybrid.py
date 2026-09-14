#!/usr/bin/env python3
"""Compatibility entrypoint for legacy prepare/recovery wiring.

The canonical release-input validator is scripts/check_release_input.py. This file
must not duplicate Admission, analysis-depth, homepage-tier, or low-volume rules.
Keeping this thin shim avoids breaking older operational references while ensuring
all validation uses one current implementation.
"""
from pathlib import Path
import runpy

TARGET = Path(__file__).with_name('check_release_input.py')

if __name__ == '__main__':
    runpy.run_path(str(TARGET), run_name='__main__')
