from app.parsers.classifier import classify
from app.parsers.registry import get_parser
from tests.synthetic import box, mg_rg_back_boxes, mg_rg_front_boxes, rg_back_boxes
from tests.test_parsers import cnh_front_boxes


def test_identifies_rg_layouts():
    assert classify(rg_back_boxes()).doc_type == "rg"
    assert classify(mg_rg_front_boxes() + mg_rg_back_boxes()).doc_type == "rg"


def test_identifies_cnh():
    header = [box("CARTEIRA NACIONAL DE HABILITAÇÃO", 0, 0, 600, 40)]
    assert classify(header + cnh_front_boxes()).doc_type == "cnh"


def test_identifies_cpf_card():
    boxes = [box("MINISTÉRIO DA FAZENDA", 0, 0, 400, 30), box("CADASTRO DE PESSOAS FÍSICAS", 0, 40, 500, 70)]
    assert classify(boxes).doc_type == "cpf"


def test_unknown_document_falls_back_to_rg_without_claiming_detection():
    result = classify([box("TEXTO QUALQUER", 0, 0, 200, 30)])
    assert result.doc_type == "rg"
    assert not result.detected


def test_extracted_values_have_no_accents():
    boxes = [
        box("NOME JOÃO JOSÉ ÂNGELO", 0, 0, 500, 30),
        box("NATURALIDADE", 0, 60, 200, 90),
        box("SÃO JOÃO DEL-REI-MG", 0, 96, 300, 126),
    ]
    values = get_parser("rg").parse(boxes, []).values()
    assert values["full_name"] == "JOAO JOSE ANGELO"
    assert values["birthplace"] == "SAO JOAO DEL-REI-MG"
