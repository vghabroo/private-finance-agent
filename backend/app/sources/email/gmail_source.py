from datetime import date

from app.agent.categorizer import categorize_merchant
from app.sources.email.gmail_client import GmailClient, extract_fields
from app.sources.email.parsers import PARSERS


class GmailTransactionSource:
    """TransactionSource backed by Gmail transaction-alert emails.

    Each email is run through the deterministic parser registry only — no
    email content is ever sent to the local LLM. The LLM is only reached
    (via categorize_merchant) with a bare merchant string, after parsing.
    """

    def __init__(self, client: GmailClient, query: str, max_results: int):
        self.client = client
        self.query = query
        self.max_results = max_results

    def fetch(self) -> dict:
        message_ids = self.client.list_message_ids(self.query, self.max_results)
        transactions = []
        unparsed = 0

        for message_id in message_ids:
            fields = extract_fields(self.client.get_message(message_id))

            parsed = None
            for parser in PARSERS:
                parsed = parser.try_parse(fields["subject"], fields["body"])
                if parsed:
                    break

            if not parsed:
                unparsed += 1
                continue

            txn_date = parsed.get("txn_date") or date.fromtimestamp(
                fields["internal_date_ms"] / 1000
            ).isoformat()
            merchant = parsed["merchant"]
            category, confidence, evidence = categorize_merchant(merchant, parsed.get("description"))

            transactions.append({
                "txn_date": txn_date,
                "merchant": merchant,
                "amount_cents": parsed["amount_cents"],
                "currency": "INR",
                "txn_type": parsed["txn_type"],
                "category": category,
                "category_confidence": confidence,
                "category_source": evidence,
                "account_last4": parsed.get("account_last4"),
                "description": parsed.get("description"),
                "source": "gmail",
                "source_id": f"gmail:{fields['id']}",
            })

        return {"transactions": transactions, "unparsed": unparsed, "scanned": len(message_ids)}
