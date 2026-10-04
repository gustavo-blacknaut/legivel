from app.ocr.base import TextBox
from app.parsers.base import DocumentParser, ExtractedField, FieldDefinition, combine_sides
from app.parsers.common import CPF_PATTERN, as_cpf, as_date, as_name, first_present, has_cpf, has_date, looks_like_name
from app.parsers.layout import find_value, search_pattern
from app.parsers.registry import register
from app.validators.rules import DocumentRules

LABELS = {
    "cpf": ("NUMERO DE INSCRICAO", "N DE INSCRICAO", "CPF"),
    "full_name": ("NOME",),
    "birth_date": ("DATA DE NASCIMENTO", "NASCIMENTO"),
}
ALL_LABELS = tuple(variant for variants in LABELS.values() for variant in variants) + (
    "MINISTERIO DA FAZENDA",
    "RECEITA FEDERAL",
    "CADASTRO DE PESSOAS FISICAS",
)


@register
class CpfParser(DocumentParser):
    doc_type = "cpf"
    display_name = "Cartão CPF"
    keywords = {
        "CADASTRO DE PESSOAS FISICAS": 5,
        "RECEITA FEDERAL": 3,
        "NUMERO DE INSCRICAO": 2,
        "MINISTERIO DA FAZENDA": 1,
    }
    field_definitions = (
        FieldDefinition("full_name", "Nome completo"),
        FieldDefinition("cpf", "CPF", "cpf"),
        FieldDefinition("birth_date", "Data de nascimento", "date"),
    )
    rules = DocumentRules(required_fields=("full_name", "cpf"), cpf_fields=("cpf",), past_date_fields=("birth_date",))

    def extract(self, front: list[TextBox], back: list[TextBox]) -> dict[str, ExtractedField]:
        boxes = combine_sides(front, back)
        fields = {
            "full_name": as_name(find_value(boxes, LABELS["full_name"], ALL_LABELS, looks_like_name)),
            "cpf": as_cpf(
                first_present(find_value(boxes, LABELS["cpf"], ALL_LABELS, has_cpf), search_pattern(boxes, CPF_PATTERN))
            ),
            "birth_date": as_date(find_value(boxes, LABELS["birth_date"], ALL_LABELS, has_date)),
        }
        return {name: value for name, value in fields.items() if value}
