# tests/conftest.py
import sys
import os

# Ensure `governance` package is importable when pytest runs from this directory
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
