import io
from pathlib import Path

from PIL import Image
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

from legivel.db.models import Record
from legivel.storage.file_store import FileStore

FONT_NAME = "DejaVuSans"
FONT_PATHS = ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "C:/Windows/Fonts/arial.ttf")
PAGE_WIDTH_POINTS = 595.0
INVISIBLE = 3


def register_font() -> str:
    if FONT_NAME in pdfmetrics.getRegisteredFontNames():
        return FONT_NAME
    for candidate in FONT_PATHS:
        if Path(candidate).exists():
            pdfmetrics.registerFont(TTFont(FONT_NAME, candidate))
            return FONT_NAME
    return "Helvetica"


def record_text(record: Record) -> str:
    return "\n\n".join(page.text or "" for page in record.pages).strip()


def to_txt(record: Record) -> bytes:
    header = record.title or ""
    return f"{header}\n\n{record_text(record)}\n".encode()


def to_markdown(record: Record) -> bytes:
    parts = [f"# {record.title or 'Documento'}"]
    for page in record.pages:
        markdown = (page.layout or {}).get("markdown") or page.text or ""
        parts.append(f"<!-- página {page.page_number} -->\n\n{markdown}")
    return ("\n\n".join(parts) + "\n").encode()


def to_searchable_pdf(record: Record, store: FileStore) -> bytes:
    font = register_font()
    buffer = io.BytesIO()
    document = canvas.Canvas(buffer)
    document.setTitle(record.title or "Documento")
    for page in record.pages:
        source = page.processed_path or page.original_path
        if not source:
            continue
        image = Image.open(io.BytesIO(store.load(source)))
        width = PAGE_WIDTH_POINTS
        height = width * image.height / image.width
        document.setPageSize((width, height))
        document.drawImage(ImageReader(image), 0, 0, width=width, height=height)
        for text, x0, y0, x1, y1 in (page.layout or {}).get("boxes", []):
            box_height = (y1 - y0) * height
            box_width = (x1 - x0) * width
            if not text.strip() or box_height <= 0:
                continue
            size = max(box_height * 0.85, 1)
            text_object = document.beginText()
            text_object.setTextRenderMode(INVISIBLE)
            text_object.setFont(font, size)
            natural = pdfmetrics.stringWidth(text, font, size) or 1
            text_object.setHorizScale(max(10.0, min(400.0, box_width / natural * 100)))
            text_object.setTextOrigin(x0 * width, height - y1 * height + box_height * 0.15)
            text_object.textLine(text)
            document.drawText(text_object)
        document.showPage()
    document.save()
    return buffer.getvalue()
