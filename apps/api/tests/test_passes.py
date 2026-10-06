from dataclasses import replace

import numpy as np

from legivel.db.models import Document, ImageSide
from legivel.imaging.variants import enhancement_variants
from legivel.parsers.base import ExtractedField
from legivel.services.documents import SideReading, apply_extraction, better_field
from tests.synthetic import rg_back_boxes


class VariantEngine:
    name = "variantes"

    def __init__(self, extra_boxes):
        self.extra_boxes = extra_boxes
        self.calls = 0

    def read(self, image_bgr):
        self.calls += 1
        return self.extra_boxes


def reading(boxes):
    return SideReading(ImageSide.BACK, np.full((400, 600, 3), 200, dtype=np.uint8), boxes)


def weakened(boxes, name_fragment, confidence):
    return [replace(box, confidence=confidence) if name_fragment in box.text else box for box in boxes]


def test_variants_keep_image_size():
    image = np.random.default_rng(1).integers(0, 255, (120, 200, 3), dtype=np.uint8)
    variants = enhancement_variants(image, 3)
    assert len(variants) == 3
    assert all(variant.shape == image.shape for variant in variants)
    assert enhancement_variants(image, 0) == []


def test_extra_pass_replaces_low_confidence_field():
    base = weakened(rg_back_boxes(), "MARIANA", 0.41)
    engine = VariantEngine(rg_back_boxes())
    document = Document(doc_type="rg", field_confidence={}, extra_fields={})
    apply_extraction(document, engine, [reading(base)], passes=3)
    assert engine.calls >= 1
    assert document.field_confidence["full_name"] > 0.9


def test_no_extra_pass_when_reading_is_confident():
    engine = VariantEngine([])
    document = Document(doc_type="rg", field_confidence={}, extra_fields={})
    apply_extraction(document, engine, [reading(rg_back_boxes())], passes=3)
    assert engine.calls == 0


def test_single_pass_setting_skips_variants():
    engine = VariantEngine(rg_back_boxes())
    document = Document(doc_type="rg", field_confidence={}, extra_fields={})
    apply_extraction(document, engine, [reading(weakened(rg_back_boxes(), "MARIANA", 0.3))], passes=1)
    assert engine.calls == 0


def test_cpf_is_only_replaced_by_a_valid_one():
    valid = ExtractedField("529.982.247-25", 0.5)
    invalid = ExtractedField("529.982.247-20", 0.99)
    assert better_field("cpf", None, valid)
    assert not better_field("cpf", valid, invalid)
    assert better_field("cpf", ExtractedField("529.982.247-20", 0.99), valid)
    assert better_field("full_name", ExtractedField("A", 0.5), ExtractedField("B", 0.8))
    assert not better_field("full_name", ExtractedField("A", 0.9), ExtractedField("B", 0.8))


