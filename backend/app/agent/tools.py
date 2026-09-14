from datetime import date
from app.agent.categorizer import categorize_merchant as _categorize_merchant
from app.finance.service import FinanceService

SERVICE = FinanceService()


def get_month_summary(year: int, month: int):
    return SERVICE.monthly_summary(year, month)


def get_transactions(category=None, start_date=None, end_date=None, limit=100):
    return SERVICE.list_transactions(
        category=category,
        start_date=date.fromisoformat(start_date) if start_date else None,
        end_date=date.fromisoformat(end_date) if end_date else None,
        limit=limit or 100,
    )


def aggregate_spending(category, start_date, end_date):
    return SERVICE.aggregate_spending(category, start_date, end_date)


def compare_months(category, year, month):
    return SERVICE.compare_months(category, year, month)


def detect_recurring():
    return SERVICE.recurring()


def detect_anomalies(start_date=None, end_date=None):
    return SERVICE.anomalies(start_date, end_date)


def get_budget_status(category, year, month):
    return SERVICE.budget_status(category, year, month)


def forecast_month(category, year, month):
    return SERVICE.forecast(category, year, month)


def propose_budget_change(category, new_amount):
    return SERVICE.propose_budget_change(category, new_amount)


def categorize_merchant(merchant, description=None):
    category, confidence, evidence = _categorize_merchant(merchant, description)
    return {"merchant": merchant, "category": category, "confidence": confidence, "evidence": evidence}


def get_recent_insights(unresolved_only=True):
    return SERVICE.insights(unresolved_only)


FUNCTIONS = {
    "get_month_summary": get_month_summary,
    "get_transactions": get_transactions,
    "aggregate_spending": aggregate_spending,
    "compare_months": compare_months,
    "detect_recurring": detect_recurring,
    "detect_anomalies": detect_anomalies,
    "get_budget_status": get_budget_status,
    "forecast_month": forecast_month,
    "propose_budget_change": propose_budget_change,
    "categorize_merchant": categorize_merchant,
    "get_recent_insights": get_recent_insights,
}
