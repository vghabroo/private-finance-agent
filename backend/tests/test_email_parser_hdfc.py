from app.sources.email.parsers import hdfc


def test_parses_upi_debit_alert():
    body = (
        "Dear Customer, Rs.1000.00 is debited from your account ending 4321 "
        "towards VPA ravi.kumar@okhdfcbank on 24-08-26. If this transaction is "
        "not initiated by you, please call 18002586161 immediately."
    )
    result = hdfc.try_parse("You have done a UPI txn", body)

    assert result["amount_cents"] == 100000
    assert result["txn_type"] == "debit"
    assert result["merchant"] == "ravi.kumar"
    assert result["account_last4"] == "4321"
    assert result["txn_date"] == "2026-08-24"


def test_parses_upi_debit_alert_with_fully_masked_account():
    body = (
        "Rs.1000.00 is debited from your account ending **** towards VPA "
        "ravi.kumar@okhdfcbank on 24-08-26."
    )
    result = hdfc.try_parse("", body)

    assert result["amount_cents"] == 100000
    assert result["account_last4"] is None
    assert result["txn_date"] == "2026-08-24"


def test_parses_credit_card_debit_alert():
    body = (
        "We would like to inform you that Rs. 1190.53 has been debited from "
        "your HDFC Bank Credit Card ending 5566 at AMAZON RETAIL on 20-08-26."
    )
    result = hdfc.try_parse("Transaction alert", body)

    assert result["amount_cents"] == 119053
    assert result["txn_type"] == "debit"
    assert result["merchant"] == "AMAZON RETAIL"
    assert result["account_last4"] == "5566"
    assert result["txn_date"] == "2026-08-20"


def test_credit_card_alert_without_merchant_or_date_falls_back():
    body = "We would like to inform you that Rs. 1190.53 has been debited from your HDFC Bank Credit Card."
    result = hdfc.try_parse("Transaction alert", body)

    assert result["amount_cents"] == 119053
    assert result["merchant"] == "HDFC Credit Card"
    assert result["txn_date"] is None


def test_returns_none_for_unrelated_email():
    assert hdfc.try_parse("Newsletter", "Check out our new features this week!") is None
