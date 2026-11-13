# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Formulario de transferencia bancaria ante rechazos.

Escenario de negocio: si una transferencia no se puede registrar por datos
inválidos, el usuario debe volver al formulario de transferencia con sus
errores, no a un formulario de pago genérico. Si falta permiso de creación, la
respuesta debe ser de autorización y no un 200 con otro formulario.
"""

from __future__ import annotations

import json
from datetime import date

import pytest

from cacao_accounting import create_app
from cacao_accounting.auth import proteger_passwd
from cacao_accounting.auth.permisos import cargar_permisos_predeterminados
from cacao_accounting.auth.roles import asigna_rol_a_usuario, crea_roles_predeterminados
from cacao_accounting.bancos import services as bancos_services
from cacao_accounting.bancos.services import _create_payment_from_request
from cacao_accounting.config import configuracion
from cacao_accounting.database import (
    Accounts,
    Bank,
    BankAccount,
    Currency,
    Entity,
    Modules,
    PaymentEntry,
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
                Currency(code="NIO", name="Córdoba", decimals=2, active=True, default=True),
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
        gl_origen = Accounts(
            code="1.01.02.001",
            name="Banco origen",
            entity="cacao",
            group=False,
            active=True,
            enabled=True,
            account_type="bank",
        )
        gl_destino = Accounts(
            code="1.01.02.002",
            name="Banco destino",
            entity="cacao",
            group=False,
            active=True,
            enabled=True,
            account_type="bank",
        )
        database.session.add_all([gl_origen, gl_destino])
        database.session.flush()
        origen = BankAccount(
            company="cacao",
            bank_id=banco.id,
            account_name="Cuenta Cacao",
            account_no="CA-1",
            currency="NIO",
            gl_account_id=gl_origen.id,
        )
        destino = BankAccount(
            company="cacao",
            bank_id=banco.id,
            account_name="Cuenta Destino",
            account_no="CA-2",
            currency="NIO",
            gl_account_id=gl_destino.id,
        )
        database.session.add_all([origen, destino])
        database.session.commit()
        crea_roles_predeterminados()
        cargar_permisos_predeterminados()
        asigna_rol_a_usuario("tesorero", "head_of_treasury")
        database.session.commit()
        ids = {"origen": origen.id, "destino": destino.id}
    yield application, ids
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
    cuerpo = response.get_data(as_text=True)
    assert "bankTransferForm" in cuerpo
    assert "La compañía es obligatoria." in cuerpo
    with application.app_context():
        assert database.session.execute(database.select(PaymentEntry)).scalars().all() == []


def test_sin_permiso_de_creacion_responde_403(transferencias_cloud):
    """El rechazo de ACL no se convierte en un 200 con otro formulario."""
    application, ids = transferencias_cloud
    client = application.test_client()
    _iniciar(client, "viewer")

    response = client.post(
        "/cash_management/payment/transfer/new",
        data={
            "payment_payload": (
                '{"payment_type": "internal_transfer", "company": "cacao", '
                f'"bank_account_id": "{ids["origen"]}", "posting_date": "{FECHA.isoformat()}", "paid_amount": "10"}}'
            )
        },
    )

    assert response.status_code == 403
    with application.app_context():
        assert database.session.execute(database.select(PaymentEntry)).scalars().all() == []


def test_fallo_inesperado_propaga_y_hace_rollback(transferencias_cloud, monkeypatch):
    """Un fallo tras el flush no deja el pago huérfano ni oculta el error."""
    application, ids = transferencias_cloud

    def _fallo(*args, **kwargs):
        raise RuntimeError("fallo inesperado después del flush")

    monkeypatch.setattr(bancos_services, "assign_document_identifier", _fallo)
    payload = {
        "payment_type": "internal_transfer",
        "company": "cacao",
        "bank_account_id": ids["origen"],
        "target_bank_account_id": ids["destino"],
        "posting_date": FECHA.isoformat(),
        "paid_amount": "10",
    }

    with application.test_request_context(
        "/cash_management/payment/transfer/new",
        method="POST",
        data={"payment_payload": json.dumps(payload)},
    ):
        from flask_login import login_user

        from cacao_accounting.database import User

        usuario = database.session.execute(database.select(User).filter_by(user="tesorero")).scalar_one()
        login_user(usuario)
        with pytest.raises(RuntimeError, match="fallo inesperado"):
            _create_payment_from_request()

    with application.app_context():
        assert database.session.execute(database.select(PaymentEntry)).scalars().all() == []
