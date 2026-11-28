# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 William José Moreno Reyes

"""#1805: la factura de venta conserva y actualiza el nombre del cliente."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import uuid4

from sqlalchemy import inspect, select

from cacao_accounting.database import CompanyParty, Party, SalesInvoice, SalesMatchingConfig, User, database

FECHA = date(2026, 5, 15)


def _cliente(app):
    """Autentica al administrador de la aplicación aislada."""
    with app.app_context():
        admin = database.session.execute(select(User).filter_by(user="admin")).scalar_one()
        admin_id = str(inspect(admin).identity[0])
    client = app.test_client()
    with client.session_transaction() as session:
        session["_user_id"] = admin_id
        session["_fresh"] = True
    return client


def _customer(app, suffix: str) -> str:
    """Crea un cliente activo y habilitado para la compañía de prueba."""
    with app.app_context():
        customer = Party(
            code=f"CLI-{suffix}",
            name=f"Cliente {suffix}",
            is_customer=True,
            is_active=True,
        )
        database.session.add(customer)
        database.session.flush()
        database.session.add(CompanyParty(company="cacao", party_id=customer.id, is_active=True))
        database.session.commit()
        return str(customer.id)


def _form(customer_id: str, remarks: str) -> dict[str, str]:
    """Payload HTTP válido para crear y editar una factura de venta."""
    return {
        "company": "cacao",
        "customer_id": customer_id,
        "posting_date": FECHA.isoformat(),
        "transaction_currency": "NIO",
        "remarks": remarks,
        "item_code_0": "ART01",
        "item_name_0": "Articulo Comercial",
        "qty_0": "1",
        "uom_0": "UND",
        "rate_0": "10",
        "amount_0": "10",
    }


def test_factura_creada_y_editada_actualiza_nombre_del_cliente(entorno_contable_aislado):
    """El snapshot comercial sigue al cliente en alta y cambio de tercero."""
    app = entorno_contable_aislado.app
    suffix = uuid4().hex[:8]
    first_id = _customer(app, f"1805A-{suffix}")
    second_id = _customer(app, f"1805B-{suffix}")
    with app.app_context():
        config = database.session.execute(select(SalesMatchingConfig).filter_by(company="cacao")).scalar_one_or_none()
        if config is None:
            config = SalesMatchingConfig(company="cacao", matching_type="2-way", require_sales_order=False)
            database.session.add(config)
        else:
            config.matching_type = "2-way"
            config.require_sales_order = False
        database.session.commit()

    client = _cliente(app)
    created = client.post("/sales/sales-invoice/new", data=_form(first_id, f"CLIENTE-1805-{suffix}"))
    assert created.status_code == 302

    with app.app_context():
        invoice = database.session.execute(
            select(SalesInvoice).filter_by(remarks=f"CLIENTE-1805-{suffix}", docstatus=0)
        ).scalar_one()
        invoice_id = invoice.id
        assert invoice.customer_id == first_id
        assert invoice.customer_name == f"Cliente 1805A-{suffix}"

    edited = client.post(
        f"/sales/sales-invoice/{invoice_id}/edit",
        data=_form(second_id, f"CLIENTE-1805-EDIT-{suffix}"),
    )
    assert edited.status_code == 302

    with app.app_context():
        invoice = database.session.get(SalesInvoice, invoice_id)
        assert invoice is not None
        assert invoice.customer_id == second_id
        assert invoice.customer_name == f"Cliente 1805B-{suffix}"
        assert invoice.grand_total == Decimal("10")
