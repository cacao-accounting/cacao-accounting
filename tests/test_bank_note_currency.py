# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""La nota bancaria muestra la moneda de la cuenta seleccionada.

Escenario de negocio (issue #2040): el callback leía
``event.detail.extra.currency``, pero search-select serializa ``currency`` en
el nivel superior de la opción. La moneda nunca se cargaba en la pantalla.
"""

from __future__ import annotations

from sqlalchemy.pool import StaticPool

from cacao_accounting import create_app
from cacao_accounting.config import configuracion
from cacao_accounting.database import (
    Bank,
    BankAccount,
    Currency,
    Entity,
    Modules,
    User,
    database,
)
from cacao_accounting.search_select import search_select


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
                Currency(code="NIO", name="Córdoba", decimals=2, active=True, default=True),
                Modules(module="cash", default=False, enabled=True),
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
                Bank(name="Banco de Prueba", swift_code="TESTNI2N", is_active=True),
            ]
        )
        database.session.flush()
        banco = database.session.execute(database.select(Bank)).scalar_one()
        database.session.add(
            BankAccount(
                company="cacao",
                bank_id=banco.id,
                account_name="Cuenta Operativa",
                account_no="CTA-001",
                currency="NIO",
                is_active=True,
            )
        )
        database.session.commit()
    return application


def test_search_select_expone_la_moneda_en_la_opcion():
    """El contrato que consume la plantilla es currency de primer nivel."""
    application = _crear_app()
    try:
        with application.app_context():
            payload = search_select("bank_account", "", {"company": ["cacao"]}, limit=5)

            opcion = payload["results"][0]
            assert opcion["currency"] == "NIO"
            assert "extra" not in opcion
    finally:
        with application.app_context():
            database.session.remove()
            database.engine.dispose()


def test_la_nota_lee_la_moneda_del_contrato_vigente():
    """El formulario usa event.detail.currency y no la propiedad inexistente."""
    application = _crear_app()
    try:
        client = application.test_client()
        with client.session_transaction() as session:
            session["_user_id"] = "admin"
            session["_fresh"] = True

        for ruta in (
            "/cash_management/payment/debit-note/new",
            "/cash_management/payment/credit-note/new",
        ):
            respuesta = client.get(ruta)
            assert respuesta.status_code == 200
            html = respuesta.get_data(as_text=True)
            assert "event.detail.currency" in html
            assert "extra.currency" not in html
    finally:
        with application.app_context():
            database.session.remove()
            database.engine.dispose()
