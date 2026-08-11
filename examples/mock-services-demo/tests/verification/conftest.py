"""Permit inventory tests to run from the repository root test command."""
# ruff: noqa: I001

import sys
from pathlib import Path


DEMO_ROOT = Path(__file__).resolve().parents[2]
SOURCE_ROOT = DEMO_ROOT / "src"
if str(SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(SOURCE_ROOT))
