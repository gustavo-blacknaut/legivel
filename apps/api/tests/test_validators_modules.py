from datetime import date
from decimal import Decimal

import pytest

from legivel.ocr.languages import detect_latin_language
from legivel.parsers.mrz import parse_td3
from legivel.validators.cards import card_brand, luhn_is_valid, mask_card_number, parse_expiry
from legivel.validators.civil import (
    certificate_kind,
    format_certificate_number,
    is_plausible_certificate_number,
    is_valid_voter_id,
    voter_id_check_digits,
    voter_id_state,
)
from legivel.validators.financial import (
    bank_barcode_check_digit,
    cnpj_check_digits,
    collection_check_digit,
    format_bank_line,
    format_money,
    is_valid_cnpj,
    is_valid_nfe_key,
    modulo10,
    nfe_key_check_digit,
    parse_bank_slip,
    parse_money,
)


def build_bank_line(bank: str, factor: int, amount_cents: int, free_field: str) -> str:
    body = f"{bank}9{factor:04d}{amount_cents:010d}{free_field}"
    dv = bank_barcode_check_digit(body)
    barcode = body[:4] + str(dv) + body[4:]
    field1 = barcode[0:4] + barcode[19:24]
    field2 = barcode[24:34]
    field3 = barcode[34:44]
    return f"{field1}{modulo10(field1)}{field2}{modulo10(field2)}{field3}{modulo10(field3)}" + barcode[4] + barcode[5:19]


def build_collection_line(value_cents: int) -> str:
    body = f"86{value_cents:011d}0001" + "1" * 26
    barcode_without_dv = "8" + "6" + "6" + body[2:]
    barcode_without_dv = barcode_without_dv[:43]
    dv = collection_check_digit(barcode_without_dv, "6")
    barcode = barcode_without_dv[:3] + str(dv) + barcode_without_dv[3:]
    blocks = [barcode[index : index + 11] for index in range(0, 44, 11)]
    return "".join(block + str(collection_check_digit(block, "6")) for block in blocks)


@pytest.mark.parametrize(
    ("number", "brand"),
    [
        ("4111 1111 1111 1111", "Visa"),
        ("5555 5555 5555 4444", "Mastercard"),
        ("3782 822463 10005", "American Express"),
        ("6362 9700 0045 7013", "Elo"),
        ("6062 8256 2425 4001", "Hipercard"),
    ],
)
def test_luhn_and_brand_on_test_cards(number, brand):
    assert luhn_is_valid(number)
    assert card_brand(number) == brand


def test_luhn_rejects_typos():
    assert not luhn_is_valid("4111 1111 1111 1112")
    assert not luhn_is_valid("1234")


def test_card_masking_and_expiry():
    assert mask_card_number("4111111111111111") == "•••• •••• •••• 1111"
    expiry = parse_expiry("VALID THRU 08/29")
    assert expiry.label == "08/29"
    assert not expiry.is_expired(date(2026, 10, 5))
    assert parse_expiry("01/2020").is_expired(date(2026, 10, 5))


def test_bank_slip_line_is_validated_and_decoded():
    line = build_bank_line("001", 9999, 12345, "0" * 6 + "1234567890123456789")
    slip = parse_bank_slip(line, today=date(2025, 1, 1))
    assert slip.valid
    assert slip.kind == "bancario"
    assert slip.amount == Decimal("123.45")
    assert slip.bank_code == "001"
    assert slip.due_date == date(2025, 2, 21)
    assert format_bank_line(line).count(" ") == 4


def test_bank_slip_detects_wrong_digit():
    line = build_bank_line("341", 1500, 9990, "1" * 25)
    corrupted = line[:-1] + str((int(line[-1]) + 1) % 10)
    assert not parse_bank_slip(corrupted).valid


def test_collection_slip_is_validated():
    line = build_collection_line(15890)
    slip = parse_bank_slip(line)
    assert slip.kind == "arrecadacao"
    assert slip.valid
    assert slip.amount == Decimal("158.90")


def test_cnpj_validation():
    assert is_valid_cnpj("11.222.333/0001-81")
    assert not is_valid_cnpj("11.222.333/0001-80")
    assert not is_valid_cnpj("00.000.000/0000-00")
    assert cnpj_check_digits("112223330001") == "81"


def test_nfe_access_key():
    body = "35" + "2610" + "11222333000181" + "55" + "001" + "000012345" + "1" + "12345678"
    key = body + str(nfe_key_check_digit(body))
    assert len(key) == 44
    assert is_valid_nfe_key(key)
    assert not is_valid_nfe_key(key[:-1] + str((int(key[-1]) + 1) % 10))


def test_money_parsing_and_formatting():
    assert parse_money("R$ 1.234,56") == Decimal("1234.56")
    assert format_money(Decimal("1234.5")) == "R$ 1.234,50"


def test_voter_id_check_digits():
    sequence, state = "10293847", "02"
    digits = voter_id_check_digits(sequence, state)
    number = sequence + state + digits
    assert is_valid_voter_id(number)
    assert voter_id_state(number) == "MG"
    assert not is_valid_voter_id(sequence + state + str((int(digits[0]) + 1) % 10) + digits[1])
    assert not is_valid_voter_id("123456789999")


def test_certificate_number_structure():
    number = "104539" + "01" + "55" + "2015" + "1" + "00012" + "021" + "0004567" + "12"
    assert is_plausible_certificate_number(number)
    assert certificate_kind(number) == "Nascimento"
    assert format_certificate_number(number).startswith("104539 01 55 2015 1")
    assert not is_plausible_certificate_number(number[:-1])


def test_passport_mrz_icao_specimen():
    mrz = parse_td3(
        [
            "P<UTOERIKSSON<<ANNA<MARIA<<<<<<<<<<<<<<<<<<<",
            "L898902C36UTO7408122F1204159ZE184226B<<<<<10",
        ]
    )
    assert mrz.checks_valid
    assert mrz.surname == "ERIKSSON"
    assert mrz.given_names == "ANNA MARIA"
    assert mrz.passport_number == "L898902C3"
    assert mrz.nationality == "UTO"
    assert mrz.sex == "Feminino"
    assert mrz.birth_date == date(1974, 8, 12)


def test_passport_mrz_detects_tampering():
    mrz = parse_td3(
        [
            "P<UTOERIKSSON<<ANNA<MARIA<<<<<<<<<<<<<<<<<<<",
            "L898902C46UTO7408122F1204159ZE184226B<<<<<10",
        ]
    )
    assert not mrz.checks_valid


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("O documento foi enviado para a empresa e não houve resposta dos responsáveis", "pt"),
        ("The document was sent to the company and there was no answer from the people in charge", "en"),
        ("El documento fue enviado a la empresa y no hubo respuesta de los responsables", "es"),
        ("Le document a été envoyé à la société et il n'y a pas eu de réponse des responsables", "fr"),
    ],
)
def test_latin_language_detection(text, expected):
    assert detect_latin_language(text, ["pt", "en", "es", "fr", "de", "it"]) == expected
