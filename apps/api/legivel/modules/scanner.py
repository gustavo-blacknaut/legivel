import cv2
import numpy as np

from legivel.imaging.preprocess import enhance_contrast, find_document_corners, load_image, resize_long_side, warp_to_corners
from legivel.modules.base import (
    FieldSpec,
    FieldValue,
    ModuleOutput,
    OcrModule,
    PageOutput,
    ProcessingContext,
    boxes_payload,
    mean_box_confidence,
)
from legivel.modules.reading_order import analyze_layout
from legivel.modules.registry import register_module

MODES = ("color", "gray", "bw")
MODE_LABELS = {"color": "Colorido", "gray": "Escala de cinza", "bw": "Preto e branco"}
OUTPUT_LONG_SIDE = 3000


def rectify(content: bytes) -> tuple[np.ndarray, bool, str, int, int]:
    image, mime = load_image(content)
    bgr = cv2.cvtColor(np.asarray(image), cv2.COLOR_RGB2BGR)
    corners = find_document_corners(bgr)
    page = warp_to_corners(bgr, corners) if corners is not None else bgr
    return (
        resize_long_side(page, min(OUTPUT_LONG_SIDE, max(page.shape[:2]))),
        corners is not None,
        mime,
        image.width,
        image.height,
    )


def enhance(image: np.ndarray, mode: str) -> np.ndarray:
    if mode == "gray":
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        return cv2.cvtColor(cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8)).apply(gray), cv2.COLOR_GRAY2BGR)
    if mode == "bw":
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        background = cv2.medianBlur(gray, 41)
        normalized = cv2.divide(gray, background, scale=255)
        binary = cv2.adaptiveThreshold(normalized, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 31, 15)
        return cv2.cvtColor(binary, cv2.COLOR_GRAY2BGR)
    return enhance_contrast(image)


@register_module
class ScannerModule(OcrModule):
    key = "scanner"
    name = "Digitalização"
    description = (
        "Modo scanner: bordas detectadas, perspectiva corrigida e realce em cor, cinza ou preto e branco. "
        "Várias páginas em um só PDF."
    )
    icon = "scan"
    multi_page = True
    max_pages = 100
    exports = ("pdf", "txt")
    fields_by_kind = {
        "": (
            FieldSpec("title", "Título"),
            FieldSpec("mode", "Realce", "readonly"),
            FieldSpec("pages", "Páginas", "readonly"),
            FieldSpec("detected", "Bordas detectadas", "readonly"),
        )
    }

    def process(self, context: ProcessingContext, uploads: list[bytes]) -> ModuleOutput:
        mode = context.options.get("mode", "color")
        mode = mode if mode in MODES else "color"
        run_ocr = context.options.get("ocr", True)
        pages: list[PageOutput] = []
        detected = 0
        confidences: list[float] = []
        title = None
        for content in uploads:
            page, found, mime, width, height = rectify(content)
            detected += int(found)
            text, layout = "", {}
            if run_ocr:
                reading = context.read(page)
                page = reading.image
                analysis = analyze_layout(reading.boxes)
                text, layout = analysis.text, {**analysis.as_dict(), "boxes": boxes_payload(reading.boxes, reading.image)}
                if (confidence := mean_box_confidence(reading.boxes)) is not None:
                    confidences.append(confidence)
                if title is None and analysis.blocks:
                    title = " ".join(line.text for line in analysis.blocks[0].lines)[:120]
            pages.append(
                PageOutput(
                    original=content,
                    processed=enhance(page, mode),
                    original_mime=mime,
                    text=text,
                    layout=layout,
                    width=width,
                    height=height,
                )
            )
        fields = {
            "title": FieldValue(title or f"Digitalização de {len(pages)} página(s)", None),
            "mode": FieldValue(MODE_LABELS[mode], 1.0),
            "pages": FieldValue(str(len(pages)), 1.0),
            "detected": FieldValue(f"{detected} de {len(pages)}", 1.0),
        }
        return ModuleOutput(
            kind=mode,
            title=fields["title"].value,
            fields=fields,
            pages=pages,
            confidence=sum(confidences) / len(confidences) if confidences else None,
            search_text="\n\n".join(page.text for page in pages),
        )
