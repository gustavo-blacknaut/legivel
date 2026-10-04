import re

from app.ocr.base import TextBox
from app.parsers.base import DocumentParser, ExtractedField, FieldDefinition, combine_sides, is_placeholder
from app.parsers.common import (
    CPF_PATTERN,
    STATES,
    as_cpf,
    as_date,
    as_name,
    clean_name,
    extract_optional_fields,
    find_issuing_authority,
    first_present,
    has_cpf,
    has_date,
    looks_like_name,
    with_value,
)
from app.parsers.layout import find_label, find_value, lines_below, normalize, search_pattern
from app.parsers.registry import register
from app.validators.rules import DocumentRules

RG_NUMBER_PATTERN = re.compile(
    rf"(?:\b(?:{STATES})\s*-?\s*)?\d{{1,2}}\.?\d{{3}}\.?\d{{3}}(?:\s*-\s*[\dX]|(?<=\d)[\dX](?!\d))?|\b\d{{5,14}}\b"
)
AUTHORITY_VALUE_PATTERN = re.compile(rf"^[A-Z]{{2,10}}(?:\s*[-/]?\s*(?:{STATES}))?$")
STATES_WITH_MOTHER_FIRST = {"MINAS GERAIS"}
BLOOD_TYPE_PATTERN = re.compile(r"^(A|B|AB|O|0)s*(RH)?s*([+-]|POS|NEG|POSITIVO|NEGATIVO)$")
STATE_HEADER_PATTERN = re.compile(r"ESTADO D[EOA] ([A-Z ]+)")

LABELS = {
    "rg_number": ("REGISTRO GERAL", "REG. GERAL", "REG GERAL", "N DO RG", "RG"),
    "issue_date": ("DATA DE EXPEDICAO", "DATA EXPEDICAO", "EXPEDICAO", "DATA DE EMISSAO"),
    "full_name": ("NOME", "NOME SOCIAL"),
    "filiation": ("FILIACAO",),
    "birthplace": ("NATURALIDADE", "LOCAL DE NASCIMENTO"),
    "birth_date": ("DATA DE NASCIMENTO", "DATA NASCIMENTO", "NASCIMENTO"),
    "issuing_authority": ("ORGAO EXPEDIDOR", "ORG. EXPEDIDOR", "ORGAO EMISSOR"),
    "cpf": ("CPF", "C.P.F."),
}
OPTIONAL_LABELS = {
    "dni": ("DNI",),
    "blood_type": ("FATOR RH", "TIPO SANGUINEO"),
    "civil_registry": ("REGISTRO CIVIL", "DOC. ORIGEM", "DOC ORIGEM", "DOCUMENTO DE ORIGEM"),
    "voter_id": ("T. ELEITOR / ZONA / SECAO", "T. ELEITOR", "TITULO DE ELEITOR", "TITULO ELEITOR"),
    "work_card": ("CTPS / SERIE / UF", "CTPS"),
    "nis_pis": ("NIS / PIS / PASEP", "NIS/PIS/PASEP", "PIS/PASEP", "NIS"),
    "health_card": ("CNS", "CARTAO NACIONAL DE SAUDE"),
    "driver_license": ("CNH",),
    "military_certificate": ("CERT. MILITAR", "CERTIFICADO MILITAR", "CERT MILITAR"),
    "professional_id": ("IDENTIDADE PROFISSIONAL",),
}
OTHER_LABELS = (
    "ASSINATURA DO DIRETOR",
    "ASSINATURA DO TITULAR",
    "DIRETOR DO INSTITUTO DE IDENTIFICACAO",
    "VALIDA EM TODO O TERRITORIO NACIONAL",
    "LEI",
    "POLEGAR DIREITO",
    "SEXO",
    "NACIONALIDADE",
    "CARTEIRA DE IDENTIDADE",
    "REPUBLICA FEDERATIVA DO BRASIL",
    "INSTITUTO DE IDENTIFICACAO",
    "ZONA",
    "SECAO",
    "SEC",
    "SERIE",
    "UF",
)
ALL_LABELS = (
    tuple(variant for variants in LABELS.values() for variant in variants)
    + tuple(variant for variants in OPTIONAL_LABELS.values() for variant in variants)
    + OTHER_LABELS
)


def accepts_rg_number(text: str) -> bool:
    return RG_NUMBER_PATTERN.search(normalize(text)) is not None and not has_cpf(text) and not has_date(text)


def extract_rg_number(field: ExtractedField | None) -> ExtractedField | None:
    if field is None:
        return None
    match = RG_NUMBER_PATTERN.search(normalize(field.value))
    return with_value(field, re.sub(r"\s", "", match.group(0))) if match else None


def accepts_birthplace(text: str) -> bool:
    return len(text.strip()) >= 3 and not has_date(text) and not any(char.isdigit() for char in text)


def accepts_authority(text: str) -> bool:
    return AUTHORITY_VALUE_PATTERN.match(normalize(text)) is not None


def accepts_optional(text: str) -> bool:
    return len(text.strip()) >= 2 and not has_date(text) and not is_placeholder(text)


def normalize_authority(field: ExtractedField | None) -> ExtractedField | None:
    if field is None:
        return None
    return with_value(field, find_issuing_authority(field.value) or normalize(field.value))


def detect_state(boxes: list[TextBox]) -> str | None:
    for box in boxes:
        match = STATE_HEADER_PATTERN.search(normalize(box.text))
        if match:
            return match.group(1).strip()
    return None


@register
class RgParser(DocumentParser):
    doc_type = "rg"
    display_name = "RG (Carteira de Identidade)"
    keywords = {
        "CARTEIRA DE IDENTIDADE": 3,
        "REGISTRO GERAL": 3,
        "INSTITUTO DE IDENTIFICACAO": 2,
        "LEI N 7.116": 2,
        "POLEGAR DIREITO": 1,
        "FILIACAO": 1,
        "NATURALIDADE": 1,
        "DOC. ORIGEM": 1,
    }
    field_definitions = (
        FieldDefinition("full_name", "Nome completo"),
        FieldDefinition("rg_number", "Número do RG"),
        FieldDefinition("issuing_authority", "Órgão expedidor"),
        FieldDefinition("issue_date", "Data de expedição", "date"),
        FieldDefinition("birth_date", "Data de nascimento", "date"),
        FieldDefinition("birthplace", "Naturalidade"),
        FieldDefinition("mother_name", "Filiação (mãe)", "parent"),
        FieldDefinition("father_name", "Filiação (pai)", "parent"),
        FieldDefinition("cpf", "CPF", "cpf"),
        FieldDefinition("dni", "DNI", "extra"),
        FieldDefinition("blood_type", "Fator RH", "extra"),
        FieldDefinition("civil_registry", "Registro civil / doc. origem", "extra"),
        FieldDefinition("voter_id", "Título de eleitor", "extra"),
        FieldDefinition("work_card", "CTPS", "extra"),
        FieldDefinition("nis_pis", "NIS / PIS / PASEP", "extra"),
        FieldDefinition("health_card", "CNS", "extra"),
        FieldDefinition("driver_license", "CNH", "extra"),
        FieldDefinition("military_certificate", "Certificado militar", "extra"),
        FieldDefinition("professional_id", "Identidade profissional", "extra"),
        FieldDefinition("issuing_state", "Estado emissor", "extra"),
    )
    rules = DocumentRules(
        required_fields=("full_name", "rg_number", "birth_date"),
        cpf_fields=("cpf",),
        past_date_fields=("birth_date", "issue_date"),
        ordered_dates=(("birth_date", "issue_date"),),
    )

    def extract(self, front: list[TextBox], back: list[TextBox]) -> dict[str, ExtractedField]:
        boxes = combine_sides(front, back)
        state = detect_state(boxes)
        fields: dict[str, ExtractedField | None] = {
            "full_name": as_name(find_value(boxes, LABELS["full_name"], ALL_LABELS, looks_like_name)),
            "rg_number": extract_rg_number(
                find_value(boxes, LABELS["rg_number"], ALL_LABELS, accepts_rg_number, prefer="right")
            ),
            "issue_date": as_date(find_value(boxes, LABELS["issue_date"], ALL_LABELS, has_date, prefer="right")),
            "birth_date": as_date(find_value(boxes, LABELS["birth_date"], ALL_LABELS, has_date)),
            "birthplace": find_value(boxes, LABELS["birthplace"], ALL_LABELS, accepts_birthplace),
            "cpf": as_cpf(
                first_present(
                    find_value(boxes, LABELS["cpf"], ALL_LABELS, has_cpf, prefer="right"),
                    search_pattern(boxes, CPF_PATTERN),
                )
            ),
            "issuing_authority": normalize_authority(
                first_present(
                    find_value(boxes, LABELS["issuing_authority"], ALL_LABELS, accepts_authority),
                    self.authority_anywhere(boxes),
                )
            ),
        }
        fields.update(extract_optional_fields(boxes, OPTIONAL_LABELS, ALL_LABELS, accepts_optional))
        fields["blood_type"] = find_value(boxes, OPTIONAL_LABELS["blood_type"], ALL_LABELS, accepts_blood_type)
        fields.update(self.extract_filiation(boxes, mother_first=state in STATES_WITH_MOTHER_FIRST))
        if state:
            fields["issuing_state"] = ExtractedField(state, 1.0)
        return {name: value for name, value in fields.items() if value}

    @staticmethod
    def authority_anywhere(boxes: list[TextBox]) -> ExtractedField | None:
        for box in boxes:
            found = find_issuing_authority(box.text)
            if found:
                return ExtractedField(found, box.confidence, box)
        return None

    @staticmethod
    def extract_filiation(boxes: list[TextBox], mother_first: bool) -> dict[str, ExtractedField | None]:
        if find_label(boxes, LABELS["filiation"]) is None:
            return {}
        lines = lines_below(boxes, LABELS["filiation"], ALL_LABELS, limit=4)
        parents = [ExtractedField(clean_name(box.text), box.confidence, box) for box in lines if looks_like_name(box.text)][:2]
        if len(parents) == 1:
            return {"mother_name": parents[0]}
        if len(parents) == 2:
            first, second = parents
            if mother_first:
                return {"mother_name": first, "father_name": second}
            return {"father_name": first, "mother_name": second}
        return {}


def accepts_blood_type(text: str) -> bool:
    return BLOOD_TYPE_PATTERN.match(normalize(text).replace(" ", "")) is not None
