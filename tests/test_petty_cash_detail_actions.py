# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Acciones de caja chica alineadas con el permiso efectivo.

Escenario de negocio: un usuario con ``cash.consultar`` puede abrir el detalle
del fondo, pero no debe ver botones de edición, activación ni predeterminado
que el servidor rechazará con 403.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from cacao_accounting import create_app
from cacao_accounting.auth import proteger_passwd
from cacao_accounting.config import configuracion
from cacao_accounting.database import (
    Accounts,
    Currency,
    Entity,
    Modules,
    PettyCashAccount,
    Roles,
    RolesAccess,
    RolesUser,
    User,
    UserCompanyAccess,
    database,
)
from cacao_accounting.database.helpers import obtener_id_modulo_por_nombre

CONTRASENA = "caja-detalle-2026"


@pytest.fixture
def detalle_caja():
    """Fondo de caja chica con un lector y un editor de Caja."""
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
                    id="lector",
                    user="lector",
                    name="Lector Caja",
                    password=proteger_passwd(CONTRASENA),
                    active=True,
                ),
                User(
                    id="editor",
                    user="editor",
                    name="Editor Caja",
                    password=proteger_passwd(CONTRASENA),
                    active=True,
                ),
            ]
        )
        database.session.flush()
        database.session.add_all(
            [
                UserCompanyAccess(user_id="lector", company_code="cacao"),
                UserCompanyAccess(user_id="editor", company_code="cacao"),
                Accounts(
                    code="1.01.05.001",
                    name="Caja Chica",
                    entity="cacao",
                    group=False,
                    active=True,
                    enabled=True,
                    account_type="petty_cash",
                ),
            ]
        )
        database.session.flush()
        caja = PettyCashAccount(
            company="cacao",
            account_id=database.session.execute(database.select(Accounts)).scalar_one().id,
            name="Fondo Principal",
            currency="NIO",
            float_amount=Decimal("1000"),
            is_default=False,
            is_active=True,
        )
        database.session.add(caja)
        database.session.flush()
        rol_lector = Roles(name="caja_lector", note="Solo consulta")
        rol_editor = Roles(name="caja_editor", note="Consulta y edita")
        database.session.add_all([rol_lector, rol_editor])
        database.session.flush()
        cash_id = obtener_id_modulo_por_nombre("cash")
        database.session.add_all(
            [
                RolesAccess(
                    rol_id=rol_lector.id,
                    module_id=cash_id,
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
                ),
                RolesAccess(
                    rol_id=rol_editor.id,
                    module_id=cash_id,
                    access=True,
                    update=False,
                    set_null=False,
                    approve=False,
                    bi=False,
                    close=False,
                    setup=False,
                    view=True,
                    create=False,
                    edit=True,
                    delete=False,
                    import_=False,
                    report=False,
                    request=False,
                    validate=False,
                ),
                RolesUser(user_id="lector", role_id=rol_lector.id, active=True),
                RolesUser(user_id="editor", role_id=rol_editor.id, active=True),
            ]
        )
        database.session.commit()
        caja_id = caja.id
    yield application, caja_id
    with application.app_context():
        database.session.remove()
        database.engine.dispose()


def _iniciar(client, usuario: str) -> None:
    response = client.post("/login", data={"usuario": usuario, "acceso": CONTRASENA}, follow_redirects=True)
    assert response.status_code == 200


def test_detalle_oculta_mutaciones_sin_permiso_editar(detalle_caja):
    """El lector solo ve el listado, no controles que terminan en 403."""
    application, caja_id = detalle_caja
    client = application.test_client()
    _iniciar(client, "lector")

    response = client.get(f"/cash_management/petty-cash/{caja_id}")

    assert response.status_code == 200
    cuerpo = response.get_data(as_text=True)
    assert "Desactivar" not in cuerpo
    assert "Marcar predeterminada" not in cuerpo
    assert f"/cash_management/petty-cash/{caja_id}/edit" not in cuerpo
    assert "Listado" in cuerpo


def test_detalle_muestra_mutaciones_con_permiso_editar(detalle_caja):
    """Control positivo: el editor conserva las acciones."""
    application, caja_id = detalle_caja
    client = application.test_client()
    _iniciar(client, "editor")

    response = client.get(f"/cash_management/petty-cash/{caja_id}")

    assert response.status_code == 200
    cuerpo = response.get_data(as_text=True)
    assert "Desactivar" in cuerpo
    assert "Marcar predeterminada" in cuerpo
    assert f"/cash_management/petty-cash/{caja_id}/edit" in cuerpo


def test_mutaciones_siguen_rechazando_sin_editar(detalle_caja):
    """El servidor conserva las guardias aunque la UI oculte los controles."""
    application, caja_id = detalle_caja
    client = application.test_client()
    _iniciar(client, "lector")

    assert client.get(f"/cash_management/petty-cash/{caja_id}/edit").status_code == 403
    assert client.post(f"/cash_management/petty-cash/{caja_id}/toggle").status_code == 403
    assert client.post(f"/cash_management/petty-cash/{caja_id}/default").status_code == 403
