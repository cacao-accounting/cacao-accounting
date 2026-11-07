# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Acción requerida en las rutas de escritura de contabilidad.

Escenario de negocio (#1601, consolidación #1649): el acceso sencillo
(`access`) no concede escrituras; rutas como ``/accounting/currency/new``
exigen el permiso de la acción propia (``crear``/``editar``/``anular``).
"""

import pytest

from cacao_accounting import create_app
from cacao_accounting.auth import proteger_passwd
from cacao_accounting.config import configuracion
from cacao_accounting.database import database

CONTRASENA = "acciones-contab-2026"


def _sembrar(app):
    with app.app_context():
        database.create_all()
        from cacao_accounting.database import (
            Entity,
            Modules,
            Roles,
            RolesAccess,
            RolesUser,
            User,
            UserCompanyAccess,
            database as _database,
        )
        from cacao_accounting.database.helpers import obtener_id_modulo_por_nombre

        database.session.add_all(
            [
                Modules(module="accounting", default=False, enabled=True),
                Entity(
                    code="cacao",
                    name="Cacao Accounting",
                    company_name="Cacao Accounting SA",
                    tax_id="J0001",
                    currency="NIO",
                    enabled=True,
                    status="default",
                ),
                User(
                    id="revisor",
                    user="revisor",
                    name="Revisor",
                    password=proteger_passwd(CONTRASENA),
                    active=True,
                ),
                User(
                    id="creador",
                    user="creador",
                    name="Creador",
                    password=proteger_passwd(CONTRASENA),
                    active=True,
                ),
                UserCompanyAccess(user_id="revisor", company_code="cacao"),
                UserCompanyAccess(user_id="creador", company_code="cacao"),
            ]
        )
        database.session.commit()

        rol = Roles(name="revisor-contab", note="Access sin view/create")
        database.session.add(rol)
        database.session.flush()
        _database.session.add(
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
                view=False,
                create=False,
                edit=False,
                delete=False,
                import_=False,
                report=False,
                request=False,
                validate=False,
            )
        )
        rol_creador = Roles(name="editor-contab", note="Access, view y create")
        database.session.add(rol_creador)
        database.session.flush()
        _database.session.add(
            RolesAccess(
                rol_id=rol_creador.id,
                module_id=obtener_id_modulo_por_nombre("accounting"),
                access=True,
                update=False,
                set_null=False,
                approve=False,
                bi=False,
                close=False,
                setup=False,
                view=True,
                create=True,
                edit=False,
                delete=False,
                import_=False,
                report=False,
                request=False,
                validate=False,
            )
        )
        database.session.add_all(
            [
                RolesUser(user_id="revisor", role_id=rol.id, active=True),
                RolesUser(user_id="creador", role_id=rol_creador.id, active=True),
            ]
        )
        database.session.commit()


@pytest.fixture
def contabilidad_roles():
    """Aplicación con dos roles calibrados (revisor sin crear; creador con crear)."""
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
    _sembrar(application)
    yield application
    with application.app_context():
        database.session.remove()
        database.engine.dispose()


def test_moneda_rechaza_acceso_sin_permiso_crear(contabilidad_roles):
    """#1601: access sin create no persiste una moneda nueva; 403."""
    application = contabilidad_roles
    client = application.test_client()
    assert client.post("/login", data={"usuario": "revisor", "acceso": CONTRASENA}, follow_redirects=True).status_code == 200
    response = client.post(
        "/accounting/currency/new",
        data={"code": "TST", "name": "Test Currency", "decimals": "2"},
        follow_redirects=False,
    )
    assert response.status_code == 403
    with application.app_context():
        from cacao_accounting.database import Currency, database

        assert database.session.execute(database.select(Currency).filter_by(code="TST")).scalar_one_or_none() is None


def test_moneda_acepta_al_usuario_con_permiso_crear(contabilidad_roles):
    """Control positivo: el creador persiste la moneda."""
    application = contabilidad_roles
    client = application.test_client()
    assert client.post("/login", data={"usuario": "creador", "acceso": CONTRASENA}, follow_redirects=True).status_code == 200
    response = client.post(
        "/accounting/currency/new",
        data={"code": "TST", "name": "Test Currency", "decimals": "2"},
        follow_redirects=False,
    )
    assert response.status_code == 302
    with application.app_context():
        from cacao_accounting.database import Currency, database

        assert database.session.execute(database.select(Currency).filter_by(code="TST")).scalar_one() is not None
