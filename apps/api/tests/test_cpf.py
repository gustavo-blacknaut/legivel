import pytest

from legivel.validators.cpf import calculate_check_digits, format_cpf, is_valid_cpf, normalize_cpf


@pytest.mark.parametrize("cpf", ["529.982.247-25", "52998224725", "111.444.777-35", " 111 444 777 35 "])
def test_accepts_valid_cpf(cpf):
    assert is_valid_cpf(cpf)


@pytest.mark.parametrize(
    "cpf",
    ["529.982.247-24", "111.111.111-11", "000.000.000-00", "1234567890", "123456789012", "", "abc"],
)
def test_rejects_invalid_cpf(cpf):
    assert not is_valid_cpf(cpf)


def test_calculates_check_digits():
    assert calculate_check_digits("529982247") == "25"
    assert calculate_check_digits("111444777") == "35"


def test_normalize_returns_digits_only_when_valid():
    assert normalize_cpf("529.982.247-25") == "52998224725"
    assert normalize_cpf("529.982.247-26") is None


def test_format_cpf():
    assert format_cpf("52998224725") == "529.982.247-25"
    assert format_cpf("123") == "123"
