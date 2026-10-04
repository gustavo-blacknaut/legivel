from app.ocr.base import TextBox
from app.parsers.layout import find_label, normalize
from app.parsers.mrz import check_digit, find_mrz_lines, parse_td1
from app.parsers.registry import available_parsers, get_parser
from tests.synthetic import FICTITIOUS_RG, label_value_boxes, rg_back_boxes

EXPECTED_RG = {
    "full_name": "MARIANA OLIVEIRA DOS SANTOS",
    "rg_number": "48.217.395-6",
    "issue_date": "12/06/2015",
    "birth_date": "23/09/1991",
    "birthplace": "CAMPINAS-SP",
    "father_name": "CARLOS EDUARDO DOS SANTOS",
    "mother_name": "LUCIA HELENA OLIVEIRA",
    "cpf": "529.982.247-25",
    "issuing_authority": "SSP/SP",
    "civil_registry": "CERT. NASC. LV 12 FL 34 N 5678",
}


def test_registry_lists_builtin_parsers():
    assert {parser.doc_type for parser in available_parsers()} >= {"rg", "cnh", "cpf"}


def test_normalize_removes_accents():
    assert normalize("Filiação  data") == "FILIACAO DATA"


def test_label_matching_tolerates_ocr_errors():
    boxes = [TextBox("FlLIAÇAO", 0.8, 0, 0, 80, 20)]
    assert find_label(boxes, ("FILIACAO",)) is not None


def test_rg_parser_extracts_all_fields_from_back():
    result = get_parser("rg").parse([], rg_back_boxes())
    assert result.values() == EXPECTED_RG
    assert result.issues == []


def test_rg_parser_handles_label_and_value_in_same_box():
    boxes = label_value_boxes(
        [
            ("NOME: JOAO PEDRO ALVES", 40, 100, 300),
            ("DATA DE NASCIMENTO 01/02/1980", 40, 160, 300),
            ("REGISTRO GERAL 12.345.678-9", 40, 40, 300),
        ]
    )
    values = get_parser("rg").parse(boxes, []).values()
    assert values["full_name"] == "JOAO PEDRO ALVES"
    assert values["birth_date"] == "01/02/1980"
    assert values["rg_number"] == "12.345.678-9"


def test_rg_parser_reports_invalid_cpf_and_missing_fields():
    values = dict(FICTITIOUS_RG, cpf="529.982.247-20")
    boxes = [box for box in rg_back_boxes(values) if box.text not in ("NOME", values["full_name"])]
    result = get_parser("rg").parse([], boxes)
    codes = {(issue["field"], issue["code"]) for issue in result.issues}
    assert ("cpf", "invalid_cpf") in codes
    assert ("full_name", "required_missing") in codes


def test_rg_parser_normalizes_noisy_date_and_cpf():
    boxes = label_value_boxes(
        [
            ("DATA DE NASCIMENTO", 40, 40, 190),
            ("23 / 09 / 1991", 40, 68, 140),
            ("CPF", 40, 120, 40),
            ("529 982 247 25", 40, 148, 160),
        ]
    )
    values = get_parser("rg").parse([], boxes).values()
    assert values["birth_date"] == "23/09/1991"
    assert values["cpf"] == "529.982.247-25"


def cnh_front_boxes() -> list[TextBox]:
    return label_value_boxes(
        [
            ("2 e 1 NOME E SOBRENOME", 40, 40, 220),
            ("RAFAEL MOREIRA COSTA", 40, 68, 300),
            ("3 DATA, LOCAL E UF DE NASCIMENTO", 40, 120, 320),
            ("14/02/1988, BELO HORIZONTE, MG", 40, 148, 330),
            ("4a DATA EMISSÃO", 40, 200, 150),
            ("10/01/2023", 40, 228, 110),
            ("4b VALIDADE", 260, 200, 120),
            ("10/01/2033", 260, 228, 110),
            ("4c DOC IDENTIDADE/ÓRG EMISSOR/UF", 40, 280, 320),
            ("MG12345678 SSP MG", 40, 308, 200),
            ("4d CPF", 40, 360, 60),
            ("111.444.777-35", 40, 388, 150),
            ("5 Nº REGISTRO", 260, 360, 140),
            ("04417558216", 260, 388, 130),
            ("9 CAT HAB", 480, 360, 100),
            ("AB", 480, 388, 30),
            ("1ª HABILITAÇÃO", 40, 440, 150),
            ("05/06/2007", 40, 468, 110),
            ("FILIAÇÃO", 40, 520, 90),
            ("JOSE MOREIRA COSTA", 40, 548, 250),
            ("ANA PAULA MOREIRA", 40, 576, 240),
        ]
    )


def test_cnh_parser_extracts_new_model_fields():
    result = get_parser("cnh").parse(cnh_front_boxes(), [])
    values = result.values()
    assert values["full_name"] == "RAFAEL MOREIRA COSTA"
    assert values["birth_date"] == "14/02/1988"
    assert values["birthplace"] == "BELO HORIZONTE, MG"
    assert values["cpf"] == "111.444.777-35"
    assert values["cnh_register"] == "04417558216"
    assert values["cnh_category"] == "AB"
    assert values["valid_until"] == "10/01/2033"
    assert values["first_license_date"] == "05/06/2007"
    assert values["issue_date"] == "10/01/2023"
    assert values["issuing_authority"] == "SSP/MG"
    assert values["father_name"] == "JOSE MOREIRA COSTA"
    assert values["mother_name"] == "ANA PAULA MOREIRA"
    assert result.issues == []


def build_td1(document_number: str, birth: str, expiry: str, names: str) -> list[str]:
    first = f"I<BRA{document_number}{check_digit(document_number)}".ljust(30, "<")
    second = f"{birth}{check_digit(birth)}M{expiry}{check_digit(expiry)}BRA".ljust(30, "<")
    return [first, second, names.ljust(30, "<")]


def test_mrz_td1_parsing_and_check_digits():
    lines = build_td1("044175582", "880214", "330110", "COSTA<<RAFAEL<MOREIRA")
    mrz = parse_td1(lines)
    assert mrz.checks_valid
    assert mrz.document_number == "044175582"
    assert mrz.birth_date.isoformat() == "1988-02-14"
    assert mrz.expiry_date.isoformat() == "2033-01-10"
    assert mrz.surname == "COSTA"
    assert mrz.given_names == "RAFAEL MOREIRA"


def test_mrz_detects_corrupted_check_digit():
    lines = build_td1("044175582", "880214", "330110", "COSTA<<RAFAEL")
    lines[1] = lines[1][:6] + "0" + lines[1][7:] if lines[1][6] != "0" else lines[1][:6] + "1" + lines[1][7:]
    assert not parse_td1(lines).checks_valid


def test_cnh_parser_reads_mrz_from_back():
    lines = build_td1("044175582", "880214", "330110", "COSTA<<RAFAEL<MOREIRA")
    back = [TextBox(line, 0.9, 20, 400 + index * 30, 700, 425 + index * 30) for index, line in enumerate(lines)]
    assert find_mrz_lines(back) == lines
    values = get_parser("cnh").parse(cnh_front_boxes(), back).values()
    assert values["mrz_raw"] == "\n".join(lines)


def test_cpf_card_parser():
    boxes = label_value_boxes(
        [
            ("Número de Inscrição", 40, 40, 200),
            ("111.444.777-35", 40, 68, 150),
            ("Nome", 40, 120, 60),
            ("FERNANDA LIMA ROCHA", 40, 148, 260),
            ("Data de Nascimento", 40, 200, 180),
            ("30/11/1995", 40, 228, 110),
        ]
    )
    assert get_parser("cpf").parse(boxes, []).values() == {
        "cpf": "111.444.777-35",
        "full_name": "FERNANDA LIMA ROCHA",
        "birth_date": "30/11/1995",
    }
