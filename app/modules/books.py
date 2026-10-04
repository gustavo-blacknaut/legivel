from app.imaging.preprocess import load_image, prepare_image
from app.modules.base import (
    FieldSpec,
    FieldValue,
    ModuleOutput,
    OcrModule,
    PageOutput,
    ProcessingContext,
    boxes_payload,
    mean_box_confidence,
)
from app.modules.reading_order import analyze_layout
from app.modules.registry import register_module

TITLE_MAX_LENGTH = 120
LONG_SIDE = 2400


@register_module
class BooksModule(OcrModule):
    key = "books"
    name = "Livros e textos"
    description = (
        "Texto corrido em várias páginas, com detecção de colunas e ordem de leitura. Exporta PDF pesquisável, TXT e Markdown."
    )
    icon = "book-open"
    multi_page = True
    max_pages = 300
    exports = ("pdf", "txt", "md")
    fields_by_kind = {
        "": (
            FieldSpec("title", "Título"),
            FieldSpec("pages", "Páginas", "readonly"),
            FieldSpec("words", "Palavras", "readonly"),
            FieldSpec("columns", "Colunas detectadas", "readonly"),
        )
    }

    def process(self, context: ProcessingContext, uploads: list[bytes]) -> ModuleOutput:
        pages: list[PageOutput] = []
        confidences: list[float] = []
        languages: list[tuple[str, int]] = []
        max_columns = 0
        title = None
        for content in uploads:
            prepared = prepare_image(content, long_side=LONG_SIDE)
            reading = context.read(prepared.ocr_image)
            layout = analyze_layout(reading.boxes)
            max_columns = max(max_columns, layout.columns)
            languages.append((reading.language, sum(len(box.text) for box in reading.boxes)))
            if (confidence := mean_box_confidence(reading.boxes)) is not None:
                confidences.append(confidence)
            if title is None:
                heading = next((block for block in layout.blocks if block.heading), None)
                first = heading or (layout.blocks[0] if layout.blocks else None)
                title = " ".join(line.text for line in first.lines)[:TITLE_MAX_LENGTH] if first else None
            image, mime = load_image(content)
            pages.append(
                PageOutput(
                    original=content,
                    processed=reading.image,
                    original_mime=mime,
                    text=layout.text,
                    layout={
                        **layout.as_dict(),
                        "markdown": layout.markdown(),
                        "boxes": boxes_payload(reading.boxes, reading.image),
                    },
                    width=image.width,
                    height=image.height,
                )
            )
        full_text = "\n\n".join(page.text for page in pages)
        words = len(full_text.split())
        language = max(
            {code for code, _ in languages}, key=lambda code: sum(size for item, size in languages if item == code), default=None
        )
        fields = {
            "title": FieldValue(title or f"Documento de {len(pages)} página(s)", None),
            "pages": FieldValue(str(len(pages)), 1.0),
            "words": FieldValue(f"{words:,}".replace(",", "."), 1.0),
            "columns": FieldValue(str(max_columns), None),
        }
        return ModuleOutput(
            kind=None,
            title=fields["title"].value,
            fields=fields,
            pages=pages,
            language=language,
            confidence=sum(confidences) / len(confidences) if confidences else None,
            search_text=full_text,
        )
