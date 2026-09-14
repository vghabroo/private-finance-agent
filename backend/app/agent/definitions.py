TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_month_summary",
            "description": "Get income, spending, net cash flow and category totals for a calendar month.",
            "parameters": {
                "type": "object",
                "properties": {"year": {"type": "integer"}, "month": {"type": "integer", "minimum": 1, "maximum": 12}},
                "required": ["year", "month"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_transactions",
            "description": "Search transactions using category and date filters. Use this when individual transactions are needed.",
            "parameters": {
                "type": "object",
                "properties": {
                    "category": {"type": "string"},
                    "start_date": {"type": "string"},
                    "end_date": {"type": "string"},
                    "limit": {"type": "integer", "minimum": 1, "maximum": 200},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "aggregate_spending",
            "description": "Calculate debit spending for one category over a date range.",
            "parameters": {
                "type": "object",
                "properties": {
                    "category": {"type": "string"},
                    "start_date": {"type": "string"},
                    "end_date": {"type": "string"},
                },
                "required": ["category", "start_date", "end_date"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "compare_months",
            "description": "Compare one category's spending with the previous calendar month.",
            "parameters": {
                "type": "object",
                "properties": {
                    "category": {"type": "string"},
                    "year": {"type": "integer"},
                    "month": {"type": "integer"},
                },
                "required": ["category", "year", "month"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "detect_recurring",
            "description": "Find repeated merchant and amount combinations that may indicate recurring charges.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "detect_anomalies",
            "description": "Detect unusually large debit transactions using a deterministic z-score detector.",
            "parameters": {
                "type": "object",
                "properties": {"start_date": {"type": "string"}, "end_date": {"type": "string"}},
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_budget_status",
            "description": "Check spending against a configured monthly budget.",
            "parameters": {
                "type": "object",
                "properties": {
                    "category": {"type": "string"},
                    "year": {"type": "integer"},
                    "month": {"type": "integer"},
                },
                "required": ["category", "year", "month"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "forecast_month",
            "description": "Forecast category spending using a deterministic 3-month moving average.",
            "parameters": {
                "type": "object",
                "properties": {
                    "category": {"type": "string"},
                    "year": {"type": "integer"},
                    "month": {"type": "integer"},
                },
                "required": ["category", "year", "month"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "propose_budget_change",
            "description": "Create a budget-change proposal. This tool NEVER writes or changes a budget.",
            "parameters": {
                "type": "object",
                "properties": {"category": {"type": "string"}, "new_amount": {"type": "number", "minimum": 0}},
                "required": ["category", "new_amount"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "categorize_merchant",
            "description": "Classify a merchant name into a spending category using rules first, falling back to the local model.",
            "parameters": {
                "type": "object",
                "properties": {
                    "merchant": {"type": "string"},
                    "description": {"type": "string"},
                },
                "required": ["merchant"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_recent_insights",
            "description": "Read findings previously written by the background Watcher agent (anomalies, recurring-charge changes).",
            "parameters": {
                "type": "object",
                "properties": {"unresolved_only": {"type": "boolean"}},
            },
        },
    },
]
