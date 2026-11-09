# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Permiso y conservación del mapeo NIC 7 del Estado de Flujos de Efectivo.

Escenario de negocio: un usuario con permiso de consulta contable puede abrir
la clasificación EFE, pero no mutarla. Un POST vacío o manipulado tampoco debe
borrar la clasificación existente: la ausencia de cuentas no equivale a una
orden explícita de eliminar todos los mapeos.
"""

from __future__ import annotations

import pytest

from cacao_accounting import create_app
from cacao_accounting.auth import proteger_passwd
from cacao_accounting.auth.permisos import cargar_permisos_predeterminados
from cacao_accounting.auth.roles import asigna_rol_a_usuario, crea_roles_predeterminados
from cacao_accounting.config import configuracion
from cacao_accounting.database import (
    Accounts,
    CashFlowAccountMapping,
    Entity,
    Modules,
    User,
    UserCompanyAccess,
    database,
)

CONTRASENA = "efe-mapeo-2026"


@pytest.fixture
def efe_cloud():
    """Compañía alpha con una cuenta y su clasificación EFE explícita."""
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
                Modules(module="accounting", default=False, enabled=True),
                Entity(
                    code="alpha",
                    name="Alpha",
                    company_name="Alpha SA",
                    tax_id="J0001",
                    currency="NIO",
                    enabled=True,
                    status="default",
                ),
                User(
                    id="lector",
                    user="lector",
                    name="Contador Lector",
                    password=proteger_passwd(CONTRASENA),
                    active=True,
                ),
                User(
                    id="editor",
                    user="editor",
                    name="Contador Editor",
                    password=proteger_passwd(CONTRASENA),
                    active=True,
                ),
                UserCompanyAccess(user_id="lector", company_code="alpha"),
                UserCompanyAccess(user_id="editor", company_code="alpha"),
            ]
        )
        database.session.flush()
        cuenta = Accounts(
            code="1.01.01.001",
            name="Caja",
            entity="alpha",
            group=False,
            active=True,
            enabled=True,
            account_type="cash",
        )
        database.session.add(cuenta)
        database.session.flush()
        segunda = Accounts(
            code="1.01.02.001",
            name="Banco",
            entity="alpha",
            group=False,
            active=True,
            enabled=True,
            account_type="bank",
        )
        database.session.add(segunda)
        database.session.flush()
        database.session.add(CashFlowAccountMapping(company="alpha", account_id=cuenta.id, flow_section="operating"))
        database.session.commit()
        crea_roles_predeterminados()
        cargar_permisos_predeterminados()
        asigna_rol_a_usuario("lector", "accounting_user")
        asigna_rol_a_usuario("editor", "accounting_auxiliar")
        database.session.commit()
        ids = {"cuenta": cuenta.id, "segunda": segunda.id}
    yield application, ids
    with application.app_context():
        database.session.remove()
        database.engine.dispose()


def _iniciar(client, usuario: str) -> None:
    response = client.post("/login", data={"usuario": usuario, "acceso": CONTRASENA}, follow_redirects=True)
    assert response.status_code == 200


def _seccion(application, account_id: str) -> str | None:
    with application.app_context():
        mapeo = database.session.execute(
            database.select(CashFlowAccountMapping).filter_by(company="alpha", account_id=account_id)
        ).scalar_one_or_none()
        return mapeo.flow_section if mapeo else None


def test_lector_no_puede_mutar_el_mapeo(efe_cloud):
    """Consultar no autoriza reescribir la clasificación NIC 7."""
    application, ids = efe_cloud
    client = application.test_client()
    _iniciar(client, "lector")

    response = client.post(
        "/accounting/cash-flow-config/alpha",
        data={
            "account_ids": [ids["cuenta"], ids["segunda"]],
            f"section_{ids['cuenta']}": "investing",
        },
    )

    assert response.status_code == 403
    assert _seccion(application, ids["cuenta"]) == "operating"


def test_editor_guarda_el_mapeo(efe_cloud):
    """Control positivo: editar sí permite cambiar la clasificación."""
    application, ids = efe_cloud
    client = application.test_client()
    _iniciar(client, "editor")

    response = client.post(
        "/accounting/cash-flow-config/alpha",
        data={
            "account_ids": [ids["cuenta"], ids["segunda"]],
            f"section_{ids['cuenta']}": "investing",
        },
    )

    assert response.status_code == 302
    assert _seccion(application, ids["cuenta"]) == "investing"


def test_post_parcial_no_borra_mapeos_omitidos(efe_cloud):
    """Un POST que no representa el conjunto completo no elimina mapeos."""
    application, ids = efe_cloud
    client = application.test_client()
    _iniciar(client, "editor")

    response = client.post(
        "/accounting/cash-flow-config/alpha",
        data={"account_ids": [ids["cuenta"]], f"section_{ids['cuenta']}": "investing"},
    )

    assert response.status_code == 302
    assert _seccion(application, ids["cuenta"]) == "operating"


def test_post_sin_cuentas_no_borra_la_clasificacion(efe_cloud):
    """Un POST sin account_ids no elimina la clasificación existente."""
    application, ids = efe_cloud
    client = application.test_client()
    _iniciar(client, "editor")

    response = client.post("/accounting/cash-flow-config/alpha", data={})

    assert response.status_code == 302
    assert _seccion(application, ids["cuenta"]) == "operating"
