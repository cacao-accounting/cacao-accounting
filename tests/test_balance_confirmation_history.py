# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Historial de confirmaciones de saldo limitado al alcance del usuario.

Escenario de negocio: el detalle de un cliente debe mostrar las confirmaciones
de las compañías que el usuario puede consultar, no una lista siempre vacía por
omitir el argumento ``company`` ni filas de compañías ajenas.
"""

from __future__ import annotations

from datetime import date

import pytest

from cacao_accounting import create_app
from cacao_accounting.auth import proteger_passwd
from cacao_accounting.config import configuracion
from cacao_accounting.database import (
    BalanceConfirmation,
    Currency,
    Entity,
    Modules,
    Party,
    Roles,
    RolesAccess,
    RolesUser,
    User,
    UserCompanyAccess,
    database,
)
from cacao_accounting.database.helpers import obtener_id_modulo_por_nombre

CONTRASENA = "historial-confirmaciones-2026"
FECHA = date(2026, 10, 31)


@pytest.fixture
def historial_confirmaciones():
    """Cliente con confirmaciones en cacao y alpha; contador solo de cacao."""
    application = create_app(
        {
            **configuracion,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
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
                Modules(module="accounting", default=False, enabled=True),
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
                    code="alpha",
                    name="Alpha",
                    company_name="Alpha SA",
                    tax_id="J0002",
                    currency="NIO",
                    enabled=True,
                    status="activo",
                ),
                User(
                    id="contador",
                    user="contador",
                    name="Contador Cacao",
                    password=proteger_passwd(CONTRASENA),
                    active=True,
                ),
                UserCompanyAccess(user_id="contador", company_code="cacao"),
                Party(code="CLI-1", name="Cliente Uno", is_customer=True),
            ]
        )
        database.session.flush()
        cliente = database.session.execute(database.select(Party).filter_by(code="CLI-1")).scalar_one()
        rol = Roles(name="confirmaciones_lector", note="Consulta contable")
        database.session.add(rol)
        database.session.flush()
        database.session.add(
            RolesAccess(
                rol_id=rol.id,
                module_id=obtener_id_modulo_por_nombre("accounting"),
                access=True,
                update=False,
                set_null=False,
                approve=False,
                bi=False,
                close=False,
                setup=False,
                view=True,
                create=False,
                edit=False,
                delete=False,
                import_=False,
                report=False,
                request=False,
                validate=False,
            )
        )
        database.session.add(RolesUser(user_id="contador", role_id=rol.id, active=True))
        database.session.add_all(
            [
                BalanceConfirmation(
                    company="cacao",
                    document_no="BC-CACAO",
                    party_type="customer",
                    party_id=cliente.id,
                    cutoff_date=FECHA,
                    status="draft",
                ),
                BalanceConfirmation(
                    company="alpha",
                    document_no="BC-ALPHA",
                    party_type="customer",
                    party_id=cliente.id,
                    cutoff_date=FECHA,
                    status="draft",
                ),
            ]
        )
        database.session.commit()
        ids = {"cliente": cliente.id}
    yield application, ids
    with application.app_context():
        database.session.remove()
        database.engine.dispose()


def _historial(application, cliente_id, company=None):
    from flask_login import login_user

    with application.test_request_context("/"):
        login_user(database.session.get(User, "contador"))
        helper = application.jinja_env.globals["get_balance_confirmations_history"]
        return helper(cliente_id, "customer", company)


def test_historial_sin_compania_usa_el_alcance_autorizado(historial_confirmaciones):
    """El detalle ya no muestra una lista vacía por omitir company."""
    application, ids = historial_confirmaciones

    history = _historial(application, ids["cliente"])

    assert [confirmation.company for confirmation in history] == ["cacao"]
    assert history[0].document_no == "BC-CACAO"


def test_historial_rechaza_compania_fuera_del_alcance(historial_confirmaciones):
    """Una compañía explícita no autorizada no se filtra en la consulta."""
    application, ids = historial_confirmaciones

    assert _historial(application, ids["cliente"], "alpha") == []
    assert [confirmation.company for confirmation in _historial(application, ids["cliente"], "cacao")] == ["cacao"]
