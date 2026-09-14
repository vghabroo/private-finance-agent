import os
import tempfile
from pathlib import Path

# Must run at import time, before any `app.*` module is imported by a test
# file, since Settings() reads FINANCE_DATABASE_PATH lazily on first
# get_settings() call and caches it for the process. Without this, tests hit
# the real backend/data/finance.db and wipe it (setup_function() in
# test_finance.py does `DELETE FROM transactions`).
_tmp_dir = tempfile.mkdtemp(prefix="finance-agent-tests-")
os.environ["FINANCE_DATABASE_PATH"] = str(Path(_tmp_dir) / "test.db")
