# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1586 y #1115: el Kardex incorpora existencia previa al rango consultado."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy.pool import StaticPool

from cacao_accounting import create_app
from cacao_accounting.config import configuracion
from cacao_accounting.database import (
    AccountingPeriod,
    Currency,
    Entity,
    FiscalYear,
    Item,
    StockLedgerEntry,
    UOM,
    Warehouse,
    database,
)
from cacao_accounting.reportes.services import KardexFilters, get_kardex


def _entrada(entorno, fecha, cantidad, valor, *, cancelada=False, referencia="SLE-1586"):
    with entorno.app_context():
        database.session.add(
            StockLedgerEntry(
                posting_date=fecha,
                company="cacao",
                item_code="ART-1586",
                warehouse="BOD-1586",
                qty_change=Decimal(cantidad),
                stock_value_difference=Decimal(valor),
                voucher_type="stock_entry",
                voucher_id=referencia,
                is_cancelled=cancelada,
            )
        )
        database.session.commit()


@pytest.fixture
def kardex_entorno():
    application = create_app(
        {
            **configuracion,
            "SQLALCHEMY_DATABASE_URI": "sqlite://",
            "SQLALCHEMY_ENGINE_OPTIONS": {"poolclass": StaticPool},
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
            "TESTING": True,
            "MODO_ESCRITORIO": True,
        }
    )
    with application.app_context():
        database.create_all()
        database.session.add_all(
            [
                Currency(code="NIO", name="Córdoba", decimals=2, active=True, default=True),
                Entity(
                    code="cacao",
                    name="Cacao",
                    company_name="Cacao SA",
                    tax_id="J-1586",
                    currency="NIO",
                    enabled=True,
                    status="default",
                ),
                UOM(code="UND", name="Unidad"),
            ]
        )
        database.session.flush()
        database.session.add(
            FiscalYear(
                id="FY2026",
                entity="cacao",
                name="2026",
                year_start_date=date(2026, 1, 1),
                year_end_date=date(2026, 12, 31),
                is_closed=False,
            )
        )
        database.session.flush()
        database.session.add(
            AccountingPeriod(
                id="P2026-01",
                entity="cacao",
                fiscal_year_id="FY2026",
                name="Enero 2026",
                start=date(2026, 1, 1),
                end=date(2026, 1, 31),
                enabled=True,
                is_closed=False,
            )
        )
        database.session.add(
            Item(code="ART-1586", name="Artículo Kardex", item_type="goods", is_stock_item=True, default_uom="UND")
        )
        database.session.add(Warehouse(code="BOD-1586", name="Bodega Kardex", company="cacao"))
        database.session.commit()
    _entrada(application, date(2025, 12, 31), "10", "100")
    _entrada(application, date(2026, 1, 2), "5", "60")
    yield application
    with application.app_context():
        database.session.remove()
        database.engine.dispose()


def test_kardex_acumula_la_existencia_anterior(kardex_entorno):
    """La entrada de diciembre aporta 10 unidades y 100 al saldo de enero."""
    with kardex_entorno.app_context():
        reporte = get_kardex(KardexFilters(company="cacao", date_from=date(2026, 1, 1), date_to=date(2026, 1, 31)))

    assert len(reporte.rows) == 1
    fila = reporte.rows[0].values
    assert fila["balance_qty"] == Decimal("15")
    assert fila["stock_value"] == Decimal("160")
    assert fila["incoming_qty"] == Decimal("5")
    assert Decimal(str(reporte.totals["incoming_qty"])) == Decimal("5")


def test_kardex_ignora_entradas_canceladas_antes_del_corte(kardex_entorno):
    """Una entrada cancelada no altera la existencia de apertura."""
    _entrada(kardex_entorno, date(2025, 12, 30), "-3", "-30", cancelada=True, referencia="SLE-1586-X")

    with kardex_entorno.app_context():
        reporte = get_kardex(KardexFilters(company="cacao", date_from=date(2026, 1, 1), date_to=date(2026, 1, 31)))

    assert reporte.rows[0].values["balance_qty"] == Decimal("15")
    assert reporte.rows[0].values["stock_value"] == Decimal("160")


def test_kardex_sin_movimientos_previos_parte_de_cero(kardex_entorno):
    """Un rango anterior al primer movimiento no inventa saldo inicial."""
    with kardex_entorno.app_context():
        reporte = get_kardex(KardexFilters(company="cacao", date_from=date(2025, 12, 1), date_to=date(2026, 1, 1)))

    assert [fila.values["balance_qty"] for fila in reporte.rows] == [Decimal("10")]


def test_kardex_acumula_la_existencia_anterior_al_filtrar_por_periodo(kardex_entorno):
    """El período completo usa la misma apertura histórica que el rango manual."""
    with kardex_entorno.app_context():
        reporte = get_kardex(KardexFilters(company="cacao", period_from="P2026-01", period_to="P2026-01"))

    assert len(reporte.rows) == 1
    fila = reporte.rows[0].values
    assert fila["posting_date"] == date(2026, 1, 2)
    assert fila["balance_qty"] == Decimal("15")
    assert fila["stock_value"] == Decimal("160")
    assert fila["incoming_qty"] == Decimal("5")
    assert Decimal(str(reporte.totals["incoming_qty"])) == Decimal("5")
