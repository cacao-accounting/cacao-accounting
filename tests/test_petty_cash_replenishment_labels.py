# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""La lista de reposiciones identifica el fondo y su compañía.

Escenario de negocio (issue #2036): la columna «Caja» mostraba el ULID del
fondo. Un administrador multiempresa no podía saber a qué caja ni a qué
compañía correspondía cada solicitud.
"""

from __future__ import annotations

from datetime import date

from sqlalchemy.pool import StaticPool

from cacao_accounting import create_app
from cacao_accounting.config import configuracion
from cacao_accounting.database import (
    Accounts,
    Currency,
    Entity,
    Modules,
    PettyCashAccount,
    PettyCashReplenishment,
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
        database.session.add(Currency(code="NIO", name="Córdoba", decimals=2, active=True, default=True))
        database.session.flush()
        database.session.add_all(
            [
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
                    code="beta",
                    name="Beta",
                    company_name="Beta SA",
                    tax_id="J0002",
                    currency="NIO",
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
            ]
        )
        database.session.flush()

        cuentas = {}
        for codigo in ("cacao", "beta"):
            cuenta = Accounts(
                code=f"1101-{codigo}",
                name=f"Caja chica {codigo}",
                entity=codigo,
                group=False,
                active=True,
                enabled=True,
                account_type="petty_cash",
            )
            database.session.add(cuenta)
            database.session.flush()
            cuentas[codigo] = cuenta

        fondos = {}
        for codigo, nombre in (("cacao", "Fondo Cacao"), ("beta", "Fondo Beta")):
            fondo = PettyCashAccount(
                company=codigo,
                account_id=cuentas[codigo].id,
                name=nombre,
                currency="NIO",
                float_amount=1000,
                is_active=True,
            )
            database.session.add(fondo)
            database.session.flush()
            fondos[codigo] = fondo

            database.session.add(
                PettyCashReplenishment(
                    company=codigo,
                    petty_cash_id=fondo.id,
                    request_date=date(2026, 10, 15),
                    amount=100,
                    status="borrador",
                    document_no=f"REP-{codigo.upper()}",
                )
            )
        database.session.commit()
        ids = {codigo: fondo.id for codigo, fondo in fondos.items()}
    return application, ids


def _cliente(application):
    client = application.test_client()
    with client.session_transaction() as session:
        session["_user_id"] = "admin"
        session["_fresh"] = True
    return client


def test_la_lista_muestra_nombre_de_fondo_y_compania():
    """Cada reposición se etiqueta con su fondo y compañía, sin ULID crudo."""
    application, ids = _crear_app()
    try:
        client = _cliente(application)
        respuesta = client.get("/cash_management/petty-cash-replenishment/list")

        assert respuesta.status_code == 200
        html = respuesta.get_data(as_text=True)
        assert "Fondo Cacao" in html
        assert "Fondo Beta" in html
        assert "(cacao)" in html
        assert "(beta)" in html
        assert ids["cacao"] not in html
        assert ids["beta"] not in html
    finally:
        with application.app_context():
            database.session.remove()
            database.engine.dispose()
