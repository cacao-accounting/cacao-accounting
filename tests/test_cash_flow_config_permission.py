# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1852: el mapeo NIC-7 exige permiso de edición, no solo de consulta.

La ruta ya separa GET (configurar/consultar) de POST (editar). La regresión
verifica que un usuario con ``configurar`` y ``consultar`` pero sin ``editar``
no puede mutar la clasificación del Estado de Flujo de Efectivo.
"""

from __future__ import annotations

from uuid import uuid4

import pytest

from cacao_accounting import create_app
from cacao_accounting.config import configuracion
from cacao_accounting.database import (
    Accounts,
    CashFlowAccountMapping,
    Currency,
    Entity,
    Modules,
    Roles,
    RolesAccess,
    RolesUser,
    User,
    UserCompanyAccess,
    database,
)
from cacao_accounting.reportes.cash_flow import get_cash_flow_config_overview

RUTA = "/accounting/cash-flow-config/{}"


@pytest.fixture
def escenario_efe():
    """App con una cuenta mapeable y usuarios con permisos disjuntos."""
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
    suffix = uuid4().hex[:6].upper()
    with application.app_context():
        database.create_all()
        database.session.add_all(
            [
                Currency(code="NIO", name="Córdoba", decimals=2, active=True, default=True),
                Modules(module="accounting", default=True, enabled=True),
                Entity(code="cacao", name="Cacao", company_name="Cacao SA", tax_id="J-1", currency="NIO", enabled=True),
            ]
        )
        database.session.flush()
        modulo = database.session.execute(database.select(Modules).filter_by(module="accounting")).scalar_one()
        cuenta = Accounts(
            entity="cacao",
            code=f"1{suffix}",
            name=f"Caja {suffix}",
            classification="asset",
            account_type="cash",
            active=True,
            enabled=True,
            group=False,
        )
        database.session.add(cuenta)
        database.session.flush()

        def crear_usuario(nombre: str, **permisos: bool) -> str:
            user_id = f"{nombre}-{suffix}"
            role = Roles(name=f"rol-{nombre}-{suffix}", note=nombre)
            database.session.add_all(
                [
                    User(id=user_id, user=user_id, name=nombre, password=b"unused", active=True, company="cacao"),
                    role,
                ]
            )
            database.session.flush()
            database.session.add_all(
                [
                    RolesAccess(rol_id=role.id, module_id=modulo.id, **permisos),
                    RolesUser(user_id=user_id, role_id=role.id, active=True),
                    UserCompanyAccess(user_id=user_id, company_code="cacao"),
                ]
            )
            return user_id

        ids = {
            "account": cuenta.id,
            "editor": crear_usuario("editor", access=True, view=True, setup=True, edit=True),
            "consultor": crear_usuario("consultor", access=True, view=True, setup=True, edit=False),
            "lector": crear_usuario("lector", access=True, view=True, edit=False),
            "sin_setup": crear_usuario("sin-setup", access=True, view=True, edit=True),
        }
        database.session.commit()
    yield application, ids
    with application.app_context():
        database.session.remove()
        database.engine.dispose()


def _login(application, user_id: str):
    """Cliente autenticado para el usuario indicado."""
    client = application.test_client()
    with client.session_transaction() as session:
        session["_user_id"] = user_id
        session["_fresh"] = True
    return client


def _post(client, account_id: str, seccion: str):
    """Envía el formulario completo con la única cuenta del escenario."""
    return client.post(
        RUTA.format("cacao"),
        data={"account_ids": [account_id], f"section_{account_id}": seccion},
    )


def test_consultor_con_configurar_pero_sin_editar_no_muta_el_mapeo(escenario_efe):
    """configurar/consultar permite ver, pero el POST se rechaza sin editar."""
    application, ids = escenario_efe
    client = _login(application, ids["consultor"])

    assert client.get(RUTA.format("cacao")).status_code == 200
    assert _post(client, ids["account"], "operating").status_code == 403
    with application.app_context():
        assert (
            database.session.execute(
                database.select(CashFlowAccountMapping).filter_by(company="cacao", account_id=ids["account"])
            ).scalar_one_or_none()
            is None
        )


def test_editor_guarda_la_clasificacion(escenario_efe):
    """Control positivo: editar + configurar persiste la sección NIC-7."""
    application, ids = escenario_efe
    client = _login(application, ids["editor"])

    response = _post(client, ids["account"], "operating")

    assert response.status_code == 302
    with application.app_context():
        mapping = database.session.execute(
            database.select(CashFlowAccountMapping).filter_by(company="cacao", account_id=ids["account"])
        ).scalar_one()
        assert mapping.flow_section == "operating"
        assert get_cash_flow_config_overview("cacao")["rows"][0]["section"] in ("operating", "")


def test_sin_permiso_configurar_no_accede_a_la_vista(escenario_efe):
    """El GET sigue protegido por el permiso de configuración contable."""
    application, ids = escenario_efe
    client = _login(application, ids["sin_setup"])

    assert client.get(RUTA.format("cacao")).status_code == 403


def test_lector_no_puede_borrar_ni_alterar_el_mapeo(escenario_efe):
    """Un usuario de solo lectura no accede a la vista ni muta la clasificación."""
    application, ids = escenario_efe
    client = _login(application, ids["lector"])

    assert client.get(RUTA.format("cacao")).status_code == 403
    assert _post(client, ids["account"], "financing").status_code == 403
    with application.app_context():
        assert (
            database.session.execute(
                database.select(CashFlowAccountMapping).filter_by(company="cacao", account_id=ids["account"])
            ).scalar_one_or_none()
            is None
        )


def test_post_vacio_conserva_mapeos_existentes(escenario_efe):
    """Un POST sin account_ids no borra la clasificación ya guardada (#1789)."""
    application, ids = escenario_efe
    with application.app_context():
        database.session.add(
            CashFlowAccountMapping(company="cacao", account_id=ids["account"], flow_section="investing")
        )
        database.session.commit()
    client = _login(application, ids["editor"])

    response = client.post(RUTA.format("cacao"), data={})

    assert response.status_code == 302
    with application.app_context():
        mapping = database.session.execute(
            database.select(CashFlowAccountMapping).filter_by(company="cacao", account_id=ids["account"])
        ).scalar_one()
        assert mapping.flow_section == "investing"
