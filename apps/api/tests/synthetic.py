from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

from legivel.ocr.base import TextBox

FONT_CANDIDATES = (
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "C:/Windows/Fonts/arial.ttf",
)

FICTITIOUS_RG = {
    "rg_number": "48.217.395-6",
    "issue_date": "12/06/2015",
    "full_name": "MARIANA OLIVEIRA DOS SANTOS",
    "father_name": "CARLOS EDUARDO DOS SANTOS",
    "mother_name": "LUCIA HELENA OLIVEIRA",
    "birthplace": "CAMPINAS-SP",
    "birth_date": "23/09/1991",
    "cpf": "529.982.247-25",
    "issuing_authority": "SSP/SP",
}


def label_value_boxes(layout: list[tuple[str, float, float, float]], height: float = 20) -> list[TextBox]:
    return [TextBox(text, 0.97, x, y, x + width, y + height) for text, x, y, width in layout]


def rg_back_boxes(values: dict[str, str] = FICTITIOUS_RG) -> list[TextBox]:
    return label_value_boxes(
        [
            ("REGISTRO GERAL", 40, 40, 160),
            (values["rg_number"], 220, 40, 150),
            ("DATA DE EXPEDIÇÃO", 520, 40, 170),
            (values["issue_date"], 710, 40, 110),
            ("NOME", 40, 100, 50),
            (values["full_name"], 40, 128, 380),
            ("FILIAÇÃO", 40, 180, 80),
            (values["father_name"], 40, 208, 360),
            (values["mother_name"], 40, 236, 300),
            ("NATURALIDADE", 40, 300, 130),
            (values["birthplace"], 40, 328, 140),
            ("DATA DE NASCIMENTO", 520, 300, 190),
            (values["birth_date"], 520, 328, 110),
            ("DOC. ORIGEM", 40, 390, 110),
            ("CERT. NASC. LV 12 FL 34 N 5678", 40, 418, 320),
            ("CPF", 40, 470, 40),
            (values["cpf"], 40, 498, 150),
            ("ASSINATURA DO DIRETOR", 520, 540, 220),
            (f"LEI Nº 7.116 DE 29/08/83 {values['issuing_authority']}", 40, 580, 360),
        ]
    )


def load_font(size: int) -> ImageFont.FreeTypeFont:
    for candidate in FONT_CANDIDATES:
        if Path(candidate).exists():
            return ImageFont.truetype(candidate, size)
    return ImageFont.load_default(size)


def render_rg_back(values: dict[str, str] = FICTITIOUS_RG) -> np.ndarray:
    width, height = 1400, 960
    card = Image.new("RGB", (width, height), (214, 232, 214))
    draw = ImageDraw.Draw(card)
    label_font, value_font = load_font(22), load_font(34)
    for y in range(0, height, 6):
        draw.line([(0, y), (width, y)], fill=(205, 225, 207))
    draw.rectangle([10, 10, width - 10, height - 10], outline=(90, 120, 95), width=3)
    texts = [
        ("REGISTRO GERAL", (40, 40), label_font), (values["rg_number"], (260, 30), value_font),
        ("DATA DE EXPEDIÇÃO", (820, 40), label_font), (values["issue_date"], (1080, 30), value_font),
        ("NOME", (40, 130), label_font), (values["full_name"], (40, 162), value_font),
        ("FILIAÇÃO", (40, 250), label_font), (values["father_name"], (40, 282), value_font),
        (values["mother_name"], (40, 330), value_font),
        ("NATURALIDADE", (40, 430), label_font), (values["birthplace"], (40, 462), value_font),
        ("DATA DE NASCIMENTO", (820, 430), label_font), (values["birth_date"], (820, 462), value_font),
        ("DOC. ORIGEM", (40, 560), label_font), ("CERT. NASC. LV 12 FL 34 N 5678", (40, 592), value_font),
        ("CPF", (40, 690), label_font), (values["cpf"], (40, 722), value_font),
        ("ASSINATURA DO DIRETOR", (820, 800), label_font),
        (f"LEI Nº 7.116 DE 29/08/83   {values['issuing_authority']}", (40, 870), label_font),
    ]
    for text, position, font in texts:
        draw.text(position, text, fill=(25, 30, 28), font=font)
    return cv2.cvtColor(np.asarray(card), cv2.COLOR_RGB2BGR)


def photograph(card_bgr: np.ndarray, angle_degrees: float = 8, tilt: float = 0.06) -> np.ndarray:
    card_height, card_width = card_bgr.shape[:2]
    canvas_width, canvas_height = int(card_width * 1.6), int(card_height * 1.8)
    offset_x, offset_y = canvas_width * 0.18, canvas_height * 0.2
    source = np.float32([[0, 0], [card_width, 0], [card_width, card_height], [0, card_height]])
    destination = np.float32(
        [
            [offset_x + card_width * tilt, offset_y],
            [offset_x + card_width * (1 - tilt * 0.3), offset_y + card_height * tilt],
            [offset_x + card_width, offset_y + card_height * (1 + tilt)],
            [offset_x - card_width * tilt * 0.5, offset_y + card_height * (1 - tilt * 0.2)],
        ]
    )
    center = destination.mean(axis=0)
    rotation = cv2.getRotationMatrix2D(tuple(center), angle_degrees, 1.0)
    destination = cv2.transform(destination.reshape(-1, 1, 2), rotation).reshape(-1, 2).astype(np.float32)
    matrix = cv2.getPerspectiveTransform(source, destination)
    background = np.full((canvas_height, canvas_width, 3), (48, 42, 38), dtype=np.uint8)
    noise = np.random.default_rng(7).integers(0, 18, background.shape, dtype=np.uint8)
    background = cv2.add(background, noise)
    warped = cv2.warpPerspective(card_bgr, matrix, (canvas_width, canvas_height))
    mask = cv2.warpPerspective(np.full(card_bgr.shape[:2], 255, np.uint8), matrix, (canvas_width, canvas_height))
    background[mask > 0] = warped[mask > 0]
    return cv2.GaussianBlur(background, (3, 3), 0)


def encode_jpeg(image_bgr: np.ndarray) -> bytes:
    return cv2.imencode(".jpg", image_bgr, [cv2.IMWRITE_JPEG_QUALITY, 90])[1].tobytes()


FICTITIOUS_MG_RG = {
    "full_name": "JOAO BATISTA FERREIRA",
    "mother_name": "MARIA APARECIDA FERREIRA SOUZA",
    "father_name": "ANTONIO CARLOS FERREIRA",
    "birth_date": "07/03/1994",
    "birthplace": "NOVA LIMA-MG",
    "issuing_authority": "PC/MG",
    "rg_number": "MG-12.345.678",
    "issue_date": "15/08/2019",
    "cpf": "111.444.777-35",
}


def box(text: str, x0: float, y0: float, x1: float, y1: float, confidence: float = 0.98) -> TextBox:
    return TextBox(text, confidence, x0, y0, x1, y1)


def mg_rg_front_boxes(values: dict[str, str] = FICTITIOUS_MG_RG) -> list[TextBox]:
    return [
        box("REPUBLICA FEDERATIVA DO BRASIL", 344, 171, 1325, 235),
        box("ESTADO DE MINAS GERAIS", 498, 247, 1160, 300),
        box("POLÍCIA CIVIL DO ESTADO DE MINAS GERAIS", 501, 282, 1075, 319),
        box("INSTITUTO DE IDENTIFICAÇÃO", 498, 303, 891, 335),
        box(f"NOME {values['full_name']}", 273, 388, 988, 444),
        box("FILIAÇÃO", 689, 503, 833, 541),
        box(values["mother_name"], 687, 532, 1322, 581),
        box(values["father_name"], 689, 604, 1164, 647),
        box("DATA NASCIMENTO ORGÃO EXPEDIDOR FATOR RH", 683, 656, 1420, 704),
        box("PCMG", 978, 696, 1078, 742),
        box("*****", 1275, 698, 1370, 725),
        box(values["birth_date"], 684, 699, 867, 743),
        box("NATURALIDADE", 683, 737, 919, 781),
        box(values["birthplace"], 682, 774, 927, 824),
        box("BRASILEIRO", 679, 814, 888, 863),
        box("*****", 684, 855, 783, 890),
        box("Jzao Bat Ferrera", 855, 858, 1294, 961, 0.54),
        box("ASSINATURA DO TITULAR", 889, 963, 1260, 1004),
        box("CARTEIRA DE IDENTIDADE", 508, 1017, 1266, 1084),
    ]


def mg_rg_back_boxes(values: dict[str, str] = FICTITIOUS_MG_RG) -> list[TextBox]:
    cpf_digits = values["cpf"].replace(".", "").replace("-", "")
    return [
        box("LEI Nº 7.116, DE 29 DE AGOSTO DE 1983", 318, 37, 1641, 121),
        box("VIA-1", 1584, 152, 1709, 210),
        box("PCMG-2019", 1265, 155, 1453, 213),
        box("DNI *****", 780, 156, 1005, 220),
        box(f"CPF {cpf_digits}", 181, 166, 567, 224),
        box(values["issue_date"], 1479, 217, 1707, 279),
        box("DATA DE EXPEDIÇÃO", 1025, 226, 1414, 286),
        box(f"REGISTRO GERAL {values['rg_number']}", 180, 230, 892, 294),
        box("REGISTRO CIVIL", 183, 312, 510, 357),
        box("NASC. LV-12 FL-345 TERMO 6789 NOVA LIMA-MG", 176, 343, 1047, 413),
        box("*****", 183, 405, 314, 438),
        box("CTPS / SÉRIE / UF", 712, 461, 1074, 521),
        box("T. ELEITOR / ZONA / SEC", 178, 474, 667, 527),
        box("*****", 715, 514, 847, 552),
        box("*****", 184, 527, 314, 559),
        box("POLEGAR DIREITO", 1337, 546, 1685, 605),
        box("IDENTIDADE PROFISSIONAL", 714, 562, 1253, 617),
        box("NIS / PIS / PASEP", 179, 574, 541, 631),
        box("*****", 718, 613, 849, 656),
        box("*****", 184, 629, 314, 662),
        box("*****", 719, 663, 852, 707),
        box("CERT. MILITAR", 183, 680, 485, 732),
        box("*****", 722, 718, 852, 756),
        box("*****", 186, 732, 320, 769),
        box("CNS", 719, 768, 815, 823),
        box("CNH", 180, 789, 284, 834),
        box("*****", 725, 818, 852, 855),
        box("*****", 188, 839, 314, 871),
        box("FULANO DE TAL SILVA", 693, 1053, 1155, 1116),
        box("DIRETOR DO INSTITUTO DE IDENTIFICAÇÃO", 620, 1088, 1230, 1153),
        box("VALIDA EM TODO O TERRITORIO NACIONAL", 335, 1131, 1710, 1257),
    ]
