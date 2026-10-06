from dataclasses import dataclass

from legivel.ocr.base import TextBox
from legivel.parsers.layout import compact
from legivel.parsers.registry import available_parsers

DEFAULT_DOCUMENT_TYPE = "rg"


@dataclass(frozen=True)
class Classification:
    doc_type: str
    score: float
    detected: bool


def keyword_score(text: str, keywords: dict[str, float]) -> float:
    return sum(weight for keyword, weight in keywords.items() if compact(keyword) in text)


def classify(boxes: list[TextBox]) -> Classification:
    text = compact(" ".join(box.text for box in boxes))
    scores = {parser.doc_type: keyword_score(text, parser.keywords) for parser in available_parsers()}
    doc_type, score = max(scores.items(), key=lambda item: item[1])
    if score <= 0:
        return Classification(DEFAULT_DOCUMENT_TYPE, 0.0, False)
    return Classification(doc_type, score, True)
