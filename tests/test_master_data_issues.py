# SPDX-License-Identifier: Apache-2.0

"""Regression tests for master data stabilization issues."""

from __future__ import annotations

from datetime import date
import re

import pytest

from cacao_accounting import create_app
from cacao_accounting.config import configuracion


def _checkbox_is_checked(html: str, field_name: str) -> bool:
    """Indica si un checkbox renderizado aparece marcado."""
    return re.search(rf'<input[^>]*(?:name="{field_name}"[^>]*checked|checked[^>]*name="{field_name}")', html) is not None


@pytest.fixture()
def app_ctx():
    app = create_app(
        {
            **configuracion,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
            "WTF_CSRF_ENABLED": False,
            "TESTING": True,
        }
    )
    with app.app_context():
        from cacao_accounting.database import Currency, Entity, Modules, User, database

        database.create_all()
        database.session.add_all(
            [
                Currency(code="NIO", name="Córdoba", decimals=2, active=True, default=True),
                Currency(code="USD", name="US Dollar", decimals=2, active=True, default=False),
                Entity(
                    code="cacao",
                    name="Cacao Accounting",
                    company_name="Cacao Accounting SA",
                    tax_id="J0001",
                    currency="NIO",
                    enabled=True,
                    status="default",
                ),
                Modules(module="accounting", default=True, enabled=True),
                User(
                    user="admin",
                    name="Admin",
                    classification="admin",
                    active=True,
                    **{"password": b"x"},
                ),
            ]
        )
        database.session.commit()
        yield app


def _login(client, user_id: str) -> None:
    with client.session_transaction() as session:
        session["_user_id"] = user_id
        session["_fresh"] = True


def test_entity_can_be_activated(app_ctx):
    from cacao_accounting.database import Entity, User, database

    company = Entity(code="ex2", name="EX2", company_name="EX2 SA", tax_id="J2002", currency="NIO", enabled=False)
    database.session.add(company)
    database.session.commit()

    client = app_ctx.test_client()
    _login(client, User.query.filter_by(user="admin").first().id)
    response = client.get(f"/accounting/entity/set_active/{company.id}", follow_redirects=False)
    assert response.status_code in (302, 303)
    database.session.refresh(company)
    assert company.enabled is True


def test_entity_can_be_deactivated(app_ctx):
    from cacao_accounting.database import Entity, User, database

    company = Entity(
        code="ex3",
        name="EX3",
        company_name="EX3 SA",
        tax_id="J2003",
        currency="NIO",
        enabled=True,
        status="activo",
    )
    database.session.add(company)
    database.session.commit()

    client = app_ctx.test_client()
    _login(client, User.query.filter_by(user="admin").first().id)
    response = client.get(f"/accounting/entity/set_inactive/{company.id}", follow_redirects=False)
    assert response.status_code in (302, 303)
    database.session.refresh(company)
    assert company.enabled is False


def test_existing_entities_default_to_active(app_ctx):
    from cacao_accounting.database import Entity, database

    company = Entity(code="dft1", name="Default", company_name="Default SA", tax_id="J2010", currency="NIO")
    database.session.add(company)
    database.session.commit()
    database.session.refresh(company)
    assert company.enabled is True
    assert company.is_active is True


def test_desktop_mode_requires_single_active_entity(app_ctx):
    from cacao_accounting.database import Entity, User

    app_ctx.config["MODO_ESCRITORIO"] = True
    only_company = Entity.query.filter_by(code="cacao").first()
    client = app_ctx.test_client()
    _login(client, User.query.filter_by(user="admin").first().id)
    response = client.get(f"/accounting/entity/set_inactive/{only_company.id}", follow_redirects=True)
    assert response.status_code == 200
    assert b"entidad activa" in response.data.lower()


def test_entity_search_select_returns_only_active_entities(app_ctx):
    from cacao_accounting.database import Entity, User, database

    database.session.add(
        Entity(
            code="ina1",
            name="INA1",
            company_name="Inactive SA",
            tax_id="J2101",
            currency="NIO",
            enabled=False,
        )
    )
    database.session.commit()
    client = app_ctx.test_client()
    _login(client, User.query.filter_by(user="admin").first().id)
    response = client.get("/api/search-select?doctype=company&q=&limit=20")
    assert response.status_code == 200
    payload = response.get_json()
    values = {item["value"] for item in payload["results"]}
    assert "cacao" in values
    assert "ina1" not in values


def test_entity_search_select_can_include_inactive_for_admin(app_ctx):
    from cacao_accounting.database import Entity, User, database

    database.session.add(
        Entity(
            code="ina2",
            name="INA2",
            company_name="Inactive2 SA",
            tax_id="J2102",
            currency="NIO",
            enabled=False,
        )
    )
    database.session.commit()
    client = app_ctx.test_client()
    _login(client, User.query.filter_by(user="admin").first().id)
    response = client.get("/api/search-select?doctype=company&q=&limit=20&include_inactive=true")
    assert response.status_code == 200
    payload = response.get_json()
    values = {item["value"] for item in payload["results"]}
    assert "ina2" in values


def test_entity_search_select_is_scoped_to_authorized_companies(app_ctx, monkeypatch):
    """La búsqueda de compañías no devuelve entidades fuera del alcance del usuario."""
    import sys

    from cacao_accounting.database import Entity, User, database

    database.session.add(
        Entity(
            code="other-company",
            name="Other",
            company_name="Other Company",
            tax_id="J2200",
            currency="NIO",
            enabled=True,
        )
    )
    non_admin = User(id="USER-NON-ADMIN", user="nonadmin", name="Non Admin", password=b"x", classification="user", active=True)
    database.session.add(non_admin)
    database.session.commit()

    monkeypatch.setattr(
        sys.modules["cacao_accounting.api.dashboard"],
        "user_can_access_company",
        lambda user, company: company.code == "cacao",
    )
    client = app_ctx.test_client()
    _login(client, non_admin.id)
    response = client.get("/api/search-select?doctype=company&q=&limit=20&include_inactive=true")

    assert response.status_code == 200
    values = {item["value"] for item in response.get_json()["results"]}
    assert "cacao" in values
    assert "other-company" not in values


def test_search_select_rejects_company_filter_outside_acl(app_ctx, monkeypatch):
    """Los doctypes con filtro company no permiten enumerar otra entidad."""
    import sys

    from cacao_accounting.database import Entity, User, database

    database.session.add(
        Entity(
            code="blocked-company",
            name="Blocked",
            company_name="Blocked Company",
            tax_id="J2201",
            currency="NIO",
            enabled=True,
        )
    )
    database.session.commit()
    monkeypatch.setattr(
        sys.modules["cacao_accounting.api.dashboard"],
        "user_can_access_company",
        lambda user, company: company.code == "cacao",
    )
    client = app_ctx.test_client()
    _login(client, User.query.filter_by(user="admin").first().id)

    response = client.get("/api/search-select?doctype=account&company=blocked-company&q=")

    assert response.status_code == 403


def test_backend_rejects_inactive_entity_submission(app_ctx):
    from cacao_accounting.database import Entity, User, database

    database.session.add(
        Entity(
            code="ina3",
            name="INA3",
            company_name="Inactive3 SA",
            tax_id="J2103",
            currency="NIO",
            enabled=False,
        )
    )
    database.session.commit()
    client = app_ctx.test_client()
    _login(client, User.query.filter_by(user="admin").first().id)
    response = client.post(
        "/accounting/account/new",
        data={
            "entidad": "ina3",
            "code": "1.90",
            "name": "Cuenta bloqueada",
            "clasificacion": "activo",
            "account_type": "asset",
        },
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert b"entidad indicada est" in response.data.lower()


def test_account_edit_form_prefills_all_fields(app_ctx):
    from cacao_accounting.database import Accounts, User, database

    database.session.add(Accounts(entity="cacao", code="1", name="Activo", active=True, enabled=True, group=True))
    database.session.add(
        Accounts(
            entity="cacao",
            code="1.01",
            name="Caja",
            active=True,
            enabled=True,
            group=False,
            parent="1",
            classification="activo",
        )
    )
    database.session.commit()
    client = app_ctx.test_client()
    _login(client, User.query.filter_by(user="admin").first().id)
    response = client.get("/accounting/account/cacao/1.01/edit")
    assert response.status_code == 200
    assert b'initialValue: "cacao"' in response.data
    assert b'initialLabel: "cacao - Cacao Accounting SA"' in response.data
    assert b'doctype: "account_id"' in response.data
    assert b'initialLabel: "1 - Activo"' in response.data


def test_cost_center_edit_prefills_name_status_parent_entity(app_ctx):
    from cacao_accounting.database import CostCenter, User, database

    database.session.add(CostCenter(entity="cacao", code="ADM", name="Admin", active=True, enabled=True, group=True))
    database.session.add(
        CostCenter(
            entity="cacao",
            code="ADM01",
            name="Admin 01",
            active=True,
            enabled=True,
            group=False,
            parent="ADM",
        )
    )
    database.session.commit()
    client = app_ctx.test_client()
    _login(client, User.query.filter_by(user="admin").first().id)
    response = client.get("/accounting/costs_center/ADM01/edit")
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert 'name="nombre"' in html and 'value="Admin 01"' in html
    assert _checkbox_is_checked(html, "activo")
    assert b'initialValue: "cacao"' in response.data
    assert b'initialLabel: "cacao - Cacao Accounting SA"' in response.data
    assert b'doctype: "cost_center_id"' in response.data
    assert b'initialLabel: "ADM - Admin"' in response.data


def test_account_parent_accepts_parent_id_and_rejects_cross_entity(app_ctx):
    from cacao_accounting.database import Accounts, Entity, User, database

    database.session.add(
        Entity(code="cafe", name="Cafe", company_name="Cafe SA", tax_id="J3001", currency="NIO", enabled=True, status="activo")
    )
    parent = Accounts(entity="cacao", code="1", name="Activo", active=True, enabled=True, group=True)
    database.session.add(parent)
    database.session.commit()
    client = app_ctx.test_client()
    _login(client, User.query.filter_by(user="admin").first().id)

    ok = client.post(
        "/accounting/account/new",
        data={
            "entidad": "cacao",
            "code": "1.01",
            "name": "Caja",
            "padre": str(parent.id),
            "clasificacion": "activo",
            "account_type": "asset",
        },
        follow_redirects=False,
    )
    assert ok.status_code in (302, 303)
    child = Accounts.query.filter_by(entity="cacao", code="1.01").one_or_none()
    assert child is not None
    assert child.parent == "1"

    rejected = client.post(
        "/accounting/account/new",
        data={
            "entidad": "cafe",
            "code": "1.01",
            "name": "Caja Cafe",
            "padre": str(parent.id),
            "clasificacion": "activo",
            "account_type": "asset",
        },
        follow_redirects=True,
    )
    assert rejected.status_code == 200
    assert b"cuenta padre indicada no existe para la entidad seleccionada" in rejected.data.lower()


def test_account_parent_cycle_is_rejected(app_ctx):
    from cacao_accounting.database import Accounts, User, database

    parent = Accounts(entity="cacao", code="1", name="Activo", active=True, enabled=True, group=True)
    child = Accounts(entity="cacao", code="1.01", name="Caja", active=True, enabled=True, group=True, parent="1")
    database.session.add_all([parent, child])
    database.session.commit()
    client = app_ctx.test_client()
    _login(client, User.query.filter_by(user="admin").first().id)

    response = client.post(
        "/accounting/account/cacao/1/edit",
        data={
            "entidad": "cacao",
            "code": "1",
            "name": "Activo",
            "padre": str(child.id),
            "clasificacion": "activo",
            "account_type": "asset",
            "grupo": "y",
            "activo": "y",
        },
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert b"genera un ciclo jerarquico" in response.data.lower()


def test_cost_center_parent_accepts_parent_id_and_rejects_cross_entity(app_ctx):
    from cacao_accounting.database import CostCenter, Entity, User, database

    database.session.add(
        Entity(code="cafe", name="Cafe", company_name="Cafe SA", tax_id="J3002", currency="NIO", enabled=True, status="activo")
    )
    parent = CostCenter(entity="cacao", code="ADM", name="Admin", active=True, enabled=True, group=True)
    database.session.add(parent)
    database.session.commit()
    client = app_ctx.test_client()
    _login(client, User.query.filter_by(user="admin").first().id)

    ok = client.post(
        "/accounting/costs_center/new",
        data={
            "entidad": "cacao",
            "id": "ADM01",
            "nombre": "Admin 01",
            "padre": str(parent.id),
        },
        follow_redirects=False,
    )
    assert ok.status_code in (302, 303)
    child = CostCenter.query.filter_by(entity="cacao", code="ADM01").one_or_none()
    assert child is not None
    assert child.parent == "ADM"

    rejected = client.post(
        "/accounting/costs_center/new",
        data={
            "entidad": "cafe",
            "id": "ADM01",
            "nombre": "Admin 01 Cafe",
            "padre": str(parent.id),
        },
        follow_redirects=True,
    )
    assert rejected.status_code == 200
    assert b"centro de costos padre indicado no existe para la entidad seleccionada" in rejected.data.lower()


def test_cost_center_parent_cycle_is_rejected(app_ctx):
    from cacao_accounting.database import CostCenter, User, database

    parent = CostCenter(entity="cacao", code="ADM", name="Admin", active=True, enabled=True, group=True)
    child = CostCenter(entity="cacao", code="ADM01", name="Admin 01", active=True, enabled=True, group=True, parent="ADM")
    database.session.add_all([parent, child])
    database.session.commit()
    client = app_ctx.test_client()
    _login(client, User.query.filter_by(user="admin").first().id)

    response = client.post(
        "/accounting/costs_center/ADM/edit",
        data={
            "entidad": "cacao",
            "id": "ADM",
            "nombre": "Admin",
            "padre": str(child.id),
            "grupo": "y",
            "activo": "y",
        },
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert b"genera un ciclo jerarquico" in response.data.lower()


def test_account_create_preserves_entity_and_parent_after_validation_error(app_ctx):
    from cacao_accounting.database import Accounts, User, database

    parent = Accounts(entity="cacao", code="1", name="Activo", active=True, enabled=True, group=False)
    database.session.add(parent)
    database.session.commit()
    client = app_ctx.test_client()
    _login(client, User.query.filter_by(user="admin").first().id)
    response = client.post(
        "/accounting/account/new",
        data={
            "entidad": "cacao",
            "code": "1.02",
            "name": "Banco",
            "padre": str(parent.id),
            "clasificacion": "activo",
            "account_type": "asset",
            "activo": "y",
        },
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert b"cuenta padre debe ser una cuenta de grupo" in response.data.lower()
    assert b'initialValue: "cacao"' in response.data
    assert b'initialLabel: "cacao - Cacao Accounting SA"' in response.data
    assert f'initialValue: "{parent.id}"'.encode() in response.data
    assert b'initialLabel: "1 - Activo"' in response.data


def test_cost_center_create_preserves_entity_and_parent_after_validation_error(app_ctx):
    from cacao_accounting.database import CostCenter, User, database

    parent = CostCenter(entity="cacao", code="ADM", name="Admin", active=True, enabled=True, group=False)
    database.session.add(parent)
    database.session.commit()
    client = app_ctx.test_client()
    _login(client, User.query.filter_by(user="admin").first().id)
    response = client.post(
        "/accounting/costs_center/new",
        data={
            "entidad": "cacao",
            "id": "ADM02",
            "nombre": "Admin 02",
            "padre": str(parent.id),
            "activo": "y",
        },
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert b"centro de costos padre debe ser un grupo" in response.data.lower()
    assert b'initialValue: "cacao"' in response.data
    assert b'initialLabel: "cacao - Cacao Accounting SA"' in response.data
    assert f'initialValue: "{parent.id}"'.encode() in response.data
    assert b'initialLabel: "ADM - Admin"' in response.data


def test_ledger_edit_prefills_name_currency_status(app_ctx):
    from cacao_accounting.database import Book, User, database

    database.session.add(Book(code="FISC", name="Fiscal", entity="cacao", currency="NIO", status="inactivo"))
    database.session.commit()
    client = app_ctx.test_client()
    _login(client, User.query.filter_by(user="admin").first().id)
    response = client.get("/accounting/book/edit/FISC")
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert 'name="nombre"' in html and 'value="Fiscal"' in html
    assert re.search(r'<option selected value="NIO">', html)
    assert re.search(r'<option selected value="inactivo">', html)
    assert b'initialValue: "cacao"' in response.data
    assert b'initialLabel: "cacao - Cacao Accounting SA"' in response.data


def test_project_edit_prefills_name_budget_dates_status(app_ctx):
    from cacao_accounting.database import Project, User, database

    database.session.add(
        Project(
            code="PRJ1",
            name="Proyecto 1",
            entity="cacao",
            start=date(2026, 1, 1),
            end=date(2026, 12, 31),
            budget=1000,
            budget_currency_code="NIO",
            enabled=False,
            status="closed",
        )
    )
    database.session.commit()
    client = app_ctx.test_client()
    _login(client, User.query.filter_by(user="admin").first().id)
    response = client.get("/accounting/project/PRJ1/edit")
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert 'name="nombre"' in html and 'value="Proyecto 1"' in html
    assert 'name="inicio"' in html and 'value="2026-01-01"' in html
    assert 'name="fin"' in html and 'value="2026-12-31"' in html
    assert re.search(r'<option selected value="closed">', html)
    assert b'initialValue: "cacao"' in response.data
    assert b'initialLabel: "cacao - Cacao Accounting SA"' in response.data
    assert b'budgetCurrency: "NIO"' in response.data


def test_accounting_period_edit_prefills_name_dates_status_fiscal_year(app_ctx):
    from cacao_accounting.database import AccountingPeriod, FiscalYear, User, database

    fiscal_year = FiscalYear(entity="cacao", name="FY26", year_start_date=date(2026, 1, 1), year_end_date=date(2026, 12, 31))
    database.session.add(fiscal_year)
    database.session.flush()
    period = AccountingPeriod(
        entity="cacao",
        fiscal_year_id=fiscal_year.id,
        name="Q1",
        status="Abierto",
        enabled=True,
        is_closed=True,
        start=date(2026, 1, 1),
        end=date(2026, 3, 31),
    )
    database.session.add(period)
    database.session.commit()
    client = app_ctx.test_client()
    _login(client, User.query.filter_by(user="admin").first().id)
    response = client.get(f"/accounting/accounting_period/{period.id}/edit")
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert 'name="nombre"' in html and 'value="Q1"' in html
    assert 'name="status"' not in html
    assert 'name="inicio"' in html and 'value="2026-01-01"' in html
    assert 'name="fin"' in html and 'value="2026-03-31"' in html
    assert re.search(rf'<option selected value="{fiscal_year.id}">', html)
    assert _checkbox_is_checked(html, "habilitado")
    assert _checkbox_is_checked(html, "cerrado")
    assert b'initialValue: "cacao"' in response.data
    assert b'initialLabel: "cacao - Cacao Accounting SA"' in response.data


def test_accounting_period_list_shows_operational_and_accounting_state(app_ctx):
    from cacao_accounting.database import AccountingPeriod, User, database

    database.session.add_all(
        [
            AccountingPeriod(
                entity="cacao",
                name="P-OPEN",
                status="habilitado_abierto",
                enabled=True,
                is_closed=False,
                start=date(2026, 1, 1),
                end=date(2026, 1, 31),
            ),
            AccountingPeriod(
                entity="cacao",
                name="P-CLOSED",
                status="deshabilitado_cerrado",
                enabled=False,
                is_closed=True,
                start=date(2026, 2, 1),
                end=date(2026, 2, 28),
            ),
        ]
    )
    database.session.commit()
    client = app_ctx.test_client()
    _login(client, User.query.filter_by(user="admin").first().id)
    response = client.get("/accounting/accounting_period")
    assert response.status_code == 200
    assert b"Estado operativo" in response.data
    assert b"Estado contable" in response.data
    assert b"Habilitado" in response.data
    assert b"Deshabilitado" in response.data
    assert b"Abierto" in response.data
    assert b"Cerrado" in response.data


def test_fiscal_year_edit_prefills_dates_closed_state(app_ctx):
    from cacao_accounting.database import FiscalYear, User, database

    fiscal_year = FiscalYear(
        entity="cacao",
        name="FY27",
        year_start_date=date(2027, 1, 1),
        year_end_date=date(2027, 12, 31),
        is_closed=True,
    )
    database.session.add(fiscal_year)
    database.session.commit()
    client = app_ctx.test_client()
    _login(client, User.query.filter_by(user="admin").first().id)
    response = client.get(f"/accounting/fiscal_year/{fiscal_year.id}/edit")
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert 'name="inicio"' in html and 'value="2027-01-01"' in html
    assert 'name="fin"' in html and 'value="2027-12-31"' in html
    assert _checkbox_is_checked(html, "cerrado")
    assert b'initialValue: "cacao"' in response.data
    assert b'initialLabel: "cacao - Cacao Accounting SA"' in response.data


def test_unit_detail_shows_edit_action(app_ctx):
    from cacao_accounting.database import Unit, User, database

    database.session.add(Unit(code="U1", name="Unidad", entity="cacao", enabled=True))
    database.session.commit()
    client = app_ctx.test_client()
    _login(client, User.query.filter_by(user="admin").first().id)
    response = client.get("/accounting/unit/U1")
    assert response.status_code == 200
    assert b"/accounting/unit/U1/edit" in response.data


def test_currency_detail_shows_edit_action(app_ctx):
    from cacao_accounting.database import User

    client = app_ctx.test_client()
    _login(client, User.query.filter_by(user="admin").first().id)
    response = client.get("/accounting/currency/NIO")
    assert response.status_code == 200
    assert b"/accounting/currency/NIO/edit" in response.data


def test_currency_edit_rejects_default_currency_deactivation(app_ctx):
    from cacao_accounting.database import Currency, User

    client = app_ctx.test_client()
    _login(client, User.query.filter_by(user="admin").first().id)
    response = client.post(
        "/accounting/currency/NIO/edit",
        data={"code": "NIO", "name": "Córdoba", "decimals": 2, "default": "y"},
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert b"moneda predeterminada del sistema" in response.data.lower()
    currency = Currency.query.filter_by(code="NIO").first()
    assert currency is not None
    assert currency.active is True
    assert currency.default is True


def test_currency_edit_rejects_company_currency_deactivation(app_ctx):
    from cacao_accounting.database import Currency, Entity, User, database

    database.session.add(
        Entity(
            code="usdco",
            name="USD Co",
            company_name="USD Co SA",
            tax_id="J2201",
            currency="USD",
            enabled=True,
            status="activo",
        )
    )
    database.session.commit()
    client = app_ctx.test_client()
    _login(client, User.query.filter_by(user="admin").first().id)
    response = client.post(
        "/accounting/currency/USD/edit",
        data={"code": "USD", "name": "US Dollar", "decimals": 2},
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert b"compania activa" in response.data.lower()
    currency = Currency.query.filter_by(code="USD").first()
    assert currency is not None
    assert currency.active is True


def test_currency_edit_rejects_active_ledger_currency_deactivation(app_ctx):
    from cacao_accounting.database import Book, Currency, User, database

    database.session.add(Book(code="USDL", name="Libro USD", entity="cacao", currency="USD", status="activo"))
    database.session.commit()
    client = app_ctx.test_client()
    _login(client, User.query.filter_by(user="admin").first().id)
    response = client.post(
        "/accounting/currency/USD/edit",
        data={"code": "USD", "name": "US Dollar", "decimals": 2},
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert b"libro contable activo" in response.data.lower()
    currency = Currency.query.filter_by(code="USD").first()
    assert currency is not None
    assert currency.active is True


def test_currency_edit_preserves_single_default_currency(app_ctx):
    from cacao_accounting.database import Currency, User

    client = app_ctx.test_client()
    _login(client, User.query.filter_by(user="admin").first().id)
    response = client.post(
        "/accounting/currency/USD/edit",
        data={"code": "USD", "name": "US Dollar", "decimals": 2, "active": "y", "default": "y"},
        follow_redirects=False,
    )
    assert response.status_code in (302, 303)
    nio = Currency.query.filter_by(code="NIO").first()
    usd = Currency.query.filter_by(code="USD").first()
    assert nio is not None and usd is not None
    assert nio.default is False
    assert usd.default is True
    assert usd.active is True


def test_unit_edit_prefills_entity(app_ctx):
    from cacao_accounting.database import Unit, User, database

    database.session.add(Unit(code="U1", name="Unidad", entity="cacao", enabled=True))
    database.session.commit()
    client = app_ctx.test_client()
    _login(client, User.query.filter_by(user="admin").first().id)
    response = client.get("/accounting/unit/U1/edit")
    assert response.status_code == 200
    assert b'initialValue: "cacao"' in response.data
    assert b'initialLabel: "cacao - Cacao Accounting SA"' in response.data


def test_search_select_active_only_does_not_raise_for_book(app_ctx):
    from cacao_accounting.database import Book, User, database

    database.session.add_all(
        [
            Book(code="ACT", name="Activo", entity="cacao", currency="NIO", status="activo"),
            Book(code="INA", name="Inactivo", entity="cacao", currency="NIO", status="inactivo"),
            Book(code="LEG", name="Legacy", entity="cacao", currency="NIO", status=None),
        ]
    )
    database.session.commit()
    client = app_ctx.test_client()
    _login(client, User.query.filter_by(user="admin").first().id)
    response = client.get("/api/search-select?doctype=book&q=&limit=20")
    assert response.status_code == 200
    payload = response.get_json()
    values = {item["value"] for item in payload["results"]}
    assert {"ACT", "LEG"} <= values
    assert "INA" not in values


def test_search_select_active_only_does_not_raise_for_unit(app_ctx):
    from cacao_accounting.database import Unit, User, database

    database.session.add_all(
        [
            Unit(code="UA", name="Unidad Activa", entity="cacao", enabled=True),
            Unit(code="UI", name="Unidad Inactiva", entity="cacao", enabled=False),
            Unit(code="UL", name="Unidad Legacy", entity="cacao", enabled=None),
        ]
    )
    database.session.commit()
    client = app_ctx.test_client()
    _login(client, User.query.filter_by(user="admin").first().id)
    response = client.get("/api/search-select?doctype=unit&q=&limit=20")
    assert response.status_code == 200
    payload = response.get_json()
    values = {item["value"] for item in payload["results"]}
    assert {"UA", "UL"} <= values
    assert "UI" not in values


def test_exchange_rate_detail_shows_edit_action(app_ctx):
    from cacao_accounting.database import ExchangeRate, User, database

    rate = ExchangeRate(origin="NIO", destination="USD", rate=0.0277, date=date(2026, 1, 10))
    database.session.add(rate)
    database.session.commit()
    client = app_ctx.test_client()
    _login(client, User.query.filter_by(user="admin").first().id)
    response = client.get(f"/accounting/exchange/{rate.id}")
    assert response.status_code == 200
    assert f"/accounting/exchange/{rate.id}/edit".encode() in response.data


@pytest.mark.parametrize(
    ("path", "create_label", "expect_actions"),
    [
        ("/accounting/entity/list", "Nueva Entidad", True),
        ("/accounting/accounts", "Nueva Cuenta", False),
        ("/accounting/costs_center", "Nuevo Centro", False),
        ("/accounting/unit/list", "Nueva Unidad", False),
        ("/accounting/book/list", "Nuevo Libro", True),
        ("/accounting/project/list", "Nuevo Proyecto", False),
        ("/accounting/currency/list", "Nueva Moneda", True),
        ("/accounting/exchange", "Nueva Tasa de Cambio", True),
        ("/accounting/accounting_period", "Nuevo Período", True),
        ("/accounting/fiscal_year/list", "Nuevo Año Fiscal", True),
    ],
)
def test_master_lists_render_expected_controls(app_ctx, path, create_label, expect_actions):
    from cacao_accounting.database import User

    client = app_ctx.test_client()
    _login(client, User.query.filter_by(user="admin").first().id)
    response = client.get(path)
    assert response.status_code == 200
    assert create_label.encode() in response.data
    assert b"breadcrumb" in response.data
    if expect_actions:
        assert b"Acciones" in response.data


@pytest.mark.parametrize(
    "path",
    [
        "/accounting/entity/list",
        "/accounting/currency/NIO",
        "/accounting/unit/list",
    ],
)
def test_accounting_templates_define_title(app_ctx, path):
    from cacao_accounting.database import User

    client = app_ctx.test_client()
    _login(client, User.query.filter_by(user="admin").first().id)
    response = client.get(path)
    assert response.status_code == 200
    assert b"<title>Contabilidad |" in response.data


def test_block_deletion_of_master_with_transactional_history(app_ctx):
    from cacao_accounting.database import Item, Warehouse, Party, StockLedgerEntry, GLEntry, database
    from cacao_accounting.exceptions import IntegrityError

    # 1. Create records
    item = Item(
        code="ART-RESERVE",
        name="Articulo Reserva",
        item_type="goods",
        is_stock_item=True,
        default_uom="unidad",
    )
    warehouse = Warehouse(
        code="WH-RESERVE",
        name="Bodega Reserva",
        company="cacao",
    )
    party = Party(
        code="PARTY-RESERVE",
        name="Tercero Reserva",
        is_active=True,
    )
    database.session.add_all([item, warehouse, party])
    database.session.commit()

    # First, let's simulate a transactional record for Item and Warehouse.
    sle = StockLedgerEntry(
        item_code="ART-RESERVE",
        warehouse="WH-RESERVE",
        company="cacao",
        qty_change=10,
        posting_date=date(2026, 1, 1),
        voucher_type="Stock Entry",
        voucher_id="some-id",
    )
    database.session.add(sle)
    database.session.commit()

    # Now trying to delete item should raise IntegrityError
    with pytest.raises(IntegrityError) as exc:
        database.session.delete(item)
        database.session.commit()
    assert "transacciones activas" in str(exc.value)
    database.session.rollback()

    # Trying to delete warehouse should raise IntegrityError
    with pytest.raises(IntegrityError) as exc:
        database.session.delete(warehouse)
        database.session.commit()
    assert "transacciones activas" in str(exc.value)
    database.session.rollback()

    # Now let's simulate transactional history for party
    gle = GLEntry(
        posting_date=date(2026, 1, 1),
        company="cacao",
        debit=100,
        credit=0,
        party_type="customer",
        party_id=party.id,
        voucher_type="Sales Invoice",
        voucher_id="some-id-2",
    )
    database.session.add(gle)
    database.session.commit()

    # Trying to delete party should raise IntegrityError
    with pytest.raises(IntegrityError) as exc:
        database.session.delete(party)
        database.session.commit()
    assert "transacciones activas" in str(exc.value)
    database.session.rollback()

    # Verify that clean master records (no transactions) can be deleted
    clean_item = Item(
        code="CLEAN-ITEM",
        name="Articulo Limpio",
        item_type="goods",
        is_stock_item=True,
        default_uom="unidad",
    )
    database.session.add(clean_item)
    database.session.commit()
    database.session.delete(clean_item)
    database.session.commit()
    assert Item.query.filter_by(code="CLEAN-ITEM").first() is None
