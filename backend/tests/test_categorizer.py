from app.agent.categorizer import categorize_merchant


def test_rule_based_categorization_skips_model():
    category, confidence, evidence = categorize_merchant("SWIGGY BANGALORE")
    assert category == "Food"
    assert confidence == 1.0
    assert evidence == "rule"


def test_rule_match_is_case_insensitive_and_checks_description():
    category, _, evidence = categorize_merchant("9876543210", "payment for electricity bill")
    assert category == "Bills & Utilities"
    assert evidence == "rule"
