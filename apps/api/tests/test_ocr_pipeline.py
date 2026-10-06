import importlib.util
from pathlib import Path

import pytest

from legivel.imaging.preprocess import prepare_image
from legivel.ocr.devices import DeviceChoice
from legivel.parsers.registry import get_parser
from tests.synthetic import FICTITIOUS_RG, encode_jpeg, photograph, render_rg_back

MODEL_DIR = Path("models")
pytestmark = [
    pytest.mark.ocr,
    pytest.mark.skipif(importlib.util.find_spec("rapidocr") is None, reason="RapidOCR não instalado"),
]


@pytest.fixture(scope="module")
def engine():
    from legivel.ocr.rapid_engine import RapidOcrEngine

    return RapidOcrEngine(DeviceChoice("cpu", None, "teste"), MODEL_DIR)


def test_full_pipeline_on_photographed_fictitious_rg(engine):
    photo = encode_jpeg(photograph(render_rg_back(), angle_degrees=9, tilt=0.07))
    prepared = prepare_image(photo)
    result = get_parser("rg").parse([], engine.read(prepared.ocr_image))
    values = result.values()
    for name in ("full_name", "rg_number", "birth_date", "issue_date", "cpf", "father_name", "mother_name", "birthplace"):
        assert values.get(name) == FICTITIOUS_RG[name], (name, values.get(name), result.raw_text)
    assert all(confidence > 0.8 for confidence in (field.confidence for field in result.fields.values()))


def test_engine_reports_cpu_provider_and_timing(engine):
    engine.read(prepare_image(encode_jpeg(render_rg_back())).ocr_image)
    assert engine.providers == ["CPUExecutionProvider"]
    assert engine.statistics.average_ms > 0
