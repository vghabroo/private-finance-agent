from __future__ import annotations

from datetime import date
from app.storage.database import connect


def transaction_from_row(row):
    result = dict(row)
    result["amount"] = result.pop("amount_cents") / 100
    return result


class TransactionRepository:
    def insert_many(self, transactions: list[dict]) -> dict:
        inserted = 0
        skipped = 0
        errors = []

        with connect() as conn:
            for item in transactions:
                try:
                    cursor = conn.execute(
                        '''
                        INSERT OR IGNORE INTO transactions
                        (txn_date, merchant, amount_cents, currency, txn_type, category,
                         category_confidence, category_source, account_last4, description,
                         source, source_id)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        ''',
                        (
                            item["txn_date"],
                            item["merchant"],
                            item["amount_cents"],
                            item.get("currency", "INR"),
                            item["txn_type"],
                            item["category"],
                            item.get("category_confidence"),
                            item.get("category_source"),
                            item.get("account_last4"),
                            item.get("description"),
                            item["source"],
                            item["source_id"],
                        ),
                    )
                    if cursor.rowcount:
                        inserted += 1
                    else:
                        skipped += 1
                except Exception as exc:
                    errors.append({"source_id": item.get("source_id"), "error": str(exc)})

        return {"inserted": inserted, "skipped_duplicates": skipped, "errors": errors}

    def list(
        self,
        category: str | None = None,
        start_date: date | None = None,
        end_date: date | None = None,
        limit: int = 100,
    ) -> list[dict]:
        clauses = ["1 = 1"]
        params = []

        if category:
            clauses.append("LOWER(category) = LOWER(?)")
            params.append(category)
        if start_date:
            clauses.append("txn_date >= ?")
            params.append(start_date.isoformat())
        if end_date:
            clauses.append("txn_date <= ?")
            params.append(end_date.isoformat())

        params.append(min(max(limit, 1), 5000))

        query = f'''
            SELECT id, txn_date, merchant, amount_cents, currency, txn_type, category,
                   category_confidence, category_source, account_last4, description,
                   source, source_id, created_at
            FROM transactions
            WHERE {" AND ".join(clauses)}
            ORDER BY txn_date DESC, id DESC
            LIMIT ?
        '''

        with connect() as conn:
            return [transaction_from_row(r) for r in conn.execute(query, params).fetchall()]

    def monthly_summary(self, year: int, month: int) -> dict:
        period = f"{year:04d}-{month:02d}"

        with connect() as conn:
            totals = conn.execute(
                '''
                SELECT
                  COALESCE(SUM(CASE WHEN txn_type = 'debit' THEN amount_cents ELSE 0 END), 0) spent,
                  COALESCE(SUM(CASE WHEN txn_type = 'credit' THEN amount_cents ELSE 0 END), 0) income,
                  COUNT(*) count
                FROM transactions
                WHERE substr(txn_date, 1, 7) = ?
                ''',
                (period,),
            ).fetchone()

            categories = conn.execute(
                '''
                SELECT category,
                       COALESCE(SUM(CASE WHEN txn_type = 'debit' THEN amount_cents ELSE 0 END), 0) spent,
                       COALESCE(SUM(CASE WHEN txn_type = 'credit' THEN amount_cents ELSE 0 END), 0) income,
                       COUNT(*) count
                FROM transactions
                WHERE substr(txn_date, 1, 7) = ?
                GROUP BY category
                ORDER BY spent DESC, category
                ''',
                (period,),
            ).fetchall()

        spent = totals["spent"]
        income = totals["income"]

        return {
            "period": period,
            "total_spent": spent / 100,
            "total_income": income / 100,
            "net": (income - spent) / 100,
            "transaction_count": totals["count"],
            "categories": [
                {
                    "category": row["category"],
                    "spent": row["spent"] / 100,
                    "income": row["income"] / 100,
                    "count": row["count"],
                }
                for row in categories
            ],
        }

    def category_total(self, category: str, start_date: date, end_date: date) -> dict:
        with connect() as conn:
            row = conn.execute(
                '''
                SELECT COALESCE(SUM(amount_cents), 0) total,
                       COUNT(*) count,
                       COALESCE(AVG(amount_cents), 0) average
                FROM transactions
                WHERE txn_type = 'debit'
                  AND LOWER(category) = LOWER(?)
                  AND txn_date BETWEEN ? AND ?
                ''',
                (category, start_date.isoformat(), end_date.isoformat()),
            ).fetchone()

        return {
            "category": category,
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "total": row["total"] / 100,
            "count": row["count"],
            "average": row["average"] / 100,
        }

    def set_budget(self, category: str, monthly_amount: float) -> None:
        cents = round(monthly_amount * 100)
        with connect() as conn:
            conn.execute(
                '''
                INSERT INTO budgets(category, monthly_amount_cents)
                VALUES (?, ?)
                ON CONFLICT(category)
                DO UPDATE SET monthly_amount_cents = excluded.monthly_amount_cents,
                              updated_at = CURRENT_TIMESTAMP
                ''',
                (category, cents),
            )

    def get_budget(self, category: str) -> float | None:
        with connect() as conn:
            row = conn.execute(
                "SELECT monthly_amount_cents FROM budgets WHERE LOWER(category) = LOWER(?)",
                (category,),
            ).fetchone()
        return None if row is None else row["monthly_amount_cents"] / 100

    def list_budgets(self) -> list[dict]:
        with connect() as conn:
            rows = conn.execute(
                "SELECT category, monthly_amount_cents FROM budgets ORDER BY category"
            ).fetchall()
        return [{"category": r["category"], "monthly_amount": r["monthly_amount_cents"] / 100} for r in rows]

    def insight_exists(self, dedup_key: str) -> bool:
        with connect() as conn:
            row = conn.execute(
                "SELECT 1 FROM agent_insights WHERE dedup_key = ?", (dedup_key,)
            ).fetchone()
        return row is not None

    def insert_insight(self, insight_type: str, detail: str, dedup_key: str, event_date: str) -> None:
        with connect() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO agent_insights (insight_type, detail, dedup_key, event_date) "
                "VALUES (?, ?, ?, ?)",
                (insight_type, detail, dedup_key, event_date),
            )

    def list_insights(
        self,
        unresolved_only: bool = False,
        year: int | None = None,
        month: int | None = None,
    ) -> list[dict]:
        query = "SELECT id, insight_type, detail, resolved, created_at, event_date FROM agent_insights"
        clauses = []
        params: list[str] = []
        if unresolved_only:
            clauses.append("resolved = 0")
        if year is not None and month is not None:
            clauses.append("substr(event_date, 1, 7) = ?")
            params.append(f"{year:04d}-{month:02d}")
        if clauses:
            query += " WHERE " + " AND ".join(clauses)
        query += " ORDER BY created_at DESC"
        with connect() as conn:
            return [dict(r) for r in conn.execute(query, params).fetchall()]

    def resolve_insight(self, insight_id: int) -> bool:
        with connect() as conn:
            cursor = conn.execute("UPDATE agent_insights SET resolved = 1 WHERE id = ?", (insight_id,))
        return cursor.rowcount > 0
