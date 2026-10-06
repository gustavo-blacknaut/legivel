import io
import threading
from contextlib import closing

import pypdfium2 as pdfium

MAX_PDF_PAGES = 100
PDF_LOCK = threading.Lock()  # PDFium calls must not run concurrently in a process.


def open_pdf(content: bytes, password: str = ""):
    if not content.startswith(b"%PDF-"):
        raise ValueError("Envie um PDF válido.")
    try:
        document = pdfium.PdfDocument(content, password=password or None)
    except pdfium.PdfiumError as error:
        raise ValueError("PDF inválido ou senha incorreta.") from error
    if not 1 <= len(document) <= MAX_PDF_PAGES:
        document.close()
        raise ValueError(f"O PDF precisa ter de 1 a {MAX_PDF_PAGES} páginas.")
    return document


def inspect_pdf(content: bytes, password: str = "") -> dict:
    with PDF_LOCK, open_pdf(content, password) as document:
        return {"pages": len(document)}


def render_pdf(content: bytes, selections: list[dict], password: str = "", preview: bool = False) -> list[bytes]:
    results = []
    with PDF_LOCK, open_pdf(content, password) as document:
        if not selections or len(selections) > 50 or len({item["page"] for item in selections}) != len(selections):
            raise ValueError("Selecione de 1 a 50 páginas diferentes.")
        for item in selections:
            number, rotation = item["page"], item.get("rotation", 0)
            if not 1 <= number <= len(document) or rotation not in (0, 90, 180, 270):
                raise ValueError("Página ou rotação inválida.")
            with closing(document[number - 1]) as page:
                width, height = page.get_size()
                if min(width, height) <= 0 or max(width, height) > 20_000:
                    raise ValueError("Dimensões da página acima do permitido.")
                scale = (480 if preview else 2200) / max(width, height)
                with closing(page.render(scale=scale, rotation=rotation)) as bitmap:
                    image = bitmap.to_pil().convert("RGB")
                    output = io.BytesIO()
                    image.save(output, "JPEG", quality=90)
                    results.append(output.getvalue())
    return results
