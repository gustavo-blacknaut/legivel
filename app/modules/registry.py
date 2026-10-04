from app.modules.base import OcrModule

_MODULES: dict[str, OcrModule] = {}


def register_module(module_class: type[OcrModule]) -> type[OcrModule]:
    _MODULES[module_class.key] = module_class()
    return module_class


def load_modules() -> None:
    from app.modules import books, cards, finance, scanner  # noqa: F401


def get_module(key: str) -> OcrModule:
    load_modules()
    if key not in _MODULES:
        raise KeyError(f"Módulo desconhecido: {key}")
    return _MODULES[key]


def all_modules() -> list[OcrModule]:
    load_modules()
    return list(_MODULES.values())
