from dataclasses import dataclass

import cv2
import numpy as np

from legivel.ocr.base import OcrEngine, TextBox

GOOD_ENOUGH_CONFIDENCE = 0.85
MINIMUM_BOXES = 5
PROBE_LONG_SIDE = 1000
ROTATIONS = {
    0: None,
    180: cv2.ROTATE_180,
    90: cv2.ROTATE_90_CLOCKWISE,
    270: cv2.ROTATE_90_COUNTERCLOCKWISE,
}


@dataclass(frozen=True)
class OrientedReading:
    image: np.ndarray
    boxes: list[TextBox]
    rotation: int


def reading_score(boxes: list[TextBox]) -> float:
    return sum(box.confidence**2 * len(box.text) for box in boxes)


def mean_confidence(boxes: list[TextBox]) -> float:
    total_chars = sum(len(box.text) for box in boxes)
    return sum(box.confidence * len(box.text) for box in boxes) / total_chars if total_chars else 0.0


def is_confident(boxes: list[TextBox]) -> bool:
    return mean_confidence(boxes) >= GOOD_ENOUGH_CONFIDENCE and len(boxes) >= MINIMUM_BOXES


def rotate(image: np.ndarray, rotation: int) -> np.ndarray:
    code = ROTATIONS[rotation]
    return image if code is None else cv2.rotate(image, code)


def downscale(image: np.ndarray, long_side: int) -> np.ndarray:
    scale = long_side / max(image.shape[:2])
    return image if scale >= 1 else cv2.resize(image, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)


def detect_rotation(engine: OcrEngine, image: np.ndarray) -> int:
    probe = downscale(image, PROBE_LONG_SIDE)
    best_rotation, best_score = 0, -1.0
    for rotation in ROTATIONS:
        boxes = engine.read(rotate(probe, rotation))
        score = reading_score(boxes)
        if score > best_score:
            best_rotation, best_score = rotation, score
        if is_confident(boxes) and rotation in (0, 180) and best_rotation == rotation:
            break
    return best_rotation


def read_with_best_orientation(engine: OcrEngine, image: np.ndarray) -> OrientedReading:
    rotation = detect_rotation(engine, image)
    oriented = rotate(image, rotation)
    return OrientedReading(oriented, engine.read(oriented), rotation)
