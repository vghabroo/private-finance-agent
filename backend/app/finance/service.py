import math
from calendar import monthrange
from datetime import date, timedelta

from app.storage.repository import TransactionRepository


class FinanceService:
    def __init__(self, repository: TransactionRepository | None = None):
        self.repo = repository or TransactionRepository()

    def list_transactions(self, **kwargs):
        return self.repo.list(**kwargs)

    def monthly_summary(self, year: int, month: int):
        if not 1 <= month <= 12:
            raise ValueError("month must be between 1 and 12")
        return self.repo.monthly_summary(year, month)

    def aggregate_spending(self, category: str, start_date: str, end_date: str):
        start = date.fromisoformat(start_date)
        end = date.fromisoformat(end_date)
        if end < start:
            raise ValueError("end_date must be >= start_date")
        return self.repo.category_total(category, start, end)

    def compare_months(self, category: str, year: int, month: int):
        previous_year, previous_month = (year - 1, 12) if month == 1 else (year, month - 1)
        current = self.monthly_summary(year, month)
        previous = self.monthly_summary(previous_year, previous_month)

        def total(summary):
            return next(
                (x["spent"] for x in summary["categories"]
                 if x["category"].lower() == category.lower()),
                0,
            )

        current_value = total(current)
        previous_value = total(previous)

        return {
            "category": category,
            "current": current_value,
            "previous": previous_value,
            "change": current_value - previous_value,
            "change_percent": None if previous_value == 0 else
                round((current_value - previous_value) / previous_value * 100, 2),
        }

    def recurring(self):
        transactions = self.repo.list(limit=5000)
        groups = {}

        for txn in transactions:
            if txn["txn_type"] != "debit":
                continue
            key = (txn["merchant"].strip().lower(), round(txn["amount"], 2))
            groups.setdefault(key, []).append(txn)

        result = []
        for (_, _), items in groups.items():
            if len(items) >= 2:
                result.append({
                    "merchant": items[0]["merchant"],
                    "amount": items[0]["amount"],
                    "occurrences": len(items),
                    "first_date": min(x["txn_date"] for x in items),
                    "last_date": max(x["txn_date"] for x in items),
                })

        return sorted(result, key=lambda x: x["occurrences"], reverse=True)

    def anomalies(self, start_date: str | None = None, end_date: str | None = None):
        transactions = self.repo.list(
            start_date=date.fromisoformat(start_date) if start_date else None,
            end_date=date.fromisoformat(end_date) if end_date else None,
            limit=5000,
        )
        debits = [x for x in transactions if x["txn_type"] == "debit"]

        if len(debits) < 4:
            return {"method": "z-score", "threshold": 2.5, "anomalies": []}

        values = [x["amount"] for x in debits]
        mean = sum(values) / len(values)
        std = math.sqrt(sum((x - mean) ** 2 for x in values) / len(values))

        if std == 0:
            return {"method": "z-score", "threshold": 2.5, "anomalies": []}

        anomalies = []
        for txn in debits:
            z = (txn["amount"] - mean) / std
            if abs(z) >= 2.5:
                anomalies.append({
                    "date": txn["txn_date"],
                    "merchant": txn["merchant"],
                    "amount": txn["amount"],
                    "category": txn["category"],
                    "z_score": round(z, 2),
                })

        return {"method": "z-score", "threshold": 2.5, "anomalies": anomalies}

    def budget_status(self, category: str, year: int, month: int):
        summary = self.monthly_summary(year, month)
        spent = next(
            (x["spent"] for x in summary["categories"]
             if x["category"].lower() == category.lower()),
            0,
        )
        budget = self.repo.get_budget(category)

        return {
            "category": category,
            "period": summary["period"],
            "spent": spent,
            "budget": budget,
            "remaining": None if budget is None else round(budget - spent, 2),
            "over_budget": None if budget is None else spent > budget,
        }

    def forecast(self, category: str, year: int, month: int):
        months = []
        y, m = year, month

        for _ in range(3):
            m -= 1
            if m == 0:
                y -= 1
                m = 12
            summary = self.monthly_summary(y, m)
            months.append(next(
                (x["spent"] for x in summary["categories"]
                 if x["category"].lower() == category.lower()),
                0,
            ))

        return {
            "category": category,
            "historical_monthly_spend": list(reversed(months)),
            "forecast": round(sum(months) / len(months), 2),
            "method": "3-month moving average",
        }

    def propose_budget_change(self, category: str, new_amount: float):
        return {
            "action": "propose_budget_change",
            "category": category,
            "new_amount": new_amount,
            "status": "pending_confirmation",
            "message": "No budget was changed. User confirmation is required.",
        }

    def set_budget(self, category: str, monthly_amount: float):
        self.repo.set_budget(category, monthly_amount)
        return {"category": category, "monthly_amount": monthly_amount}

    def list_budgets(self):
        return self.repo.list_budgets()

    def all_budget_status(self, year: int, month: int):
        return [self.budget_status(b["category"], year, month) for b in self.repo.list_budgets()]

    def insights(self, unresolved_only: bool = False, year: int | None = None, month: int | None = None):
        return self.repo.list_insights(unresolved_only, year, month)

    def resolve_insight(self, insight_id: int):
        return self.repo.resolve_insight(insight_id)
