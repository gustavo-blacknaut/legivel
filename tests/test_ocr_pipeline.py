import importlib.util

import pytest

from app.imaging.preprocess import prepare_image
from app.parsers.registry import get_parser
from tests.synthetic import FICTITIOUS_RG, encode_jpeg, photograph, render_rg_back

pytestmark = [
    pytest.mark.ocr,
    pytest.mark.skipif(importlib.util.find_spec("paddleocr") is None, reason="PaddleOCR não instalado"),
]


@pytest.fixture(scope="module")
def engine():
    from app.ocr.paddle_engine import PaddleOcrEngine

    return PaddleOcrEngine()


def test_full_pipeline_on_photographed_fictitious_rg(engine):
    photo = encode_jpeg(photograph(render_rg_back(), angle_degrees=9, tilt=0.07))
    prepared = prepare_image(photo)
    result = get_parser("rg").parse([], engine.read(prepared.ocr_image))
    values = result.values()
    for name in ("full_name", "rg_number", "birth_date", "issue_date", "cpf", "father_name", "mother_name", "birthplace"):
        assert values.get(name) == FICTITIOUS_RG[name], (name, values.get(name), result.raw_text)
    assert all(confidence > 0.8 for confidence in (field.confidence for field in result.fields.values()))
