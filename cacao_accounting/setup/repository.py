# Copyright 2026
# Licensed under the Apache License, Version 2.0

"""Repositorios de datos para el asistente de configuración inicial."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any
import calendar

from cacao_accounting.database import (
    AccountingPeriod,
    Book,
    CacaoConfig,
    CostCenter,
    Entity,
    FiscalYear,
    PartyGroup,
    PriceList,
    UOM,
    database,
)

try:
    from flask_babel import gettext as _
except ImportError:  # pragma: no cover

    def _(value: str) -> str:
        return value


def get_setup_value(key: str, default: Any = None) -> Any:
    """Recupera un valor de configuración por clave."""
    record = database.session.execute(database.select(CacaoConfig).filter_by(key=key)).first()
    if record:
        return record[0].value
    return default


def set_setup_value(key: str, value: str) -> None:
    """Establece o crea un valor de configuración."""
    record = database.session.execute(database.select(CacaoConfig).filter_by(key=key)).first()
    if record:
        config = record[0]
        config.value = value
    else:
        config = CacaoConfig(key=key, value=value)
        database.session.add(config)


def create_default_entity(data: dict, status: str = "default", default: bool = True) -> Entity:
    """Crea y añade una entidad en la sesión de base de datos."""
    if not data.get("id") or not data.get("razon_social") or not data.get("id_fiscal"):
        raise ValueError("Los datos de la entidad son incompletos.")

    existing_entity = database.session.execute(database.select(Entity).filter_by(code=data["id"])).scalar_one_or_none()
    if existing_entity is not None:
        raise ValueError(f"La entidad con código '{data['id']}' ya existe.")

    entity = Entity(
        code=data.get("id"),
        company_name=data.get("razon_social"),
        name=data.get("nombre_comercial") or data.get("razon_social"),
        tax_id=data.get("id_fiscal"),
        currency=data.get("moneda"),
        country=data.get("pais"),
        entity_type=data.get("tipo_entidad"),
        e_mail=data.get("correo_electronico"),
        web=data.get("web"),
        phone1=data.get("telefono1"),
        phone2=data.get("telefono2"),
        fax=data.get("fax"),
        status=status,
        enabled=True,
        default=default,
    )
    database.session.add(entity)
    return entity


def create_default_book(entity: Entity) -> "Book":
    """Create a default accounting book for the entity."""
    from cacao_accounting.database import Book

    existing_book = database.session.execute(
        database.select(Book).filter_by(entity=entity.code, default=True)
    ).scalar_one_or_none()
    if existing_book is not None:
        return existing_book

    existing_primary_book = database.session.execute(
        database.select(Book).filter_by(entity=entity.code, is_primary=True)
    ).scalar_one_or_none()
    if existing_primary_book is not None:
        existing_primary_book.default = True
        return existing_primary_book

    book_code = "LOCAL"
    if database.session.execute(database.select(Book).filter_by(code=book_code)).scalar_one_or_none() is not None:
        index = 1
        while True:
            candidate = f"LOCAL{index}"
            if database.session.execute(database.select(Book).filter_by(code=candidate)).scalar_one_or_none() is None:
                book_code = candidate
                break
            index += 1

    book = Book(
        code=book_code,
        name="Local",
        entity=entity.code,
        currency=entity.currency,
        is_primary=True,
        default=True,
    )
    database.session.add(book)
    return book


def create_default_cost_center(entity: Entity) -> "CostCenter":
    """Create a default cost center for the entity."""
    from cacao_accounting.database import CostCenter

    existing_cost_center = database.session.execute(
        database.select(CostCenter).filter_by(entity=entity.code, code="MAIN")
    ).scalar_one_or_none()
    if existing_cost_center is not None:
        return existing_cost_center

    cost_center = CostCenter(
        entity=entity.code,
        code="MAIN",
        name="Principal",
        active=True,
        enabled=True,
        default=True,
        group=False,
    )
    database.session.add(cost_center)
    return cost_center


def create_default_uoms(language: str | None = None) -> list[UOM]:
    """Crea un conjunto razonable de UOM base si el catálogo esta vacío."""
    seed_uoms = _default_uom_catalog(language)
    created: list[UOM] = []
    for code, name in seed_uoms:
        existing = database.session.execute(database.select(UOM).filter_by(code=code)).scalar_one_or_none()
        if existing is not None:
            continue
        uom = UOM(code=code, name=name, is_active=True)
        database.session.add(uom)
        created.append(uom)
    return created


def create_default_price_lists(company: str, currency: str | None, language: str | None = None) -> list[PriceList]:
    """Crea las listas de precio predeterminadas de ventas y compras para una compañia."""
    definitions = _default_price_list_catalog(language)
    created: list[PriceList] = []
    for definition in definitions:
        existing = database.session.execute(
            database.select(PriceList).filter_by(company=company, name=definition["name"])
        ).scalar_one_or_none()
        if existing is not None:
            existing.currency = existing.currency or currency
            existing.is_active = True
            existing.is_default = True
            existing.is_selling = bool(definition["is_selling"])
            existing.is_buying = bool(definition["is_buying"])
            continue
        price_list = PriceList(
            name=str(definition["name"]),
            company=company,
            currency=currency,
            is_selling=bool(definition["is_selling"]),
            is_buying=bool(definition["is_buying"]),
            is_default=True,
            is_active=True,
        )
        database.session.add(price_list)
        created.append(price_list)
    return created


def _default_uom_catalog(language: str | None) -> list[tuple[str, str]]:
    """Devuelve el catálogo base de UOM en el idioma solicitado."""
    is_english = (language or "").lower().startswith("en")
    if is_english:
        return [
            ("UND", "Unit"),
            ("CAJ", "Box"),
            ("PQT", "Pack"),
            ("DOC", "Dozen"),
            ("CJA12", "Box x 12"),
            ("CJA24", "Box x 24"),
            ("PAL", "Pallet"),
            ("KG", "Kilogram"),
            ("G", "Gram"),
            ("LB", "Pound"),
            ("L", "Liter"),
            ("ML", "Milliliter"),
            ("M", "Meter"),
            ("CM", "Centimeter"),
            ("MM", "Millimeter"),
            ("HRS", "Hour"),
            ("MIN", "Minute"),
            ("SERV", "Service"),
        ]
    return [
        ("UND", "Unidad"),
        ("CAJ", "Caja"),
        ("PQT", "Paquete"),
        ("DOC", "Docena"),
        ("CJA12", "Caja x 12"),
        ("CJA24", "Caja x 24"),
        ("PAL", "Pallet"),
        ("KG", "Kilogramo"),
        ("G", "Gramo"),
        ("LB", "Libra"),
        ("L", "Litro"),
        ("ML", "Mililitro"),
        ("M", "Metro"),
        ("CM", "Centimetro"),
        ("MM", "Milimetro"),
        ("HRS", "Hora"),
        ("MIN", "Minuto"),
        ("SERV", "Servicio"),
    ]


def _default_price_list_catalog(language: str | None) -> list[dict[str, object]]:
    """Devuelve las listas de precio predeterminadas en el idioma solicitado."""
    is_english = (language or "").lower().startswith("en")
    if is_english:
        return [
            {"name": "Default Sales Price List", "is_selling": True, "is_buying": False},
            {"name": "Default Purchase Price List", "is_selling": False, "is_buying": True},
        ]
    return [
        {"name": "Lista de Precio Venta por Defecto", "is_selling": True, "is_buying": False},
        {"name": "Lista de Precio Compra por Defecto", "is_selling": False, "is_buying": True},
    ]


def _add_months(original_date: date, months: int) -> date:
    year = original_date.year + (original_date.month - 1 + months) // 12
    month = (original_date.month - 1 + months) % 12 + 1
    day = original_date.day
    last_day = calendar.monthrange(year, month)[1]
    return date(year, month, min(day, last_day))


def _generate_fiscal_period_ranges(start: date, end: date) -> list[tuple[date, date]]:
    if start > end:
        raise ValueError("La fecha de inicio del año fiscal debe ser anterior a la fecha de fin.")

    ranges: list[tuple[date, date]] = []
    current_start = start
    for _ in range(12):
        next_start = _add_months(current_start, 1)
        period_end = min(next_start - timedelta(days=1), end)
        ranges.append((current_start, period_end))
        if period_end == end:
            break
        current_start = next_start

    if ranges and ranges[-1][1] != end:
        ranges[-1] = (ranges[-1][0], end)

    return ranges


def create_default_fiscal_year(
    entity: Entity,
    year_start_date: "date | None" = None,
    year_end_date: "date | None" = None,
    reference_date: "date | None" = None,
) -> "FiscalYear":
    """Create a default fiscal year for the entity."""
    from datetime import date as _date
    from cacao_accounting.database import FiscalYear

    if year_start_date is not None and year_end_date is not None:
        start = year_start_date
        end = year_end_date
    else:
        today = reference_date or _date.today()
        start = _date(today.year, 1, 1)
        end = _date(today.year, 12, 31)

    existing_year = database.session.execute(
        database.select(FiscalYear).filter_by(entity=entity.code, year_start_date=start, year_end_date=end)
    ).scalar_one_or_none()
    if existing_year is not None:
        return existing_year

    fiscal_year = FiscalYear(
        entity=entity.code,
        name=str(start.year) if start.year == end.year else f"{start.year}-{end.year}",
        year_start_date=start,
        year_end_date=end,
        is_closed=False,
    )
    database.session.add(fiscal_year)
    database.session.flush()
    return fiscal_year


def create_default_accounting_period(entity: Entity, fiscal_year: "FiscalYear") -> "AccountingPeriod":
    """Create default accounting periods for the fiscal year."""
    existing_period = database.session.execute(
        database.select(AccountingPeriod).filter_by(entity=entity.code, fiscal_year_id=fiscal_year.id)
    ).scalar_one_or_none()
    if existing_period is not None:
        return existing_period

    period_ranges = _generate_fiscal_period_ranges(fiscal_year.year_start_date, fiscal_year.year_end_date)
    for index, (start, end) in enumerate(period_ranges, start=1):
        period_name = f"{start:%Y-%m}"
        period = AccountingPeriod(
            entity=entity.code,
            fiscal_year_id=fiscal_year.id,
            name=period_name,
            status="open",
            enabled=True,
            is_closed=False,
            start=start,
            end=end,
        )
        database.session.add(period)

    database.session.flush()
    first_period = (
        database.session.execute(
            database.select(AccountingPeriod)
            .filter_by(entity=entity.code, fiscal_year_id=fiscal_year.id)
            .order_by(AccountingPeriod.start)
        )
        .scalars()
        .first()
    )
    if first_period is None:
        raise ValueError(_("No se pudo crear el período contable inicial."))
    return first_period


def get_default_entity() -> Entity | None:
    """Recupera la entidad predeterminada si existe."""
    return database.session.execute(database.select(Entity).filter_by(status="default")).scalar_one_or_none()


_PARTY_GROUP_CATALOG: dict[str, dict[str, list[dict[str, str]]]] = {
    "es": {
        "customer": [
            {"name": "Mayorista", "description": "Cliente mayorista"},
            {"name": "Minorista", "description": "Cliente minorista"},
            {"name": "Distribuidor", "description": "Cliente distribuidor"},
        ],
        "supplier": [
            {"name": "Bienes", "description": "Proveedor de bienes"},
            {"name": "Servicios", "description": "Proveedor de servicios"},
            {"name": "Servicios Básicos", "description": "Proveedor de servicios básicos"},
            {"name": "Materia Prima", "description": "Proveedor de materia prima"},
        ],
    },
    "en": {
        "customer": [
            {"name": "Wholesale", "description": "Wholesale customer"},
            {"name": "Retail", "description": "Retail customer"},
            {"name": "Distributor", "description": "Distributor customer"},
        ],
        "supplier": [
            {"name": "Goods", "description": "Goods supplier"},
            {"name": "Services", "description": "Services supplier"},
            {"name": "Basic Services", "description": "Basic services supplier"},
            {"name": "Raw Material", "description": "Raw material supplier"},
        ],
    },
}


def create_default_party_groups(language: str | None = None) -> list[PartyGroup]:
    """Crea los grupos de terceros predeterminados según el idioma del setup."""
    lang_key = "en" if (language or "").lower().startswith("en") else "es"
    groups_catalog = _PARTY_GROUP_CATALOG.get(lang_key, _PARTY_GROUP_CATALOG["es"])
    created: list[PartyGroup] = []
    for group_type, items in groups_catalog.items():
        for item in items:
            existing = database.session.execute(
                database.select(PartyGroup).filter_by(group_type=group_type, name=item["name"])
            ).scalar_one_or_none()
            if existing is not None:
                continue
            group = PartyGroup(
                group_type=group_type,
                name=item["name"],
                description=item["description"],
                is_active=True,
            )
            database.session.add(group)
            created.append(group)
    return created
