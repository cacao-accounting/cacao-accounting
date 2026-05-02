# Copyright 2026
# Licensed under the Apache License, Version 2.0

from os import listdir
from os.path import isfile, join
from typing import Any

from cacao_accounting.contabilidad.ctas import (
    CatalogoCtas,
    DIRECTORIO_CTAS,
    base as catalogo_base,
    cargar_catalogos,
)
from cacao_accounting.contabilidad.auxiliares import obtener_lista_monedas
from cacao_accounting.database import database
from cacao_accounting.setup.repository import (
    create_default_entity,
    get_setup_value,
    set_setup_value,
)

SETUP_LANGUAGE = "SETUP_LANGUAGE"
SETUP_COUNTRY = "SETUP_COUNTRY"
SETUP_CURRENCY = "SETUP_CURRENCY"
SETUP_COMPLETED = "SETUP_COMPLETE"
SETUP_ENTITY = "SETUP_DEFAULT_ENTITY"


def available_catalog_files() -> list[tuple[str, str]]:
    choices: list[tuple[str, str]] = []
    for filename in sorted(listdir(DIRECTORIO_CTAS), key=str.lower):
        path = join(DIRECTORIO_CTAS, filename)
        if isfile(path) and filename.lower().endswith(".csv"):
            choices.append((filename, filename))
    return choices


def choose_catalog_file(country: str, idioma: str, catalog_name: str | None = None) -> Any | None:
    if catalog_name:
        catalog_file = join(DIRECTORIO_CTAS, catalog_name)
        if isfile(catalog_file):
            return CatalogoCtas(file=catalog_file, pais=country, idioma=idioma)
        return None

    if catalogo_base.pais == country and catalogo_base.idioma == idioma:
        return catalogo_base
    return catalogo_base


def save_language(language: str) -> None:
    set_setup_value(SETUP_LANGUAGE, language)


def save_regional_settings(country: str, currency: str) -> None:
    set_setup_value(SETUP_COUNTRY, country)
    set_setup_value(SETUP_CURRENCY, currency)


def save_company_details(company_data: dict) -> None:
    set_setup_value(SETUP_ENTITY, company_data.get("id", ""))


def mark_setup_complete() -> None:
    set_setup_value(SETUP_COMPLETED, "True")


def get_setup_configuration() -> dict[str, Any]:
    return {
        "idioma": get_setup_value(SETUP_LANGUAGE, "es"),
        "pais": get_setup_value(SETUP_COUNTRY, "NI"),
        "moneda": get_setup_value(SETUP_CURRENCY, "NIO"),
    }


def available_currencies() -> list[tuple[str, str]]:
    return obtener_lista_monedas()


def finalize_setup(
    company_data: dict,
    catalogo_tipo: str,
    country: str,
    idioma: str,
    catalogo_archivo: str | None = None,
) -> None:
    session = database.session()
    transaction_context = session.begin_nested() if session.in_transaction() else session.begin()
    with transaction_context:
        entity = create_default_entity(company_data)
        if catalogo_tipo == "preexistente":
            catalogo = choose_catalog_file(country, idioma, catalogo_archivo)
            if catalogo:
                cargar_catalogos(catalogo, entity)
        save_company_details(company_data)
        mark_setup_complete()
