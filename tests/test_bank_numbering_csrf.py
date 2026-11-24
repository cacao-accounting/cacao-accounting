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
from datetime import date
from types import SimpleNamespace
from uuid import uuid4

import pytest
from sqlalchemy.exc import IntegrityError

from cacao_accounting import create_app
from cacao_accounting.auth import proteger_passwd
from cacao_accounting.bancos import routes as bank_routes
from cacao_accounting.bancos.services import _resolve_bank_account_numbering_config
from cacao_accounting.config import configuracion
from cacao_accounting.database import (
    AccountingPeriod,
    Bank,
    BankAccount,
    BankAccountNumberingConfig,
    Currency,
    Entity,
    FiscalYear,
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
from cacao_accounting.document_identifiers import IdentifierConfigurationError, assign_document_identifier

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


@pytest.mark.parametrize("reference", ["series", "counter"])
def test_configuracion_rechaza_tipo_incompatible_sin_guardado_parcial(numeracion_csrf, reference):
    """Una serie de otro doctype o un contador no-chequera se rechaza completo."""
    application, account_id = numeracion_csrf
    with application.app_context():
        if reference == "series":
            item = NamingSeries(
                name="Serie de ventas",
                entity_type="sales_invoice",
                company="cacao",
                prefix_template="INV-*YYYY*-",
                is_active=True,
            )
        else:
            item = ExternalCounter(
                company="cacao",
                name="Contador no chequera",
                counter_type="other",
                is_active=True,
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


def test_referencias_desactivadas_tras_guardar_no_se_usan(numeracion_csrf):
    """Guardar una configuración válida no la valida si luego se desactivan sus referencias."""
    application, account_id = numeracion_csrf
    with application.app_context():
        sufijo = uuid4().hex[:6]
        serie = NamingSeries(
            name=f"Serie pagos {sufijo}",
            entity_type="bank_payment",
            company="cacao",
            prefix_template="PAG-*YYYY*-",
            is_active=True,
        )
        chequera = ExternalCounter(
            company="cacao",
            name=f"Chequera {sufijo}",
            counter_type="checkbook",
            is_active=True,
        )
        database.session.add_all(
            [
                serie,
                chequera,
                FiscalYear(
                    id=f"FY{sufijo}",
                    entity="cacao",
                    name=f"2026 {sufijo}",
                    year_start_date=date(2026, 1, 1),
                    year_end_date=date(2026, 12, 31),
                    is_closed=False,
                ),
            ]
        )
        database.session.flush()
        database.session.add(
            AccountingPeriod(
                id=f"P{sufijo}",
                entity="cacao",
                fiscal_year_id=f"FY{sufijo}",
                name=f"Mayo {sufijo}",
                start=date(2026, 5, 1),
                end=date(2026, 5, 31),
                enabled=True,
                is_closed=False,
            )
        )
        database.session.commit()
        serie_id = serie.id
        chequera_id = chequera.id

    client = application.test_client()
    _login(client)
    detail = client.get(f"/cash_management/bank-account/{account_id}")
    valido = client.post(
        f"/cash_management/bank-account/{account_id}/numbering-config",
        json={
            "configs": [
                {
                    "payment_type": "pay",
                    "naming_series_id": serie_id,
                    "use_external_counter": True,
                    "external_counter_id": chequera_id,
                }
            ]
        },
        headers={"X-CSRFToken": _token(detail.get_data(as_text=True))},
    )
    assert valido.status_code == 200, valido.get_json()

    with application.app_context():
        database.session.get(NamingSeries, serie_id).is_active = False
        database.session.get(ExternalCounter, chequera_id).is_active = False
        database.session.commit()

        config = _resolve_bank_account_numbering_config(account_id, "pay")
        assert config is not None
        documento = SimpleNamespace(id="pago-1982", company="cacao", document_no=None, posting_date=None)
        with pytest.raises(IdentifierConfigurationError, match="inactiva"):
            assign_document_identifier(
                document=documento,
                entity_type="bank_payment",
                posting_date_raw=date(2026, 5, 15),
                naming_series_id=config.naming_series_id,
                external_counter_id=config.external_counter_id,
            )
        assert documento.document_no is None


def test_conflicto_de_configuracion_devuelve_409(monkeypatch, numeracion_csrf):
    """Un IntegrityError concurrente se traduce a conflicto controlado."""
    application, account_id = numeracion_csrf
    client = application.test_client()
    _login(client)
    detail = client.get(f"/cash_management/bank-account/{account_id}")
    token = _token(detail.get_data(as_text=True))

    def _conflicto(_bank_account):
        raise IntegrityError("insert", {}, Exception("unique"))

    monkeypatch.setattr(bank_routes, "_save_numbering_configs", _conflicto)
    response = client.post(
        f"/cash_management/bank-account/{account_id}/numbering-config",
        json={"configs": [{"payment_type": "pay", "use_external_counter": False}]},
        headers={"X-CSRFToken": token},
    )

    assert response.status_code == 409
    assert response.get_json()["status"] == "error"
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
