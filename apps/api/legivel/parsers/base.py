import unicodedata
from abc import ABC, abstractmethod
from dataclasses import dataclass, field, replace

from legivel.ocr.base import TextBox
from legivel.validators.rules import DocumentRules, validate_fields

SIDE_OFFSET = 100_000.0
EMPTY_PLACEHOLDERS = {"*", "-", "—", "X"}


@dataclass
class ExtractedField:
    value: str
    confidence: float | None
    box: TextBox | None = None


@dataclass
class ExtractionResult:
    doc_type: str
    fields: dict[str, ExtractedField] = field(default_factory=dict)
    issues: list[dict[str, str]] = field(default_factory=list)
    raw_text: str = ""

    def values(self) -> dict[str, str]:
        return {name: extracted.value for name, extracted in self.fields.items()}


@dataclass(frozen=True)
class FieldDefinition:
    name: str
    label: str
    kind: str = "text"


def is_placeholder(text: str) -> bool:
    stripped = text.replace(" ", "")
    return not stripped or set(stripped) <= EMPTY_PLACEHOLDERS


def combine_sides(*sides: list[TextBox]) -> list[TextBox]:
    combined: list[TextBox] = []
    for index, boxes in enumerate(sides):
        offset = index * SIDE_OFFSET
        combined.extend(replace(box, y0=box.y0 + offset, y1=box.y1 + offset) for box in boxes if not is_placeholder(box.text))
    return combined


def side_of(box: TextBox) -> tuple[int, TextBox]:
    index = int(box.y0 // SIDE_OFFSET)
    offset = index * SIDE_OFFSET
    return index, replace(box, y0=box.y0 - offset, y1=box.y1 - offset)


class DocumentParser(ABC):
    doc_type: str
    display_name: str
    field_definitions: tuple[FieldDefinition, ...]
    rules: DocumentRules
    keywords: dict[str, float] = {}

    @abstractmethod
    def extract(self, front: list[TextBox], back: list[TextBox]) -> dict[str, ExtractedField]: ...

    def parse(self, front: list[TextBox], back: list[TextBox]) -> ExtractionResult:
        fields = {
            name: replace(value, value=strip_accents(value.value))
            for name, value in self.extract(front, back).items()
            if value and value.value
        }
        result = ExtractionResult(self.doc_type, fields, raw_text=build_raw_text(front, back))
        result.issues = self.validate(result.values())
        return result

    def validate(self, values: dict[str, str]) -> list[dict[str, str]]:
        return [
            {"field": issue.field_name, "code": issue.code.value, "message": issue.message}
            for issue in validate_fields(values, self.rules)
        ]

    @property
    def field_names(self) -> tuple[str, ...]:
        return tuple(definition.name for definition in self.field_definitions)


def build_raw_text(*sides: list[TextBox]) -> str:
    blocks = []
    for boxes in sides:
        ordered = sorted(boxes, key=lambda box: (round(box.center_y / max(box.height, 1)), box.x0))
        blocks.append("\n".join(box.text for box in ordered))
    return "\n\n".join(block for block in blocks if block)


def strip_accents(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text)
    return unicodedata.normalize("NFC", "".join(char for char in decomposed if not unicodedata.combining(char)))
