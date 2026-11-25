# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1586: el Kardex incorpora la existencia anterior al rango consultado."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy.pool import StaticPool

from cacao_accounting import create_app
from cacao_accounting.config import configuracion
from cacao_accounting.database import Currency, Entity, Item, StockLedgerEntry, UOM, Warehouse, database
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


def _sembrar_reversa(entorno, fecha_original: date, fecha_reversa: date) -> str:
    """Registra un movimiento de diciembre y su reversa en enero sobre el mismo voucher."""
    with entorno.app_context():
        database.session.add(
            Item(code="ART-2263", name="Reversa interperiodo", item_type="goods", is_stock_item=True, default_uom="UND")
        )
        database.session.add(Warehouse(code="BOD-2263", name="Bodega reversa", company="cacao"))
        database.session.flush()
        original = StockLedgerEntry(
            posting_date=fecha_original,
            company="cacao",
            item_code="ART-2263",
            warehouse="BOD-2263",
            qty_change=Decimal("10"),
            stock_value_difference=Decimal("100"),
            voucher_type="stock_entry",
            voucher_id="SLE-2263",
            is_cancelled=True,
        )
        database.session.add(original)
        database.session.flush()
        database.session.add(
            StockLedgerEntry(
                posting_date=fecha_reversa,
                company="cacao",
                item_code="ART-2263",
                warehouse="BOD-2263",
                qty_change=Decimal("-10"),
                stock_value_difference=Decimal("-100"),
                voucher_type="stock_entry",
                voucher_id="SLE-2263",
                is_reversal=True,
                reversal_of=original.id,
            )
        )
        database.session.commit()
        return str(original.id)


def _filtros_2263(fecha_desde: date, fecha_hasta: date) -> KardexFilters:
    return KardexFilters(
        company="cacao",
        item_code="ART-2263",
        warehouse="BOD-2263",
        date_from=fecha_desde,
        date_to=fecha_hasta,
    )


def test_kardex_conserva_el_movimiento_original_en_su_corte(kardex_entorno):
    """#2263: la reversa de enero no borra la entrada real de diciembre."""
    _sembrar_reversa(kardex_entorno, date(2025, 12, 31), date(2026, 1, 5))

    with kardex_entorno.app_context():
        reporte = get_kardex(_filtros_2263(date(2025, 12, 1), date(2025, 12, 31)))

    assert len(reporte.rows) == 1
    assert reporte.rows[0].values["incoming_qty"] == Decimal("10")
    assert reporte.rows[0].values["balance_qty"] == Decimal("10")
    assert reporte.rows[0].values["stock_value"] == Decimal("100")


def test_kardex_muestra_la_reversa_en_el_periodo_en_que_se_registro(kardex_entorno):
    """El saldo de enero parte de 10 y la reversa lo devuelve a cero."""
    _sembrar_reversa(kardex_entorno, date(2025, 12, 31), date(2026, 1, 5))

    with kardex_entorno.app_context():
        reporte = get_kardex(_filtros_2263(date(2026, 1, 1), date(2026, 1, 31)))

    assert len(reporte.rows) == 1
    fila = reporte.rows[0].values
    assert fila["outgoing_qty"] == Decimal("10")
    assert fila["balance_qty"] == Decimal("0")
    assert fila["stock_value"] == Decimal("0")


def test_kardex_excluye_anulacion_del_mismo_dia(kardex_entorno):
    """Una anulación sin efecto neto sigue sin aparecer en el Kardex."""
    _sembrar_reversa(kardex_entorno, date(2025, 12, 31), date(2025, 12, 31))

    with kardex_entorno.app_context():
        reporte = get_kardex(_filtros_2263(date(2025, 12, 1), date(2025, 12, 31)))

    assert reporte.rows == []
