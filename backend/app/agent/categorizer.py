"""Categorizer agent: rules first, tiny local-model fallback second.

Only a bare merchant string (and optional short description) ever reaches
the model here — never raw transaction/account data.
"""
import httpx

from app.core.config import get_settings

CATEGORIES = [
    "Food", "Groceries", "Transport", "Shopping", "Entertainment",
    "Bills & Utilities", "Health", "Housing", "Travel", "Income",
    "Transfers", "Subscriptions", "Uncategorized",
]

RULES: list[tuple[str, str]] = [
    ("swiggy", "Food"), ("zomato", "Food"), ("cafe", "Food"), ("restaurant", "Food"),
    ("starbucks", "Food"), ("dominos", "Food"), ("pizza", "Food"),
    ("bigbasket", "Groceries"), ("blinkit", "Groceries"), ("zepto", "Groceries"),
    ("dmart", "Groceries"), ("grocery", "Groceries"), ("grofers", "Groceries"),
    ("uber", "Transport"), ("ola", "Transport"), ("rapido", "Transport"), ("petrol", "Transport"),
    ("fuel", "Transport"), ("irctc", "Transport"), ("metro", "Transport"),
    ("amazon", "Shopping"), ("flipkart", "Shopping"), ("myntra", "Shopping"), ("ajio", "Shopping"),
    ("netflix", "Subscriptions"), ("spotify", "Subscriptions"), ("prime video", "Subscriptions"),
    ("hotstar", "Subscriptions"), ("youtube premium", "Subscriptions"),
    ("electricity", "Bills & Utilities"), ("broadband", "Bills & Utilities"), ("airtel", "Bills & Utilities"),
    ("jio", "Bills & Utilities"), ("gas bill", "Bills & Utilities"), ("water bill", "Bills & Utilities"),
    ("pharmacy", "Health"), ("hospital", "Health"), ("apollo", "Health"), ("clinic", "Health"),
    ("rent", "Housing"), ("landlord", "Housing"), ("maintenance", "Housing"),
    ("makemytrip", "Travel"), ("indigo", "Travel"), ("airbnb", "Travel"), ("oyo", "Travel"),
    ("salary", "Income"), ("payroll", "Income"),
]


def _rule_match(merchant: str, description: str | None) -> str | None:
    haystack = f"{merchant} {description or ''}".lower()
    for keyword, category in RULES:
        if keyword in haystack:
            return category
    return None


def categorize_merchant(merchant: str, description: str | None = None) -> tuple[str, float, str]:
    """Returns (category, confidence, evidence). evidence is 'rule'|'model'|'fallback'."""
    rule_category = _rule_match(merchant, description)
    if rule_category:
        return rule_category, 1.0, "rule"

    model_category = _ask_model(merchant, description)
    if model_category:
        return model_category, 0.6, "model"

    return "Uncategorized", 0.0, "fallback"


def _ask_model(merchant: str, description: str | None) -> str | None:
    settings = get_settings()
    prompt = (
        "Classify this transaction merchant into exactly one category from this list: "
        f"{', '.join(CATEGORIES)}.\n"
        f"Merchant: {merchant}\n"
        f"Note: {description or 'none'}\n"
        "Reply with only the category name, nothing else."
    )
    try:
        response = httpx.post(
            f"{settings.ollama_base_url.rstrip('/')}/api/chat",
            json={
                "model": settings.ollama_categorizer_model,
                "messages": [{"role": "user", "content": prompt}],
                "stream": False,
                "think": False,
            },
            timeout=settings.ollama_timeout_seconds,
        )
        response.raise_for_status()
        content = response.json().get("message", {}).get("content", "").strip()
    except httpx.HTTPError:
        return None

    for category in CATEGORIES:
        if category.lower() == content.lower():
            return category
    return None
