# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Alcance por compañía del formulario de confirmación de saldos.

Escenario de negocio: un auxiliar contable autorizado en ``alpha`` no debe
poder leer el nombre ni los correos de un tercero global que no está activo en
su compañía, aunque conozca el identificador. La confirmación de saldo se
prepara para un tercero de una compañía concreta; sin vínculo activo no hay
motivo legítimo para renderizar sus datos de contacto.
"""

from __future__ import annotations

import pytest

from cacao_accounting import create_app
from cacao_accounting.auth import proteger_passwd
from cacao_accounting.auth.permisos import cargar_permisos_predeterminados
from cacao_accounting.auth.roles import asigna_rol_a_usuario, crea_roles_predeterminados
from cacao_accounting.config import configuracion
from cacao_accounting.database import (
    CompanyParty,
    Entity,
    Modules,
    Party,
    User,
    UserCompanyAccess,
    database,
)

CONTRASENA = "confirmacion-scope-2026"


@pytest.fixture
def confirmaciones_cloud():
    """Cloud con un tercero activo en alpha y otro sin vínculo de compañía."""
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
                    id="auxiliar",
                    user="auxiliar",
                    name="Auxiliar Alpha",
                    password=proteger_passwd(CONTRASENA),
                    active=True,
                ),
                UserCompanyAccess(user_id="auxiliar", company_code="alpha"),
            ]
        )
        database.session.flush()
        cliente_propio = Party(
            code="CLI-ALPHA",
            name="Cliente Alpha",
            is_customer=True,
            primary_email="contacto-alpha@example.test",
        )
        cliente_sin_vinculo = Party(
            code="CLI-ORPHAN",
            name="Cliente Sin Compañía",
            is_customer=True,
            primary_email="private-audit@example.test",
        )
        database.session.add_all([cliente_propio, cliente_sin_vinculo])
        database.session.flush()
        database.session.add(CompanyParty(company="alpha", party_id=cliente_propio.id, is_active=True))
        database.session.commit()
        crea_roles_predeterminados()
        cargar_permisos_predeterminados()
        asigna_rol_a_usuario("auxiliar", "accounting_auxiliar")
        database.session.commit()
        ids = {"propio": cliente_propio.id, "ajeno": cliente_sin_vinculo.id}
    yield application, ids
    with application.app_context():
        database.session.remove()
        database.engine.dispose()


def _iniciar(client) -> None:
    response = client.post("/login", data={"usuario": "auxiliar", "acceso": CONTRASENA}, follow_redirects=True)
    assert response.status_code == 200


def test_confirmacion_no_expone_tercero_sin_vinculo(confirmaciones_cloud):
    """Un tercero sin CompanyParty activo no se renderiza para el usuario."""
    application, ids = confirmaciones_cloud
    client = application.test_client()
    _iniciar(client)

    response = client.get(f"/accounting/balance-confirmations/new?party_id={ids['ajeno']}")

    assert response.status_code == 403
    cuerpo = response.get_data(as_text=True)
    assert "private-audit@example.test" not in cuerpo
    assert "Cliente Sin Compañía" not in cuerpo


def test_confirmacion_muestra_tercero_de_su_compania(confirmaciones_cloud):
    """Control positivo: el tercero activo en alpha sí se puede confirmar."""
    application, ids = confirmaciones_cloud
    client = application.test_client()
    _iniciar(client)

    response = client.get(f"/accounting/balance-confirmations/new?party_id={ids['propio']}")

    assert response.status_code == 200
    cuerpo = response.get_data(as_text=True)
    assert "Cliente Alpha" in cuerpo
    assert "contacto-alpha@example.test" in cuerpo
