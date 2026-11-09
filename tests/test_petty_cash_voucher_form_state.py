# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""El vale conserva compañía y fondo cuando el POST es rechazado.

Escenario de negocio (issue #2035): la ruta de alta re-renderizaba el
formulario sin rehidratar los Smart Select; la compañía y la caja volvían a
vacío y la persona usuaria debía reconstruir la selección para corregir el
error.
"""

from __future__ import annotations

from sqlalchemy.pool import StaticPool

from cacao_accounting import create_app
from cacao_accounting.config import configuracion
from cacao_accounting.database import (
    Accounts,
    Book,
    Currency,
    Entity,
    Modules,
    PettyCashAccount,
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
                Currency(code="NIO", name="Córdoba", decimals=2, active=True, default=True),
                Currency(code="USD", name="Dólar", decimals=2, active=True),
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
                Entity(
                    code="secret",
                    name="Secret",
                    company_name="Secret SA",
                    tax_id="J0002",
                    currency="USD",
                    enabled=True,
                    status="activo",
                ),
                User(
                    id="admin",
                    user="admin",
                    name="Administrador",
                    password=b"x",
                    active=True,
                    classification="admin",
                ),
                Book(
                    entity="cacao",
                    code="CACAO_BOOK",
                    name="Cacao",
                    status="activo",
                    is_primary=True,
                    currency="NIO",
                ),
                Book(
                    entity="secret",
                    code="SECRET_BOOK",
                    name="Secret",
                    status="activo",
                    is_primary=True,
                    currency="USD",
                ),
            ]
        )
        database.session.flush()
        cuenta = Accounts(
            code="1101-SECRET",
            name="Caja chica secret",
            entity="secret",
            group=False,
            active=True,
            enabled=True,
            account_type="petty_cash",
        )
        database.session.add(cuenta)
        database.session.flush()
        fondo = PettyCashAccount(
            company="secret",
            account_id=cuenta.id,
            name="Fondo secreto",
            currency="USD",
            float_amount=1000,
            is_active=True,
        )
        database.session.add(fondo)
        database.session.commit()
        ids = {"fondo": fondo.id}
    return application, ids


def _cliente(application):
    client = application.test_client()
    with client.session_transaction() as session:
        session["_user_id"] = "admin"
        session["_fresh"] = True
    return client


def test_el_rechazo_rehidrata_compania_fondo_y_moneda():
    """El formulario rechazado conserva las selecciones y la moneda del fondo."""
    application, ids = _crear_app()
    try:
        client = _cliente(application)
        respuesta = client.post(
            "/cash_management/petty-cash-voucher/new",
            data={
                "company": "secret",
                "petty_cash_id": ids["fondo"],
                "naming_series": "",
                "posting_date": "2026-10-15",
                "delivered_to": "Ana",
                "concept": "Prueba",
                "amount": "0",
            },
        )

        assert respuesta.status_code == 200
        html = respuesta.get_data(as_text=True)
        assert "El importe del vale debe ser mayor a cero." in html
        assert 'initialValue: "secret"' in html
        assert f'initialValue: "{ids["fondo"]}"' in html
        assert 'value="USD"' in html
    finally:
        with application.app_context():
            database.session.remove()
            database.engine.dispose()
