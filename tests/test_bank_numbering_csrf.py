# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Guardado AJAX de numeración bancaria con CSRF.

Escenario de negocio: el botón Guardar envía JSON al endpoint de numeración.
Con CSRFProtect activo, el fetch debe incluir ``X-CSRFToken``; sin él la
configuración no se persiste.
"""

from __future__ import annotations

import json
import re

import pytest

from cacao_accounting import create_app
from cacao_accounting.auth import proteger_passwd
from cacao_accounting.config import configuracion
from cacao_accounting.database import (
    Bank,
    BankAccount,
    BankAccountNumberingConfig,
    Currency,
    Entity,
    Modules,
    User,
    database,
)

CONTRASENA = "numeracion-csrf-2026"


@pytest.fixture
def numeracion_csrf():
    """Cuenta bancaria con CSRF activo."""
    application = create_app(
        {
            **configuracion,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
            "WTF_CSRF_ENABLED": True,
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
                    id="admin",
                    user="admin",
                    name="Administrador",
                    password=proteger_passwd(CONTRASENA),
                    active=True,
                    classification="admin",
                ),
            ]
        )
        database.session.commit()
        banco = Bank(name="Banco de Prueba", swift_code="TESTNI2N", is_active=True)
        database.session.add(banco)
        database.session.flush()
        cuenta = BankAccount(
            company="cacao",
            bank_id=banco.id,
            account_name="Cuenta Cacao",
            account_no="CA-1",
            currency="NIO",
            is_active=True,
        )
        database.session.add(cuenta)
        database.session.commit()
        cuenta_id = cuenta.id
    yield application, cuenta_id
    with application.app_context():
        database.session.remove()
        database.engine.dispose()


def _token(html: str) -> str:
    match = re.search(r"X-CSRFToken':\s*'([^']+)'", html)
    assert match is not None
    return match.group(1)


def _login(client) -> None:
    pagina = client.get("/login")
    csrf = re.search(r'csrf_token[^>]*value="([^"]+)"', pagina.get_data(as_text=True))
    assert csrf is not None
    response = client.post(
        "/login",
        data={"usuario": "admin", "acceso": CONTRASENA, "csrf_token": csrf.group(1)},
        follow_redirects=True,
    )
    assert response.status_code == 200


def test_guardado_de_numeracion_envia_csrf(numeracion_csrf):
    """El fetch incluye el token y el POST persiste la configuración."""
    application, cuenta_id = numeracion_csrf
    client = application.test_client()
    _login(client)

    pagina = client.get(f"/cash_management/bank-account/{cuenta_id}")
    assert pagina.status_code == 200
    token = _token(pagina.get_data(as_text=True))

    response = client.post(
        f"/cash_management/bank-account/{cuenta_id}/numbering-config",
        data=json.dumps({"configs": [{"payment_type": "pay", "use_external_counter": False}]}),
        content_type="application/json",
        headers={"X-CSRFToken": token},
    )

    assert response.status_code == 200
    assert response.get_json()["status"] == "ok"
    with application.app_context():
        config = database.session.execute(
            database.select(BankAccountNumberingConfig).filter_by(bank_account_id=cuenta_id, payment_type="pay")
        ).scalar_one()
        assert config.use_external_counter is False


def test_guardado_sin_csrf_es_rechazado(numeracion_csrf):
    """CSRFProtect sigue activo para el endpoint AJAX."""
    application, cuenta_id = numeracion_csrf
    client = application.test_client()
    _login(client)

    response = client.post(
        f"/cash_management/bank-account/{cuenta_id}/numbering-config",
        data=json.dumps({"configs": []}),
        content_type="application/json",
    )

    assert response.status_code == 400
