# SPDX-License-Identifier: Apache-2.0
"""Pruebas del dashboard ejecutivo."""

from datetime import date
from decimal import Decimal

import pytest
from argon2 import PasswordHasher

from cacao_accounting import create_app
from cacao_accounting.database import (
    Accounts,
    AccountingPeriod,
    Bank,
    BankAccount,
    BankTransaction,
    CompanyParty,
    Currency,
    Entity,
    GLEntry,
    Item,
    Modules,
    Party,
    PurchaseInvoice,
    PurchaseOrder,
    Roles,
    RolesAccess,
    RolesUser,
    SalesInvoice,
    SalesOrder,
    StockBin,
    StockLedgerEntry,
    UOM,
    User,
    Warehouse,
    database,
)
from cacao_accounting.modulos import (
    MODULE_ACCOUNTING,
    MODULE_BANKS,
    MODULE_INVENTORY,
    MODULE_PURCHASES,
    MODULE_SALES,
)

ph = PasswordHasher()


@pytest.fixture()
def app():
    """Crea una app aislada con datos mínimos del dashboard."""
    flask_app = create_app(
        {
            "TESTING": True,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "WTF_CSRF_ENABLED": False,
            "SECRET_KEY": "dashboard-tests",
        }
    )
    with flask_app.app_context():
        database.create_all()
        _seed_dashboard_data()
    yield flask_app


@pytest.fixture()
def client(app):
    """Cliente de pruebas Flask."""
    return app.test_client()


def test_dashboard_requires_login(client):
    """Sin sesión el endpoint no expone datos."""
    response = client.get("/api/dashboard/data?company=COMP-ID")
    assert response.status_code in {302, 401}


def test_dashboard_validates_company_parameter(client):
    """La compañía es obligatoria."""
    _login(client, "admin")
    response = client.get("/api/dashboard/data")
    assert response.status_code == 400


def test_dashboard_returns_404_for_missing_company(client):
    """Una compañía inexistente no devuelve payload parcial."""
    _login(client, "admin")
    response = client.get("/api/dashboard/data?company=missing")
    assert response.status_code == 404


def test_dashboard_returns_403_for_disabled_company(client):
    """El helper temporal bloquea compañías deshabilitadas."""
    _login(client, "admin")
    response = client.get("/api/dashboard/data?company=COMP-DISABLED-ID")
    assert response.status_code == 403


def test_dashboard_denies_inactive_user_even_with_module_access(app):
    """El aislamiento por compañía no se puede eludir con una sesión inactiva."""
    from cacao_accounting.api.dashboard import user_can_access_company

    with app.app_context():
        user = database.session.get(User, "USER-ACC")
        company = database.session.get(Entity, "COMP-ID")
        assert user is not None
        assert company is not None
        user.active = False
        database.session.flush()

        assert user_can_access_company(user, company) is False


def test_dashboard_validates_period_belongs_to_company(client):
    """El periodo debe pertenecer a la compañía seleccionada."""
    _login(client, "admin")
    response = client.get("/api/dashboard/data?company=COMP-ID&period=PER-OTHER")
    assert response.status_code == 404


def test_dashboard_returns_uniform_sections_and_metrics(client):
    """El happy path devuelve contrato uniforme y métricas ampliadas."""
    _login(client, "admin")
    response = client.get("/api/dashboard/data?company=COMP-ID&period=PER-COMP")

    assert response.status_code == 200
    data = response.get_json()
    assert set(data["sections"]) == {"accounting", "banks", "purchases", "inventory", "sales"}
    assert data["company"]["code"] == "COMP"
    assert data["period"]["id"] == "PER-COMP"

    accounting = data["sections"]["accounting"]
    assert accounting["visible"] is True
    assert accounting["kpis"]["income"]["value"] == 300.0
    assert accounting["kpis"]["expenses"]["value"] == 80.0
    assert accounting["kpis"]["profit"]["value"] == 220.0
    assert accounting["tables"]["summary"][3]["label"] == "Asientos del periodo"

    banks = data["sections"]["banks"]
    assert banks["kpis"]["accounts"]["value"] == 1
    assert banks["kpis"]["unreconciled"]["value"] == 1
    assert banks["tables"]["account_balances"][0]["balance"] == 1000.0

    purchases = data["sections"]["purchases"]
    assert purchases["kpis"]["total"]["value"] == 500.0
    assert purchases["kpis"]["outstanding"]["value"] == 150.0
    assert purchases["kpis"]["open_orders"]["value"] == 1
    assert purchases["kpis"]["suppliers"]["value"] == 1

    inventory = data["sections"]["inventory"]
    assert "lowest_stock_items" in inventory["tables"]
    assert "low_stock_items" not in inventory["tables"]
    assert inventory["tables"]["lowest_stock_items"][0]["item_code"] == "ITEM-LOW"
    assert inventory["kpis"]["value"]["value"] == 125.0

    sales = data["sections"]["sales"]
    assert sales["kpis"]["sales"]["value"] == 900.0
    assert sales["kpis"]["receivables"]["value"] == 350.0
    assert sales["kpis"]["customers"]["value"] == 1
    assert sales["tables"]["top_customers"][0]["name"] == "Cliente Demo"


def test_dashboard_hides_sales_without_permission(client):
    """Sin permiso de ventas no se devuelven datos sensibles de ventas."""
    _login(client, "accountant")
    response = client.get("/api/dashboard/data?company=COMP-ID&period=PER-COMP")

    assert response.status_code == 200
    sales = response.get_json()["sections"]["sales"]
    assert sales["visible"] is False
    assert sales["kpis"] == {}
    assert sales["tables"] == {}


def test_dashboard_hides_banks_without_permission(client):
    """Sin permiso de bancos no se devuelven saldos bancarios."""
    _login(client, "seller")
    response = client.get("/api/dashboard/data?company=COMP-ID&period=PER-COMP")

    assert response.status_code == 200
    banks = response.get_json()["sections"]["banks"]
    assert banks["visible"] is False
    assert banks["kpis"] == {}
    assert banks["tables"] == {}


def test_dashboard_handles_empty_company_data(client):
    """Las secciones visibles conservan estructura aunque no haya datos."""
    _login(client, "admin")
    response = client.get("/api/dashboard/data?company=EMPTY-ID&period=PER-EMPTY")

    assert response.status_code == 200
    sections = response.get_json()["sections"]
    assert sections["banks"]["tables"]["account_balances"] == []
    assert sections["sales"]["tables"]["top_customers"] == []
    assert sections["inventory"]["tables"]["lowest_stock_items"] == []


def test_app_renders_dashboard_shell(client):
    """La pantalla principal renderiza el dashboard y sus clases base."""
    _login(client, "admin")
    response = client.get("/app")

    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert "dashboard-section" in html
    assert "dashboard-section__badge" in html
    assert "dashboard-kpi-grid" in html
    assert "dashboard-actions" in html
    assert "dashboard-section--${sectionKey}" in html
    assert "dashboard-section:nth-child" not in html


def _seed_dashboard_data() -> None:
    """Inserta datos mínimos para métricas y permisos del dashboard."""
    _seed_modules()
    _seed_roles_and_users()
    _seed_companies_and_periods()
    _seed_master_data()
    _seed_financial_activity()
    database.session.commit()


def _seed_modules() -> None:
    """Crea módulos estándar usados por permisos."""
    for module_name in [MODULE_ACCOUNTING, MODULE_BANKS, MODULE_PURCHASES, MODULE_INVENTORY, MODULE_SALES]:
        database.session.add(Modules(id=module_name, module=module_name, default=True, enabled=True))


def _seed_roles_and_users() -> None:
    """Crea usuarios de prueba con permisos diferenciados."""
    users = [
        User(id="USER-ADMIN", user="admin", password=ph.hash("password").encode(), active=True, classification="admin"),
        User(id="USER-ACC", user="accountant", password=ph.hash("password").encode(), active=True),
        User(id="USER-SALES", user="seller", password=ph.hash("password").encode(), active=True),
    ]
    database.session.add_all(users)
    database.session.add(Roles(id="ROLE-ACC", name="accountant", note="Dashboard accountant"))
    database.session.add(Roles(id="ROLE-SALES", name="seller", note="Dashboard seller"))
    database.session.add(RolesUser(user_id="USER-ACC", role_id="ROLE-ACC", active=True))
    database.session.add(RolesUser(user_id="USER-SALES", role_id="ROLE-SALES", active=True))
    for module_name in [MODULE_ACCOUNTING, MODULE_BANKS, MODULE_PURCHASES, MODULE_INVENTORY]:
        database.session.add(_role_access("ROLE-ACC", module_name))
    for module_name in [MODULE_ACCOUNTING, MODULE_PURCHASES, MODULE_INVENTORY, MODULE_SALES]:
        database.session.add(_role_access("ROLE-SALES", module_name))


def _role_access(role_id: str, module_name: str) -> RolesAccess:
    """Crea permiso de consulta para un módulo."""
    return RolesAccess(
        rol_id=role_id,
        module_id=module_name,
        access=True,
        view=True,
        report=True,
    )


def _seed_companies_and_periods() -> None:
    """Crea compañías y periodos por compañía."""
    database.session.add(Currency(id="CUR-USD", code="USD", name="US Dollar", decimals=2, active=True))
    database.session.add(
        Entity(
            id="COMP-ID",
            code="COMP",
            name="Company",
            company_name="Company LLC",
            currency="USD",
            tax_id="TAX-COMP",
            enabled=True,
        )
    )
    database.session.add(
        Entity(
            id="EMPTY-ID",
            code="EMPTY",
            name="Empty Company",
            company_name="Empty Company LLC",
            currency="USD",
            tax_id="TAX-EMPTY",
            enabled=True,
        )
    )
    database.session.add(
        Entity(
            id="COMP-DISABLED-ID",
            code="LOCK",
            name="Locked Company",
            company_name="Locked Company LLC",
            currency="USD",
            tax_id="TAX-LOCK",
            enabled=False,
        )
    )
    database.session.add(
        AccountingPeriod(
            id="PER-COMP",
            entity="COMP",
            name="2024-01",
            start=date(2024, 1, 1),
            end=date(2024, 1, 31),
            status="Abierto",
        )
    )
    database.session.add(
        AccountingPeriod(
            id="PER-EMPTY",
            entity="EMPTY",
            name="2024-01",
            start=date(2024, 1, 1),
            end=date(2024, 1, 31),
            status="Abierto",
        )
    )
    database.session.add(
        AccountingPeriod(
            id="PER-OTHER",
            entity="OTHER",
            name="2024-02",
            start=date(2024, 2, 1),
            end=date(2024, 2, 29),
            status="Abierto",
        )
    )


def _seed_master_data() -> None:
    """Crea catálogos requeridos por bancos, inventario y terceros."""
    database.session.add(UOM(id="UOM-EA", code="EA", name="Each", is_active=True))
    database.session.add(Bank(id="BANK-1", name="Banco Demo", is_active=True))
    database.session.add(
        Item(id="ITEM-LOW-ID", code="ITEM-LOW", name="Item Bajo", item_type="goods", is_stock_item=True, default_uom="EA")
    )
    database.session.add(Warehouse(id="WH-1", code="WH-1", name="Bodega Principal", company="COMP", is_active=True))
    customer = Party(id="CUST-1", code="CUST-1", is_customer=True, name="Cliente Demo", is_active=True)
    supplier = Party(id="SUP-1", code="SUP-1", is_supplier=True, name="Proveedor Demo", is_active=True)
    database.session.add_all([customer, supplier])
    database.session.add(CompanyParty(company="COMP", party_id="CUST-1", is_active=True))
    database.session.add(CompanyParty(company="COMP", party_id="SUP-1", is_active=True))


def _seed_financial_activity() -> None:
    """Crea movimientos y documentos para poblar KPIs."""
    accounts = [
        Accounts(id="ACC-INCOME-EN", entity="COMP", code="4000", name="Income", classification="Income"),
        Accounts(id="ACC-INCOME-ES", entity="COMP", code="4001", name="Ingresos", classification="Ingresos"),
        Accounts(id="ACC-EXP-EN", entity="COMP", code="5000", name="Expense", classification="Expense"),
        Accounts(id="ACC-EXP-ES", entity="COMP", code="5001", name="Gastos", classification="Gastos"),
        Accounts(id="ACC-BANK", entity="COMP", code="1000", name="Bank", classification="Activo"),
    ]
    database.session.add_all(accounts)
    database.session.add(
        BankAccount(
            id="BANK-ACC-1",
            bank_id="BANK-1",
            company="COMP",
            account_name="Cuenta Corriente",
            account_no="001",
            currency="USD",
            gl_account_id="ACC-BANK",
            is_active=True,
        )
    )
    database.session.add_all(
        [
            _gl("GL-INCOME-EN", "ACC-INCOME-EN", debit=0, credit=100),
            _gl("GL-INCOME-ES", "ACC-INCOME-ES", debit=0, credit=200),
            _gl("GL-EXP-EN", "ACC-EXP-EN", debit=50, credit=0),
            _gl("GL-EXP-ES", "ACC-EXP-ES", debit=30, credit=0),
            _gl("GL-BANK", "ACC-BANK", debit=1000, credit=0),
        ]
    )
    database.session.add(
        BankTransaction(
            id="BT-1",
            bank_account_id="BANK-ACC-1",
            posting_date=date(2024, 1, 20),
            deposit=Decimal("100.00"),
            withdrawal=Decimal("0.00"),
            description="Depósito",
            is_reconciled=False,
        )
    )
    database.session.add(
        PurchaseOrder(id="PO-1", company="COMP", posting_date=date(2024, 1, 10), docstatus=1, supplier_id="SUP-1")
    )
    database.session.add(
        PurchaseInvoice(
            id="PI-1",
            company="COMP",
            posting_date=date(2024, 1, 15),
            docstatus=1,
            supplier_id="SUP-1",
            supplier_name="Proveedor Demo",
            document_no="PI-001",
            base_grand_total=Decimal("500.00"),
            base_outstanding_amount=Decimal("150.00"),
        )
    )
    database.session.add(
        SalesInvoice(
            id="SI-1",
            company="COMP",
            posting_date=date(2024, 1, 16),
            docstatus=1,
            customer_id="CUST-1",
            customer_name="Cliente Demo",
            document_no="SI-001",
            base_grand_total=Decimal("900.00"),
            base_outstanding_amount=Decimal("350.00"),
        )
    )
    database.session.add(
        SalesOrder(id="SO-1", company="COMP", posting_date=date(2024, 1, 11), docstatus=1, customer_id="CUST-1")
    )
    database.session.add(
        StockBin(
            id="BIN-1",
            item_code="ITEM-LOW",
            warehouse="WH-1",
            company="COMP",
            actual_qty=Decimal("3.00"),
            stock_value=Decimal("125.00"),
        )
    )
    database.session.add(
        StockLedgerEntry(
            id="SLE-1",
            posting_date=date(2024, 1, 18),
            item_code="ITEM-LOW",
            warehouse="WH-1",
            company="COMP",
            qty_change=Decimal("3.00"),
            voucher_type="stock_entry",
            voucher_id="SE-1",
        )
    )


def _gl(identifier: str, account_id: str, debit: int, credit: int) -> GLEntry:
    """Crea una línea GL de prueba."""
    return GLEntry(
        id=identifier,
        company="COMP",
        account_id=account_id,
        debit=Decimal(debit),
        credit=Decimal(credit),
        posting_date=date(2024, 1, 15),
        voucher_type="journal_entry",
        voucher_id=f"JE-{identifier}",
    )


def _login(client, username: str) -> None:
    """Inicia sesión en el cliente de pruebas."""
    response = client.post(
        "/login",
        data={"usuario": username, "acceso": "password"},
        follow_redirects=True,
    )
    assert response.status_code == 200
