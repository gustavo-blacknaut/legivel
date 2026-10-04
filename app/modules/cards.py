import re

from app.imaging.preprocess import prepare_image
from app.modules.base import CardOutput, FieldSpec, FieldValue, ModuleOutput, OcrModule, ProcessingContext
from app.modules.registry import register_module
from app.ocr.base import TextBox
from app.parsers.base import strip_accents
from app.parsers.layout import normalize
from app.validators.cards import card_brand, luhn_is_valid, mask_card_number, parse_expiry
from app.validators.cpf import only_digits

NUMBER_GROUPS = re.compile(r"(?<!\d)(\d{4}[ .-]?\d{4}[ .-]?\d{4}[ .-]?\d{4}(?:[ .-]?\d{1,3})?|\d{4}[ .-]?\d{6}[ .-]?\d{5})(?!\d)")
SECURITY_LABELS = re.compile(r"\b(CVV|CVC|CVV2|CID|COD(IGO)?\.? ?(DE )?SEGURANCA|SECURITY CODE)\b")
EXPIRY_HINTS = re.compile(r"\b(VALID|VALIDO|VAL|THRU|VENC|EXP|ATE)\b")
NON_HOLDER_WORDS = {
    "VISA",
    "MASTERCARD",
    "MASTER",
    "ELO",
    "AMEX",
    "AMERICAN",
    "EXPRESS",
    "HIPERCARD",
    "DINERS",
    "CLUB",
    "DISCOVER",
    "DEBIT",
    "DEBITO",
    "CREDIT",
    "CREDITO",
    "PLATINUM",
    "GOLD",
    "BLACK",
    "INFINITE",
    "SIGNATURE",
    "INTERNATIONAL",
    "INTERNACIONAL",
    "BANCO",
    "BANK",
    "NUBANK",
    "ITAU",
    "BRADESCO",
    "SANTANDER",
    "CAIXA",
    "INTER",
    "SICOOB",
    "SICREDI",
    "VALID",
    "THRU",
    "MEMBER",
    "SINCE",
    "CARD",
    "CARTAO",
    "MULTIPLO",
    "PREPAID",
    "CONTACTLESS",
    "BUSINESS",
    "EMPRESARIAL",
}
NAME_PATTERN = re.compile(r"^[A-Z][A-Z .'-]{3,}$")


def is_security_text(box: TextBox) -> bool:
    return SECURITY_LABELS.search(strip_accents(box.text.upper())) is not None


def find_card_number(boxes: list[TextBox]) -> tuple[str | None, float | None]:
    candidates: list[tuple[str, float]] = []
    lines = sorted(boxes, key=lambda box: (round(box.center_y / max(box.height, 1)), box.x0))
    texts = [(box.text, box.confidence) for box in lines]
    for index in range(len(lines) - 1):
        first, second = lines[index], lines[index + 1]
        if abs(first.center_y - second.center_y) < first.height * 0.6:
            texts.append((f"{first.text} {second.text}", min(first.confidence, second.confidence)))
    for text, confidence in texts:
        for match in NUMBER_GROUPS.finditer(normalize(text).replace("O", "0")):
            digits = only_digits(match.group(0))
            candidates.append((digits, confidence))
    valid = [candidate for candidate in candidates if luhn_is_valid(candidate[0])]
    chosen = max(valid or candidates, key=lambda candidate: (len(candidate[0]) in (15, 16), candidate[1]), default=None)
    return chosen if chosen else (None, None)


def find_expiry(boxes: list[TextBox]) -> tuple[str | None, float | None]:
    ranked = sorted(boxes, key=lambda box: not EXPIRY_HINTS.search(normalize(box.text)))
    for box in ranked:
        expiry = parse_expiry(normalize(box.text))
        if expiry:
            return expiry.label, box.confidence
    return None, None


def find_holder(boxes: list[TextBox], number_box_bottom: float) -> tuple[str | None, float | None]:
    candidates = []
    for box in boxes:
        text = strip_accents(box.text.upper()).strip()
        words = text.split()
        if len(words) < 2 or any(char.isdigit() for char in text) or not NAME_PATTERN.match(text):
            continue
        if any(word.strip(".") in NON_HOLDER_WORDS for word in words):
            continue
        candidates.append((box.center_y >= number_box_bottom, box.y0, text, box.confidence))
    if not candidates:
        return None, None
    _, _, name, confidence = max(candidates)
    return name, confidence


@register_module
class CardsModule(OcrModule):
    key = "cards"
    name = "Cartões"
    description = (
        "Cartões de crédito e débito: bandeira, final, nome impresso e validade, com verificação de Luhn. O CVV nunca é lido."
    )
    icon = "credit-card"
    max_pages = 1
    keep_images = False
    page_labels = ("Frente do cartão",)
    fields_by_kind = {
        "": (
            FieldSpec("brand", "Bandeira"),
            FieldSpec("masked_number", "Número", "masked"),
            FieldSpec("holder_name", "Nome impresso"),
            FieldSpec("expiry", "Validade"),
            FieldSpec("luhn", "Verificação de Luhn", "readonly"),
        )
    }

    def process(self, context: ProcessingContext, uploads: list[bytes]) -> ModuleOutput:
        prepared = prepare_image(uploads[0])
        reading = context.read(prepared.ocr_image)
        boxes = [box for box in reading.boxes if not is_security_text(box)]
        number, number_confidence = find_card_number(boxes)
        expiry, expiry_confidence = find_expiry(boxes)
        number_bottom = max((box.y1 for box in boxes if number and number[-4:] in only_digits(box.text)), default=0)
        holder, holder_confidence = find_holder(boxes, number_bottom)
        valid = bool(number) and luhn_is_valid(number)
        brand = card_brand(number) if number else None
        fields = {
            "brand": FieldValue(brand or "", number_confidence),
            "masked_number": FieldValue(mask_card_number(number) if number else "", number_confidence),
            "holder_name": FieldValue(holder or "", holder_confidence),
            "expiry": FieldValue(expiry or "", expiry_confidence),
            "luhn": FieldValue("Válido" if valid else "Inválido" if number else "", 1.0 if number else None),
        }
        issues = []
        if not number:
            issues.append({"field": "masked_number", "code": "missing", "message": "Número do cartão não encontrado"})
        elif not valid:
            issues.append({"field": "luhn", "code": "luhn", "message": "O número lido não passa na verificação de Luhn"})
        if expiry and (parsed := parse_expiry(expiry)) and parsed.is_expired():
            issues.append({"field": "expiry", "code": "expired", "message": "Cartão vencido"})
        title = f"{brand or 'Cartão'} final {number[-4:]}" if number else "Cartão sem número legível"
        return ModuleOutput(
            kind=None,
            title=title,
            fields={name: value for name, value in fields.items() if value.value},
            issues=issues,
            pages=[],
            language=reading.language,
            confidence=number_confidence,
            search_text=" ".join(filter(None, [brand, number[-4:] if number else None, holder])),
            card=CardOutput(brand, number[-4:] if number else None, holder, expiry, valid, number if valid else None),
        )
