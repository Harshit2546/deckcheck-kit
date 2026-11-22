"""Child process for the kill test: starts a run with fake stages and dies (os._exit) when it
reaches the claim named in FAKE_KILL_AT, like `kill -9` in the demo.

Called by: tests/core/test_runner.py via subprocess. Calls: core/runner.py, tests/core/fakes.py.
Usage: python tests/core/kill_child.py <db> <run_id>
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import fakes  # noqa: E402

from core import runner, store  # noqa: E402
from core.config import load_rules  # noqa: E402

if __name__ == "__main__":
    conn = store.connect(sys.argv[1])
    runner.start(conn, load_rules(), sys.argv[2], stages=fakes.STAGES)
