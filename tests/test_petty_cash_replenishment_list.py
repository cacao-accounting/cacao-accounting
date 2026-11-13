# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""La lista de reposiciones no enlaza una edición inexistente.

Escenario de negocio (issue #2034): la plantilla ofrecía «Editar» apuntando a
``bancos.caja_chica_reposicion_editar``, endpoint que no existe. Cualquier
reposición en borrador rompía el render con BuildError (HTTP 500). No hay
flujo de edición implementado ni caller que pase ``reposicion``; mientras no
se apruebe ese contrato, la acción huérfana no debe ofrecerse.
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
        cuenta = Accounts(
            code="1101-CACAO",
            name="Caja chica",
            entity="cacao",
            group=False,
            active=True,
            enabled=True,
            account_type="petty_cash",
        )
        database.session.add(cuenta)
        database.session.flush()
        fondo = PettyCashAccount(
            company="cacao",
            account_id=cuenta.id,
            name="Fondo Cacao",
            currency="NIO",
            float_amount=1000,
            is_active=True,
        )
        database.session.add(fondo)
        database.session.flush()
        database.session.add(
            PettyCashReplenishment(
                company="cacao",
                petty_cash_id=fondo.id,
                request_date=date(2026, 10, 15),
                amount=100,
                status="borrador",
                document_no="REP-CACAO",
            )
        )
        database.session.commit()
    return application


def test_el_borrador_renderiza_sin_enlace_de_edicion_inexistente():
    """La acción disponible es Solicitar/Anular, no un endpoint ausente."""
    application = _crear_app()
    try:
        client = application.test_client()
        with client.session_transaction() as session:
            session["_user_id"] = "admin"
            session["_fresh"] = True

        respuesta = client.get("/cash_management/petty-cash-replenishment/list")

        assert respuesta.status_code == 200
        html = respuesta.get_data(as_text=True)
        assert "REP-CACAO" in html
        assert "Solicitar" in html
        assert "Editar" not in html
        assert "Anular" not in html
    finally:
        with application.app_context():
            database.session.remove()
            database.engine.dispose()
