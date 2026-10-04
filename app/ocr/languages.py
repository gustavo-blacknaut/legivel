import re
import unicodedata
from dataclasses import dataclass

import numpy as np

from app.ocr.base import OcrEngine, TextBox
from app.ocr.orientation import downscale, mean_confidence, reading_score

AUTO = "auto"
PROBE_LONG_SIDE = 1100
CONFIDENT_LATIN = 0.8


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


def choose_language(engine_for_pack, image: np.ndarray, requested: str, enabled: list[str]) -> LanguageChoice:
    if requested != AUTO and requested in LANGUAGES:
        return LanguageChoice(requested, LANGUAGES[requested].pack)
    probe = downscale(image, PROBE_LONG_SIDE)
    packs = packs_for(enabled)
    best_pack, best_boxes, best_score = packs[0], [], -1.0
    for pack in packs:
        boxes: list[TextBox] = engine_for_pack(pack).read(probe)
        score = reading_score(boxes)
        if score > best_score:
            best_pack, best_boxes, best_score = pack, boxes, score
        if pack == "latin" and mean_confidence(boxes) >= CONFIDENT_LATIN and len(boxes) >= 3:
            break
    if best_pack == "latin":
        latin_enabled = [code for code in enabled if LANGUAGES.get(code) and LANGUAGES[code].pack == "latin"] or ["pt"]
        text = " ".join(box.text for box in best_boxes)
        return LanguageChoice(detect_latin_language(text, latin_enabled), "latin")
    return LanguageChoice(PACK_DEFAULT_LANGUAGE[best_pack], best_pack)


def engine_selector(factory, engine_name: str, device: str):
    def select(pack: str) -> OcrEngine:
        return factory(engine_name, device, pack)

    return select
