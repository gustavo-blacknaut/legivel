import importlib.util
from pathlib import Path

import cv2
import numpy as np
import pytest
from PIL import Image, ImageDraw

from legivel.modules.base import ProcessingContext
from legivel.modules.registry import get_module
from legivel.validators.financial import format_bank_line
from tests.synthetic import encode_jpeg, load_font, photograph
from tests.test_validators_modules import build_bank_line

pytestmark = [
    pytest.mark.ocr,
    pytest.mark.skipif(importlib.util.find_spec("rapidocr") is None, reason="RapidOCR não instalado"),
]

LEFT_COLUMN = [
    "A cooperativa reuniu os produtores",
    "da região para discutir a safra",
    "e os novos contratos de venda.",
]
RIGHT_COLUMN = [
    "Na segunda parte da reunião foram",
    "apresentados os resultados do ano",
    "e as metas para o próximo ciclo.",
]


def to_bgr(image: Image.Image) -> np.ndarray:
    return cv2.cvtColor(np.asarray(image), cv2.COLOR_RGB2BGR)


def render_two_columns() -> bytes:
    page = Image.new("RGB", (1600, 1100), (250, 248, 242))
    draw = ImageDraw.Draw(page)
    draw.text((420, 60), "RELATORIO DA COOPERATIVA", fill=(20, 20, 20), font=load_font(54))
    body = load_font(34)
    for index, line in enumerate(LEFT_COLUMN):
        draw.text((80, 220 + index * 60), line, fill=(30, 30, 30), font=body)
    for index, line in enumerate(RIGHT_COLUMN):
        draw.text((860, 220 + index * 60), line, fill=(30, 30, 30), font=body)
    return encode_jpeg(photograph(to_bgr(page), angle_degrees=3, tilt=0.03))


def render_bank_slip(line: str) -> bytes:
    page = Image.new("RGB", (1800, 700), (255, 255, 255))
    draw = ImageDraw.Draw(page)
    label, value = load_font(24), load_font(34)
    draw.text((60, 40), "LOCAL DE PAGAMENTO", fill=(60, 60, 60), font=label)
    draw.text((60, 75), "PAGAVEL EM QUALQUER BANCO ATE O VENCIMENTO", fill=(10, 10, 10), font=value)
    draw.text((60, 170), "BENEFICIARIO", fill=(60, 60, 60), font=label)
    draw.text((60, 205), "ESCOLA MODELO LTDA", fill=(10, 10, 10), font=value)
    draw.text((60, 330), format_bank_line(line), fill=(10, 10, 10), font=load_font(40))
    return encode_jpeg(photograph(to_bgr(page), angle_degrees=2, tilt=0.02))


def render_card() -> bytes:
    card = Image.new("RGB", (1200, 760), (28, 32, 36))
    draw = ImageDraw.Draw(card)
    draw.text((70, 60), "BANCO EXEMPLO", fill=(240, 240, 240), font=load_font(48))
    draw.text((70, 330), "4111 1111 1111 1111", fill=(245, 245, 245), font=load_font(78))
    draw.text((560, 470), "VALID THRU 08/29", fill=(230, 230, 230), font=load_font(40))
    draw.text((70, 600), "MARIA S OLIVEIRA", fill=(245, 245, 245), font=load_font(52))
    draw.text((900, 600), "CVV 987", fill=(200, 200, 200), font=load_font(36))
    background = Image.new("RGB", (1700, 1200), (225, 222, 215))
    background.paste(card, (250, 220))
    return encode_jpeg(to_bgr(background))


def render_english() -> bytes:
    page = Image.new("RGB", (1500, 700), (255, 255, 255))
    draw = ImageDraw.Draw(page)
    lines = [
        "The committee reviewed the annual report and the budget",
        "for the next year. It was decided that the project will",
        "continue with the same team and a new schedule.",
    ]
    for index, line in enumerate(lines):
        draw.text((70, 120 + index * 70), line, fill=(20, 20, 20), font=load_font(38))
    return encode_jpeg(to_bgr(page))


@pytest.fixture(scope="module")
def context_factory():
    from legivel.ocr.factory import get_ocr_engine

    def build(options=None, languages=("pt", "en", "es")):
        return ProcessingContext(
            engine_for_pack=lambda pack: get_ocr_engine("rapidocr", "cpu", Path("models"), pack=pack),
            enabled_languages=list(languages),
            options=options or {},
        )

    return build


def test_books_module_reads_two_columns_in_order(context_factory):
    output = get_module("books").process(context_factory(), [render_two_columns()])
    text = output.pages[0].text.lower()
    assert output.pages[0].layout["columns"] == 2, text
    assert text.index("contratos de venda") < text.index("segunda parte"), text
    assert output.language == "pt"


def test_finance_module_reads_real_bank_slip(context_factory):
    line = build_bank_line("001", 9999, 25990, "0" * 6 + "1234567890123456789")
    output = get_module("finance").process(context_factory(), [render_bank_slip(line)])
    assert output.kind == "boleto"
    values = {name: field.value for name, field in output.fields.items()}
    assert values["digitable_line"].replace(" ", "").replace(".", "") == line, output.search_text
    assert values["amount"] == "R$ 259,90"
    assert output.issues == []


def test_card_module_reads_card_and_drops_cvv(context_factory):
    output = get_module("cards").process(context_factory(), [render_card()])
    assert output.card.last4 == "1111"
    assert output.card.brand == "Visa"
    assert output.card.luhn_valid
    assert output.card.expiry == "08/29"
    assert "987" not in output.search_text
    assert all("987" not in field.value for field in output.fields.values())
    assert output.pages == []


def test_language_detection_on_english_text(context_factory):
    output = get_module("books").process(context_factory(), [render_english()])
    assert output.language == "en"


def render_russian() -> bytes:
    page = Image.new("RGB", (1500, 500), (255, 255, 255))
    draw = ImageDraw.Draw(page)
    draw.text((70, 120), "Комитет рассмотрел годовой отчет", fill=(20, 20, 20), font=load_font(46))
    draw.text((70, 220), "и бюджет на следующий год", fill=(20, 20, 20), font=load_font(46))
    return encode_jpeg(to_bgr(page))


def test_cyrillic_pack_is_detected_automatically(context_factory):
    output = get_module("books").process(context_factory(languages=("pt", "en", "ru")), [render_russian()])
    assert output.language == "ru"
    assert "отчет" in output.search_text.lower()
