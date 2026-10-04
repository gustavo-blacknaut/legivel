import io
from dataclasses import dataclass

import cv2
import numpy as np
from PIL import Image, ImageOps, UnidentifiedImageError
from pillow_heif import register_heif_opener

register_heif_opener()

OCR_LONG_SIDE = 2000
THUMBNAIL_LONG_SIDE = 480
DETECTION_LONG_SIDE = 800
MINIMUM_DOCUMENT_AREA_RATIO = 0.2
ALLOWED_FORMATS = {"JPEG", "PNG", "WEBP", "HEIF", "HEIC", "MPO"}


class InvalidImageError(ValueError):
    pass


@dataclass(frozen=True)
class PreparedImage:
    ocr_image: np.ndarray
    original_mime: str
    width: int
    height: int
    document_detected: bool


def load_image(content: bytes) -> tuple[Image.Image, str]:
    try:
        image = Image.open(io.BytesIO(content))
        image_format = image.format or ""
        image.load()
    except (UnidentifiedImageError, OSError) as error:
        raise InvalidImageError("Arquivo não é uma imagem válida") from error
    if image_format not in ALLOWED_FORMATS:
        raise InvalidImageError(f"Formato de imagem não suportado: {image_format}")
    mime = Image.MIME.get(image_format, "image/heif")
    return ImageOps.exif_transpose(image).convert("RGB"), mime


def order_corners(points: np.ndarray) -> np.ndarray:
    points = points.reshape(4, 2).astype(np.float32)
    sums = points.sum(axis=1)
    differences = np.diff(points, axis=1).ravel()
    return np.array(
        [points[np.argmin(sums)], points[np.argmin(differences)], points[np.argmax(sums)], points[np.argmax(differences)]],
        dtype=np.float32,
    )


def find_document_corners(image_bgr: np.ndarray) -> np.ndarray | None:
    height, width = image_bgr.shape[:2]
    scale = DETECTION_LONG_SIDE / max(height, width)
    small = cv2.resize(image_bgr, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA) if scale < 1 else image_bgr
    scale = min(scale, 1.0)
    gray = cv2.GaussianBlur(cv2.cvtColor(small, cv2.COLOR_BGR2GRAY), (5, 5), 0)
    edges = cv2.dilate(cv2.Canny(gray, 50, 150), np.ones((5, 5), np.uint8), iterations=2)
    contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    minimum_area = MINIMUM_DOCUMENT_AREA_RATIO * small.shape[0] * small.shape[1]
    for contour in sorted(contours, key=cv2.contourArea, reverse=True)[:5]:
        if cv2.contourArea(contour) < minimum_area:
            break
        approximation = cv2.approxPolyDP(contour, 0.02 * cv2.arcLength(contour, True), True)
        if len(approximation) == 4 and cv2.isContourConvex(approximation):
            return order_corners(approximation) / scale
        if cv2.contourArea(cv2.convexHull(contour)) >= minimum_area:
            return order_corners(cv2.boxPoints(cv2.minAreaRect(contour))) / scale
    return None


def warp_to_corners(image_bgr: np.ndarray, corners: np.ndarray) -> np.ndarray:
    top_left, top_right, bottom_right, bottom_left = corners
    width = int(max(np.linalg.norm(top_right - top_left), np.linalg.norm(bottom_right - bottom_left)))
    height = int(max(np.linalg.norm(bottom_left - top_left), np.linalg.norm(bottom_right - top_right)))
    target = np.array([[0, 0], [width - 1, 0], [width - 1, height - 1], [0, height - 1]], dtype=np.float32)
    matrix = cv2.getPerspectiveTransform(corners, target)
    return cv2.warpPerspective(image_bgr, matrix, (width, height), flags=cv2.INTER_CUBIC)


def resize_long_side(image: np.ndarray, long_side: int) -> np.ndarray:
    height, width = image.shape[:2]
    scale = long_side / max(height, width)
    interpolation = cv2.INTER_AREA if scale < 1 else cv2.INTER_CUBIC
    return cv2.resize(image, None, fx=scale, fy=scale, interpolation=interpolation)


def enhance_contrast(image_bgr: np.ndarray) -> np.ndarray:
    lab = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2LAB)
    lightness, channel_a, channel_b = cv2.split(lab)
    lightness = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8)).apply(lightness)
    return cv2.cvtColor(cv2.merge((lightness, channel_a, channel_b)), cv2.COLOR_LAB2BGR)


def encode(image_bgr: np.ndarray, extension: str, quality: int) -> bytes:
    flag = cv2.IMWRITE_WEBP_QUALITY if extension == ".webp" else cv2.IMWRITE_JPEG_QUALITY
    success, buffer = cv2.imencode(extension, image_bgr, [flag, quality])
    if not success:
        raise InvalidImageError("Falha ao codificar imagem")
    return buffer.tobytes()


def prepare_image(content: bytes, long_side: int = OCR_LONG_SIDE) -> PreparedImage:
    pil_image, mime = load_image(content)
    image_bgr = cv2.cvtColor(np.asarray(pil_image), cv2.COLOR_RGB2BGR)
    corners = find_document_corners(image_bgr)
    document = warp_to_corners(image_bgr, corners) if corners is not None else image_bgr
    if document.shape[0] > document.shape[1] * 1.15 and corners is not None:
        document = cv2.rotate(document, cv2.ROTATE_90_CLOCKWISE)
    return PreparedImage(
        ocr_image=enhance_contrast(resize_long_side(document, long_side)),
        original_mime=mime,
        width=pil_image.width,
        height=pil_image.height,
        document_detected=corners is not None,
    )


def encode_processed(image_bgr: np.ndarray) -> bytes:
    return encode(image_bgr, ".jpg", 92)


def encode_thumbnail(image_bgr: np.ndarray) -> bytes:
    return encode(resize_long_side(image_bgr, THUMBNAIL_LONG_SIDE), ".webp", 82)
