from legivel.parsers.base import DocumentParser

_PARSERS: dict[str, DocumentParser] = {}
BUILTIN_MODULES = (
    "legivel.parsers.cnh",
    "legivel.parsers.cpf",
    "legivel.parsers.rg",
    "legivel.parsers.passport",
    "legivel.parsers.voter",
    "legivel.parsers.certificate",
)


def register(parser_class: type[DocumentParser]) -> type[DocumentParser]:
    _PARSERS[parser_class.doc_type] = parser_class()
    return parser_class


def get_parser(doc_type: str) -> DocumentParser:
    load_builtin_parsers()
    if doc_type not in _PARSERS:
        raise KeyError(f"Tipo de documento não suportado: {doc_type}")
    return _PARSERS[doc_type]


def available_parsers() -> list[DocumentParser]:
    load_builtin_parsers()
    return list(_PARSERS.values())


def load_builtin_parsers() -> None:
    import importlib

    for name in BUILTIN_MODULES:
        importlib.import_module(name)
