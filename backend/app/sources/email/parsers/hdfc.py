"""Deterministic parser for HDFC Bank transaction-alert emails.

No LLM is involved here by design: email text stays out of any model's
context entirely, and only the structured fields extracted below ever reach
the rest of the app.
"""
import re
from datetime import datetime

SENDER_HINT = "hdfcbank"

_AMOUNT = r"Rs\.?\s*([\d,]+\.\d{2})"

CC_DEBIT_RE = re.compile(
    _AMOUNT + r"\s+has\s+been\s+debited\s+from\s+your\s+HDFC\s+Bank\s+Credit\s+Card",
    re.IGNORECASE,
)
CC_MERCHANT_RE = re.compile(r"\bat\s+([A-Za-z0-9&._' -]{2,60}?)\s+on\b", re.IGNORECASE)
CC_ACCOUNT_RE = re.compile(r"\bending\s+([\d*]{2,8})\b", re.IGNORECASE)
GENERIC_DATE_RE = re.compile(r"\bon\s+(\d{2}-\d{2}-\d{2,4})\b")

UPI_RE = re.compile(
    _AMOUNT + r"\s+is\s+(debited|credited)\s+(?:from|to)\s+your\s+account"
    r"\s+ending\s+([\d*]{2,8})\s+towards\s+VPA\s+([^\s,]+)",
    re.IGNORECASE,
)


def _parse_amount(raw: str) -> int:
    return round(float(raw.replace(",", "")) * 100)


def _parse_date(raw: str | None) -> str | None:
    if not raw:
        return None
    for fmt in ("%d-%m-%y", "%d-%m-%Y"):
        try:
            return datetime.strptime(raw, fmt).date().isoformat()
        except ValueError:
            continue
    return None


def _last4(raw: str | None) -> str | None:
    if raw and raw.isdigit():
        return raw[-4:]
    return None


def try_parse(subject: str, body: str) -> dict | None:
    text = f"{subject}\n{body}"

    upi = UPI_RE.search(text)
    if upi:
        amount_raw, direction, account, vpa = upi.groups()
        date_match = GENERIC_DATE_RE.search(text)
        is_debit = direction.lower() == "debited"
        return {
            "amount_cents": _parse_amount(amount_raw),
            "txn_type": "debit" if is_debit else "credit",
            "merchant": vpa.split("@")[0] or vpa,
            "account_last4": _last4(account),
            "txn_date": _parse_date(date_match.group(1) if date_match else None),
            "description": f"UPI {'to' if is_debit else 'from'} {vpa}",
        }

    cc_debit = CC_DEBIT_RE.search(text)
    if cc_debit:
        merchant_match = CC_MERCHANT_RE.search(text)
        account_match = CC_ACCOUNT_RE.search(text)
        date_match = GENERIC_DATE_RE.search(text)
        return {
            "amount_cents": _parse_amount(cc_debit.group(1)),
            "txn_type": "debit",
            "merchant": (merchant_match.group(1).strip() if merchant_match else "HDFC Credit Card"),
            "account_last4": _last4(account_match.group(1) if account_match else None),
            "txn_date": _parse_date(date_match.group(1) if date_match else None),
            "description": "HDFC Bank Credit Card transaction",
        }

    return None
