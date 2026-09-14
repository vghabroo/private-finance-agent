SENSITIVE_KEYS = {"account_last4", "source_id", "source_message_id"}


def redact_for_model(value):
    if isinstance(value, list):
        return [redact_for_model(item) for item in value]
    if isinstance(value, dict):
        return {
            key: "[REDACTED]" if key in SENSITIVE_KEYS else redact_for_model(item)
            for key, item in value.items()
        }
    return value
