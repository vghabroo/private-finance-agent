from app.finance.service import FinanceService
from app.storage.database import connect
from app.storage.repository import TransactionRepository
from app.agent.watcher import run_watcher


def setup_function():
    with connect() as conn:
        conn.execute("DELETE FROM transactions")
        conn.execute("DELETE FROM budgets")
        conn.execute("DELETE FROM agent_insights")


def test_set_and_list_budgets():
    service = FinanceService()
    service.set_budget("Food", 5000)

    budgets = service.list_budgets()
    assert {"category": "Food", "monthly_amount": 5000.0} in budgets


def test_all_budget_status_reports_over_budget():
    repo = TransactionRepository()
    repo.insert_many([
        {"txn_date": "2026-08-01", "merchant": "Cafe", "amount_cents": 600000,
         "txn_type": "debit", "category": "Food", "source": "test", "source_id": "b1"},
    ])
    service = FinanceService(repo)
    service.set_budget("Food", 5000)

    status = service.all_budget_status(2026, 8)
    food = next(x for x in status if x["category"] == "Food")
    assert food["spent"] == 6000
    assert food["over_budget"] is True


def _seed_for_watcher():
    # 7 baseline debits (~Rs.300) + a recurring Netflix pair + one very large
    # outlier. With only a handful of points, a single outlier's z-score is
    # mathematically capped at sqrt(n-1) (all mass concentrated in one
    # point) -- n needs to be large enough that sqrt(n-1) clears the
    # detector's 2.5 threshold. n=10 here (max ~3.0) comfortably does.
    repo = TransactionRepository()
    repo.insert_many([
        {"txn_date": "2026-08-01", "merchant": "Cafe A", "amount_cents": 29000,
         "txn_type": "debit", "category": "Food", "source": "test", "source_id": "w1"},
        {"txn_date": "2026-08-02", "merchant": "Cafe B", "amount_cents": 30000,
         "txn_type": "debit", "category": "Food", "source": "test", "source_id": "w2"},
        {"txn_date": "2026-08-03", "merchant": "Cafe C", "amount_cents": 31000,
         "txn_type": "debit", "category": "Food", "source": "test", "source_id": "w3"},
        {"txn_date": "2026-08-04", "merchant": "Cafe D", "amount_cents": 29500,
         "txn_type": "debit", "category": "Food", "source": "test", "source_id": "w4"},
        {"txn_date": "2026-08-05", "merchant": "Cafe E", "amount_cents": 30500,
         "txn_type": "debit", "category": "Food", "source": "test", "source_id": "w5"},
        {"txn_date": "2026-08-06", "merchant": "Cafe F", "amount_cents": 30000,
         "txn_type": "debit", "category": "Food", "source": "test", "source_id": "w6"},
        {"txn_date": "2026-08-07", "merchant": "Cafe G", "amount_cents": 30000,
         "txn_type": "debit", "category": "Food", "source": "test", "source_id": "w7"},
        {"txn_date": "2026-08-08", "merchant": "Electronics Store", "amount_cents": 20000000,
         "txn_type": "debit", "category": "Shopping", "source": "test", "source_id": "w8"},
        {"txn_date": "2026-08-09", "merchant": "Netflix", "amount_cents": 50000,
         "txn_type": "debit", "category": "Subscriptions", "source": "test", "source_id": "w9"},
        {"txn_date": "2026-09-09", "merchant": "Netflix", "amount_cents": 50000,
         "txn_type": "debit", "category": "Subscriptions", "source": "test", "source_id": "w10"},
    ])


def test_watcher_writes_anomaly_and_recurring_once():
    _seed_for_watcher()

    first = run_watcher()
    types = {item["type"] for item in first["new_insights"]}
    assert "anomaly" in types
    assert "recurring" in types

    second = run_watcher()
    assert second["new_insights"] == []
