import re
import unicodedata
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from difflib import SequenceMatcher

from app.ocr.base import TextBox
from app.parsers.base import ExtractedField, is_placeholder

LABEL_SIMILARITY = 0.82
MAX_BELOW_GAP_FACTOR = 3.5
SAME_LINE_FACTOR = 0.6
INNER_LABEL_SCORE = 0.9
MIN_INNER_LABEL_LENGTH = 6

ValueCheck = Callable[[str], bool]


def normalize(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text)
    without_accents = "".join(char for char in decomposed if not unicodedata.combining(char))
    return re.sub(r"\s+", " ", without_accents.upper()).strip()


def compact(text: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", normalize(text))


@dataclass(frozen=True)
class LabelMatch:
    box: TextBox
    remainder: str
    score: float


def match_label(box: TextBox, variants: Iterable[str]) -> LabelMatch | None:
    box_compact = compact(box.text)
    best: LabelMatch | None = None
    for variant in variants:
        variant_compact = compact(variant)
        if not variant_compact or not box_compact:
            continue
        prefix = box_compact[: len(variant_compact)]
        score = 1.0 if prefix == variant_compact else SequenceMatcher(None, prefix, variant_compact).ratio()
        if score >= LABEL_SIMILARITY and not (best and best.score >= score):
            best = LabelMatch(box, text_after_compact_position(box.text, len(variant_compact)), score)
            continue
        position = box_compact.find(variant_compact, 1)
        if position > 0 and len(variant_compact) >= MIN_INNER_LABEL_LENGTH and not (best and best.score >= INNER_LABEL_SCORE):
            best = inner_label_match(box, box_compact, position, len(variant_compact))
    return best


def inner_label_match(box: TextBox, box_compact: str, position: int, length: int) -> LabelMatch:
    width = box.x1 - box.x0
    x0 = box.x0 + width * position / len(box_compact)
    x1 = box.x0 + width * (position + length) / len(box_compact)
    virtual = TextBox(box.text, box.confidence, x0, box.y0, x1, box.y1)
    return LabelMatch(virtual, text_after_compact_position(box.text, position + length), INNER_LABEL_SCORE)


def text_after_compact_position(text: str, compact_length: int) -> str:
    consumed = 0
    for index, char in enumerate(normalize(text)):
        if char.isalnum():
            consumed += 1
        if consumed == compact_length:
            return text[index + 1:].strip(" :.-/").strip()
    return ""


def find_label(boxes: list[TextBox], variants: Iterable[str]) -> LabelMatch | None:
    variants = tuple(variants)
    matches = [match for box in boxes if (match := match_label(box, variants))]
    return max(matches, key=lambda match: (match.score, -match.box.y0), default=None)


def is_label_text(text: str, all_labels: Iterable[str]) -> bool:
    remaining = compact(text)
    label_compacts = sorted({compact(label) for label in all_labels if compact(label)}, key=len, reverse=True)
    while remaining:
        prefix = next((label for label in label_compacts if remaining.startswith(label)), None)
        if prefix is None:
            return False
        remaining = remaining[len(prefix):]
    return True


def is_any_label(box: TextBox, all_labels: Iterable[str]) -> bool:
    all_labels = tuple(all_labels)
    match = match_label(box, all_labels)
    return bool(match and match.score >= LABEL_SIMILARITY and (not match.remainder or is_label_text(match.remainder, all_labels)))


def boxes_right_of(label: TextBox, boxes: list[TextBox]) -> list[TextBox]:
    tolerance = label.height * SAME_LINE_FACTOR
    candidates = [
        box for box in boxes
        if box is not label and abs(box.center_y - label.center_y) <= tolerance and box.x0 >= label.x1 - label.height
    ]
    return sorted(candidates, key=lambda box: box.x0)


def boxes_below(label: TextBox, boxes: list[TextBox]) -> list[TextBox]:
    max_gap = label.height * MAX_BELOW_GAP_FACTOR
    candidates = [
        box for box in boxes
        if box is not label
        and box.y0 >= label.center_y
        and box.center_y > label.y1 - label.height * 0.2
        and box.x0 <= label.x1 + label.height * 2
        and box.x1 >= label.x0 - label.height
    ]
    candidates.sort(key=lambda box: (box.y0, abs(box.x0 - label.x0)))
    if not candidates or candidates[0].y0 - label.y1 > max_gap:
        return []
    return candidates


def find_value(
    boxes: list[TextBox],
    variants: Iterable[str],
    all_labels: Iterable[str],
    accepts: ValueCheck = bool,
    prefer: str = "below",
) -> ExtractedField | None:
    label = find_label(boxes, variants)
    if label is None:
        return None
    all_labels = tuple(all_labels)
    if label.remainder and is_placeholder(label.remainder):
        return None
    if label.remainder and is_label_text(label.remainder, all_labels):
        label = LabelMatch(label.box, "", label.score)
    if label.remainder and accepts(label.remainder):
        return ExtractedField(label.remainder, label.box.confidence, label.box)
    directions = (boxes_below, boxes_right_of) if prefer == "below" else (boxes_right_of, boxes_below)
    for direction in directions:
        for candidate in direction(label.box, boxes)[:3]:
            if is_any_label(candidate, all_labels):
                if direction is boxes_below:
                    break
                continue
            if accepts(candidate.text):
                return ExtractedField(candidate.text.strip(), candidate.confidence, candidate)
    return None


def lines_below(boxes: list[TextBox], variants: Iterable[str], all_labels: Iterable[str], limit: int) -> list[TextBox]:
    label = find_label(boxes, variants)
    if label is None:
        return []
    all_labels = tuple(all_labels)
    lines: list[TextBox] = []
    previous_bottom = label.box.y1
    for candidate in boxes_below(label.box, boxes):
        if candidate.y0 - previous_bottom > label.box.height * MAX_BELOW_GAP_FACTOR:
            break
        if is_any_label(candidate, all_labels):
            break
        if lines and abs(candidate.center_y - lines[-1].center_y) < candidate.height * SAME_LINE_FACTOR:
            continue
        lines.append(candidate)
        previous_bottom = candidate.y1
        if len(lines) == limit:
            break
    return lines


def search_pattern(boxes: list[TextBox], pattern: re.Pattern) -> ExtractedField | None:
    for box in sorted(boxes, key=lambda item: (item.y0, item.x0)):
        match = pattern.search(normalize(box.text))
        if match:
            return ExtractedField(match.group(0), box.confidence, box)
    return None
