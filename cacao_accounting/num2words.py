# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes
"""Módulo independiente y reusable para la conversión de números a letras.

Soporta internacionalización (i18n) y localización (l10n) usando el sistema
de traducción existente de Cacao Accounting (`cacao_accounting.i18n`).
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from cacao_accounting.i18n import _, _get_locale

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


def num2words(amount: Any, currency: str | None = None, lang: str | None = None) -> str:
    """Convierte un importe numérico a su representación en letras.

    Utiliza el idioma especificado o el idioma activo de la aplicación mediante `_get_locale()`.
    """
    try:
        num = Decimal(str(amount or 0)).quantize(Decimal("0.01"))
    except (TypeError, ValueError, ArithmeticError):
        num = Decimal("0.00")

    target_lang = str(lang or _get_locale() or "es").lower()
    if target_lang.startswith("en"):
        return _amount_to_words_en(num, currency)
    return _amount_to_words_es(num, currency)


def numero_a_letras(amount: Any, currency: str | None = None, lang: str | None = None) -> str:
    """Alias para compatibilidad con `num2words`."""
    return num2words(amount, currency=currency, lang=lang)


def _amount_to_words_es(num: Decimal, currency: str | None = None) -> str:
    """Convierte un importe numérico a letras en español utilizando Flask-Babel / i18n."""
    if num < 0:
        prefix = _("MENOS")
        return f"{prefix} {_amount_to_words_es(abs(num), currency)}"

    entero = int(abs(num))
    centavos = int(round((abs(num) - entero) * 100))

    texto_entero = _("CERO") if entero == 0 else _convertir_entero_a_letras_es(entero)
    curr_str = f" {currency.strip().upper()}" if currency and currency.strip() else ""
    con_str = _("CON")
    return f"{texto_entero}{curr_str} {con_str} {centavos:02d}/100"


def _amount_to_words_en(num: Decimal, currency: str | None = None) -> str:
    """Convierte un importe numérico a letras en inglés utilizando Flask-Babel / i18n."""
    if num < 0:
        prefix = _("MINUS")
        return f"{prefix} {_amount_to_words_en(abs(num), currency)}"

    integer_part = int(abs(num))
    cents_part = int(round((abs(num) - integer_part) * 100))

    text_integer = _("ZERO") if integer_part == 0 else _convert_integer_to_words_en(integer_part)
    curr_str = f" {currency.strip().upper()}" if currency and currency.strip() else ""
    and_str = _("AND")
    return f"{text_integer}{curr_str} {and_str} {cents_part:02d}/100"


def _convertir_grupo_tres_cifras_es(num: int) -> str:
    """Convierte un grupo de tres cifras (0-999) a letras en español."""
    if num == 0:
        return ""
    if num == 100:
        return _("CIEN")

    c = num // 100
    resto = num % 100
    str_c = _(CENTENAS_ES[c]) if c > 0 else ""

    if resto == 0:
        return str_c

    if resto < 30:
        str_r = _(UNIDADES_ES[resto])
    else:
        d = resto // 10
        u = resto % 10
        y_str = _("Y")
        str_r = f"{_(DECENAS_ES[d])} {y_str} {_(UNIDADES_ES[u])}" if u > 0 else _(DECENAS_ES[d])

    return f"{str_c} {str_r}".strip()


def _convertir_miles_es(n: int) -> str:
    """Convierte miles (1000-999999) a letras en español."""
    miles = n // 1000
    resto = n % 1000
    mil_str = _("MIL")
    un_mil_str = _("UN MIL")
    str_miles = un_mil_str if miles == 1 else f"{_convertir_grupo_tres_cifras_es(miles)} {mil_str}"

    if str_miles.endswith("VEINTIUNO MIL"):
        str_miles = str_miles[:-13] + f"{_('VEINTIÚN')} {mil_str}"
    elif str_miles.endswith("UNO MIL") and not str_miles.endswith("VEINTIUNO MIL"):
        str_miles = str_miles[:-7] + f"{_('UN')} {mil_str}"

    str_resto = _convertir_grupo_tres_cifras_es(resto)
    return f"{str_miles} {str_resto}".strip()


def _convertir_millones_es(n: int) -> str:
    """Convierte millones (>=1000000) a letras en español."""
    millones = n // 1000000
    resto = n % 1000000
    un_millon_str = _("UN MILLÓN")
    millones_str = _("MILLONES")
    str_millones = un_millon_str if millones == 1 else f"{_convertir_entero_a_letras_es(millones)} {millones_str}"

    if str_millones.endswith("VEINTIUNO MILLONES"):
        str_millones = str_millones[:-18] + f"{_('VEINTIÚN')} {millones_str}"
    elif str_millones.endswith("UNO MILLONES"):
        str_millones = str_millones[:-12] + f"{_('UN')} {millones_str}"

    str_resto = _convertir_entero_a_letras_es(resto)
    return f"{str_millones} {str_resto}".strip()


def _convertir_entero_a_letras_es(n: int) -> str:
    """Convierte la parte entera de un número a letras en español."""
    if n < 1000:
        return _convertir_grupo_tres_cifras_es(n)
    if n < 1000000:
        return _convertir_miles_es(n)
    return _convertir_millones_es(n)


def _convert_3digits_en(num: int) -> str:
    """Convierte un grupo de tres cifras (0-999) a letras en inglés."""
    if num == 0:
        return ""
    h = num // 100
    rem = num % 100
    hundred_str = _("HUNDRED")
    res = f"{_(EN_UNITS[h])} {hundred_str}" if h > 0 else ""

    if rem == 0:
        return res

    if rem < 20:
        str_rem = _(EN_UNITS[rem])
    else:
        t = rem // 10
        u = rem % 10
        str_rem = f"{_(EN_TENS[t])} {_(EN_UNITS[u])}" if u > 0 else _(EN_TENS[t])

    return f"{res} {str_rem}".strip()


def _convert_integer_to_words_en(n: int) -> str:
    """Convierte la parte entera de un número a letras en inglés."""
    if n == 0:
        return ""
    if n < 1000:
        return _convert_3digits_en(n)
    if n < 1000000:
        thousands = n // 1000
        rem = n % 1000
        thousand_str = _("THOUSAND")
        str_th = f"{_convert_3digits_en(thousands)} {thousand_str}"
        str_rem = _convert_3digits_en(rem)
        return f"{str_th} {str_rem}".strip()

    millions = n // 1000000
    rem = n % 1000000
    million_str = _("MILLION")
    str_mil = f"{_convert_integer_to_words_en(millions)} {million_str}"
    str_rem = _convert_integer_to_words_en(rem)
    return f"{str_mil} {str_rem}".strip()
