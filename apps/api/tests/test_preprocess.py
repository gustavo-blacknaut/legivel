import io

import cv2
import numpy as np
import pytest
from PIL import Image

from legivel.imaging.preprocess import (
    InvalidImageError,
    encode_processed,
    encode_thumbnail,
    find_document_corners,
    prepare_image,
)
from legivel.ocr.base import TextBox
from legivel.ocr.orientation import read_with_best_orientation
from tests.synthetic import encode_jpeg, photograph, render_rg_back


def test_detects_and_rectifies_photographed_document():
    card = render_rg_back()
    prepared = prepare_image(encode_jpeg(photograph(card)))
    assert prepared.document_detected
    height, width = prepared.ocr_image.shape[:2]
    expected_ratio = card.shape[1] / card.shape[0]
    assert width / height == pytest.approx(expected_ratio, rel=0.12)


def test_corners_are_close_to_real_document_area():
    corners = find_document_corners(photograph(render_rg_back()))
    assert corners is not None
    area = cv2.contourArea(corners.astype(np.float32))
    assert area > 1400 * 960 * 0.8


def test_derivatives_are_compressed():
    original = encode_jpeg(photograph(render_rg_back()))
    prepared = prepare_image(original)
    thumbnail = encode_thumbnail(prepared.ocr_image)
    assert thumbnail[:4] == b"RIFF"
    assert encode_processed(prepared.ocr_image)[:2] == b"\xff\xd8"
    assert len(thumbnail) < len(original)
    assert prepared.original_mime == "image/jpeg"


def test_orientation_search_picks_upright_reading():
    upright = render_rg_back()
    upright[:60, :60] = 0

    class OrientationAwareEngine:
        name = "fake"

        def __init__(self):
            self.calls = 0

        def read(self, image):
            self.calls += 1
            is_upright = image[:8, :8].mean() < 40
            confidence = 0.98 if is_upright else 0.2
            return [TextBox("TEXTO", confidence, 0, index * 30, 100, index * 30 + 20) for index in range(6)]

    upside_down = cv2.rotate(upright, cv2.ROTATE_180)
    engine = OrientationAwareEngine()
    reading = read_with_best_orientation(engine, upside_down)
    assert reading.rotation == 180
    assert np.array_equal(reading.image, upright)
    assert engine.calls == 3


def test_applies_exif_orientation():
    image = Image.new("RGB", (400, 200), "white")
    exif = Image.Exif()
    exif[0x0112] = 6
    buffer = io.BytesIO()
    image.save(buffer, "JPEG", exif=exif)
    prepared = prepare_image(buffer.getvalue())
    assert (prepared.width, prepared.height) == (200, 400)


def test_rejects_non_image():
    with pytest.raises(InvalidImageError):
        prepare_image(b"not an image")
