from app.ai_service import (
    analyze_request,
    simulate_ai,
    _score_category,
    _score_priority,
    AnalysisResult,
)


def test_rule_engine_category_account_access():
    result = simulate_ai("Mein Benutzerkonto ist gesperrt und ich kann mich nicht anmelden.")
    assert result.category == "account_access"


def test_rule_engine_category_incident():
    result = simulate_ai("Seit heute Morgen ist das Produktivsystem nicht erreichbar.")
    assert result.category == "incident"


def test_rule_engine_category_billing():
    result = simulate_ai("Wie kann ich meine Rechnungsadresse ändern?")
    assert result.category == "billing"


def test_rule_engine_category_how_to():
    result = simulate_ai("Wie kann ich ein neues Projekt anlegen?")
    assert result.category == "how_to"


def test_rule_engine_priority_critical():
    result = simulate_ai("Das Produktivsystem ist komplett ausgefallen, alle Nutzer sind betroffen.")
    assert result.priority == "critical"


def test_rule_engine_team_mapping():
    result = simulate_ai("Mein Benutzerkonto ist gesperrt.")
    assert result.assigned_team == "identity-operations"


def test_rule_engine_manual_review_required():
    result = simulate_ai("Seit heute ist das Produktivsystem komplett nicht erreichbar, alle Nutzer betroffen.")
    assert result.status == "manual_review_required"


def test_rule_engine_default_status_open():
    result = simulate_ai("Wie kann ich meine Rechnungsadresse ändern?")
    assert result.status == "open"


def test_analyze_request_uses_simulated_when_provider_set():
    result = analyze_request("Mein Konto ist gesperrt.")
    assert isinstance(result, AnalysisResult)
    assert result.category == "account_access"


def test_score_category_general_fallback():
    category, score = _score_category("Hallo, ich brauche Hilfe bei etwas ganz anderem.")
    assert category == "general"
    assert score == 0


def test_score_priority_default_low():
    assert _score_priority("Das Wetter ist heute schön.") == "low"
