from dataclasses import dataclass

import cv2
import numpy as np

from app.ocr.base import TextBox
from app.parsers.layout import find_label

FACE_CASCADE = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
SIGNATURE_LABELS = ("ASSINATURA DO TITULAR", "ASSINATURA DO PORTADOR")
FINGERPRINT_LABELS = ("POLEGAR DIREITO", "POLEGAR")
MINIMUM_FACE_RATIO = 0.08


@dataclass(frozen=True)
class Region:
    x0: int
    y0: int
    x1: int
    y1: int

    def clip(self, image: np.ndarray) -> "Region":
        height, width = image.shape[:2]
        return Region(max(self.x0, 0), max(self.y0, 0), min(self.x1, width), min(self.y1, height))

    def crop(self, image: np.ndarray) -> np.ndarray | None:
        region = self.clip(image)
        if region.x1 - region.x0 < 20 or region.y1 - region.y0 < 20:
            return None
        return image[region.y0:region.y1, region.x0:region.x1]


def find_portrait(image: np.ndarray) -> np.ndarray | None:
    gray = cv2.equalizeHist(cv2.cvtColor(image, cv2.COLOR_BGR2GRAY))
    minimum = int(min(gray.shape) * MINIMUM_FACE_RATIO)
    faces = FACE_CASCADE.detectMultiScale(gray, scaleFactor=1.08, minNeighbors=6, minSize=(minimum, minimum))
    if len(faces) == 0:
        return None
    x, y, width, height = max(faces, key=lambda face: face[2] * face[3])
    return Region(int(x - width * 0.45), int(y - height * 0.55), int(x + width * 1.45), int(y + height * 1.75)).crop(image)


def ink_density(image: np.ndarray, region: Region, text_boxes: list[TextBox]) -> float:
    patch = region.crop(image)
    if patch is None:
        return 0.0
    gray = cv2.cvtColor(patch, cv2.COLOR_BGR2GRAY)
    binary = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_MEAN_C, cv2.THRESH_BINARY_INV, 25, 15)
    clipped = region.clip(image)
    for box in text_boxes:
        x0, y0 = int(box.x0) - clipped.x0, int(box.y0) - clipped.y0
        x1, y1 = int(box.x1) - clipped.x0, int(box.y1) - clipped.y0
        binary[max(y0, 0):max(y1, 0), max(x0, 0):max(x1, 0)] = 0
    return float(binary.mean()) / 255


def find_signature(image: np.ndarray, boxes: list[TextBox]) -> np.ndarray | None:
    label = find_label(boxes, SIGNATURE_LABELS)
    if label is None:
        return None
    box = label.box
    width = box.x1 - box.x0
    region = Region(int(box.x0 - width * 0.35), int(box.y0 - box.height * 3.2), int(box.x1 + width * 0.35), int(box.y0))
    return region.crop(image)


def find_fingerprint(image: np.ndarray, boxes: list[TextBox]) -> np.ndarray | None:
    label = find_label(boxes, FINGERPRINT_LABELS)
    if label is None:
        return None
    box = label.box
    width = box.x1 - box.x0
    side = int(width * 1.1)
    center_x = int(box.center_x)
    below = Region(center_x - side // 2, int(box.y1), center_x + side // 2, int(box.y1) + int(side * 1.2))
    above = Region(center_x - side // 2, int(box.y0) - int(side * 1.2), center_x + side // 2, int(box.y0))
    others = [other for other in boxes if other is not box]
    best = max((below, above), key=lambda region: ink_density(image, region, others))
    return best.crop(image)
