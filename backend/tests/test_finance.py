from app.storage.database import connect
from app.storage.repository import TransactionRepository
from app.finance.service import FinanceService


def seed():
    repo = TransactionRepository()
    repo.insert_many([
        {"txn_date":"2026-07-01","merchant":"Salary","amount_cents":8000000,"currency":"INR","txn_type":"credit","category":"Income","source":"test","source_id":"1"},
        {"txn_date":"2026-07-02","merchant":"Rent","amount_cents":2500000,"currency":"INR","txn_type":"debit","category":"Housing","source":"test","source_id":"2"},
        {"txn_date":"2026-07-04","merchant":"Cafe","amount_cents":50000,"currency":"INR","txn_type":"debit","category":"Food","source":"test","source_id":"3"},
        {"txn_date":"2026-08-01","merchant":"Salary","amount_cents":8000000,"currency":"INR","txn_type":"credit","category":"Income","source":"test","source_id":"4"},
        {"txn_date":"2026-08-02","merchant":"Rent","amount_cents":2500000,"currency":"INR","txn_type":"debit","category":"Housing","source":"test","source_id":"5"},
        {"txn_date":"2026-08-04","merchant":"Cafe","amount_cents":90000,"currency":"INR","txn_type":"debit","category":"Food","source":"test","source_id":"6"},
    ])


def setup_function():
    with connect() as conn:
        conn.execute("DELETE FROM transactions")
        conn.execute("DELETE FROM budgets")
    seed()


def test_monthly_summary_uses_exact_money():
    service = FinanceService()
    result = service.monthly_summary(2026, 8)
    assert result["total_spent"] == 25900
    assert result["total_income"] == 80000
    assert result["net"] == 54100


def test_month_comparison():
    service = FinanceService()
    result = service.compare_months("Food", 2026, 8)
    assert result["current"] == 900
    assert result["previous"] == 500
    assert result["change_percent"] == 80
