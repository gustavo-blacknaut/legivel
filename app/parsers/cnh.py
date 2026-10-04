import re

from app.ocr.base import TextBox
from app.parsers.base import DocumentParser, ExtractedField, FieldDefinition, combine_sides
from app.parsers.common import (
    CPF_PATTERN,
    as_cpf,
    as_date,
    as_name,
    clean_name,
    find_issuing_authority,
    first_present,
    has_cpf,
    has_date,
    looks_like_name,
)
from app.parsers.layout import find_value, lines_below, normalize, search_pattern
from app.parsers.mrz import find_mrz_lines, parse_td1
from app.parsers.registry import register
from app.validators.dates import format_brazilian_date
from app.validators.rules import DocumentRules

REGISTER_PATTERN = re.compile(r"\b\d{11}\b")
FORMATTED_CPF = re.compile(r"\d{3}\.\d{3}\.\d{3}-\d{2}")
CATEGORY_PATTERN = re.compile(r"\b(ACC|AB|AC|AD|AE|A|B|C|D|E)\b")

LABELS = {
    "full_name": ("NOME E SOBRENOME", "2 E 1 NOME E SOBRENOME", "NOME"),
    "identity": ("DOC. IDENTIDADE/ORG. EMISSOR/UF", "4C DOC IDENTIDADE", "DOC IDENTIDADE", "DOC. IDENTIDADE"),
    "cpf": ("4D CPF", "CPF"),
    "birth_date": ("3 DATA, LOCAL E UF DE NASCIMENTO", "DATA, LOCAL E UF DE NASCIMENTO", "DATA NASCIMENTO", "DATA DE NASCIMENTO"),
    "filiation": ("FILIACAO",),
    "cnh_register": ("5 NO REGISTRO", "5 N REGISTRO","N REGISTRO", "NO REGISTRO", "N. REGISTRO", "REGISTRO"),
    "valid_until": ("4B VALIDADE", "VALIDADE"),
    "first_license_date": ("1A HABILITACAO", "1 HABILITACAO", "PRIMEIRA HABILITACAO"),
    "cnh_category": ("9 CAT HAB", "CAT. HAB.", "CAT HAB", "CATEGORIA"),
    "issue_date": ("4A DATA EMISSAO", "DATA EMISSAO", "DATA DE EMISSAO"),
}
ALL_LABELS = tuple(variant for variants in LABELS.values() for variant in variants) + (
    "PERMISSAO",
    "ACC",
    "OBSERVACOES",
    "ASSINATURA DO PORTADOR",
    "LOCAL",
    "REPUBLICA FEDERATIVA DO BRASIL",
    "CARTEIRA NACIONAL DE HABILITACAO",
)


def accepts_register(text: str) -> bool:
    return REGISTER_PATTERN.search(re.sub(r"[\s.]", "", normalize(text))) is not None and not FORMATTED_CPF.search(text)


def accepts_category(text: str) -> bool:
    return CATEGORY_PATTERN.fullmatch(normalize(text).strip()) is not None


def birthplace_from(field: ExtractedField | None) -> ExtractedField | None:
    if field is None:
        return None
    remainder = re.sub(r"^\D*\d{1,2}\s?[/.\-]\s?\d{1,2}\s?[/.\-]\s?\d{2,4}", "", field.value).strip(" ,-")
    return ExtractedField(remainder, field.confidence) if len(remainder) >= 3 else None


@register
class CnhParser(DocumentParser):
    doc_type = "cnh"
    display_name = "CNH (Carteira de Habilitação)"
    keywords = {
        "CARTEIRA NACIONAL DE HABILITACAO": 5,
        "DEPARTAMENTO NACIONAL DE TRANSITO": 3,
        "SECRETARIA NACIONAL DE TRANSITO": 3,
        "PERMISSAO": 2,
        "CAT. HAB": 2,
        "CAT HAB": 2,
        "1A HABILITACAO": 2,
        "N REGISTRO": 1,
        "DETRAN": 1,
    }
    field_definitions = (
        FieldDefinition("full_name", "Nome completo"),
        FieldDefinition("cpf", "CPF", "cpf"),
        FieldDefinition("birth_date", "Data de nascimento", "date"),
        FieldDefinition("birthplace", "Local de nascimento"),
        FieldDefinition("cnh_register", "Nº de registro"),
        FieldDefinition("cnh_category", "Categoria"),
        FieldDefinition("valid_until", "Validade", "date"),
        FieldDefinition("first_license_date", "1ª habilitação", "date"),
        FieldDefinition("issue_date", "Data de emissão", "date"),
        FieldDefinition("rg_number", "Doc. identidade"),
        FieldDefinition("issuing_authority", "Órgão emissor"),
        FieldDefinition("father_name", "Filiação (pai)", "parent"),
        FieldDefinition("mother_name", "Filiação (mãe)", "parent"),
        FieldDefinition("mrz_raw", "MRZ (verso)", "multiline"),
    )
    rules = DocumentRules(
        required_fields=("full_name", "cpf", "birth_date", "cnh_register", "valid_until"),
        cpf_fields=("cpf",),
        past_date_fields=("birth_date", "first_license_date", "issue_date"),
        any_date_fields=("valid_until",),
        ordered_dates=(("birth_date", "first_license_date"), ("first_license_date", "valid_until")),
    )

    def extract(self, front: list[TextBox], back: list[TextBox]) -> dict[str, ExtractedField]:
        boxes = combine_sides(front, back)
        birth = find_value(boxes, LABELS["birth_date"], ALL_LABELS, has_date)
        identity = find_value(boxes, LABELS["identity"], ALL_LABELS, lambda text: any(char.isdigit() for char in text))
        fields: dict[str, ExtractedField | None] = {
            "full_name": as_name(find_value(boxes, LABELS["full_name"], ALL_LABELS, looks_like_name)),
            "cpf": as_cpf(
                first_present(find_value(boxes, LABELS["cpf"], ALL_LABELS, has_cpf), search_pattern(boxes, CPF_PATTERN))
            ),
            "birth_date": as_date(birth),
            "birthplace": birthplace_from(birth),
            "cnh_register": self.register_number(find_value(boxes, LABELS["cnh_register"], ALL_LABELS, accepts_register)),
            "cnh_category": find_value(boxes, LABELS["cnh_category"], ALL_LABELS, accepts_category),
            "valid_until": as_date(find_value(boxes, LABELS["valid_until"], ALL_LABELS, has_date)),
            "first_license_date": as_date(find_value(boxes, LABELS["first_license_date"], ALL_LABELS, has_date)),
            "issue_date": as_date(find_value(boxes, LABELS["issue_date"], ALL_LABELS, has_date)),
        }
        if identity:
            number = re.search(r"\d[\d.\-X]{3,}", normalize(identity.value))
            fields["rg_number"] = ExtractedField(number.group(0), identity.confidence) if number else None
            authority = find_issuing_authority(identity.value)
            fields["issuing_authority"] = ExtractedField(authority, identity.confidence) if authority else None
        parents = [box for box in lines_below(boxes, LABELS["filiation"], ALL_LABELS, limit=4) if looks_like_name(box.text)]
        if len(parents) >= 2:
            fields["father_name"] = ExtractedField(clean_name(parents[0].text), parents[0].confidence)
            fields["mother_name"] = ExtractedField(clean_name(parents[1].text), parents[1].confidence)
        elif parents:
            fields["mother_name"] = ExtractedField(clean_name(parents[0].text), parents[0].confidence)
        self.merge_mrz(back or front, fields)
        return {name: value for name, value in fields.items() if value}

    @staticmethod
    def register_number(field: ExtractedField | None) -> ExtractedField | None:
        if field is None:
            return None
        match = REGISTER_PATTERN.search(re.sub(r"[\s.]", "", normalize(field.value)))
        return ExtractedField(match.group(0), field.confidence) if match else None

    @staticmethod
    def merge_mrz(boxes: list[TextBox], fields: dict[str, ExtractedField | None]) -> None:
        mrz = parse_td1(find_mrz_lines(boxes))
        if mrz is None:
            return
        confidence = 0.95 if mrz.checks_valid else 0.5
        fields["mrz_raw"] = ExtractedField(mrz.raw, confidence)
        if not fields.get("full_name") and mrz.given_names:
            fields["full_name"] = ExtractedField(f"{mrz.given_names} {mrz.surname}".strip(), confidence)
        if not fields.get("birth_date") and mrz.birth_date:
            fields["birth_date"] = ExtractedField(format_brazilian_date(mrz.birth_date), confidence)
        if not fields.get("valid_until") and mrz.expiry_date:
            fields["valid_until"] = ExtractedField(format_brazilian_date(mrz.expiry_date), confidence)
