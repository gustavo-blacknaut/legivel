from datetime import date

from app.validators.rules import DocumentRules, IssueCode, validate_fields

TODAY = date(2026, 10, 2)
CNH_LIKE_RULES = DocumentRules(
    required_fields=("full_name", "cpf"),
    cpf_fields=("cpf",),
    past_date_fields=("birth_date", "first_license_date"),
    any_date_fields=("valid_until",),
    ordered_dates=(("birth_date", "first_license_date"), ("first_license_date", "valid_until")),
)


def issue_codes(fields):
    return {(issue.field_name, issue.code) for issue in validate_fields(fields, CNH_LIKE_RULES, TODAY)}


def test_valid_document_has_no_issues():
    fields = {
        "full_name": "MARIA DA SILVA",
        "cpf": "529.982.247-25",
        "birth_date": "10/05/1985",
        "first_license_date": "20/08/2005",
        "valid_until": "20/08/2030",
    }
    assert issue_codes(fields) == set()


def test_detects_missing_required_fields():
    assert issue_codes({"full_name": "  "}) == {
        ("full_name", IssueCode.REQUIRED_MISSING),
        ("cpf", IssueCode.REQUIRED_MISSING),
    }


def test_detects_invalid_cpf():
    assert ("cpf", IssueCode.INVALID_CPF) in issue_codes({"full_name": "X", "cpf": "529.982.247-20"})


def test_detects_invalid_and_future_dates():
    codes = issue_codes({"full_name": "X", "cpf": "52998224725", "birth_date": "31/02/1990", "first_license_date": "01/01/2027"})
    assert ("birth_date", IssueCode.INVALID_DATE) in codes
    assert ("first_license_date", IssueCode.FUTURE_DATE) in codes


def test_future_validity_is_allowed():
    assert issue_codes({"full_name": "X", "cpf": "52998224725", "valid_until": "01/01/2031"}) == set()


def test_detects_date_order_violation():
    codes = issue_codes(
        {"full_name": "X", "cpf": "52998224725", "birth_date": "10/05/2000", "first_license_date": "10/05/1999"}
    )
    assert ("first_license_date", IssueCode.DATE_ORDER) in codes


def test_issue_has_portuguese_message():
    issue = validate_fields({}, DocumentRules(required_fields=("cpf",)), TODAY)[0]
    assert issue.message == "Campo obrigatório não encontrado"
