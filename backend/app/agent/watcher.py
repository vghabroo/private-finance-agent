"""Watcher agent: scans deterministic detectors and records new findings.

Meant to run nightly (see main.py's scheduler) or on demand via
POST /api/insights/run. Writes are deduplicated by a stable key so re-runs
don't spam the insights table with the same finding.
"""
from datetime import date

from app.finance.service import FinanceService
from app.storage.repository import TransactionRepository


def run_watcher(repository: TransactionRepository | None = None) -> dict:
    repo = repository or TransactionRepository()
    service = FinanceService(repo)

    written = []

    for item in service.anomalies()["anomalies"]:
        key = f"anomaly:{item['date']}:{item['merchant']}:{item['amount']}"
        if repo.insight_exists(key):
            continue
        detail = (
            f"Unusually large {item['category']} charge of Rs.{item['amount']:.2f} "
            f"at {item['merchant']} on {item['date']} (z={item['z_score']})."
        )
        repo.insert_insight("anomaly", detail, key, item["date"])
        written.append({"type": "anomaly", "detail": detail})

    for item in service.recurring():
        key = f"recurring:{item['merchant']}:{item['amount']}"
        if repo.insight_exists(key):
            continue
        detail = (
            f"Recurring charge detected: Rs.{item['amount']:.2f} at {item['merchant']} "
            f"({item['occurrences']} times, last on {item['last_date']})."
        )
        repo.insert_insight("recurring", detail, key, item["last_date"])
        written.append({"type": "recurring", "detail": detail})

    return {"scanned_on": date.today().isoformat(), "new_insights": written}
