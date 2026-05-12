# Copyright 2026
# Licensed under the Apache License, Version 2.0

"""Servicios del asistente de configuración inicial."""

from __future__ import annotations

from os import listdir
from os.path import isfile, join
from typing import Any

from cacao_accounting.contabilidad.default_accounts import (
    DefaultAccountError,
    apply_catalog_default_mapping,
    catalog_has_default_mapping,
)
from cacao_accounting.contabilidad.ctas import (
    CatalogoCtas,
    DIRECTORIO_CTAS,
    base as catalogo_base,
    cargar_catalogos,
)
from cacao_accounting.document_flow.status import _
from cacao_accounting.contabilidad.auxiliares import obtener_lista_monedas
from cacao_accounting.database import Entity, database
from cacao_accounting.document_identifiers import ensure_default_naming_series_for_company
from cacao_accounting.setup.repository import (
    create_default_accounting_period,
    create_default_book,
    create_default_cost_center,
    create_default_entity,
    create_default_fiscal_year,
    get_setup_value,
    set_setup_value,
)

SETUP_LANGUAGE = "SETUP_LANGUAGE"
SETUP_COUNTRY = "SETUP_COUNTRY"
SETUP_CURRENCY = "SETUP_CURRENCY"
SETUP_COMPLETED = "SETUP_COMPLETE"
SETUP_ENTITY = "SETUP_DEFAULT_ENTITY"
CATALOG_FILE_ALIASES = {
    "base_es.csv": "Predeterminado - ES",
    "base_en.csv": "Default - EN",
}


def catalog_display_name(filename: str) -> str:
    """Devuelve el alias visible de un catalogo o su nombre de archivo."""
    return CATALOG_FILE_ALIASES.get(filename, filename)


def available_catalog_files() -> list[tuple[str, str]]:
    """Devuelve los archivos de catálogo disponibles para el asistente de configuración."""
    choices: list[tuple[str, str]] = []
    for filename in sorted(listdir(DIRECTORIO_CTAS), key=str.lower):
        path = join(DIRECTORIO_CTAS, filename)
        if isfile(path) and filename.lower().endswith(".csv") and catalog_has_default_mapping(path):
            choices.append((filename, catalog_display_name(filename)))
    return choices


def choose_catalog_file(country: str, idioma: str, catalog_name: str | None = None) -> Any | None:
    """Selecciona el catálogo contable adecuado según país, idioma y nombre de archivo."""
    if catalog_name:
        catalog_file = join(DIRECTORIO_CTAS, catalog_name)
        if isfile(catalog_file) and catalog_has_default_mapping(catalog_file):
            return CatalogoCtas(file=catalog_file, pais=country, idioma=idioma)
        return None

    if catalogo_base.pais == country and catalogo_base.idioma == idioma:
        return catalogo_base
    return catalogo_base


def create_company(
    company_data: dict,
    catalogo_tipo: str | None = None,
    country: str | None = None,
    idioma: str | None = None,
    catalogo_archivo: str | None = None,
    status: str = "activo",
    default: bool = False,
) -> "Entity":
    """Crea una compañia con los registros contables mínimos necesarios."""
    entity = create_default_entity(company_data, status=status, default=default)
    create_default_book(entity)
    create_default_cost_center(entity)
    fiscal_year = create_default_fiscal_year(
        entity,
        year_start_date=company_data.get("inicio_anio_fiscal"),
        year_end_date=company_data.get("fin_anio_fiscal"),
    )
    create_default_accounting_period(entity, fiscal_year)
    ensure_default_naming_series_for_company(entity.code)

    if catalogo_tipo == "preexistente":
        if country is None or idioma is None:
            raise ValueError("No se puede cargar el catálogo sin país e idioma.")
        catalogo = choose_catalog_file(country, idioma, catalogo_archivo)
        if catalogo is None:
            raise ValueError(_("El catálogo seleccionado no está disponible o no tiene mapping JSON de cuentas por defecto."))
        cargar_catalogos(catalogo, entity)
        try:
            apply_catalog_default_mapping(entity.code, catalogo.file)
        except DefaultAccountError as exc:
            raise ValueError(str(exc)) from exc

    return entity


def save_language(language: str) -> None:
    """Guarda el idioma de configuración seleccionado."""
    set_setup_value(SETUP_LANGUAGE, language)


def save_regional_settings(country: str, currency: str) -> None:
    """Guarda los valores regionales de país y moneda."""
    set_setup_value(SETUP_COUNTRY, country)
    set_setup_value(SETUP_CURRENCY, currency)


def save_company_details(company_data: dict) -> None:
    """Almacena los datos de la entidad configurada."""
    set_setup_value(SETUP_ENTITY, company_data.get("id", ""))


def mark_setup_complete() -> None:
    """Marca el proceso de configuración como finalizado."""
    set_setup_value(SETUP_COMPLETED, "True")


def get_setup_configuration() -> dict[str, Any]:
    """Recupera la configuración guardada del asistente de instalación."""
    return {
        "idioma": get_setup_value(SETUP_LANGUAGE, "es"),
        "pais": get_setup_value(SETUP_COUNTRY, "NI"),
        "moneda": get_setup_value(SETUP_CURRENCY, "NIO"),
    }


def available_currencies() -> list[tuple[str, str]]:
    """Devuelve las monedas disponibles para el formulario de configuración."""
    return obtener_lista_monedas()


def finalize_setup(
    company_data: dict,
    catalogo_tipo: str,
    country: str,
    idioma: str,
    catalogo_archivo: str | None = None,
) -> None:
    """Completa el proceso de configuración inicial y crea la entidad por defecto."""
    create_company(
        company_data,
        catalogo_tipo=catalogo_tipo,
        country=country,
        idioma=idioma,
        catalogo_archivo=catalogo_archivo,
        status="default",
        default=True,
    )
    save_company_details(company_data)
    mark_setup_complete()
    database.session.commit()
