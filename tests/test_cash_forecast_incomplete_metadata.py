# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1325: el pronóstico informa las conversiones que excluyó.

Una factura o entrada manual sin tasa no se suma, pero la matriz debe
marcarse incompleta y listar la fuente, moneda, fecha e importe excluidos.
"""

from datetime import date
from decimal import Decimal
from uuid import uuid4

from sqlalchemy import select

from cacao_accounting.bancos.cash_forecast_service import get_cash_forecast_matrix
from cacao_accounting.database import (
    CashForecast,
    CashForecastEntry,
    Currency,
    FiscalYear,
    Party,
    SalesInvoice,
    database,
)

FECHA = date(2026, 5, 15)


def _forecast() -> str:
    """Crea un pronóstico mensual sobre el año fiscal del escenario."""
    fiscal_year_id = database.session.execute(select(FiscalYear.id).filter_by(entity="cacao")).scalar_one()
    forecast = CashForecast(
        company="cacao",
        version=f"Draft-{uuid4().hex[:6]}",
        description="Pronóstico 1325",
        fiscal_year_id=fiscal_year_id,
        periodicity="monthly",
        status="Draft",
    )
    database.session.add(forecast)
    database.session.commit()
    return str(forecast.id)


def _invoice(exchange_rate: Decimal | None) -> str:
    """Crea una factura AR en USD con vencimiento en el período."""
    customer_id = str(database.session.execute(select(Party.id).filter_by(code="CLI001")).scalar_one())
    invoice = SalesInvoice(
        company="cacao",
        customer_id=customer_id,
        document_type="sales_invoice",
        document_no="FAC-1325",
        posting_date=date(2026, 5, 20),
        docstatus=1,
        total=Decimal("100"),
        grand_total=Decimal("100"),
        base_total=Decimal("100"),
        base_grand_total=Decimal("100"),
        transaction_currency="USD",
        base_currency="NIO",
        exchange_rate=exchange_rate,
    )
    database.session.add(invoice)
    database.session.commit()
    return str(invoice.id)


def _may_row(matrix: list[dict]) -> dict:
    """Devuelve la fila cuyo rango contiene el vencimiento."""
    for row in matrix:
        if row["start_date"] <= date(2026, 5, 20) <= row["end_date"]:
            return row
    raise AssertionError("No se generó la fila de mayo")


def test_factura_sin_tasa_marca_la_matriz_incompleta(entorno_contable_aislado):
    """La factura excluida aparece listada con su importe y moneda."""
    app = entorno_contable_aislado.app
    with app.app_context():
        forecast_id = _forecast()
        invoice_id = _invoice(None)

        row = _may_row(get_cash_forecast_matrix("cacao", forecast_id, today_date=FECHA))

        assert row["is_incomplete"] is True
        assert row["proj_ar"] == Decimal("0")
        assert row["incomplete_invoice_entries"] == [
            {
                "id": invoice_id,
                "document_no": "FAC-1325",
                "document_type": "sales_invoice",
                "amount": Decimal("100.0000"),
                "currency": "USD",
                "date": date(2026, 5, 20),
                "reason": ("No existe tipo de cambio para USD -> NIO en 2026-05-20."),
            }
        ]


def test_factura_con_tasa_se_convierte_y_no_marca_incompleta(entorno_contable_aislado):
    """Con tasa presente el importe entra y la fila queda completa."""
    app = entorno_contable_aislado.app
    with app.app_context():
        forecast_id = _forecast()
        _invoice(Decimal("36"))

        row = _may_row(get_cash_forecast_matrix("cacao", forecast_id, today_date=FECHA))

        assert row["proj_ar"] == Decimal("3600.0000")
        assert row["is_incomplete"] is False
        assert row["incomplete_invoice_entries"] == []


def test_entrada_manual_sin_tasa_tambien_marca_incompleta(entorno_contable_aislado):
    """El criterio cubre las proyecciones manuales, no solo facturas."""
    app = entorno_contable_aislado.app
    with app.app_context():
        forecast_id = _forecast()
        database.session.add(Currency(code="EUR", name="Euro", decimals=2, active=True, default=False))
        database.session.flush()
        database.session.add(
            CashForecastEntry(
                forecast_id=forecast_id,
                type="Income",
                concept="Cobro en EUR",
                currency="EUR",
                amount=Decimal("50"),
                estimated_date=date(2026, 5, 21),
            )
        )
        database.session.commit()

        row = _may_row(get_cash_forecast_matrix("cacao", forecast_id, today_date=FECHA))

        assert row["is_incomplete"] is True
        assert row["manual_inflow"] == Decimal("0")
        assert [entry["concept"] for entry in row["incomplete_manual_entries"]] == ["Cobro en EUR"]
