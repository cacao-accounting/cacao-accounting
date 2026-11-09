# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Contratos de UI de caja chica y pagos.

Escenario de negocio:
- #1945: el gasto no transportaba el voucher_id precargado.
- #1946: la reposición pedía el ID interno de la cuenta bancaria.
- #1949: listado/detalle mostraban paid_amount y etiquetas incorrectas.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from sqlalchemy.pool import StaticPool

from cacao_accounting import create_app
from cacao_accounting.config import configuracion
from cacao_accounting.database import (
    Bank,
    Book,
    BankAccount,
    Currency,
    Entity,
    Modules,
    PaymentEntry,
    PettyCashAccount,
    PettyCashReplenishment,
    PettyCashVoucher,
    User,
    database,
)


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
            "MODO_ESCRITORIO": False,
        }
    )
    with application.app_context():
        database.create_all()
        database.session.add_all(
            [
                Modules(module="cash", default=False, enabled=True),
                Currency(code="NIO", name="Córdoba", decimals=2, active=True, default=True),
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
                ),
                Bank(name="Banco Uno", is_active=True),
                Book(code="LIBRO", name="Libro principal", entity="cacao", currency="NIO", status="activo"),
            ]
        )
        database.session.flush()
        banco = database.session.execute(database.select(Bank)).scalar_one()
        fondo = PettyCashAccount(
            company="cacao",
            account_id="CTA-CAJA",
            name="Caja principal",
            currency="NIO",
            float_amount=Decimal("100"),
            is_active=True,
        )
        database.session.add(fondo)
        cuenta_bancaria = BankAccount(
            bank_id=banco.id,
            company="cacao",
            account_name="Cuenta operativa",
            account_no="001-001",
            currency="NIO",
            is_active=True,
        )
        database.session.add(cuenta_bancaria)
        database.session.flush()
        voucher = PettyCashVoucher(
            company="cacao",
            petty_cash_id=fondo.id,
            voucher_no="V-1",
            voucher_status="entregado",
            delivered_to="Ana",
            concept="Compra",
            amount=Decimal("10"),
        )
        reposicion = PettyCashReplenishment(
            company="cacao",
            petty_cash_id=fondo.id,
            request_date=date(2026, 11, 5),
            amount=Decimal("10"),
            status="aprobado",
        )
        recibo = PaymentEntry(
            company="cacao",
            payment_type="receive",
            document_no="REC-1",
            currency="NIO",
            transaction_currency="NIO",
            paid_amount=Decimal("0"),
            received_amount=Decimal("125.50"),
        )
        credito = PaymentEntry(
            company="cacao",
            payment_type="credit_note",
            document_no="CN-1",
            currency="NIO",
            transaction_currency="NIO",
            paid_amount=Decimal("0"),
            received_amount=Decimal("125.50"),
        )
        debito = PaymentEntry(
            company="cacao",
            payment_type="debit_note",
            document_no="DN-1",
            currency="NIO",
            transaction_currency="NIO",
            paid_amount=Decimal("125.50"),
            received_amount=Decimal("0"),
        )
        database.session.add_all([voucher, reposicion, recibo, credito, debito])
        database.session.commit()
        ids = {
            "voucher": voucher.id,
            "replenishment": reposicion.id,
            "receive": recibo.id,
            "credit": credito.id,
            "debit": debito.id,
            "bank_account": cuenta_bancaria.id,
        }
    return application, ids


def _cliente(application):
    client = application.test_client()
    with client.session_transaction() as session:
        session["_user_id"] = "admin"
        session["_fresh"] = True
    return client


def test_gasto_transporta_el_vale_precargado():
    """#1945: el formulario incluye voucher_id como campo oculto."""
    application, ids = _crear_app()
    try:
        client = _cliente(application)
        respuesta = client.get(f"/cash_management/petty-cash-expense/new?voucher_id={ids['voucher']}")

        assert respuesta.status_code == 200
        html = respuesta.get_data(as_text=True)
        assert 'name="voucher_id"' in html
        assert f'value="{ids["voucher"]}"' in html
    finally:
        with application.app_context():
            database.session.remove()
            database.engine.dispose()


def test_reposicion_ofrece_cuentas_bancarias_activas():
    """#1946: la reposición usa un selector con cuentas de la compañía."""
    application, ids = _crear_app()
    try:
        client = _cliente(application)
        respuesta = client.get("/cash_management/petty-cash-replenishment/list")

        assert respuesta.status_code == 200
        html = respuesta.get_data(as_text=True)
        assert 'name="bank_account_id"' in html
        assert "<select" in html
        assert f'value="{ids["bank_account"]}"' in html
        assert "Cuenta operativa" in html
        assert "ID cuenta bancaria" not in html
    finally:
        with application.app_context():
            database.session.remove()
            database.engine.dispose()


def test_listado_de_pagos_usa_received_amount():
    """#1949: recibos muestran received_amount y su moneda."""
    application, _ids = _crear_app()
    try:
        client = _cliente(application)
        respuesta = client.get("/cash_management/payment/list")

        assert respuesta.status_code == 200
        html = respuesta.get_data(as_text=True)
        assert "125.50" in html
        assert "NIO" in html
        assert "Recibir" in html
    finally:
        with application.app_context():
            database.session.remove()
            database.engine.dispose()


def test_detalle_etiqueta_y_monto_por_tipo():
    """#1949: crédito usa received_amount y débito paid_amount con sus etiquetas."""
    application, ids = _crear_app()
    try:
        client = _cliente(application)
        credito = client.get(f"/cash_management/payment/{ids['credit']}").get_data(as_text=True)
        debito = client.get(f"/cash_management/payment/{ids['debit']}").get_data(as_text=True)

        assert "125.50" in credito
        assert "Nota de crédito" in credito
        assert "125.50" in debito
        assert "Nota de débito" in debito
    finally:
        with application.app_context():
            database.session.remove()
            database.engine.dispose()
