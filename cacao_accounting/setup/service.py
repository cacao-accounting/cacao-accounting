# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Servicios del asistente de configuración inicial."""

from __future__ import annotations

from csv import DictReader, Error as CSVError
from os import listdir
from os.path import isfile, join
from typing import Any

from cacao_accounting.contabilidad.default_accounts import (
    DEFAULT_ACCOUNT_DEFINITION_BY_FIELD,
    DefaultAccountError,
    apply_catalog_default_mapping,
    catalog_has_default_mapping,
    load_catalog_default_mapping,
)
from cacao_accounting.bancos.services import create_default_petty_cash
from cacao_accounting.contabilidad.ctas import (
    CatalogoCtas,
    DIRECTORIO_CTAS,
    HEADER_ALIASES,
    _is_group,
    cargar_catalogos,
)
from cacao_accounting.database import CacaoConfig, Entity, database
from cacao_accounting.document_identifiers import ensure_default_naming_series_for_company, ensure_global_naming_series
from cacao_accounting.runtime_mode import force_single_entity
from cacao_accounting.setup.catalogs import normalize_language
from cacao_accounting.setup.repository import (
    create_default_accounting_period,
    create_default_book,
    create_default_cost_center,
    create_default_party_groups,
    create_default_price_lists,
    create_default_uoms,
    create_default_entity,
    create_default_fiscal_year,
    get_setup_value,
    set_setup_value,
)

from cacao_accounting.i18n import _

SETUP_LANGUAGE = "SETUP_LANGUAGE"
SETUP_COUNTRY = "SETUP_COUNTRY"
SETUP_CURRENCY = "SETUP_CURRENCY"
SETUP_TIMEZONE = "SETUP_TIMEZONE"
SETUP_COMPLETED = "SETUP_COMPLETE"
SETUP_ENTITY = "SETUP_DEFAULT_ENTITY"
CATALOG_FILE_ALIASES = {
    "base_es.csv": "Predeterminado - ES",
    "base_en.csv": "Default - EN",
    "niif_pymes_es.csv": "NIIF Pymes (ES)",
    "ifrs_smes_en.csv": "IFRS SMEs (EN)",
    "us_gaap.csv": "US GAAP — Standard",
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
    """Resuelve el catálogo seleccionado explícitamente, sin fallback regional."""
    idioma_normalizado = normalize_language(idioma).upper()
    if not catalog_name or catalog_name not in {name for name, _ in available_catalog_files()}:
        return None
    catalog_file = join(DIRECTORIO_CTAS, catalog_name)
    if not _valid_catalog_file(catalog_file):
        return None
    return CatalogoCtas(file=catalog_file, pais=country, idioma=idioma_normalizado)


def _valid_catalog_file(catalog_file: str) -> bool:
    """Verifica formato y referencias del mapping antes de crear la compañía."""
    try:
        mapping = load_catalog_default_mapping(catalog_file)
        with open(catalog_file, encoding="utf-8", newline="") as catalog:
            reader = DictReader(catalog)
            headers = set(reader.fieldnames or ())
            if any(not headers.intersection(HEADER_ALIASES[field]) for field in ("code", "name", "classification")):
                return False
            fields = {
                field: next(header for header in HEADER_ALIASES[field] if header in headers)
                for field in ("code", "name", "classification")
            }
            account_types: dict[str, str] = {}
            group_codes: set[str] = set()
            type_field = next((header for header in HEADER_ALIASES["account_type"] if header in headers), None)
            group_field = next((header for header in HEADER_ALIASES["group"] if header in headers), None)
            for row in reader:
                if None in row or any(not str(row.get(column) or "").strip() for column in fields.values()):
                    return False
                code = str(row[fields["code"]]).strip()
                if code in account_types:
                    return False
                account_types[code] = str(row.get(type_field) or "").strip() if type_field else ""
                if group_field and _is_group(str(row.get(group_field) or "")):
                    group_codes.add(code)
        return bool(account_types) and all(
            code in account_types
            and code not in group_codes
            and (
                not account_types[code]
                or account_types[code] in DEFAULT_ACCOUNT_DEFINITION_BY_FIELD[field].allowed_account_types
            )
            for field, code in mapping.items()
        )
    except (OSError, UnicodeError, CSVError, ValueError, TypeError, AttributeError):
        return False


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
    company_count = database.session.execute(database.select(database.func.count(Entity.id))).scalar() or 0
    if force_single_entity() and company_count >= 1:
        raise ValueError(_("Esta instalación solo permite una compañía."))

    catalogo = None
    if catalogo_tipo == "preexistente":
        if country is None or idioma is None:
            raise ValueError(_("No se puede cargar el catálogo sin país e idioma."))
        catalogo = choose_catalog_file(country, idioma, catalogo_archivo)
        if catalogo is None:
            raise ValueError(_("El catálogo seleccionado no está disponible o no tiene mapping JSON de cuentas por defecto."))

    entity = create_default_entity(company_data, status=status, default=default)
    create_default_book(entity)
    create_default_cost_center(entity)
    create_default_uoms(idioma)
    create_default_price_lists(entity.code, entity.currency, idioma)
    fiscal_year = create_default_fiscal_year(
        entity,
        year_start_date=company_data.get("inicio_anio_fiscal"),
        year_end_date=company_data.get("fin_anio_fiscal"),
    )
    create_default_accounting_period(entity, fiscal_year)
    ensure_default_naming_series_for_company(entity.code)
    ensure_global_naming_series()

    if catalogo_tipo == "preexistente":
        cargar_catalogos(catalogo, entity)
        try:
            apply_catalog_default_mapping(entity.code, catalogo.file)
        except DefaultAccountError as exc:
            raise ValueError(str(exc)) from exc
        # #1265: informar cuando no se pudo crear el fondo predeterminado por no
        # haber una cuenta de caja chica utilizable.
        entity._petty_cash_created = create_default_petty_cash(entity.code) is not None

    return entity


def save_language(language: str) -> None:
    """Guarda el idioma de configuración seleccionado."""
    set_setup_value(SETUP_LANGUAGE, normalize_language(language))
    database.session.commit()


def save_regional_settings(country: str, currency: str, timezone: str) -> None:
    """Guarda los valores regionales de país, moneda y zona horaria."""
    from cacao_accounting.database import Currency
    import zoneinfo

    selected_currency = database.session.execute(
        database.select(Currency).filter_by(code=currency, active=True)
    ).scalar_one_or_none()
    if selected_currency is None:
        raise ValueError(_("La moneda seleccionada no existe o no está activa."))

    if timezone not in zoneinfo.available_timezones():
        raise ValueError(_("La zona horaria seleccionada no es válida."))

    set_setup_value(SETUP_COUNTRY, country)
    set_setup_value(SETUP_CURRENCY, currency)
    set_setup_value(SETUP_TIMEZONE, timezone)
    database.session.commit()


def save_company_details(company_data: dict) -> None:
    """Almacena los datos de la entidad configurada."""
    set_setup_value(SETUP_ENTITY, company_data.get("id", ""))


def mark_setup_complete() -> None:
    """Marca el proceso de configuración como finalizado."""
    set_setup_value(SETUP_COMPLETED, "True")


def get_setup_configuration() -> dict[str, Any]:
    """Recupera la configuración guardada del asistente de instalación."""
    return {
        "idioma": normalize_language(get_setup_value(SETUP_LANGUAGE, "es")),
        "pais": get_setup_value(SETUP_COUNTRY, "NI"),
        "moneda": get_setup_value(SETUP_CURRENCY, "NIO"),
        "zona_horaria": get_setup_value(SETUP_TIMEZONE, "America/Managua"),
    }


def is_setup_complete() -> bool:
    """Indica si el asistente de configuración ya finalizó con éxito."""
    return (get_setup_value(SETUP_COMPLETED, "") or "") == "True"


def available_currencies() -> list[tuple[str, str]]:
    """Devuelve las monedas disponibles para el formulario de configuración."""
    from cacao_accounting.database import Currency

    currencies = database.session.execute(
        database.select(Currency).filter(Currency.active.is_(True)).order_by(Currency.code)
    ).scalars()
    return [(currency.code, f"{currency.code} - {currency.name}") for currency in currencies]


def _activate_and_set_default_currency(currency_code: str) -> None:
    """Activa la moneda seleccionada y la marca como predeterminada unica."""
    from cacao_accounting.database import Currency, database

    if not currency_code:
        return

    currencies = list(database.session.execute(database.select(Currency)).scalars().all())
    selected_currency = next((currency for currency in currencies if currency.code == currency_code), None)
    if selected_currency is None:
        selected_currency = Currency(code=currency_code, name=currency_code, decimals=2, active=True, default=True)
        database.session.add(selected_currency)
        currencies.append(selected_currency)

    for currency in currencies:
        is_selected = currency.code == currency_code
        if is_selected:
            currency.active = True
        currency.default = is_selected


class SetupAlreadyComplete(RuntimeError):
    """La instalación ya completó el asistente inicial."""


def claim_setup_completion() -> None:
    """Reclama de forma atómica la finalización única del asistente (#1021).

    La clave ``SETUP_COMPLETE`` es única. El proceso toma el bloqueo de alcance
    y relee la fila: si el valor ya es ``True``, la instalación se considera
    completada; si existe en ``False``, la marca como completada. Así un segundo
    proceso concurrente no duplica la compañía ni sus libros.
    """
    from sqlalchemy.exc import IntegrityError
    from cacao_accounting.default_scope import lock_default_scope

    lock_default_scope("setup_completion")
    row = database.session.execute(
        database.select(CacaoConfig).filter_by(key=SETUP_COMPLETED).with_for_update().execution_options(populate_existing=True)
    ).scalar_one_or_none()
    if row is not None:
        if row.value == "True":
            raise SetupAlreadyComplete(_("La configuración inicial ya fue completada."))
        row.value = "True"
        database.session.flush()
        return

    database.session.add(CacaoConfig(key=SETUP_COMPLETED, value="True"))
    try:
        database.session.flush()
    except IntegrityError as exc:
        database.session.rollback()
        raise SetupAlreadyComplete(_("La configuración inicial ya fue completada.")) from exc


def finalize_setup(
    company_data: dict,
    catalogo_tipo: str,
    country: str,
    idioma: str,
    catalogo_archivo: str | None = None,
) -> bool:
    """Completa la configuración inicial y crea la entidad por defecto.

    Devuelve ``False`` cuando no se creó el fondo de caja chica predeterminado
    por falta de una cuenta utilizable, para que el asistente pueda informarlo
    (#1265).
    """
    claim_setup_completion()
    try:
        is_initial_entity = (database.session.execute(database.select(database.func.count(Entity.id))).scalar() or 0) == 0
        entity = create_company(
            company_data,
            catalogo_tipo=catalogo_tipo,
            country=country,
            idioma=idioma,
            catalogo_archivo=catalogo_archivo,
            status="default" if is_initial_entity else "activo",
            default=is_initial_entity,
        )
        _activate_and_set_default_currency(company_data.get("moneda", ""))
        create_default_party_groups(idioma)
        save_company_details(company_data)
        database.session.commit()
    except Exception:
        database.session.rollback()
        raise
    return bool(getattr(entity, "_petty_cash_created", True))
