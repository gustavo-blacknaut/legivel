from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass, field

import numpy as np

from legivel.ocr.base import OcrEngine, TextBox
from legivel.ocr.languages import AUTO, read_any_language


@dataclass(frozen=True)
class FieldSpec:
    name: str
    label: str
    kind: str = "text"


@dataclass
class FieldValue:
    value: str
    confidence: float | None = None


@dataclass
class PageOutput:
    original: bytes | None
    processed: np.ndarray | None
    original_mime: str | None
    text: str = ""
    layout: dict = field(default_factory=dict)
    width: int | None = None
    height: int | None = None


@dataclass
class CardOutput:
    brand: str | None
    last4: str | None
    holder_name: str | None
    expiry: str | None
    luhn_valid: bool
    full_number: str | None


@dataclass
class ModuleOutput:
    kind: str | None
    title: str | None
    fields: dict[str, FieldValue] = field(default_factory=dict)
    issues: list[dict[str, str]] = field(default_factory=list)
    pages: list[PageOutput] = field(default_factory=list)
    language: str | None = None
    confidence: float | None = None
    search_text: str = ""
    card: CardOutput | None = None


@dataclass(frozen=True)
class PageReading:
    image: np.ndarray
    boxes: list[TextBox]
    language: str


@dataclass
class ProcessingContext:
    engine_for_pack: Callable[[str], OcrEngine]
    enabled_languages: list[str]
    language: str = AUTO
    options: dict = field(default_factory=dict)
    progress: Callable[[], None] | None = None

    def read(self, image: np.ndarray) -> PageReading:
        reading = read_any_language(self.engine_for_pack, image, self.language, self.enabled_languages)
        if self.progress:
            self.progress()
        return PageReading(reading.image, reading.boxes, reading.language)


def mean_box_confidence(boxes: list[TextBox]) -> float | None:
    return sum(box.confidence for box in boxes) / len(boxes) if boxes else None


class OcrModule(ABC):
    key: str
    name: str
    description: str
    icon: str
    multi_page: bool = False
    max_pages: int = 2
    keep_images: bool = True
    page_labels: tuple[str, ...] = ()
    exports: tuple[str, ...] = ()
    kinds: dict[str, str] = {}
    fields_by_kind: dict[str, tuple[FieldSpec, ...]] = {}

    @abstractmethod
    def process(self, context: ProcessingContext, uploads: list[bytes]) -> ModuleOutput: ...

    def fields_for(self, kind: str | None) -> tuple[FieldSpec, ...]:
        return self.fields_by_kind.get(kind or "", self.fields_by_kind.get("", ()))

    def validate(self, kind: str | None, values: dict[str, str]) -> list[dict[str, str]]:
        return []


def boxes_payload(boxes: list[TextBox], image: np.ndarray) -> list[list]:
    height, width = image.shape[:2]
    return [
        [box.text, round(box.x0 / width, 4), round(box.y0 / height, 4), round(box.x1 / width, 4), round(box.y1 / height, 4)]
        for box in boxes
    ]
