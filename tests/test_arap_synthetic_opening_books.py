# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Las aperturas AR/AP sintéticas reciben valoración por libro.

Escenario de negocio (issue #2118): cuando falta la apertura del documento y
se crea una sintética, el servicio no generaba ``ARAPLedgerBookEntry``. El
saldo por libro omitía la apertura y la conciliación subledger-GL quedaba
incompleta.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from sqlalchemy.pool import StaticPool

from cacao_accounting import create_app
from cacao_accounting.config import configuracion
from cacao_accounting.contabilidad.arap_ledger_service import _resolve_application_target_item
from cacao_accounting.database import (
    ARAPLedgerBookEntry,
    Accounts,
    Book,
    Currency,
    Entity,
    GLEntry,
    Party,
    SalesInvoice,
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
                Currency(code="NIO", name="Córdoba", decimals=2, active=True, default=True),
                Currency(code="USD", name="Dólar", decimals=2, active=True),
                Entity(
                    code="cacao",
                    name="Cacao",
                    company_name="Cacao SA",
                    tax_id="J0001",
                    currency="NIO",
                    enabled=True,
                    status="default",
                ),
            ]
        )
        database.session.flush()
        cliente = Party(id="CUST-1", code="CUST-1", name="Cliente", is_customer=True, is_supplier=False)
        database.session.add(cliente)
        database.session.flush()
        libro_nio = Book(
            entity="cacao",
            code="NIO_BOOK",
            name="Libro NIO",
            status="activo",
            currency="NIO",
            is_primary=True,
        )
        libro_usd = Book(
            entity="cacao",
            code="USD_BOOK",
            name="Libro USD",
            status="activo",
            currency="USD",
        )
        cuenta = Accounts(
            code="1.01.02.001",
            name="Cuentas por cobrar",
            entity="cacao",
            group=False,
            active=True,
            enabled=True,
            account_type="receivable",
        )
        database.session.add_all([libro_nio, libro_usd, cuenta])
        database.session.flush()
        factura = SalesInvoice(
            company="cacao",
            posting_date=FECHA,
            docstatus=1,
            customer_id="CUST-1",
            customer_name="Cliente",
            grand_total=100,
            transaction_currency="NIO",
        )
        database.session.add(factura)
        database.session.flush()
        for libro, importe in ((libro_nio, Decimal("100")), (libro_usd, Decimal("28"))):
            database.session.add(
                GLEntry(
                    posting_date=FECHA,
                    company="cacao",
                    ledger_id=libro.id,
                    account_id=cuenta.id,
                    debit=importe,
                    credit=Decimal("0"),
                    voucher_type="sales_invoice",
                    voucher_id=factura.id,
                    party_type="customer",
                    party_id="CUST-1",
                )
            )
        database.session.commit()
        ids = {"nio": libro_nio.id, "usd": libro_usd.id, "factura": factura.id}
    return application, ids


def test_la_apertura_sintetica_valora_todos_los_libros():
    """Cada libro activo recibe la valoración desde su GL correspondiente."""
    application, ids = _crear_app()
    try:
        with application.app_context():
            factura = database.session.get(SalesInvoice, ids["factura"])
            apertura, _cache, nuevas = _resolve_application_target_item(
                "cacao",
                factura,
                "sales_invoice",
                "NIO",
                "customer",
                "CUST-1",
                "AR",
                Decimal("100"),
                FECHA,
            )
            database.session.flush()

            assert nuevas == [apertura]
            filas = (
                database.session.execute(database.select(ARAPLedgerBookEntry).filter_by(ledger_entry_id=apertura.id))
                .scalars()
                .all()
            )
            por_libro = {fila.ledger_id: fila.book_amount for fila in filas}
            assert por_libro[ids["nio"]] == Decimal("100")
            assert por_libro[ids["usd"]] == Decimal("28")
    finally:
        with application.app_context():
            database.session.remove()
            database.engine.dispose()
