import re
from collections.abc import Callable

from app.imaging.preprocess import load_image, prepare_image
from app.modules.base import (
    FieldSpec,
    FieldValue,
    ModuleOutput,
    OcrModule,
    PageOutput,
    ProcessingContext,
    boxes_payload,
    mean_box_confidence,
)
from app.modules.reading_order import analyze_layout
from app.modules.registry import register_module
from app.ocr.base import TextBox
from app.parsers.base import combine_sides, strip_accents
from app.parsers.layout import compact, find_value, normalize
from app.validators.cpf import format_cpf, is_valid_cpf, only_digits
from app.validators.dates import format_brazilian_date, parse_brazilian_date
from app.validators.financial import (
    format_bank_line,
    format_cnpj,
    format_money,
    format_nfe_key,
    is_valid_cnpj,
    is_valid_nfe_key,
    nfe_key_cnpj,
    parse_bank_slip,
    parse_money,
)

DIGIT_RUN = re.compile(r"[\d.\s-]{44,70}")
CNPJ_PATTERN = re.compile(r"\d{2}\.?\d{3}\.?\d{3}/?\d{4}-?\d{2}")
CPF_PATTERN = re.compile(r"\d{3}\.\d{3}\.\d{3}-\d{2}")
CEP_PATTERN = re.compile(r"\b\d{5}-?\d{3}\b")
MONEY_PATTERN = re.compile(r"(?:R\$\s?)?\d{1,3}(?:\.\d{3})*,\d{2}")
DATE_PATTERN = re.compile(r"\d{2}/\d{2}/\d{4}")
REFERENCE_PATTERN = re.compile(
    r"\b(0[1-9]|1[0-2])/(\d{4})\b|\b(JAN|FEV|MAR|ABR|MAI|JUN|JUL|AGO|SET|OUT|NOV|DEZ)[A-Z]*/?\s?(\d{4})\b"
)
ADDRESS_START = re.compile(r"^(RUA|R\.|AVENIDA|AV\.?|TRAVESSA|TV\.?|ALAMEDA|AL\.?|ESTRADA|RODOVIA|PRACA|LARGO|QUADRA|SQN|SQS)\b")
UTILITY_ISSUERS = (
    "ENEL",
    "CEMIG",
    "COPEL",
    "CPFL",
    "LIGHT",
    "ELETROPAULO",
    "EQUATORIAL",
    "ENERGISA",
    "NEOENERGIA",
    "COELBA",
    "CELPE",
    "SABESP",
    "COPASA",
    "CEDAE",
    "SANEPAR",
    "EMBASA",
    "COMPESA",
    "CORSAN",
    "CAESB",
    "CLARO",
    "VIVO",
    "TIM",
    "OI",
    "NET",
    "SKY",
    "COMGAS",
    "NATURGY",
)

KINDS = {
    "boleto": "Boleto",
    "nfe": "Nota fiscal (DANFE)",
    "receipt": "Cupom fiscal",
    "cnpj_card": "Cartão CNPJ",
    "residence": "Comprovante de residência",
}
KIND_KEYWORDS = {
    "boleto": {
        "PAGAVEL": 3,
        "BENEFICIARIO": 2,
        "CEDENTE": 2,
        "NOSSO NUMERO": 3,
        "LOCAL DE PAGAMENTO": 3,
        "SACADO": 1,
        "PAGADOR": 1,
    },
    "nfe": {"DANFE": 6, "DOCUMENTO AUXILIAR DA NOTA FISCAL": 6, "CHAVE DE ACESSO": 3, "NATUREZA DA OPERACAO": 2},
    "receipt": {"CUPOM FISCAL": 5, "CF-E": 4, "NFC-E": 5, "EXTRATO": 1, "CONSUMIDOR": 2, "SAT": 1},
    "cnpj_card": {
        "COMPROVANTE DE INSCRICAO E DE SITUACAO CADASTRAL": 8,
        "NOME EMPRESARIAL": 4,
        "SITUACAO CADASTRAL": 3,
        "NATUREZA JURIDICA": 3,
    },
    "residence": {"CONSUMO": 2, "LEITURA": 2, "INSTALACAO": 2, "REFERENCIA": 2, "KWH": 3, "M3": 2, "FATURA": 2, "CONTA": 1},
}


def classify(text: str) -> str:
    compacted = compact(text)
    scores = {
        kind: sum(weight for word, weight in words.items() if compact(word) in compacted) for kind, words in KIND_KEYWORDS.items()
    }
    if any(issuer in normalize(text).split() for issuer in UTILITY_ISSUERS):
        scores["residence"] += 3
    kind, score = max(scores.items(), key=lambda item: item[1])
    return kind if score > 0 else "residence"


def find_digit_sequences(text: str, length: int) -> list[str]:
    found = []
    for match in DIGIT_RUN.finditer(text):
        digits = only_digits(match.group(0))
        for start in range(0, len(digits) - length + 1):
            found.append(digits[start : start + length])
    return found


def first_match(pattern: re.Pattern, text: str, check: Callable[[str], bool] = bool) -> str | None:
    return next((match.group(0) for match in pattern.finditer(text) if check(match.group(0))), None)


def money_after(lines: list[str], labels: tuple[str, ...]) -> str | None:
    for index, line in enumerate(lines):
        normalized = strip_accents(line.upper())
        if any(label in normalized for label in labels):
            for candidate in (line, *lines[index + 1 : index + 3]):
                amounts = MONEY_PATTERN.findall(candidate)
                if amounts:
                    return format_money(parse_money(amounts[-1]))
    return None


def value_of(
    boxes: list[TextBox], labels: tuple[str, ...], accepts: Callable[[str], bool] = lambda text: len(text.strip()) >= 2
) -> str | None:
    field = find_value(boxes, labels, labels, accepts)
    return field.value.strip() if field else None


def date_after(lines: list[str], labels: tuple[str, ...]) -> str | None:
    for index, line in enumerate(lines):
        if any(label in strip_accents(line.upper()) for label in labels):
            for candidate in (line, *lines[index + 1 : index + 3]):
                match = DATE_PATTERN.search(candidate)
                if match and (parsed := parse_brazilian_date(match.group(0))):
                    return format_brazilian_date(parsed)
    return None


def parse_boleto(text: str, lines: list[str], boxes: list[TextBox]) -> tuple[dict[str, str], list[dict[str, str]]]:
    slip = None
    for length in (47, 48):
        for digits in find_digit_sequences(text, length):
            candidate = parse_bank_slip(digits)
            if candidate and (slip is None or (candidate.valid and not slip.valid)):
                slip = candidate
        if slip and slip.valid:
            break
    values: dict[str, str] = {}
    issues = []
    if slip:
        values["digitable_line"] = format_bank_line(slip.digitable_line)
        values["slip_kind"] = "Bancário" if slip.kind == "bancario" else "Arrecadação (concessionárias e tributos)"
        if slip.amount:
            values["amount"] = format_money(slip.amount)
        if slip.due_date:
            values["due_date"] = format_brazilian_date(slip.due_date)
        if slip.bank_code:
            values["bank_code"] = slip.bank_code
        if not slip.valid:
            issues.append(
                {"field": "digitable_line", "code": "invalid", "message": "Dígitos verificadores da linha digitável não conferem"}
            )
    else:
        issues.append({"field": "digitable_line", "code": "missing", "message": "Linha digitável não encontrada"})
    values.setdefault("amount", money_after(lines, ("VALOR DO DOCUMENTO", "VALOR COBRADO", "(=) VALOR")) or "")
    values.setdefault("due_date", date_after(lines, ("VENCIMENTO",)) or "")
    values["beneficiary"] = value_of(boxes, ("BENEFICIARIO", "CEDENTE")) or ""
    values["payer"] = value_of(boxes, ("PAGADOR", "SACADO")) or ""
    cnpj = first_match(CNPJ_PATTERN, text, is_valid_cnpj)
    if cnpj:
        values["beneficiary_cnpj"] = format_cnpj(cnpj)
    return values, issues


def parse_nfe(text: str, lines: list[str], boxes: list[TextBox]) -> tuple[dict[str, str], list[dict[str, str]]]:
    keys = find_digit_sequences(text, 44)
    key = next((candidate for candidate in keys if is_valid_nfe_key(candidate)), keys[0] if keys else None)
    values: dict[str, str] = {}
    issues = []
    if key:
        values["access_key"] = format_nfe_key(key)
        values["issuer_cnpj"] = format_cnpj(nfe_key_cnpj(key))
        values["invoice_number"] = str(int(key[25:34]))
        values["series"] = str(int(key[22:25]))
        if not is_valid_nfe_key(key):
            issues.append(
                {"field": "access_key", "code": "invalid", "message": "Dígito verificador da chave de acesso não confere"}
            )
    else:
        issues.append({"field": "access_key", "code": "missing", "message": "Chave de acesso não encontrada"})
    values["issuer_name"] = value_of(boxes, ("RAZAO SOCIAL", "EMITENTE", "IDENTIFICACAO DO EMITENTE")) or (
        lines[0] if lines else ""
    )
    values["issue_date"] = date_after(lines, ("DATA DA EMISSAO", "DATA DE EMISSAO", "EMISSAO")) or ""
    values["amount"] = money_after(lines, ("VALOR TOTAL DA NOTA", "V. TOTAL DA NOTA", "VALOR TOTAL")) or ""
    return values, issues


def parse_receipt(text: str, lines: list[str], boxes: list[TextBox]) -> tuple[dict[str, str], list[dict[str, str]]]:
    values = {
        "issuer_name": lines[0] if lines else "",
        "amount": money_after(lines, ("VALOR TOTAL", "TOTAL R$", "TOTAL")) or "",
        "issue_date": first_match(DATE_PATTERN, text, lambda value: parse_brazilian_date(value) is not None) or "",
    }
    cnpj = first_match(CNPJ_PATTERN, text, is_valid_cnpj)
    if cnpj:
        values["issuer_cnpj"] = format_cnpj(cnpj)
    keys = [candidate for candidate in find_digit_sequences(text, 44) if is_valid_nfe_key(candidate)]
    if keys:
        values["access_key"] = format_nfe_key(keys[0])
    consumer = first_match(CPF_PATTERN, text, is_valid_cpf)
    if consumer:
        values["consumer_cpf"] = format_cpf(only_digits(consumer))
    return values, []


def parse_cnpj_card(text: str, lines: list[str], boxes: list[TextBox]) -> tuple[dict[str, str], list[dict[str, str]]]:
    cnpj = first_match(CNPJ_PATTERN, text)
    values = {
        "cnpj": format_cnpj(cnpj) if cnpj else "",
        "company_name": value_of(boxes, ("NOME EMPRESARIAL",)) or "",
        "trade_name": value_of(boxes, ("TITULO DO ESTABELECIMENTO (NOME DE FANTASIA)", "NOME DE FANTASIA")) or "",
        "opening_date": date_after(lines, ("DATA DE ABERTURA",)) or "",
        "status": value_of(boxes, ("SITUACAO CADASTRAL",), lambda value: not DATE_PATTERN.search(value)) or "",
        "main_activity": value_of(boxes, ("CODIGO E DESCRICAO DA ATIVIDADE ECONOMICA PRINCIPAL",)) or "",
        "legal_nature": value_of(boxes, ("CODIGO E DESCRICAO DA NATUREZA JURIDICA",)) or "",
        "address": " ".join(
            filter(None, (value_of(boxes, (label,)) for label in ("LOGRADOURO", "NUMERO", "BAIRRO/DISTRITO", "MUNICIPIO", "UF")))
        ),
        "postal_code": first_match(CEP_PATTERN, text) or "",
    }
    issues = []
    if cnpj and not is_valid_cnpj(cnpj):
        issues.append({"field": "cnpj", "code": "invalid", "message": "Dígitos verificadores do CNPJ não conferem"})
    return values, issues


def parse_residence(text: str, lines: list[str], boxes: list[TextBox]) -> tuple[dict[str, str], list[dict[str, str]]]:
    normalized_words = normalize(text).split()
    issuer = next((name for name in UTILITY_ISSUERS if name in normalized_words), None)
    address = next((line for line in lines if ADDRESS_START.match(strip_accents(line.upper()))), "")
    reference = REFERENCE_PATTERN.search(strip_accents(text.upper()))
    values = {
        "holder_name": value_of(boxes, ("TITULAR", "CLIENTE", "NOME DO CLIENTE", "NOME")) or "",
        "address": address,
        "postal_code": first_match(CEP_PATTERN, text) or "",
        "issuer": issuer or (lines[0] if lines else ""),
        "reference": reference.group(0) if reference else "",
        "due_date": date_after(lines, ("VENCIMENTO",)) or "",
        "amount": money_after(lines, ("TOTAL A PAGAR", "VALOR A PAGAR", "VALOR TOTAL", "TOTAL")) or "",
    }
    document = first_match(CPF_PATTERN, text, is_valid_cpf)
    if document:
        values["holder_document"] = format_cpf(only_digits(document))
    issues = []
    if not values["address"]:
        issues.append({"field": "address", "code": "missing", "message": "Endereço não encontrado"})
    return values, issues


PARSERS = {
    "boleto": parse_boleto,
    "nfe": parse_nfe,
    "receipt": parse_receipt,
    "cnpj_card": parse_cnpj_card,
    "residence": parse_residence,
}


@register_module
class FinanceModule(OcrModule):
    key = "finance"
    name = "Financeiro"
    description = "Boletos com linha digitável validada, notas fiscais, cupons, cartão CNPJ e comprovantes de residência."
    icon = "receipt"
    multi_page = True
    max_pages = 4
    exports = ("txt",)
    kinds = KINDS
    fields_by_kind = {
        "boleto": (
            FieldSpec("digitable_line", "Linha digitável"),
            FieldSpec("slip_kind", "Tipo de boleto", "readonly"),
            FieldSpec("amount", "Valor"),
            FieldSpec("due_date", "Vencimento", "date"),
            FieldSpec("beneficiary", "Beneficiário"),
            FieldSpec("beneficiary_cnpj", "CNPJ do beneficiário"),
            FieldSpec("payer", "Pagador"),
            FieldSpec("bank_code", "Banco"),
        ),
        "nfe": (
            FieldSpec("access_key", "Chave de acesso"),
            FieldSpec("issuer_name", "Emitente"),
            FieldSpec("issuer_cnpj", "CNPJ do emitente"),
            FieldSpec("invoice_number", "Número"),
            FieldSpec("series", "Série"),
            FieldSpec("issue_date", "Emissão", "date"),
            FieldSpec("amount", "Valor total"),
        ),
        "receipt": (
            FieldSpec("issuer_name", "Estabelecimento"),
            FieldSpec("issuer_cnpj", "CNPJ"),
            FieldSpec("issue_date", "Data", "date"),
            FieldSpec("amount", "Total"),
            FieldSpec("consumer_cpf", "CPF do consumidor"),
            FieldSpec("access_key", "Chave de acesso"),
        ),
        "cnpj_card": (
            FieldSpec("cnpj", "CNPJ"),
            FieldSpec("company_name", "Nome empresarial"),
            FieldSpec("trade_name", "Nome fantasia"),
            FieldSpec("opening_date", "Data de abertura", "date"),
            FieldSpec("status", "Situação cadastral"),
            FieldSpec("main_activity", "Atividade principal"),
            FieldSpec("legal_nature", "Natureza jurídica"),
            FieldSpec("address", "Endereço"),
            FieldSpec("postal_code", "CEP"),
        ),
        "residence": (
            FieldSpec("holder_name", "Titular"),
            FieldSpec("holder_document", "CPF do titular"),
            FieldSpec("address", "Endereço"),
            FieldSpec("postal_code", "CEP"),
            FieldSpec("issuer", "Emissor"),
            FieldSpec("reference", "Referência"),
            FieldSpec("due_date", "Vencimento", "date"),
            FieldSpec("amount", "Valor"),
        ),
    }

    def process(self, context: ProcessingContext, uploads: list[bytes]) -> ModuleOutput:
        pages: list[PageOutput] = []
        sides: list[list[TextBox]] = []
        texts: list[str] = []
        lines: list[str] = []
        language = None
        for content in uploads:
            prepared = prepare_image(content)
            reading = context.read(prepared.ocr_image)
            language = language or reading.language
            layout = analyze_layout(reading.boxes)
            image, mime = load_image(content)
            sides.append(reading.boxes)
            texts.append("\n".join(box.text for box in sorted(reading.boxes, key=lambda box: (box.y0, box.x0))))
            lines.extend(box.text for box in sorted(reading.boxes, key=lambda box: (box.y0, box.x0)))
            page_layout = {**layout.as_dict(), "boxes": boxes_payload(reading.boxes, reading.image)}
            pages.append(PageOutput(content, reading.image, mime, layout.text, page_layout, image.width, image.height))
        text = "\n".join(texts)
        kind = context.options.get("kind") if context.options.get("kind") in KINDS else classify(text)
        boxes = combine_sides(*sides)
        values, issues = PARSERS[kind](text, lines, boxes)
        confidence = mean_box_confidence([box for side in sides for box in side])
        fields = {name: FieldValue(value, confidence) for name, value in values.items() if value}
        title = self.title_for(kind, values)
        return ModuleOutput(
            kind=kind,
            title=title,
            fields=fields,
            issues=issues,
            pages=pages,
            language=language,
            confidence=confidence,
            search_text=text,
        )

    @staticmethod
    def title_for(kind: str, values: dict[str, str]) -> str:
        label = KINDS[kind]
        detail = (
            values.get("beneficiary") or values.get("issuer_name") or values.get("company_name") or values.get("issuer") or ""
        )
        amount = values.get("amount")
        return " · ".join(filter(None, (label, detail[:60], amount)))

    def validate(self, kind: str | None, values: dict[str, str]) -> list[dict[str, str]]:
        issues = []
        if kind == "boleto" and values.get("digitable_line"):
            slip = parse_bank_slip(values["digitable_line"])
            if slip is None or not slip.valid:
                issues.append({"field": "digitable_line", "code": "invalid", "message": "Linha digitável inválida"})
        if kind in ("nfe", "receipt") and values.get("access_key") and not is_valid_nfe_key(values["access_key"]):
            issues.append({"field": "access_key", "code": "invalid", "message": "Chave de acesso inválida"})
        for name in ("cnpj", "issuer_cnpj", "beneficiary_cnpj"):
            if values.get(name) and not is_valid_cnpj(values[name]):
                issues.append({"field": name, "code": "invalid", "message": "CNPJ inválido"})
        return issues
