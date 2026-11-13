# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Una asignación de rol revocada no conserva la edición de precios.

Escenario de negocio (issue #2011): ``is_sales_price_editor`` aceptaba
cualquier RolesUser de sales_manager sin mirar ``active``; el usuario seguía
viendo y creando listas de precios con una asignación desactivada.
"""

from __future__ import annotations

import pytest
from sqlalchemy.pool import StaticPool

from cacao_accounting import create_app
from cacao_accounting.config import configuracion
from cacao_accounting.database import (
    Currency,
    Entity,
    Modules,
    PriceList,
    Roles,
    RolesUser,
    User,
    UserCompanyAccess,
    database,
)


def _crear_app(rol_activo: bool):
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
                Modules(module="admin", default=False, enabled=True),
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
                    id="ventas",
                    user="ventas",
                    name="Ventas",
                    password=b"x",
                    active=True,
                    classification="system",
                    company="cacao",
                ),
                UserCompanyAccess(user_id="ventas", company_code="cacao"),
                Roles(name="sales_manager", note="Gerente de Ventas"),
            ]
        )
        database.session.flush()
        rol = database.session.execute(database.select(Roles).filter_by(name="sales_manager")).scalar_one()
        database.session.add(RolesUser(user_id="ventas", role_id=rol.id, active=rol_activo))
        database.session.commit()
    return application


def _cliente(application):
    client = application.test_client()
    with client.session_transaction() as session:
        session["_user_id"] = "ventas"
        session["_fresh"] = True
    return client


def test_una_asignacion_revocada_no_entra_al_catalogo():
    """El rol inactivo bloquea GET y POST de listas de precios."""
    application = _crear_app(rol_activo=False)
    try:
        client = _cliente(application)

        assert client.get("/settings/price-lists").status_code == 403
        respuesta = client.post(
            "/settings/price-lists",
            data={"name": "Revoked role write", "company": "cacao", "is_selling": "1", "is_active": "1"},
        )
        assert respuesta.status_code == 403
        with application.app_context():
            assert database.session.execute(database.select(PriceList)).scalars().all() == []
    finally:
        with application.app_context():
            database.session.remove()
            database.engine.dispose()


@pytest.mark.parametrize("rol_activo", [True])
def test_una_asignacion_vigente_conserva_el_acceso(rol_activo):
    """El control positivo mantiene la operación normal del gerente."""
    application = _crear_app(rol_activo=rol_activo)
    try:
        client = _cliente(application)

        assert client.get("/settings/price-lists").status_code == 200
        respuesta = client.post(
            "/settings/price-lists",
            data={"name": "Lista vigente", "company": "cacao", "is_selling": "1", "is_active": "1"},
        )
        assert respuesta.status_code == 302
        with application.app_context():
            lista = database.session.execute(database.select(PriceList)).scalar_one()
            assert lista.name == "Lista vigente"
    finally:
        with application.app_context():
            database.session.remove()
            database.engine.dispose()
