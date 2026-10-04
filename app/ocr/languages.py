import re
import unicodedata
from dataclasses import dataclass

import numpy as np

from app.ocr.base import TextBox
from app.ocr.orientation import ROTATIONS, downscale, mean_confidence, reading_score, rotate

AUTO = "auto"
PROBE_LONG_SIDE = 1100


@dataclass(frozen=True)
class Language:
    code: str
    name: str
    pack: str


LANGUAGES: dict[str, Language] = {
    language.code: language
    for language in (
        Language("pt", "Português", "latin"),
        Language("en", "Inglês", "latin"),
        Language("es", "Espanhol", "latin"),
        Language("fr", "Francês", "latin"),
        Language("de", "Alemão", "latin"),
        Language("it", "Italiano", "latin"),
        Language("ru", "Russo", "cyrillic"),
        Language("zh", "Chinês", "chinese"),
        Language("ja", "Japonês", "japanese"),
        Language("ko", "Coreano", "korean"),
        Language("ar", "Árabe", "arabic"),
        Language("hi", "Hindi", "devanagari"),
    )
}
PACK_DEFAULT_LANGUAGE = {"cyrillic": "ru", "chinese": "zh", "japanese": "ja", "korean": "ko", "arabic": "ar", "devanagari": "hi"}
STOPWORDS = {
    "pt": {
        "de",
        "da",
        "do",
        "que",
        "e",
        "o",
        "a",
        "os",
        "as",
        "em",
        "para",
        "com",
        "não",
        "uma",
        "um",
        "por",
        "mais",
        "dos",
        "das",
        "se",
        "na",
        "no",
    },
    "en": {
        "the",
        "and",
        "of",
        "to",
        "in",
        "is",
        "that",
        "for",
        "it",
        "with",
        "as",
        "was",
        "on",
        "be",
        "by",
        "this",
        "are",
        "from",
        "or",
        "an",
    },
    "es": {
        "de",
        "la",
        "que",
        "el",
        "en",
        "y",
        "los",
        "se",
        "del",
        "las",
        "por",
        "un",
        "para",
        "con",
        "no",
        "una",
        "su",
        "al",
        "lo",
        "como",
    },
    "fr": {
        "de",
        "la",
        "le",
        "et",
        "les",
        "des",
        "en",
        "un",
        "du",
        "une",
        "que",
        "est",
        "pour",
        "qui",
        "dans",
        "par",
        "pas",
        "au",
        "sur",
        "ne",
    },
    "de": {
        "der",
        "die",
        "und",
        "in",
        "den",
        "von",
        "zu",
        "das",
        "mit",
        "sich",
        "des",
        "auf",
        "für",
        "ist",
        "im",
        "dem",
        "nicht",
        "ein",
        "eine",
        "als",
    },
    "it": {
        "di",
        "e",
        "il",
        "la",
        "che",
        "in",
        "a",
        "per",
        "un",
        "del",
        "non",
        "una",
        "della",
        "le",
        "si",
        "con",
        "sono",
        "da",
        "al",
        "gli",
    },
}
ACCENT_HINTS = {"pt": "ãõç", "es": "ñ¿¡", "fr": "èêëœàù", "de": "äöüß", "it": "òì"}


def packs_for(languages: list[str]) -> list[str]:
    packs: list[str] = []
    for code in languages:
        language = LANGUAGES.get(code)
        if language and language.pack not in packs:
            packs.append(language.pack)
    return packs or ["latin"]


def detect_latin_language(text: str, candidates: list[str]) -> str:
    words = re.findall(r"[^\W\d_]+", text.lower())
    if not words:
        return candidates[0] if candidates else "pt"
    scores = {}
    for code in candidates:
        stopwords = STOPWORDS.get(code)
        if not stopwords:
            continue
        hits = sum(1 for word in words if word in stopwords)
        accents = sum(text.lower().count(char) for char in ACCENT_HINTS.get(code, ""))
        scores[code] = hits + accents * 0.5
    if not scores:
        return candidates[0] if candidates else "pt"
    return max(scores, key=lambda code: (scores[code], code == "pt"))


def strip_marks(text: str) -> str:
    return "".join(char for char in unicodedata.normalize("NFKD", text) if not unicodedata.combining(char))


@dataclass(frozen=True)
class LanguageChoice:
    language: str
    pack: str


SCRIPT_RANGES = {
    "cyrillic": ((0x0400, 0x04FF),),
    "chinese": ((0x4E00, 0x9FFF),),
    "japanese": ((0x3040, 0x30FF), (0x4E00, 0x9FFF)),
    "korean": ((0xAC00, 0xD7AF), (0x1100, 0x11FF)),
    "arabic": ((0x0600, 0x06FF), (0x0750, 0x077F)),
    "devanagari": ((0x0900, 0x097F),),
}
MINIMUM_SCRIPT_SHARE = 0.5
MINIMUM_SCRIPT_CONFIDENCE = 0.6


def script_share(text: str, pack: str) -> float:
    letters = [char for char in text if char.isalpha()]
    if not letters:
        return 0.0
    ranges = SCRIPT_RANGES.get(pack, ())
    inside = sum(1 for char in letters if any(start <= ord(char) <= end for start, end in ranges))
    return inside / len(letters)


@dataclass(frozen=True)
class LanguageReading:
    image: np.ndarray
    boxes: list[TextBox]
    language: str


CONFIDENT_READING = 0.85
CONFIDENT_CHARACTERS = 20


def is_confident_reading(boxes: list[TextBox]) -> bool:
    return mean_confidence(boxes) >= CONFIDENT_READING and sum(len(box.text) for box in boxes) >= CONFIDENT_CHARACTERS


def pack_score(pack: str, boxes: list[TextBox]) -> float:
    if pack != "latin":
        text = " ".join(box.text for box in boxes)
        if script_share(text, pack) < MINIMUM_SCRIPT_SHARE or mean_confidence(boxes) < MINIMUM_SCRIPT_CONFIDENCE:
            return 0.0
    return reading_score(boxes)


def read_any_language(engine_for_pack, image: np.ndarray, requested: str, enabled: list[str]) -> LanguageReading:
    fixed = requested != AUTO and requested in LANGUAGES
    packs = [LANGUAGES[requested].pack] if fixed else packs_for(enabled)
    probe = downscale(image, PROBE_LONG_SIDE)
    best_pack, best_rotation, best_score, best_boxes = packs[0], 0, -1.0, []
    for rotation in ROTATIONS:
        for pack in packs:
            boxes = engine_for_pack(pack).read(rotate(probe, rotation))
            score = pack_score(pack, boxes)
            if score > best_score:
                best_pack, best_rotation, best_score, best_boxes = pack, rotation, score, boxes
        if best_rotation == rotation and rotation in (0, 180) and best_score > 0 and is_confident_reading(best_boxes):
            break
    oriented = rotate(image, best_rotation)
    boxes = engine_for_pack(best_pack).read(oriented)
    if fixed:
        return LanguageReading(oriented, boxes, requested)
    if best_pack != "latin":
        return LanguageReading(oriented, boxes, PACK_DEFAULT_LANGUAGE[best_pack])
    latin_enabled = [code for code in enabled if LANGUAGES.get(code) and LANGUAGES[code].pack == "latin"] or ["pt"]
    language = detect_latin_language(" ".join(box.text for box in boxes), latin_enabled)
    return LanguageReading(oriented, boxes, language)
