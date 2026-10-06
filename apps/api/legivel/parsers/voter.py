import re

from legivel.ocr.base import TextBox
from legivel.parsers.base import DocumentParser, ExtractedField, FieldDefinition, combine_sides
from legivel.parsers.common import as_date, as_name, has_date, looks_like_name, with_value
from legivel.parsers.layout import find_value, normalize, search_pattern
from legivel.parsers.registry import register
from legivel.validators.civil import is_valid_voter_id, voter_id_state
from legivel.validators.cpf import only_digits
from legivel.validators.rules import DocumentRules

VOTER_ID_PATTERN = re.compile(r"(?<!\d)\d{4}\s?\d{4}\s?\d{4}(?!\d)")
SHORT_NUMBER = re.compile(r"^\d{1,4}$")
LABELS = {
    "full_name": ("NOME DO ELEITOR", "ELEITOR", "NOME"),
    "voter_id": ("INSCRICAO", "N DE INSCRICAO", "NUMERO DE INSCRICAO"),
    "birth_date": ("DATA DE NASCIMENTO", "NASCIMENTO"),
    "zone": ("ZONA",),
    "section": ("SECAO",),
    "municipality": ("MUNICIPIO/UF", "MUNICIPIO / UF", "MUNICIPIO"),
    "issue_date": ("DATA DE EMISSAO", "EMISSAO"),
}
ALL_LABELS = tuple(variant for variants in LABELS.values() for variant in variants) + (
    "JUSTICA ELEITORAL",
    "TITULO ELEITORAL",
    "TRIBUNAL REGIONAL ELEITORAL",
    "ASSINATURA DO ELEITOR",
)


def accepts_voter_id(text: str) -> bool:
    return VOTER_ID_PATTERN.search(normalize(text)) is not None


@register
class VoterIdParser(DocumentParser):
    doc_type = "voter"
    display_name = "Título de eleitor"
    keywords = {"TITULO ELEITORAL": 5, "JUSTICA ELEITORAL": 4, "ZONA": 1, "SECAO": 1, "ELEITOR": 2}
    field_definitions = (
        FieldDefinition("full_name", "Nome do eleitor"),
        FieldDefinition("birth_date", "Data de nascimento", "date"),
        FieldDefinition("voter_id", "Número de inscrição"),
        FieldDefinition("zone", "Zona"),
        FieldDefinition("section", "Seção"),
        FieldDefinition("municipality", "Município/UF"),
        FieldDefinition("issue_date", "Data de emissão", "date"),
        FieldDefinition("voter_state", "UF da inscrição"),
    )
    rules = DocumentRules(
        required_fields=("full_name", "voter_id"),
        past_date_fields=("birth_date", "issue_date"),
        ordered_dates=(("birth_date", "issue_date"),),
    )

    def extract(self, front: list[TextBox], back: list[TextBox]) -> dict[str, ExtractedField]:
        boxes = combine_sides(front, back)
        number = find_value(boxes, LABELS["voter_id"], ALL_LABELS, accepts_voter_id) or search_pattern(boxes, VOTER_ID_PATTERN)
        if number:
            digits = only_digits(VOTER_ID_PATTERN.search(normalize(number.value)).group(0))
            number = with_value(number, f"{digits[:4]} {digits[4:8]} {digits[8:]}")
        fields: dict[str, ExtractedField | None] = {
            "full_name": as_name(find_value(boxes, LABELS["full_name"], ALL_LABELS, looks_like_name)),
            "birth_date": as_date(find_value(boxes, LABELS["birth_date"], ALL_LABELS, has_date)),
            "voter_id": number,
            "zone": find_value(boxes, LABELS["zone"], ALL_LABELS, lambda text: bool(SHORT_NUMBER.match(text.strip()))),
            "section": find_value(boxes, LABELS["section"], ALL_LABELS, lambda text: bool(SHORT_NUMBER.match(text.strip()))),
            "municipality": find_value(boxes, LABELS["municipality"], ALL_LABELS, lambda text: len(text.strip()) >= 3),
            "issue_date": as_date(find_value(boxes, LABELS["issue_date"], ALL_LABELS, has_date)),
        }
        if number and (state := voter_id_state(number.value)):
            fields["voter_state"] = ExtractedField(state, number.confidence)
        return {name: value for name, value in fields.items() if value}

    def validate(self, values: dict[str, str]) -> list[dict[str, str]]:
        issues = super().validate(values)
        if values.get("voter_id") and not is_valid_voter_id(values["voter_id"]):
            issues.append(
                {"field": "voter_id", "code": "invalid_voter_id", "message": "Dígito verificador do título não confere"}
            )
        return issues
