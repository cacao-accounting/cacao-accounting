# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 William José Moreno Reyes

"""#1099: la prevalidación usa la misma tasa histórica que la aplicación."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

from cacao_accounting.api.line_import import _validate_payment_reconciliation_row
from cacao_accounting.database import Party, PaymentEntry, SalesInvoice, database

FECHA = date(2026, 5, 1)


def _escenario(app, payment_amount: str) -> dict[str, str]:
    """Crea una factura USD y un pago NIO con la tasa histórica 36.5."""
    suffix = uuid4().hex[:8]
    with app.app_context():
        cliente = Party(code=f"FX-{suffix}", name="Cliente FX", is_customer=True, is_active=True)
        database.session.add(cliente)
        database.session.flush()
        factura = SalesInvoice(
            company="cacao",
            posting_date=FECHA,
            docstatus=1,
            document_no=f"FX-{suffix}",
            document_type="sales_invoice",
            customer_id=cliente.id,
            customer_name=cliente.name,
            transaction_currency="USD",
            base_currency="NIO",
            exchange_rate=Decimal("36.50"),
            grand_total=Decimal("100"),
            outstanding_amount=Decimal("100"),
        )
        pago = PaymentEntry(
            company="cacao",
            payment_type="receive",
            posting_date=FECHA,
            paid_amount=Decimal(payment_amount),
            received_amount=Decimal(payment_amount),
            currency="NIO",
            party_type="customer",
            party_id=cliente.id,
            docstatus=1,
            document_no=f"FXPAY-{suffix}",
        )
        database.session.add_all([factura, pago])
        database.session.commit()
        return {"payment": pago.id, "reference": factura.id, "party": cliente.id}


def _validar(app, ids: dict[str, str], *, rate: str, allocation_date: date) -> list[dict]:
    """Ejecuta la prevalidación de una fila multimoneda."""
    errors: list[dict] = []
    with app.app_context():
        _validate_payment_reconciliation_row(
            {
                "payment_id": ids["payment"],
                "reference_type": "sales_invoice",
                "reference_id": ids["reference"],
                "allocated_amount": "100",
                "payment_exchange_rate": rate,
            },
            1,
            "cacao",
            errors,
            party_type="customer",
            party_id=ids["party"],
            allocation_date=allocation_date,
        )
    return errors


def test_tasa_declarada_baja_no_oculta_el_exceso_historico(entorno_contable_aislado):
    """Con tasa histórica 36.5 y pago 3600, declarar 35 no debe aceptar 100 USD."""
    app = entorno_contable_aislado.app
    ids = _escenario(app, "3600")

    errors = _validar(app, ids, rate="35", allocation_date=FECHA)

    assert any("saldo disponible del pago" in error["message"] for error in errors)


def test_tasa_declarada_alta_no_rechaza_una_asignacion_valida(entorno_contable_aislado):
    """Con tasa histórica 36.5 y pago 3700, declarar 40 no debe rechazar 100 USD."""
    app = entorno_contable_aislado.app
    ids = _escenario(app, "3700")

    errors = _validar(app, ids, rate="40", allocation_date=FECHA)

    assert errors == []


def test_el_endpoint_rechaza_una_fecha_de_aplicacion_invalida(app, entorno_contable, authenticated_client):
    """La prevalidación HTTP no acepta una fecha de aplicación malformada."""
    del entorno_contable
    response = authenticated_client("admin").post(
        "/api/line-import/validate",
        json={
            "doctype": "payment_reconciliation",
            "context": {"company_id": "cacao", "allocation_date": "no-es-fecha", "filters": {}},
            "rows": [{}],
        },
    )

    assert response.status_code == 400, response.get_data(as_text=True)
    assert "fecha de aplicación no es válida" in response.get_json()["errors"][0]["message"]


def test_el_formulario_envia_la_fecha_de_aplicacion_al_prevalidador():
    """La importación usa la misma fecha de aplicación que el POST real."""
    template = (
        Path(__file__).resolve().parents[1]
        / "cacao_accounting"
        / "bancos"
        / "templates"
        / "bancos"
        / "conciliacion_facturas_pagos.html"
    )
    contenido = template.read_text(encoding="utf-8")

    assert "allocation_date: this.filters.allocation_date" in contenido


def test_tasa_historica_ausente_bloquea_la_prevalidacion(entorno_contable_aislado):
    """Sin tasa registrada antes de la fecha, la fila no puede validarse."""
    app = entorno_contable_aislado.app
    ids = _escenario(app, "3700")

    errors = _validar(app, ids, rate="36.5", allocation_date=date(2026, 4, 30))

    assert any("tasa registrada" in error["message"] for error in errors)
