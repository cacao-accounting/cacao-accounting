# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Formulario de transferencia bancaria ante rechazos.

Escenario de negocio: si una transferencia no se puede registrar por datos
inválidos, el usuario debe volver al formulario de transferencia con sus
errores, no a un formulario de pago genérico. Si falta permiso de creación, la
respuesta debe ser de autorización y no un 200 con otro formulario.
"""

from __future__ import annotations

from datetime import date

import pytest

from cacao_accounting import create_app
from cacao_accounting.auth import proteger_passwd
from cacao_accounting.auth.permisos import cargar_permisos_predeterminados
from cacao_accounting.auth.roles import asigna_rol_a_usuario, crea_roles_predeterminados
from cacao_accounting.config import configuracion
from cacao_accounting.database import (
    Bank,
    BankAccount,
    Entity,
    Modules,
    User,
    UserCompanyAccess,
    database,
)

CONTRASENA = "transferencia-form-2026"
FECHA = date(2026, 10, 20)


@pytest.fixture
def transferencias_cloud():
    """Cloud con cuenta bancaria y usuarios con y sin permiso de caja."""
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
                    id="tesorero",
                    user="tesorero",
                    name="Tesorero",
                    password=proteger_passwd(CONTRASENA),
                    active=True,
                ),
                User(
                    id="viewer",
                    user="viewer",
                    name="Solo Lectura",
                    password=proteger_passwd(CONTRASENA),
                    active=True,
                ),
                UserCompanyAccess(user_id="tesorero", company_code="cacao"),
            ]
        )
        database.session.commit()
        banco = Bank(name="Banco de Prueba", swift_code="TESTNI2N", is_active=True)
        database.session.add(banco)
        database.session.flush()
        cuenta = BankAccount(company="cacao", bank_id=banco.id, account_name="Cuenta Cacao", account_no="CA-1")
        database.session.add(cuenta)
        database.session.commit()
        crea_roles_predeterminados()
        cargar_permisos_predeterminados()
        asigna_rol_a_usuario("tesorero", "head_of_treasury")
        database.session.commit()
        cuenta_id = cuenta.id
    yield application, cuenta_id
    with application.app_context():
        database.session.remove()
        database.engine.dispose()


def _iniciar(client, usuario: str) -> None:
    response = client.post("/login", data={"usuario": usuario, "acceso": CONTRASENA}, follow_redirects=True)
    assert response.status_code == 200


def test_datos_invalidos_vuelven_al_formulario_de_transferencia(transferencias_cloud):
    """Un POST inválido conserva el formulario de transferencia, no el de pago."""
    application, _ = transferencias_cloud
    client = application.test_client()
    _iniciar(client, "tesorero")

    response = client.post("/cash_management/payment/transfer/new", data={})

    assert response.status_code == 200
    assert "bankTransferForm" in response.get_data(as_text=True)


def test_sin_permiso_de_creacion_responde_403(transferencias_cloud):
    """El rechazo de ACL no se convierte en un 200 con otro formulario."""
    application, cuenta_id = transferencias_cloud
    client = application.test_client()
    _iniciar(client, "viewer")

    response = client.post(
        "/cash_management/payment/transfer/new",
        data={
            "payment_payload": (
                '{"payment_type": "internal_transfer", "company": "cacao", '
                f'"bank_account_id": "{cuenta_id}", "posting_date": "{FECHA.isoformat()}", "paid_amount": "10"}}'
            )
        },
    )

    assert response.status_code == 403
