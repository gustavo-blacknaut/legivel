from dataclasses import dataclass
from typing import Protocol

import numpy as np


@dataclass(frozen=True)
class TextBox:
    text: str
    confidence: float
    x0: float
    y0: float
    x1: float
    y1: float

    @property
    def height(self) -> float:
        return max(self.y1 - self.y0, 1.0)

    @property
    def center_x(self) -> float:
        return (self.x0 + self.x1) / 2

    @property
    def center_y(self) -> float:
        return (self.y0 + self.y1) / 2


class OcrEngine(Protocol):
    name: str

    def read(self, image_bgr: np.ndarray) -> list[TextBox]: ...
