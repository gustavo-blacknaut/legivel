import re

from legivel.ocr.base import TextBox
from legivel.parsers.base import DocumentParser, ExtractedField, FieldDefinition, combine_sides
from legivel.parsers.common import as_date, as_name, clean_name, has_date, looks_like_name
from legivel.parsers.layout import find_value, lines_below, normalize
from legivel.parsers.registry import register
from legivel.validators.civil import certificate_kind, format_certificate_number, is_plausible_certificate_number
from legivel.validators.cpf import only_digits
from legivel.validators.rules import DocumentRules

REGISTRATION_PATTERN = re.compile(r"(?:\d[\s.]?){32}")
LABELS = {
    "full_name": ("NOME", "NOME DO REGISTRADO"),
    "registration": ("MATRICULA",),
    "birth_date": ("DATA DE NASCIMENTO", "DATA DO NASCIMENTO"),
    "birthplace": ("LOCAL DE NASCIMENTO", "NATURALIDADE", "MUNICIPIO DE NASCIMENTO"),
    "filiation": ("FILIACAO", "PAIS", "FILIACAO / PAIS"),
    "registry_office": ("CARTORIO", "OFICIAL DE REGISTRO CIVIL", "SERVENTIA"),
    "issue_date": ("DATA DA EMISSAO", "EMITIDA EM"),
}
ALL_LABELS = tuple(variant for variants in LABELS.values() for variant in variants) + (
    "REPUBLICA FEDERATIVA DO BRASIL",
    "REGISTRO CIVIL DAS PESSOAS NATURAIS",
    "CERTIDAO DE NASCIMENTO",
    "CERTIDAO DE CASAMENTO",
    "AVOS",
    "SEXO",
    "OBSERVACOES",
)


def find_registration(boxes: list[TextBox]) -> ExtractedField | None:
    for box in sorted(boxes, key=lambda item: item.y0):
        match = REGISTRATION_PATTERN.search(normalize(box.text))
        if match:
            digits = only_digits(match.group(0))
            return ExtractedField(format_certificate_number(digits), box.confidence, box)
    return None


@register
class CertificateParser(DocumentParser):
    doc_type = "certificate"
    display_name = "Certidão civil"
    keywords = {"CERTIDAO DE NASCIMENTO": 6, "CERTIDAO DE CASAMENTO": 6, "REGISTRO CIVIL DAS PESSOAS NATURAIS": 4, "MATRICULA": 2}
    field_definitions = (
        FieldDefinition("full_name", "Nome"),
        FieldDefinition("birth_date", "Data de nascimento", "date"),
        FieldDefinition("birthplace", "Local de nascimento"),
        FieldDefinition("mother_name", "Filiação (mãe)", "parent"),
        FieldDefinition("father_name", "Filiação (pai)", "parent"),
        FieldDefinition("registration", "Matrícula"),
        FieldDefinition("certificate_kind", "Tipo de certidão"),
        FieldDefinition("registry_office", "Cartório"),
        FieldDefinition("issue_date", "Data de emissão", "date"),
    )
    rules = DocumentRules(required_fields=("full_name", "registration"), past_date_fields=("birth_date", "issue_date"))

    def extract(self, front: list[TextBox], back: list[TextBox]) -> dict[str, ExtractedField]:
        boxes = combine_sides(front, back)
        registration = find_registration(boxes)
        fields: dict[str, ExtractedField | None] = {
            "full_name": as_name(find_value(boxes, LABELS["full_name"], ALL_LABELS, looks_like_name)),
            "birth_date": as_date(find_value(boxes, LABELS["birth_date"], ALL_LABELS, has_date)),
            "birthplace": find_value(
                boxes, LABELS["birthplace"], ALL_LABELS, lambda text: len(text.strip()) >= 3 and not has_date(text)
            ),
            "registration": registration,
            "registry_office": find_value(boxes, LABELS["registry_office"], ALL_LABELS, lambda text: len(text.strip()) >= 5),
            "issue_date": as_date(find_value(boxes, LABELS["issue_date"], ALL_LABELS, has_date)),
        }
        if registration and (kind := certificate_kind(registration.value)):
            fields["certificate_kind"] = ExtractedField(kind, registration.confidence)
        parents = [box for box in lines_below(boxes, LABELS["filiation"], ALL_LABELS, limit=4) if looks_like_name(box.text)]
        if len(parents) >= 2:
            fields["father_name"] = ExtractedField(clean_name(parents[0].text), parents[0].confidence)
            fields["mother_name"] = ExtractedField(clean_name(parents[1].text), parents[1].confidence)
        elif parents:
            fields["mother_name"] = ExtractedField(clean_name(parents[0].text), parents[0].confidence)
        return {name: value for name, value in fields.items() if value}

    def validate(self, values: dict[str, str]) -> list[dict[str, str]]:
        issues = super().validate(values)
        if values.get("registration") and not is_plausible_certificate_number(values["registration"]):
            issues.append(
                {"field": "registration", "code": "invalid_registration", "message": "Matrícula fora do padrão de 32 dígitos"}
            )
        return issues
