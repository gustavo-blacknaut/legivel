import io
import math

from PIL import Image, ImageDraw
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas


def redacted_image(content: bytes, regions: list[list[float]]) -> bytes:
    image = Image.open(io.BytesIO(content)).convert("RGB")
    draw = ImageDraw.Draw(image)
    for x0, y0, x1, y1 in regions:
        draw.rectangle(
            (
                max(0, math.floor(x0 * image.width) - 3),
                max(0, math.floor(y0 * image.height) - 3),
                min(image.width - 1, math.ceil(x1 * image.width) + 3),
                min(image.height - 1, math.ceil(y1 * image.height) + 3),
            ),
            fill="black",
        )
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def redacted_pdf(pages: list[bytes]) -> bytes:
    buffer = io.BytesIO()
    pdf = canvas.Canvas(buffer)
    pdf.setTitle("Cópia com dados ocultados")
    for content in pages:
        image = Image.open(io.BytesIO(content)).convert("RGB")
        width, height = 595, 595 * image.height / image.width
        pdf.setPageSize((width, height))
        pdf.drawImage(ImageReader(image), 0, 0, width=width, height=height)
        pdf.showPage()
    # Raster-only export: no original metadata, attachments, or hidden text layer.
    pdf.save()
    return buffer.getvalue()
