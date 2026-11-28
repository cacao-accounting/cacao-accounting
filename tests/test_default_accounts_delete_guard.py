# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 William José Moreno Reyes

"""#2062: el borrado de cuentas predeterminadas no produce 500.

`CompanyDefaultAccount` es un modelo sensible; el guard ORM rechaza su borrado.
La ruta debe presentar ese rechazo como error controlado y conservar la
configuración, en lugar de terminar en HTTP 500.
"""

from __future__ import annotations

import json

import pytest

from cacao_accounting import create_app
from cacao_accounting.config import configuracion
from cacao_accounting.database import (
    Accounts,
    AuditTrail,
    CompanyDefaultAccount,
    Currency,
    Entity,
    Modules,
    Roles,
    RolesUser,
    User,
    UserCompanyAccess,
    database,
)


@pytest.fixture(params=[True, False], ids=["desktop", "cloud"])
def default_accounts_scenario(request):
    """Admin con acceso y una configuración de cuentas por defecto."""
    app = create_app(
        {
            **configuracion,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
            "WTF_CSRF_ENABLED": False,
            "TESTING": True,
            "MODO_ESCRITORIO": request.param,
            "INTERNAL_CONTROLS_ENFORCE": True,
        }
    )
    with app.app_context():
        database.create_all()
        database.session.add_all(
            [
                Modules(module="admin", default=False, enabled=True),
                Currency(code="NIO", name="Córdoba", decimals=2, active=True, default=True),
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
                    name="Admin",
                    password=b"x",
                    classification="admin",
                    active=True,
                    company="cacao",
                ),
            ]
        )
        database.session.flush()
        database.session.add(UserCompanyAccess(user_id="admin", company_code="cacao"))
        rol = Roles(name="admin", note="admin")
        database.session.add(rol)
        database.session.flush()
        database.session.add(RolesUser(user_id="admin", role_id=rol.id, active=True))
        database.session.add(CompanyDefaultAccount(company="cacao", default_cash=None))
        database.session.commit()
    yield app
    with app.app_context():
        database.session.remove()
        database.engine.dispose()


def _client(application):
    client = application.test_client()
    with application.app_context():
        version = database.session.get(User, "admin").auth_version
    with client.session_transaction() as session:
        session["_user_id"] = "admin"
        session["_auth_version"] = version
        session["_fresh"] = True
    return client


def test_delete_de_cuentas_predeterminadas_se_rechaza(default_accounts_scenario):
    """Una solicitud antigua no puede eliminar la configuración protegida."""
    application = default_accounts_scenario
    response = _client(application).post(
        "/settings/default-accounts",
        data={"action": "delete", "company": "cacao"},
        follow_redirects=False,
    )

    assert response.status_code == 400
    with application.app_context():
        config = database.session.execute(
            database.select(CompanyDefaultAccount).filter_by(company="cacao")
        ).scalar_one_or_none()
        assert config is not None


def test_se_puede_actualizar_pero_no_se_ofrece_eliminar(default_accounts_scenario):
    """La interfaz permite guardar y el endpoint conserva la fila existente."""
    application = default_accounts_scenario
    client = _client(application)
    response = client.get("/settings/default-accounts?company=cacao")
    assert response.status_code == 200
    assert b'value="delete"' not in response.data
    response = client.post(
        "/settings/default-accounts", data={"action": "save", "company": "cacao", "apply_advances_automatically": "on"}
    )
    assert response.status_code == 302
    with application.app_context():
        config = database.session.execute(database.select(CompanyDefaultAccount).filter_by(company="cacao")).scalar_one()
        assert config.apply_advances_automatically is True


def test_asignacion_y_limpieza_registran_auditoria(default_accounts_scenario):
    """Setting and clearing a cash account each produce one auditable change."""
    application = default_accounts_scenario
    with application.app_context():
        account = Accounts(entity="cacao", code="CAJA", name="Caja", account_type="cash", active=True, enabled=True)
        database.session.add(account)
        database.session.commit()
        account_id = account.id
        config = database.session.execute(database.select(CompanyDefaultAccount).filter_by(company="cacao")).scalar_one()
        config_id = config.id
        existing = (
            database.session.execute(
                database.select(AuditTrail.id).filter_by(document_type="company_default_account", document_id=config_id)
            )
            .scalars()
            .all()
        )

    client = _client(application)
    for account_value in (account_id, ""):
        response = client.post(
            "/settings/default-accounts", data={"action": "save", "company": "cacao", "default_cash": account_value}
        )
        assert response.status_code == 302

    with application.app_context():
        config = database.session.get(CompanyDefaultAccount, config_id)
        assert config is not None and config.default_cash is None
        entries = (
            database.session.execute(
                database.select(AuditTrail)
                .filter_by(document_type="company_default_account", document_id=config_id, action="updated")
                .order_by(AuditTrail.timestamp, AuditTrail.id)
            )
            .scalars()
            .all()
        )
        changes = [json.loads(entry.changes_json) for entry in entries if entry.id not in existing]
        assert len(changes) == 2
        assert {str(change["default_cash"]["after"]) for change in changes} == {str(account_id), "None"}
        assert all(entry.company == "cacao" and entry.actor_user_id == "admin" for entry in entries)


def test_cuenta_invalida_no_cambia_ni_audita(default_accounts_scenario):
    """A failed account validation preserves the whole configuration."""
    application = default_accounts_scenario
    with application.app_context():
        config = database.session.execute(database.select(CompanyDefaultAccount).filter_by(company="cacao")).scalar_one()
        config_id = config.id
        count_before = database.session.query(AuditTrail).filter_by(document_type="company_default_account").count()
    response = _client(application).post(
        "/settings/default-accounts", data={"action": "save", "company": "cacao", "default_cash": "inexistente"}
    )
    assert response.status_code == 302
    with application.app_context():
        assert database.session.get(CompanyDefaultAccount, config_id).default_cash is None
        assert database.session.query(AuditTrail).filter_by(document_type="company_default_account").count() == count_before


@pytest.mark.parametrize("invalid_state", ["inactive", "disabled", "group"])
def test_cuenta_no_operativa_rechaza_cambios_sin_auditoria(default_accounts_scenario, invalid_state):
    """An unusable posting account cannot replace the current default account."""
    application = default_accounts_scenario
    with application.app_context():
        valid = Accounts(entity="cacao", code="VALID", name="Caja válida", account_type="cash", active=True, enabled=True)
        invalid = Accounts(
            entity="cacao",
            code="INVALID",
            name="Caja no operativa",
            account_type="cash",
            active=invalid_state != "inactive",
            enabled=invalid_state != "disabled",
            group=invalid_state == "group",
        )
        database.session.add_all([valid, invalid])
        database.session.flush()
        config = database.session.execute(database.select(CompanyDefaultAccount).filter_by(company="cacao")).scalar_one()
        config.default_cash = valid.id
        database.session.commit()
        config_id, valid_id, invalid_id = config.id, valid.id, invalid.id
        count_before = database.session.query(AuditTrail).filter_by(document_type="company_default_account").count()

    response = _client(application).post(
        "/settings/default-accounts",
        data={"action": "save", "company": "cacao", "default_cash": invalid_id, "apply_advances_automatically": "on"},
    )
    assert response.status_code == 302
    with application.app_context():
        config = database.session.get(CompanyDefaultAccount, config_id)
        assert config.default_cash == valid_id
        assert not config.apply_advances_automatically
        assert database.session.query(AuditTrail).filter_by(document_type="company_default_account").count() == count_before
