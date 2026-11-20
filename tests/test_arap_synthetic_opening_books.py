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

import pytest
from sqlalchemy.pool import StaticPool

from cacao_accounting import create_app
from cacao_accounting.config import configuracion
from cacao_accounting.contabilidad.arap_ledger_service import (
    _resolve_application_payment_item,
    _resolve_application_target_item,
)
from cacao_accounting.contabilidad.posting_service import PostingError
from cacao_accounting.database import (
    ARAPLedgerBookEntry,
    Accounts,
    Book,
    Currency,
    Entity,
    ExchangeRate,
    GLEntry,
    Party,
    PaymentEntry,
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
        cliente = Party(code="CUST-1", name="Cliente", is_customer=True, is_active=True)
        database.session.add_all([libro_nio, libro_usd, cuenta, cliente])
        database.session.flush()
        cliente_id = str(cliente.id)
        factura = SalesInvoice(
            company="cacao",
            posting_date=FECHA,
            docstatus=1,
            customer_id=cliente_id,
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
                    party_id=cliente_id,
                )
            )

        pago = PaymentEntry(
            company="cacao",
            posting_date=FECHA,
            docstatus=1,
            document_no="PAY-2118",
            payment_type="receive",
            party_type="customer",
            party_id=cliente_id,
            party_name="Cliente",
            currency="NIO",
            exchange_rate=Decimal("1"),
            received_amount=Decimal("80"),
            base_received_amount=Decimal("80"),
            unallocated_amount=Decimal("80"),
        )
        factura_sin_gl = SalesInvoice(
            company="cacao",
            posting_date=FECHA,
            docstatus=1,
            customer_id=cliente_id,
            customer_name="Cliente",
            grand_total=200,
            transaction_currency="NIO",
        )
        factura_usd_sin_gl = SalesInvoice(
            company="cacao",
            posting_date=FECHA,
            docstatus=1,
            customer_id=cliente_id,
            customer_name="Cliente",
            grand_total=200,
            transaction_currency="USD",
            exchange_rate=Decimal("35"),
        )
        database.session.add_all([pago, factura_sin_gl, factura_usd_sin_gl])
        database.session.flush()
        for libro, importe in ((libro_nio, Decimal("80")), (libro_usd, Decimal("20"))):
            database.session.add(
                GLEntry(
                    posting_date=FECHA,
                    company="cacao",
                    ledger_id=libro.id,
                    account_id=cuenta.id,
                    debit=Decimal("0"),
                    credit=importe,
                    voucher_type="payment_entry",
                    voucher_id=pago.id,
                    party_type="customer",
                    party_id=cliente_id,
                )
            )
        database.session.commit()
        ids = {
            "nio": libro_nio.id,
            "usd": libro_usd.id,
            "factura": factura.id,
            "factura_sin_gl": factura_sin_gl.id,
            "factura_usd_sin_gl": factura_usd_sin_gl.id,
            "pago": pago.id,
            "cliente": cliente_id,
        }
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
                ids["cliente"],
                "AR",
                Decimal("100"),
                FECHA,
            )
            database.session.flush()

            assert nuevas == [apertura]
            por_libro = _valoracion_por_libro(apertura)
            assert por_libro[ids["nio"]] == Decimal("100")
            assert por_libro[ids["usd"]] == Decimal("28")
    finally:
        with application.app_context():
            database.session.remove()
            database.engine.dispose()


def _valoracion_por_libro(apertura) -> dict[str, Decimal]:
    """Devuelve el importe valorado de la apertura en cada libro."""
    filas = (
        database.session.execute(database.select(ARAPLedgerBookEntry).filter_by(ledger_entry_id=apertura.id)).scalars().all()
    )
    return {fila.ledger_id: fila.book_amount for fila in filas}


def test_la_apertura_sintetica_del_pago_valora_todos_los_libros():
    """El camino de pagos también genera la valoración por libro de la apertura."""
    application, ids = _crear_app()
    try:
        with application.app_context():
            pago = database.session.get(PaymentEntry, ids["pago"])
            apertura, _cache, nuevas = _resolve_application_payment_item(
                "cacao",
                pago,
                "payment_entry",
                ids["pago"],
                "NIO",
                "customer",
                ids["cliente"],
                "AR",
                Decimal("80"),
                FECHA,
            )
            database.session.flush()

            assert nuevas == [apertura]
            por_libro = _valoracion_por_libro(apertura)
            assert por_libro[ids["nio"]] == Decimal("-80")
            assert por_libro[ids["usd"]] == Decimal("-20")
    finally:
        with application.app_context():
            database.session.remove()
            database.engine.dispose()


def test_apertura_sintetica_sin_gl_valora_con_la_tasa_del_libro():
    """Sin líneas GL la apertura se convierte con la tasa vigente del libro."""
    application, ids = _crear_app()
    try:
        with application.app_context():
            database.session.add(ExchangeRate(origin="NIO", destination="USD", date=FECHA, rate=Decimal("0.0357")))
            database.session.commit()
            factura = database.session.get(SalesInvoice, ids["factura_sin_gl"])
            apertura, _cache, nuevas = _resolve_application_target_item(
                "cacao",
                factura,
                "sales_invoice",
                "NIO",
                "customer",
                ids["cliente"],
                "AR",
                Decimal("200"),
                FECHA,
            )
            database.session.flush()

            assert nuevas == [apertura]
            por_libro = _valoracion_por_libro(apertura)
            assert por_libro[ids["nio"]] == Decimal("200")
            assert por_libro[ids["usd"]] == Decimal("7.14")
    finally:
        with application.app_context():
            database.session.remove()
            database.engine.dispose()


def test_apertura_sintetica_sin_tasa_bloquea_el_registro():
    """Falta la tasa hacia el libro y no se puede registrar la apertura."""
    application, ids = _crear_app()
    try:
        with application.app_context():
            factura = database.session.get(SalesInvoice, ids["factura_sin_gl"])
            with pytest.raises(PostingError):
                _resolve_application_target_item(
                    "cacao",
                    factura,
                    "sales_invoice",
                    "NIO",
                    "customer",
                    ids["cliente"],
                    "AR",
                    Decimal("200"),
                    FECHA,
                )
            database.session.rollback()
    finally:
        with application.app_context():
            database.session.remove()
            database.engine.dispose()


def test_apertura_sintetica_sin_gl_usa_la_tasa_del_documento():
    """Sin GL ni tasas registradas, el libro funcional usa la tasa histórica del documento."""
    application, ids = _crear_app()
    try:
        with application.app_context():
            factura = database.session.get(SalesInvoice, ids["factura_usd_sin_gl"])
            apertura, _cache, nuevas = _resolve_application_target_item(
                "cacao",
                factura,
                "sales_invoice",
                "USD",
                "customer",
                ids["cliente"],
                "AR",
                Decimal("200"),
                FECHA,
            )
            database.session.flush()

            assert nuevas == [apertura]
            por_libro = _valoracion_por_libro(apertura)
            assert por_libro[ids["nio"]] == Decimal("7000")
            assert por_libro[ids["usd"]] == Decimal("200")
    finally:
        with application.app_context():
            database.session.remove()
            database.engine.dispose()


def test_apertura_sintetica_sin_tasa_de_documento_bloquea_el_registro():
    """Sin GL, sin tasas y sin tasa histórica no se valoriza 1:1 contra el libro funcional."""
    application, ids = _crear_app()
    try:
        with application.app_context():
            factura = database.session.get(SalesInvoice, ids["factura_usd_sin_gl"])
            factura.exchange_rate = None
            with pytest.raises(PostingError):
                _resolve_application_target_item(
                    "cacao",
                    factura,
                    "sales_invoice",
                    "USD",
                    "customer",
                    ids["cliente"],
                    "AR",
                    Decimal("200"),
                    FECHA,
                )
            database.session.rollback()
            assert database.session.execute(database.select(ARAPLedgerBookEntry.id)).scalar_one_or_none() is None
    finally:
        with application.app_context():
            database.session.remove()
            database.engine.dispose()
