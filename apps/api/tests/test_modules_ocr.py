import importlib.util
from pathlib import Path

import pytest
from PIL import Image, ImageDraw

from legivel.modules.base import ProcessingContext
from legivel.modules.registry import get_module
from legivel.validators.financial import format_bank_line
from tests.synthetic import encode_jpeg, load_font, photograph, render_card, render_two_columns, to_bgr
from tests.test_validators_modules import build_bank_line

pytestmark = [
    pytest.mark.ocr,
    pytest.mark.skipif(importlib.util.find_spec("rapidocr") is None, reason="RapidOCR não instalado"),
]



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
