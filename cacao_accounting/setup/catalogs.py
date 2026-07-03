# Copyright 2026
# Licensed under the Apache License, Version 2.0

"""Catálogos localizados para el asistente de configuración inicial."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

SUPPORTED_LANGUAGES = ("es", "en")
LANGUAGE_CHOICES = [
    ("es", "Español"),
    ("en", "English"),
]

AMERICA_CURRENCY_CODES = (
    "ARS",
    "BSD",
    "BBD",
    "BZD",
    "BOB",
    "BRL",
    "CAD",
    "CLP",
    "COP",
    "CRC",
    "CUP",
    "DOP",
    "GTQ",
    "GYD",
    "HTG",
    "HNL",
    "JMD",
    "MXN",
    "NIO",
    "PAB",
    "PYG",
    "PEN",
    "SRD",
    "TTD",
    "USD",
    "UYU",
    "VES",
    "XCD",
)
SETUP_SEED_CURRENCY_CODES = tuple(dict.fromkeys((*AMERICA_CURRENCY_CODES, "EUR")))


@dataclass(frozen=True)
class CountryOption:
    """País disponible para el setup inicial."""

    code: str
    name_es: str
    name_en: str
    currency: str


AMERICA_COUNTRIES = (
    CountryOption("AG", "Antigua y Barbuda", "Antigua and Barbuda", "XCD"),
    CountryOption("AR", "Argentina", "Argentina", "ARS"),
    CountryOption("BS", "Bahamas", "Bahamas", "BSD"),
    CountryOption("BB", "Barbados", "Barbados", "BBD"),
    CountryOption("BZ", "Belice", "Belize", "BZD"),
    CountryOption("BO", "Bolivia", "Bolivia", "BOB"),
    CountryOption("BR", "Brasil", "Brazil", "BRL"),
    CountryOption("CA", "Canadá", "Canada", "CAD"),
    CountryOption("CL", "Chile", "Chile", "CLP"),
    CountryOption("CO", "Colombia", "Colombia", "COP"),
    CountryOption("CR", "Costa Rica", "Costa Rica", "CRC"),
    CountryOption("CU", "Cuba", "Cuba", "CUP"),
    CountryOption("DM", "Dominica", "Dominica", "XCD"),
    CountryOption("DO", "República Dominicana", "Dominican Republic", "DOP"),
    CountryOption("EC", "Ecuador", "Ecuador", "USD"),
    CountryOption("SV", "El Salvador", "El Salvador", "USD"),
    CountryOption("US", "Estados Unidos", "United States", "USD"),
    CountryOption("GD", "Granada", "Grenada", "XCD"),
    CountryOption("GT", "Guatemala", "Guatemala", "GTQ"),
    CountryOption("GY", "Guyana", "Guyana", "GYD"),
    CountryOption("HT", "Haití", "Haiti", "HTG"),
    CountryOption("HN", "Honduras", "Honduras", "HNL"),
    CountryOption("JM", "Jamaica", "Jamaica", "JMD"),
    CountryOption("MX", "México", "Mexico", "MXN"),
    CountryOption("NI", "Nicaragua", "Nicaragua", "NIO"),
    CountryOption("PA", "Panamá", "Panama", "PAB"),
    CountryOption("PY", "Paraguay", "Paraguay", "PYG"),
    CountryOption("PE", "Perú", "Peru", "PEN"),
    CountryOption("KN", "San Cristóbal y Nieves", "Saint Kitts and Nevis", "XCD"),
    CountryOption("LC", "Santa Lucía", "Saint Lucia", "XCD"),
    CountryOption("VC", "San Vicente y las Granadinas", "Saint Vincent and the Grenadines", "XCD"),
    CountryOption("SR", "Surinam", "Suriname", "SRD"),
    CountryOption("TT", "Trinidad y Tobago", "Trinidad and Tobago", "TTD"),
    CountryOption("UY", "Uruguay", "Uruguay", "UYU"),
    CountryOption("VE", "Venezuela", "Venezuela", "VES"),
)


SETUP_TEXTS: dict[str, dict[str, str]] = {
    "es": {
        "title": "Asistente de configuración inicial",
        "subtitle": "Complete los pasos para crear la empresa predeterminada y configurar el sistema.",
        "eyebrow": "Cacao Accounting",
        "step_1": "Idioma",
        "step_2": "Regional",
        "step_3": "Empresa",
        "step_label": "Paso {step}",
        "language_title": "Elija el idioma del setup",
        "language_help": "El asistente usará este idioma durante la configuración inicial.",
        "language": "Idioma predeterminado",
        "regional_title": "Defina país y moneda",
        "regional_help": "La moneda se sugiere según el país y solo se listan monedas disponibles en la base de datos.",
        "country": "País predeterminado",
        "currency": "Moneda predeterminada",
        "company_title": "Datos de empresa",
        "company_help": "Estos datos crean la compañía base, su libro contable y el período inicial.",
        "company_code": "Código de empresa",
        "entity_type": "Tipo de entidad",
        "tax_id": "Identificación fiscal",
        "fiscal_year": "Año fiscal",
        "fiscal_year_start": "Inicio Año Fiscal",
        "fiscal_year_end": "Fin Año Fiscal",
        "legal_name": "Razón social",
        "trade_name": "Nombre comercial",
        "catalog_title": "Catálogo contable",
        "existing_catalog": "Catálogo existente",
        "existing_catalog_help": "Seleccione un catálogo de cuentas disponible en el sistema para usarlo como base.",
        "empty_catalog_help": "Se creará una estructura contable vacía para configurar las cuentas manualmente.",
        "back": "Atrás",
        "next": "Siguiente",
        "finish": "Finalizar",
        "invalid_step": "Paso inválido del asistente.",
        "invalid_language": "Seleccione un idioma válido.",
        "invalid_regional": "Complete los datos regionales correctamente.",
        "invalid_currency": "La moneda seleccionada no existe o no está activa.",
        "invalid_company": "Complete los datos de la empresa correctamente.",
        "catalog_required": "Seleccione un catálogo de cuentas existente.",
        "setup_complete": "Configuración inicial completada.",
        "select_catalog": "Seleccione un catálogo existente",
        "use_existing_catalog": "Usar catálogo contable preexistente",
        "create_empty_catalog": "Crear catálogo contable en cero",
        "visual_note": "Configuración guiada",
    },
    "en": {
        "title": "Initial setup wizard",
        "subtitle": "Complete these steps to create the default company and configure the system.",
        "eyebrow": "Cacao Accounting",
        "step_1": "Language",
        "step_2": "Regional",
        "step_3": "Company",
        "step_label": "Step {step}",
        "language_title": "Choose the setup language",
        "language_help": "The wizard will use this language during the initial setup.",
        "language": "Default language",
        "regional_title": "Set country and currency",
        "regional_help": "Currency is suggested by country and only database currencies are listed.",
        "country": "Default country",
        "currency": "Default currency",
        "company_title": "Company details",
        "company_help": "These details create the base company, accounting book, and initial period.",
        "company_code": "Company code",
        "entity_type": "Entity type",
        "tax_id": "Tax identification",
        "fiscal_year": "Fiscal year",
        "fiscal_year_start": "Fiscal year start",
        "fiscal_year_end": "Fiscal year end",
        "legal_name": "Legal name",
        "trade_name": "Trade name",
        "catalog_title": "Chart of accounts",
        "existing_catalog": "Existing chart",
        "existing_catalog_help": "Select an available chart of accounts to use as the starting point.",
        "empty_catalog_help": "An empty accounting structure will be created so accounts can be configured manually.",
        "back": "Back",
        "next": "Next",
        "finish": "Finish",
        "invalid_step": "Invalid wizard step.",
        "invalid_language": "Select a valid language.",
        "invalid_regional": "Complete the regional details correctly.",
        "invalid_currency": "The selected currency does not exist or is not active.",
        "invalid_company": "Complete the company details correctly.",
        "catalog_required": "Select an existing chart of accounts.",
        "setup_complete": "Initial setup completed.",
        "select_catalog": "Select an existing chart",
        "use_existing_catalog": "Use an existing chart of accounts",
        "create_empty_catalog": "Create an empty chart of accounts",
        "visual_note": "Guided configuration",
    },
}


def normalize_language(language: str | None) -> str:
    """Normaliza el idioma soportado por el setup inicial."""
    return "en" if (language or "").lower().startswith("en") else "es"


def setup_texts(language: str | None) -> dict[str, str]:
    """Devuelve los textos localizados para el setup."""
    return SETUP_TEXTS[normalize_language(language)]


def country_choices(language: str | None) -> list[tuple[str, str]]:
    """Devuelve países soberanos de América en el idioma solicitado."""
    is_english = normalize_language(language) == "en"
    return [(country.code, country.name_en if is_english else country.name_es) for country in AMERICA_COUNTRIES]


def country_currency_map() -> dict[str, str]:
    """Devuelve la moneda sugerida por país."""
    return {country.code: country.currency for country in AMERICA_COUNTRIES}


def catalog_choices(language: str | None) -> list[tuple[str, str]]:
    """Devuelve opciones localizadas de catálogo contable."""
    texts = setup_texts(language)
    return [
        ("preexistente", texts["use_existing_catalog"]),
        ("en_cero", texts["create_empty_catalog"]),
    ]


def setup_template_context(language: str | None) -> dict[str, Any]:
    """Agrupa catálogos y textos del setup para renderizar la plantilla."""
    return {
        "texts": setup_texts(language),
        "country_currency_map": country_currency_map(),
        "language": normalize_language(language),
    }
