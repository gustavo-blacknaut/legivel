import cv2
import numpy as np

CLAHE_LIMIT = 3.0
CLAHE_TILES = (8, 8)


def sharpened_contrast(image_bgr: np.ndarray) -> np.ndarray:
    lab = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2LAB)
    lightness, a, b = cv2.split(lab)
    lightness = cv2.createCLAHE(clipLimit=CLAHE_LIMIT, tileGridSize=CLAHE_TILES).apply(lightness)
    boosted = cv2.cvtColor(cv2.merge((lightness, a, b)), cv2.COLOR_LAB2BGR)
    blurred = cv2.GaussianBlur(boosted, (0, 0), 2)
    return cv2.addWeighted(boosted, 1.7, blurred, -0.7, 0)


def binarized(image_bgr: np.ndarray) -> np.ndarray:
    gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)
    denoised = cv2.bilateralFilter(gray, 7, 50, 50)
    threshold = cv2.adaptiveThreshold(denoised, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 31, 12)
    return cv2.cvtColor(threshold, cv2.COLOR_GRAY2BGR)


def darkened(image_bgr: np.ndarray) -> np.ndarray:
    table = np.array([((value / 255.0) ** 1.6) * 255 for value in range(256)], dtype=np.uint8)
    return cv2.LUT(cv2.fastNlMeansDenoisingColored(image_bgr, None, 5, 5, 7, 21), table)


VARIANTS = (sharpened_contrast, binarized, darkened)


def enhancement_variants(image_bgr: np.ndarray, count: int) -> list[np.ndarray]:
    return [variant(image_bgr) for variant in VARIANTS[: max(count, 0)]]
