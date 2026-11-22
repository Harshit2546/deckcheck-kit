"""Test setup for tests/eval: puts the repo root and this folder on sys.path so `import run_eval` works.

Called by: pytest. Calls: nothing.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
