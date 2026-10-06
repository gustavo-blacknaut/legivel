from legivel.parsers.base import combine_sides, side_of
from legivel.parsers.common import repair_cpf_candidates
from legivel.parsers.layout import find_label
from legivel.parsers.registry import get_parser
from tests.synthetic import FICTITIOUS_MG_RG, box, mg_rg_back_boxes, mg_rg_front_boxes


def parse_mg():
    return get_parser("rg").parse(mg_rg_front_boxes(), mg_rg_back_boxes())


def test_mg_rg_extracts_all_main_fields():
    values = parse_mg().values()
    for name, expected in FICTITIOUS_MG_RG.items():
        assert values.get(name) == expected, name


def test_mg_rg_has_no_validation_issues():
    assert parse_mg().issues == []


def test_naturalidade_is_not_taken_from_the_other_side():
    assert parse_mg().values()["birthplace"] == "NOVA LIMA-MG"


def test_mg_rg_lists_mother_first():
    values = parse_mg().values()
    assert values["mother_name"] == FICTITIOUS_MG_RG["mother_name"]
    assert values["father_name"] == FICTITIOUS_MG_RG["father_name"]


def test_mg_rg_extracts_extra_information():
    values = parse_mg().values()
    assert values["issuing_state"] == "MINAS GERAIS"
    assert values["civil_registry"].startswith("NASC. LV-12")
    for empty in ("dni", "voter_id", "work_card", "nis_pis", "health_card", "driver_license", "military_certificate"):
        assert empty not in values


def test_rg_number_with_state_prefix():
    for text, expected in (("REGISTRO GERAL MG-12.345.678", "MG-12.345.678"), ("REGISTRO GERAL 48.217.395-6", "48.217.395-6")):
        values = get_parser("rg").parse([box(text, 0, 0, 500, 40)], []).values()
        assert values["rg_number"] == expected


def test_label_inside_combined_line_is_located_horizontally():
    line = box("DATA NASCIMENTO ORGÃO EXPEDIDOR FATOR RH", 683, 656, 1420, 704)
    match = find_label([line], ("ORGAO EXPEDIDOR",))
    assert match is not None
    assert 900 < match.box.x0 < 1050
    assert match.remainder == "FATOR RH"


def test_combine_sides_keeps_sides_apart_and_is_reversible():
    front = [box("A", 10, 10, 50, 30)]
    back = [box("B", 10, 10, 50, 30), box("*****", 0, 0, 10, 10)]
    combined = combine_sides(front, back)
    assert len(combined) == 2
    assert combined[1].y0 > 50_000
    side, original = side_of(combined[1])
    assert side == 1
    assert (original.y0, original.y1) == (10, 30)


def test_cpf_repair_fixes_letter_confusions():
    assert repair_cpf_candidates("111.444.777-3S") == ["11144477735"]
    assert repair_cpf_candidates("lll.444.777-35") == ["11144477735"]


def test_cpf_repair_fixes_single_ambiguous_digit():
    assert "11144477735" in repair_cpf_candidates("111.444.177-35")


def test_cpf_repair_rejects_garbage():
    assert repair_cpf_candidates("ABC") == []


def test_blood_type_ignores_signature_scribble():
    assert "blood_type" not in parse_mg().values()


def test_blood_type_is_read_when_present():
    front = [box(text, x0, y0, x1, y1) if text != "*****" else box("O+", x0, y0, x1, y1) for text, x0, y0, x1, y1 in (
        (item.text, item.x0, item.y0, item.x1, item.y1) for item in mg_rg_front_boxes()
    )]
    assert get_parser("rg").parse(front, mg_rg_back_boxes()).values()["blood_type"] == "O+"


def test_label_words_after_label_are_not_values():
    assert "voter_id" not in parse_mg().values()
