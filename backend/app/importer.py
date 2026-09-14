import csv
import hashlib
from datetime import date, datetime
from io import StringIO


REQUIRED_COLUMNS = {"date", "merchant", "amount", "type", "category"}


def parse_csv(data: bytes) -> list[dict]:
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ValueError("CSV must be UTF-8 encoded.") from exc

    reader = csv.DictReader(StringIO(text))
    if not reader.fieldnames:
        raise ValueError("CSV is empty.")

    columns = {x.strip().lower() for x in reader.fieldnames}
    missing = REQUIRED_COLUMNS - columns
    if missing:
        raise ValueError(f"Missing required columns: {sorted(missing)}")

    result = []
    for row_number, raw in enumerate(reader, start=2):
        row = {(k or "").strip().lower(): (v or "").strip() for k, v in raw.items()}

        try:
            txn_date = date.fromisoformat(row["date"])
            amount = float(row["amount"].replace(",", "").replace("₹", "").strip())
            if amount < 0:
                raise ValueError("amount must be non-negative")

            txn_type = row["type"].lower()
            if txn_type not in {"debit", "credit"}:
                raise ValueError("type must be debit or credit")

            merchant = row["merchant"] or "Unknown"
            category = row["category"] or "Uncategorized"
            description = row.get("description") or None

            source_id = hashlib.sha256(
                f"{txn_date.isoformat()}|{merchant.lower()}|{amount:.2f}|"
                f"{txn_type}|{description or ''}".encode()
            ).hexdigest()

            result.append({
                "txn_date": txn_date.isoformat(),
                "merchant": merchant,
                "amount_cents": round(amount * 100),
                "currency": row.get("currency") or "INR",
                "txn_type": txn_type,
                "category": category,
                "account_last4": row.get("account_last4") or None,
                "description": description,
                "source": "csv",
                "source_id": source_id,
            })
        except (KeyError, ValueError) as exc:
            raise ValueError(f"Invalid row {row_number}: {exc}") from exc

    return result
