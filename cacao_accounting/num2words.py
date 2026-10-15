# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes
"""Módulo independiente y reusable para la conversión de números a letras.

Soporta internacionalización (i18n) y localización (l10n). El idioma se
selecciona explícitamente mediante ``lang`` o, en su defecto, con el idioma
activo de la aplicación (``cacao_accounting.i18n._get_locale``).

Cada idioma se describe con una :class:`_LanguageSpec` que reúne sus tablas
(unidades, decenas, centenas y escalas) y su estrategia de composición. La
composición del importe (signo, moneda y centavos) es compartida, de modo que
agregar un idioma nuevo consiste en declarar una ``_LanguageSpec`` y registrarla
en ``_LANGUAGES`` sin duplicar la lógica común.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Callable

from cacao_accounting.i18n import _get_locale

__all__ = ["num2words", "numero_a_letras", "register_language", "available_languages", "SPANISH", "ENGLISH"]


@dataclass(frozen=True)
class _Scale:
    """Escala numérica: forma singular ("un mil") y plural ("mil", "millones")."""

    value: int
    one_form: str
    plural: str


@dataclass(frozen=True)
class _LanguageSpec:
    """Estructura común para describir un idioma de conversión numérica.

    ``resolver`` convierte un entero a letras usando las tablas de la propia
    spec; ``hundreds`` puede quedar vacío cuando el idioma compone las centenas
    con un rótulo (por ejemplo el inglés, que usa ``hundred_label``).
    """

    code: str
    units: tuple[str, ...]
    tens: tuple[str, ...]
    scales: tuple[_Scale, ...]
    zero: str
    minus: str
    connector: str
    resolver: Callable[["_LanguageSpec", int, bool], str]
    hundreds: tuple[str, ...] = ()
    hundred_label: str = ""


UNIDADES_ES = (
    "",
    "UN",
    "DOS",
    "TRES",
    "CUATRO",
    "CINCO",
    "SEIS",
    "SIETE",
    "OCHO",
    "NUEVE",
    "DIEZ",
    "ONCE",
    "DOCE",
    "TRECE",
    "CATORCE",
    "QUINCE",
    "DIECISÉIS",
    "DIECISIETE",
    "DIECIOCHO",
    "DIECINUEVE",
    "VEINTE",
    "VEINTIUNO",
    "VEINTIDÓS",
    "VEINTITRÉS",
    "VEINTICUATRO",
    "VEINTICINCO",
    "VEINTISÉIS",
    "VEINTISIETE",
    "VEINTIOCHO",
    "VEINTINUEVE",
)

DECENAS_ES = ("", "", "", "TREINTA", "CUARENTA", "CINCUENTA", "SESENTA", "SETENTA", "OCHENTA", "NOVENTA")

CENTENAS_ES = (
    "",
    "CIENTO",
    "DOSCIENTOS",
    "TRESCIENTOS",
    "CUATROCIENTOS",
    "QUINIENTOS",
    "SEISCIENTOS",
    "SETECIENTOS",
    "OCHOCIENTOS",
    "NOVECIENTOS",
)

EN_UNITS = (
    "",
    "ONE",
    "TWO",
    "THREE",
    "FOUR",
    "FIVE",
    "SIX",
    "SEVEN",
    "EIGHT",
    "NINE",
    "TEN",
    "ELEVEN",
    "TWELVE",
    "THIRTEEN",
    "FOURTEEN",
    "FIFTEEN",
    "SIXTEEN",
    "SEVENTEEN",
    "EIGHTEEN",
    "NINETEEN",
)

EN_TENS = ("", "", "TWENTY", "THIRTY", "FORTY", "FIFTY", "SIXTY", "SEVENTY", "EIGHTY", "NINETY")


def _es_two_digits(spec: _LanguageSpec, num: int, apocope: bool = False) -> str:
    """Convierte 0-99 a letras en español; ``apocope`` aplica la forma corta (veintiún)."""
    if num == 0:
        return ""
    if num < 30:
        if num == 21 and apocope:
            return "VEINTIÚN"
        return spec.units[num]

    decenas, unidades = divmod(num, 10)
    if unidades == 0:
        return spec.tens[decenas]
    return f"{spec.tens[decenas]} Y {spec.units[unidades]}"


def _es_three_digits(spec: _LanguageSpec, num: int, apocope: bool = False) -> str:
    """Convierte 0-999 a letras en español."""
    if num == 0:
        return ""
    if num == 100:
        return "CIEN"

    centenas, resto = divmod(num, 100)
    partes = [spec.hundreds[centenas] if centenas else "", _es_two_digits(spec, resto, apocope)]
    return " ".join(parte for parte in partes if parte)


def _es_multiplier(spec: _LanguageSpec, num: int) -> str:
    """Convierte el multiplicador de una escala aplicando la apócope final."""
    if num < 1000:
        return _es_three_digits(spec, num, apocope=True)

    miles, resto = divmod(num, 1000)
    prefijo = "UN MIL" if miles == 1 else f"{_es_three_digits(spec, miles, apocope=True)} MIL"
    sufijo = _es_three_digits(spec, resto, apocope=True)
    return " ".join(parte for parte in (prefijo, sufijo) if parte)


def _es_resolver(spec: _LanguageSpec, num: int, apocope: bool = False) -> str:
    """Convierte un entero a letras en español usando escalas declarativas."""
    if num == 0:
        return spec.zero
    partes: list[str] = []
    restante = num
    for scale in spec.scales:
        if restante < scale.value:
            continue
        cuenta, restante = divmod(restante, scale.value)
        partes.append(scale.one_form if cuenta == 1 else f"{_es_multiplier(spec, cuenta)} {scale.plural}")
    if restante > 0:
        partes.append(_es_three_digits(spec, restante, apocope))
    return " ".join(parte for parte in partes if parte)


def _en_two_digits(spec: _LanguageSpec, num: int, apocope: bool = False) -> str:
    """Convierte 0-99 a letras en inglés."""
    if num == 0:
        return ""
    if num < 20:
        return spec.units[num]
    decenas, unidades = divmod(num, 10)
    if unidades == 0:
        return spec.tens[decenas]
    return f"{spec.tens[decenas]} {spec.units[unidades]}"


def _en_three_digits(spec: _LanguageSpec, num: int, apocope: bool = False) -> str:
    """Convierte 0-999 a letras en inglés."""
    if num == 0:
        return ""
    centenas, resto = divmod(num, 100)
    partes = [f"{spec.units[centenas]} {spec.hundred_label}" if centenas else "", _en_two_digits(spec, resto)]
    return " ".join(parte for parte in partes if parte)


def _en_resolver(spec: _LanguageSpec, num: int, apocope: bool = False) -> str:
    """Convierte un entero a letras en inglés usando escalas declarativas."""
    if num == 0:
        return spec.zero
    partes: list[str] = []
    restante = num
    for scale in spec.scales:
        if restante < scale.value:
            continue
        cuenta, restante = divmod(restante, scale.value)
        partes.append(scale.one_form if cuenta == 1 else f"{_en_resolver(spec, cuenta)} {scale.plural}")
    if restante > 0:
        partes.append(_en_three_digits(spec, restante))
    return " ".join(parte for parte in partes if parte)


SPANISH = _LanguageSpec(
    code="es",
    units=UNIDADES_ES,
    tens=DECENAS_ES,
    hundreds=CENTENAS_ES,
    scales=(
        _Scale(10**12, "UN BILLÓN", "BILLONES"),
        _Scale(10**6, "UN MILLÓN", "MILLONES"),
        _Scale(10**3, "UN MIL", "MIL"),
    ),
    zero="CERO",
    minus="MENOS",
    connector="CON",
    resolver=_es_resolver,
)

ENGLISH = _LanguageSpec(
    code="en",
    units=EN_UNITS,
    tens=EN_TENS,
    hundred_label="HUNDRED",
    scales=(
        _Scale(10**12, "ONE TRILLION", "TRILLION"),
        _Scale(10**9, "ONE BILLION", "BILLION"),
        _Scale(10**6, "ONE MILLION", "MILLION"),
        _Scale(10**3, "ONE THOUSAND", "THOUSAND"),
    ),
    zero="ZERO",
    minus="MINUS",
    connector="AND",
    resolver=_en_resolver,
)

DEFAULT_LANGUAGE = "es"

# Registro de idiomas disponibles. Agregar un idioma nuevo consiste en declarar
# su `_LanguageSpec` y llamar a `register_language`; la composición del importe
# y la resolución de locale (incluidas variantes regionales tipo "es-NI") se
# comparten sin tocar el resto del módulo.
_LANGUAGES: dict[str, _LanguageSpec] = {}


def register_language(spec: _LanguageSpec) -> _LanguageSpec:
    """Registra (o reemplaza) una especificación de idioma por su código ISO."""
    _LANGUAGES[spec.code] = spec
    return spec


def available_languages() -> tuple[str, ...]:
    """Devuelve los códigos de idioma registrados."""
    return tuple(sorted(_LANGUAGES))


def _resolve_spec(lang: str | None) -> _LanguageSpec:
    """Selecciona la especificación de idioma aceptando variantes regionales.

    ``lang`` o el idioma activo se normalizan (``es_NI`` -> ``es-ni``) y se
    resuelven primero por código completo y luego por subetiqueta primaria
    (``es``), con ``DEFAULT_LANGUAGE`` como último recurso.
    """
    target_lang = str(lang or _get_locale() or DEFAULT_LANGUAGE).lower().replace("_", "-")
    primary = target_lang.split("-", 1)[0]
    return _LANGUAGES.get(target_lang) or _LANGUAGES.get(primary) or _LANGUAGES[DEFAULT_LANGUAGE]


register_language(SPANISH)
register_language(ENGLISH)


def num2words(amount: Any, currency: str | None = None, lang: str | None = None) -> str:
    """Convierte un importe numérico a su representación en letras."""
    try:
        num = Decimal(str(amount or 0)).quantize(Decimal("0.01"))
    except (TypeError, ValueError, ArithmeticError):
        num = Decimal("0.00")
    return _format_amount(_resolve_spec(lang), num, currency)


def numero_a_letras(amount: Any, currency: str | None = None, lang: str | None = None) -> str:
    """Alias en español para compatibilidad con ``num2words``."""
    return num2words(amount, currency=currency, lang=lang)


def _format_amount(spec: _LanguageSpec, num: Decimal, currency: str | None) -> str:
    """Compone el importe en letras con la moneda y los centavos (xx/100)."""
    if num < 0:
        return f"{spec.minus} {_format_amount(spec, abs(num), currency)}"

    absolute = abs(num)
    entero = int(absolute)
    centavos = int(round((absolute - entero) * 100))
    if centavos == 100:
        entero += 1
        centavos = 0

    texto_entero = spec.resolver(spec, entero, False) if entero else spec.zero
    curr_str = f" {currency.strip().upper()}" if currency and currency.strip() else ""
    return f"{texto_entero}{curr_str} {spec.connector} {centavos:02d}/100"
