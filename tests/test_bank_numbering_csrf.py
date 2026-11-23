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
    ExternalCounter,
    NamingSeries,
    Roles,
    RolesAccess,
    RolesUser,
    User,
    UserCompanyAccess,
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
        database.session.add(Currency(code="NIO", name="Córdoba", decimals=2, active=True, default=True))
        database.session.flush()
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
                    id="admin",
                    user="admin",
                    name="Administrador",
                    password=proteger_passwd(CONTRASENA),
                    active=True,
                    classification="admin",
                ),
                UserCompanyAccess(user_id="admin", company_code="cacao"),
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
    html = pagina.get_data(as_text=True)
    assert "Editar" in html
    token = _token(html)

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


@pytest.mark.parametrize("reference", ["series", "counter"])
def test_configuracion_rechaza_referencia_inactiva_sin_guardado_parcial(numeracion_csrf, reference):
    """La configuración no persiste ninguna entrada si una referencia está inactiva."""
    application, account_id = numeracion_csrf
    with application.app_context():
        if reference == "series":
            item = NamingSeries(
                name="Serie inactiva",
                entity_type="payment_entry",
                company="cacao",
                prefix_template="PAY-*YYYY*-",
                is_active=False,
            )
        else:
            item = ExternalCounter(
                company="cacao",
                name="Chequera inactiva",
                counter_type="checkbook",
                is_active=False,
            )
        database.session.add(item)
        database.session.commit()
        item_id = item.id

    client = application.test_client()
    _login(client)
    detail = client.get(f"/cash_management/bank-account/{account_id}")
    payload = {"payment_type": "pay", "use_external_counter": reference == "counter"}
    payload["naming_series_id" if reference == "series" else "external_counter_id"] = item_id
    response = client.post(
        f"/cash_management/bank-account/{account_id}/numbering-config",
        json={"configs": [payload, {"payment_type": "receive", "use_external_counter": False}]},
        headers={"X-CSRFToken": _token(detail.get_data(as_text=True))},
    )

    assert response.status_code == 400
    with application.app_context():
        assert (
            database.session.execute(database.select(BankAccountNumberingConfig).filter_by(bank_account_id=account_id))
            .scalars()
            .all()
            == []
        )


def test_usuario_solo_consulta_no_ve_edicion_y_no_guarda(numeracion_csrf):
    """La UI y el endpoint de numeración requieren permiso de edición."""
    application, account_id = numeracion_csrf
    with application.app_context():
        module_id = database.session.execute(database.select(Modules.id).filter_by(module="cash")).scalar_one()
        role = Roles(name="cash-reader", note="Solo consulta caja")
        user = User(
            id="cash_reader",
            user="cash_reader",
            name="Consulta Caja",
            password=proteger_passwd(CONTRASENA),
            active=True,
            classification="user",
            company="cacao",
        )
        database.session.add_all([role, user])
        database.session.flush()
        database.session.add_all(
            [
                RolesAccess(rol_id=role.id, module_id=module_id, access=True, view=True, edit=False),
                RolesUser(user_id=user.id, role_id=role.id, active=True),
                UserCompanyAccess(user_id=user.id, company_code="cacao"),
            ]
        )
        database.session.commit()
        user_id = user.id
        auth_version = user.auth_version

    client = application.test_client()
    with client.session_transaction() as session:
        session["_user_id"] = user_id
        session["_auth_version"] = auth_version
        session["_fresh"] = True
    detail = client.get(f"/cash_management/bank-account/{account_id}")

    assert detail.status_code == 200
    html = detail.get_data(as_text=True)
    assert "Configuracion de Numeracion" in html
    assert "numberingConfig()" in html
    assert "Editar" not in html
    denied = client.post(
        f"/cash_management/bank-account/{account_id}/numbering-config",
        json={"configs": [{"payment_type": "pay", "use_external_counter": True}]},
        headers={"X-CSRFToken": _token(html)},
    )

    assert denied.status_code == 403
    with application.app_context():
        assert (
            database.session.execute(
                database.select(BankAccountNumberingConfig).filter_by(bank_account_id=account_id, payment_type="pay")
            ).scalar_one_or_none()
            is None
        )
