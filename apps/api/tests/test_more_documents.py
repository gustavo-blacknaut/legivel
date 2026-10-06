import pytest

from legivel.ocr.base import TextBox
from legivel.parsers.classifier import classify
from legivel.parsers.registry import get_parser
from legivel.validators.civil import voter_id_check_digits
from tests.conftest import login
from tests.synthetic import encode_jpeg, photograph, render_rg_back

PASSPORT_MRZ = (
    "P<BRASOUZA<<JOANA<FICTICIA<<<<<<<<<<<<<<<<<<",
    "FZ12345656BRA9003152F3101012<<<<<<<<<<<<<<02",
)


def box(text: str, y: float, x: float = 40) -> TextBox:
    return TextBox(text, 0.97, x, y, x + 20 * len(text), y + 30)


def passport_boxes() -> list[TextBox]:
    return [
        box("REPUBLICA FEDERATIVA DO BRASIL", 20),
        box("PASSAPORTE PASSPORT", 60),
        box(PASSPORT_MRZ[0], 600),
        box(PASSPORT_MRZ[1], 640),
    ]


def voter_boxes() -> list[TextBox]:
    sequence, state = "00451234", "02"
    number = sequence + state + voter_id_check_digits(sequence, state)
    return [
        box("JUSTICA ELEITORAL", 20),
        box("TITULO ELEITORAL", 60),
        box("NOME DO ELEITOR", 120),
        box("CARLOS FICTICIO DA SILVA", 150),
        box("INSCRICAO", 220),
        box(f"{number[:4]} {number[4:8]} {number[8:]}", 250),
        box("ZONA", 320),
        box("101", 350),
        box("SECAO", 420),
        box("0234", 450),
    ]


def certificate_boxes() -> list[TextBox]:
    return [
        box("REGISTRO CIVIL DAS PESSOAS NATURAIS", 20),
        box("CERTIDAO DE NASCIMENTO", 60),
        box("MATRICULA", 120),
        box("104539 01 55 2015 1 00012 021 0012345 13", 150),
    ]


@pytest.mark.parametrize(
    ("boxes", "expected"),
    [(passport_boxes(), "passport"), (voter_boxes(), "voter"), (certificate_boxes(), "certificate")],
)
def test_new_document_types_are_recognized(boxes, expected):
    assert classify(boxes).doc_type == expected


def test_passport_fields_come_from_the_checked_mrz():
    fields = get_parser("passport").extract(passport_boxes(), [])
    assert fields["full_name"].value == "JOANA FICTICIA SOUZA"
    assert fields["passport_number"].value == "FZ1234565"
    assert fields["birth_date"].value == "15/03/1990"
    assert fields["valid_until"].value == "01/01/2031"


def test_voter_id_number_and_state():
    fields = get_parser("voter").extract(voter_boxes(), [])
    assert fields["voter_id"].value.replace(" ", "").startswith("0045123402")
    assert fields["voter_state"].value == "MG"
    assert fields["zone"].value == "101"


class StaticEngine:
    name = "fake"

    def __init__(self, boxes: list[TextBox]):
        self.boxes = boxes

    def read(self, image):
        return self.boxes


def test_passport_upload_goes_through_the_document_flow(client):
    login(client)
    client.app_state.ocr_engine = StaticEngine(passport_boxes())
    image = encode_jpeg(photograph(render_rg_back()))
    response = client.post("/api/documents", files={"front": ("passaporte.jpg", image, "image/jpeg")})
    assert response.status_code == 201, response.text
    detail = response.json()
    assert detail["doc_type"] == "passport"
    values = {field["name"]: field["value"] for field in detail["fields"]}
    assert values["full_name"] == "JOANA FICTICIA SOUZA"
