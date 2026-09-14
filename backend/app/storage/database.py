import re
import sqlite3
from pathlib import Path
from app.core.config import get_settings


SCHEMA = '''
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS transactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    txn_date TEXT NOT NULL,
    merchant TEXT NOT NULL,
    amount_cents INTEGER NOT NULL CHECK(amount_cents >= 0),
    currency TEXT NOT NULL DEFAULT 'INR',
    txn_type TEXT NOT NULL CHECK(txn_type IN ('debit', 'credit')),
    category TEXT NOT NULL,
    account_last4 TEXT,
    description TEXT,
    source TEXT NOT NULL,
    source_id TEXT NOT NULL UNIQUE,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_transactions_date ON transactions(txn_date);
CREATE INDEX IF NOT EXISTS idx_transactions_category ON transactions(category);
CREATE INDEX IF NOT EXISTS idx_transactions_merchant ON transactions(merchant);

CREATE TABLE IF NOT EXISTS budgets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    category TEXT NOT NULL UNIQUE,
    monthly_amount_cents INTEGER NOT NULL CHECK(monthly_amount_cents >= 0),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS agent_insights (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    insight_type TEXT NOT NULL,
    detail TEXT NOT NULL,
    dedup_key TEXT NOT NULL UNIQUE,
    resolved INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
'''


_DATE_IN_TEXT = re.compile(r"\d{4}-\d{2}-\d{2}")


def _ensure_columns(conn: sqlite3.Connection) -> None:
    existing = {row["name"] for row in conn.execute("PRAGMA table_info(transactions)").fetchall()}
    if "category_confidence" not in existing:
        conn.execute("ALTER TABLE transactions ADD COLUMN category_confidence REAL")
    if "category_source" not in existing:
        conn.execute("ALTER TABLE transactions ADD COLUMN category_source TEXT")

    insight_columns = {row["name"] for row in conn.execute("PRAGMA table_info(agent_insights)").fetchall()}
    if "event_date" not in insight_columns:
        conn.execute("ALTER TABLE agent_insights ADD COLUMN event_date TEXT")
        # Backfill existing rows from the date already embedded in their detail text
        # (e.g. "... on 2026-08-08 (z=3.0)." or "... last on 2026-08-30)."), since
        # they were written before this column existed.
        rows = conn.execute(
            "SELECT id, detail FROM agent_insights WHERE event_date IS NULL"
        ).fetchall()
        for row in rows:
            match = _DATE_IN_TEXT.findall(row["detail"])
            if match:
                conn.execute(
                    "UPDATE agent_insights SET event_date = ? WHERE id = ?",
                    (match[-1], row["id"]),
                )


def connect() -> sqlite3.Connection:
    settings = get_settings()
    path = Path(settings.database_path)
    if not path.is_absolute():
        path = Path(__file__).resolve().parents[2] / path
    path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(SCHEMA)
    _ensure_columns(conn)
    return conn
