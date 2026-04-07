# conftest.py — pytest runs from the project root (zep-explore/).
# The governance package is installed via: uv pip install -e ".[dev]"
# or importable directly since tests run with project root on sys.path.
import sys
from pathlib import Path

# Ensure project root is on sys.path so `governance` is importable
# whether or not the package is installed in editable mode.
sys.path.insert(0, str(Path(__file__).parent.parent))
