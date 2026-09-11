"""File-based internationalization for the NEOMapper UI and renderers."""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

LOCALES_DIR = Path(__file__).with_name("locales")
DEFAULT_LOCALE = "en"
ALIASES = {"EN": "en", "PT": "pt-BR", "PT_BR": "pt-BR", "ES": "es"}


def normalize_locale(locale: str | None) -> str:
    value = (locale or DEFAULT_LOCALE).strip().replace("_", "-")
    return ALIASES.get(value.upper(), value)


@lru_cache(maxsize=32)
def load_catalog(locale: str | None) -> dict:
    code = normalize_locale(locale)
    path = LOCALES_DIR / f"{code}.json"
    if not path.exists() and "-" in code:
        path = LOCALES_DIR / f"{code.split('-', 1)[0]}.json"
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    return data.get("translations", data)


def available_locales() -> list[tuple[str, str]]:
    locales = []
    for path in sorted(LOCALES_DIR.glob("*.json")):
        with path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
        locales.append((data.get("code", path.stem), data.get("name", path.stem)))
    return locales


class Translator:
    def __init__(self, locale: str | None):
        self.locale = normalize_locale(locale)
        self.fallback = load_catalog(DEFAULT_LOCALE)
        self.catalog = load_catalog(self.locale)

    def tr(self, key: str, **values) -> str:
        text = self.catalog.get(key, self.fallback.get(key, key))
        try:
            return text.format(**values)
        except (KeyError, ValueError):
            return text

    def merged(self, legacy: dict | None = None) -> dict:
        result = dict(self.fallback)
        if legacy:
            result.update(legacy)
        result.update(self.catalog)
        return result


def format_number(value, decimals: int = 0, locale: str | None = None, grouping: bool = True) -> str:
    """Format display numbers using the selected language conventions."""
    code = normalize_locale(locale).lower()
    precision = max(0, int(decimals))
    text = format(float(value), f",.{precision}f" if grouping else f".{precision}f")
    if code.startswith(("pt", "es")):
        return text.replace(",", "\u0000").replace(".", ",").replace("\u0000", ".")
    return text
