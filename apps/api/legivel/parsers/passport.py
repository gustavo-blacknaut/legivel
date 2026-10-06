import re

from legivel.ocr.base import TextBox
from legivel.parsers.base import DocumentParser, ExtractedField, FieldDefinition, combine_sides
from legivel.parsers.common import as_date, as_name, looks_like_name
from legivel.parsers.layout import find_value, normalize
from legivel.parsers.mrz import find_td3_lines, parse_td3
from legivel.parsers.registry import register
from legivel.validators.dates import format_brazilian_date
from legivel.validators.rules import DocumentRules

PASSPORT_NUMBER = re.compile(r"\b[A-Z]{2}\d{6}\b")
MRZ_CONFIDENCE = 0.97
LABELS = {
    "full_name": ("NOME / NAME", "NOME/NAME", "NOME"),
    "surname": ("SOBRENOME / SURNAME", "SOBRENOME/SURNAME", "SOBRENOME"),
    "passport_number": ("PASSAPORTE N", "PASSAPORTE / PASSPORT N", "PASSPORT NO"),
    "birth_date": ("DATA DE NASCIMENTO / DATE OF BIRTH", "DATA DE NASCIMENTO"),
    "issue_date": ("DATA DE EXPEDICAO / DATE OF ISSUE", "DATA DE EXPEDICAO"),
    "valid_until": ("VALIDO ATE / DATE OF EXPIRY", "VALIDO ATE"),
}
ALL_LABELS = tuple(variant for variants in LABELS.values() for variant in variants) + (
    "REPUBLICA FEDERATIVA DO BRASIL",
    "PASSAPORTE",
    "PASSPORT",
    "NACIONALIDADE / NATIONALITY",
    "SEXO / SEX",
)


@register
class PassportParser(DocumentParser):
    doc_type = "passport"
    display_name = "Passaporte"
    keywords = {"PASSAPORTE": 4, "PASSPORT": 4, "P<BRA": 6, "DATE OF EXPIRY": 2, "NATIONALITY": 2}
    field_definitions = (
        FieldDefinition("full_name", "Nome completo"),
        FieldDefinition("birth_date", "Data de nascimento", "date"),
        FieldDefinition("passport_number", "Número do passaporte"),
        FieldDefinition("nationality", "Nacionalidade"),
        FieldDefinition("issuing_country", "País emissor"),
        FieldDefinition("sex", "Sexo"),
        FieldDefinition("issue_date", "Data de expedição", "date"),
        FieldDefinition("valid_until", "Validade", "date"),
        FieldDefinition("mrz_raw", "MRZ", "multiline"),
    )
    rules = DocumentRules(
        required_fields=("full_name", "passport_number", "birth_date", "valid_until"),
        past_date_fields=("birth_date", "issue_date"),
        any_date_fields=("valid_until",),
        ordered_dates=(("birth_date", "issue_date"), ("issue_date", "valid_until")),
    )

    def extract(self, front: list[TextBox], back: list[TextBox]) -> dict[str, ExtractedField]:
        boxes = combine_sides(front, back)
        fields: dict[str, ExtractedField | None] = {
            "full_name": as_name(find_value(boxes, LABELS["full_name"], ALL_LABELS, looks_like_name)),
            "passport_number": self.passport_number(boxes),
            "birth_date": as_date(find_value(boxes, LABELS["birth_date"], ALL_LABELS, lambda text: bool(re.search(r"\d", text)))),
            "issue_date": as_date(find_value(boxes, LABELS["issue_date"], ALL_LABELS, lambda text: bool(re.search(r"\d", text)))),
            "valid_until": as_date(
                find_value(boxes, LABELS["valid_until"], ALL_LABELS, lambda text: bool(re.search(r"\d", text)))
            ),
        }
        surname = find_value(boxes, LABELS["surname"], ALL_LABELS, looks_like_name)
        if surname and fields["full_name"] and surname.value not in fields["full_name"].value:
            fields["full_name"] = ExtractedField(f"{fields['full_name'].value} {surname.value}", fields["full_name"].confidence)
        mrz = parse_td3(find_td3_lines(front + back))
        if mrz:
            confidence = MRZ_CONFIDENCE if mrz.checks_valid else 0.5
            mrz_values = {
                "full_name": f"{mrz.given_names} {mrz.surname}".strip(),
                "passport_number": mrz.passport_number,
                "nationality": mrz.nationality,
                "issuing_country": mrz.issuing_country,
                "sex": mrz.sex,
                "birth_date": format_brazilian_date(mrz.birth_date) if mrz.birth_date else "",
                "valid_until": format_brazilian_date(mrz.expiry_date) if mrz.expiry_date else "",
                "mrz_raw": mrz.raw,
            }
            for name, value in mrz_values.items():
                if value and (mrz.checks_valid or not fields.get(name)):
                    fields[name] = ExtractedField(value, confidence)
        return {name: value for name, value in fields.items() if value}

    @staticmethod
    def passport_number(boxes: list[TextBox]) -> ExtractedField | None:
        for box in boxes:
            match = PASSPORT_NUMBER.search(normalize(box.text))
            if match:
                return ExtractedField(match.group(0), box.confidence, box)
        return None
