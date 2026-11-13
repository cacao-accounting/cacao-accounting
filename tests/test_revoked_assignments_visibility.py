# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Las asignaciones de rol revocadas dejan de mostrarse y autorizar.

Escenario de negocio (paraguas #1716): la lista de usuarios y el formulario de
roles seguían mostrando asignaciones con ``RolesUser.active=False``, y la
página de desarrollo seguía habilitando el acceso con ese vínculo revocado.

Cubre #2064 (lectura administrativa) y #2075 (acceso a /info).
"""

from __future__ import annotations

import re

import pytest
from sqlalchemy.pool import StaticPool

from cacao_accounting import create_app
from cacao_accounting.config import configuracion
from cacao_accounting.database import (
    Currency,
    Entity,
    Modules,
    Roles,
    RolesUser,
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
                Modules(module="admin", default=False, enabled=True),
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
                    id="root",
                    user="root",
                    name="Administrador",
                    password=b"x",
                    active=True,
                    classification="admin",
                ),
                *[
                    User(
                        id=user_id,
                        user=user_id,
                        name=user_id,
                        password=b"x",
                        active=True,
                        classification="system",
                    )
                    for user_id in ("revocado", "vigente", "legacy")
                ],
                Roles(name="admin", note="Administrador"),
                Roles(name="auditor", note="Auditor"),
            ]
        )
        database.session.flush()
        admin_role = database.session.execute(database.select(Roles).filter_by(name="admin")).scalar_one()
        auditor_role = database.session.execute(database.select(Roles).filter_by(name="auditor")).scalar_one()
        database.session.add_all(
            [
                RolesUser(user_id="revocado", role_id=admin_role.id, active=False),
                RolesUser(user_id="vigente", role_id=admin_role.id, active=True),
                RolesUser(user_id="legacy", role_id=admin_role.id, active=None),
                RolesUser(user_id="revocado", role_id=auditor_role.id, active=True),
            ]
        )
        database.session.commit()
        roles = {"admin": admin_role.id, "auditor": auditor_role.id}
    return application, roles


def _cliente(application, user_id: str = "root"):
    client = application.test_client()
    with client.session_transaction() as session:
        session["_user_id"] = user_id
        session["_fresh"] = True
    return client


def test_la_lista_de_usuarios_ignora_asignaciones_revocadas():
    """#2064: el lector administrativo solo devuelve roles vigentes."""
    from cacao_accounting.admin.services import _obtener_roles_por_usuario

    application, roles = _crear_app()
    try:
        with application.app_context():
            vigentes = {rol.id for rol in _obtener_roles_por_usuario("revocado")}
            assert vigentes == {roles["auditor"]}
            assert roles["admin"] not in vigentes
    finally:
        with application.app_context():
            database.session.remove()
            database.engine.dispose()


def test_el_formulario_no_marca_el_rol_revocado():
    """#2064: la selección inicial no incluye la asignación revocada."""
    application, roles = _crear_app()
    try:
        client = _cliente(application)
        html = client.get("/settings/users/revocado/roles").get_data(as_text=True)

        etiqueta_admin = next(
            (etiqueta for etiqueta in re.findall(r"<input[^>]*>", html) if f'value="{roles["admin"]}"' in etiqueta),
            None,
        )
        assert etiqueta_admin is not None
        assert "checked" not in etiqueta_admin
    finally:
        with application.app_context():
            database.session.remove()
            database.engine.dispose()


@pytest.mark.parametrize(
    ("user_id", "esperado"),
    [("revocado", 403), ("vigente", 200), ("legacy", 403)],
)
def test_la_pagina_de_desarrollo_exige_asignacion_vigente(user_id, esperado):
    """#2075: solo una asignación activa autoriza; NULL no es soporte legacy."""
    application, _roles = _crear_app()
    try:
        client = _cliente(application, user_id)
        respuesta = client.get("/info")

        assert respuesta.status_code == esperado
    finally:
        with application.app_context():
            database.session.remove()
            database.engine.dispose()
