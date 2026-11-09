# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""La lista de notas de débito pagina y clasifica por su propio tipo.

Escenario de negocio (issue #2050): la plantilla compartida paginaba hacia la
lista de devoluciones y calculaba el estado como ``sales_invoice``. La página
2 mostraba notas de crédito y un débito pendiente de aprobación aparecía como
pendiente de cobro.
"""

from __future__ import annotations

from datetime import date

from sqlalchemy.pool import StaticPool

from cacao_accounting import create_app
from cacao_accounting.config import configuracion
from cacao_accounting.database import (
    ApprovalRequest,
    Entity,
    Modules,
    SalesInvoice,
    User,
    database,
)

FECHA = date(2026, 10, 15)


def _crear_app():
    application = create_app(
        {
            **configuracion,
            "SQLALCHEMY_DATABASE_URI": "sqlite://",
            "SQLALCHEMY_ENGINE_OPTIONS": {
                "poolclass": StaticPool,
                "connect_args": {"check_same_thread": False},
            },
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
            "WTF_CSRF_ENABLED": False,
            "TESTING": True,
            "MODO_ESCRITORIO": True,
        }
    )
    with application.app_context():
        database.create_all()
        database.session.add_all(
            [
                Modules(module="sales", default=False, enabled=True),
                Entity(
                    code="cacao",
                    name="Cacao",
                    company_name="Cacao SA",
                    tax_id="J0001",
                    currency="NIO",
                    enabled=True,
                    status="default",
                ),
                User(
                    id="admin",
                    user="admin",
                    name="Administrador",
                    password=b"x",
                    active=True,
                    classification="admin",
                    company="cacao",
                ),
            ]
        )
        database.session.flush()
        for indice in range(12):
            database.session.add(
                SalesInvoice(
                    company="cacao",
                    posting_date=FECHA,
                    docstatus=0,
                    document_type="sales_debit_note",
                    document_no=f"DN-{indice:02d}",
                    customer_name="Cliente",
                    transaction_currency="NIO",
                )
            )
            database.session.add(
                SalesInvoice(
                    company="cacao",
                    posting_date=FECHA,
                    docstatus=0,
                    document_type="sales_credit_note",
                    document_no=f"CN-{indice:02d}",
                    customer_name="Cliente",
                    transaction_currency="NIO",
                )
            )
        database.session.commit()
        pendiente = database.session.execute(database.select(SalesInvoice).filter_by(document_no="DN-00")).scalar_one()
        database.session.add(
            ApprovalRequest(
                document_type="sales_debit_note",
                document_id=pendiente.id,
                company_id="cacao",
                requested_by="admin",
                current_level=1,
                required_level=1,
                status="Pending Approval",
            )
        )
        database.session.commit()
    return application


def _cliente(application):
    client = application.test_client()
    with client.session_transaction() as session:
        session["_user_id"] = "admin"
        session["_fresh"] = True
    return client


def test_la_pagina_dos_conserva_la_lista_de_debitos():
    """Siguiente apunta al endpoint de notas de débito, no a devoluciones."""
    application = _crear_app()
    try:
        client = _cliente(application)
        primera = client.get("/sales/sales-invoice/debit-note/list").get_data(as_text=True)
        segunda = client.get("/sales/sales-invoice/debit-note/list?page=2").get_data(as_text=True)

        assert "sales-invoice/debit-note/list?page=2" in primera
        assert "CN-" not in primera
        assert "CN-" not in segunda
        assert any(f"DN-{indice:02d}" in segunda for indice in range(10, 12))
    finally:
        with application.app_context():
            database.session.remove()
            database.engine.dispose()


def test_el_estado_usa_el_tipo_documental_de_la_fila():
    """Una nota de débito pendiente se muestra como pendiente de aprobación."""
    application = _crear_app()
    try:
        client = _cliente(application)
        html = client.get("/sales/sales-invoice/debit-note/list?search=DN-00").get_data(as_text=True)

        assert "Pendiente de Aprobación" in html
        assert "Pendiente Cobrar" not in html
    finally:
        with application.app_context():
            database.session.remove()
            database.engine.dispose()
