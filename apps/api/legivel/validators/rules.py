from dataclasses import dataclass, field
from datetime import date
from enum import StrEnum

from legivel.validators.cpf import is_valid_cpf
from legivel.validators.dates import parse_brazilian_date

MINIMUM_PLAUSIBLE_YEAR = 1900


class IssueCode(StrEnum):
    REQUIRED_MISSING = "required_missing"
    INVALID_CPF = "invalid_cpf"
    INVALID_DATE = "invalid_date"
    FUTURE_DATE = "future_date"
    DATE_ORDER = "date_order"


ISSUE_MESSAGES = {
    IssueCode.REQUIRED_MISSING: "Campo obrigatório não encontrado",
    IssueCode.INVALID_CPF: "CPF com dígito verificador inválido",
    IssueCode.INVALID_DATE: "Data em formato inválido",
    IssueCode.FUTURE_DATE: "Data no futuro",
    IssueCode.DATE_ORDER: "Data incoerente com outra data do documento",
}


@dataclass(frozen=True)
class ValidationIssue:
    field_name: str
    code: IssueCode

    @property
    def message(self) -> str:
        return ISSUE_MESSAGES[self.code]


@dataclass(frozen=True)
class DocumentRules:
    required_fields: tuple[str, ...] = ()
    cpf_fields: tuple[str, ...] = ()
    past_date_fields: tuple[str, ...] = ()
    any_date_fields: tuple[str, ...] = ()
    ordered_dates: tuple[tuple[str, str], ...] = field(default_factory=tuple)


def validate_fields(fields: dict[str, str | None], rules: DocumentRules, today: date | None = None) -> list[ValidationIssue]:
    reference = today or date.today()
    issues: list[ValidationIssue] = []
    for name in rules.required_fields:
        if not (fields.get(name) or "").strip():
            issues.append(ValidationIssue(name, IssueCode.REQUIRED_MISSING))
    for name in rules.cpf_fields:
        value = fields.get(name)
        if value and not is_valid_cpf(value):
            issues.append(ValidationIssue(name, IssueCode.INVALID_CPF))
    parsed_dates: dict[str, date] = {}
    for name in (*rules.past_date_fields, *rules.any_date_fields):
        value = fields.get(name)
        if not value:
            continue
        parsed = parse_brazilian_date(value, reference)
        if parsed is None or parsed.year < MINIMUM_PLAUSIBLE_YEAR:
            issues.append(ValidationIssue(name, IssueCode.INVALID_DATE))
            continue
        if name in rules.past_date_fields and parsed > reference:
            issues.append(ValidationIssue(name, IssueCode.FUTURE_DATE))
        parsed_dates[name] = parsed
    for earlier, later in rules.ordered_dates:
        if earlier in parsed_dates and later in parsed_dates and parsed_dates[earlier] > parsed_dates[later]:
            issues.append(ValidationIssue(later, IssueCode.DATE_ORDER))
    return issues
