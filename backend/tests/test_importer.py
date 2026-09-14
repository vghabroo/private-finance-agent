import pytest
from app.importer import parse_csv


def test_parse_csv_normalizes_rupees():
    rows = parse_csv(
        b"date,merchant,amount,type,category\n"
        b"2026-08-01,Cafe,\"1,250.50\",debit,Food\n"
    )
    assert rows[0]["amount_cents"] == 125050


def test_parse_csv_rejects_invalid_type():
    with pytest.raises(ValueError):
        parse_csv(b"date,merchant,amount,type,category\n2026-08-01,X,10,foo,Food\n")


def test_parse_csv_requires_columns():
    with pytest.raises(ValueError):
        parse_csv(b"date,merchant,amount\n2026-08-01,X,10\n")
