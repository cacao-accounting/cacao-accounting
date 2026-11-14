# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Una actualización de cliente conserva la operación de compras del tercero dual."""

from __future__ import annotations

import os
from datetime import date
from pathlib import Path
from typing import Any, cast
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, select, text

from cacao_accounting import create_app
from cacao_accounting.config import configuracion
from cacao_accounting.database import (
    AccountingPeriod,
    Accounts,
    CompanyParty,
    Currency,
    Entity,
    FiscalYear,
    Item,
    Modules,
    Party,
    PartyAccount,
    PurchaseInvoice,
    PurchaseInvoiceItem,
    PurchaseMatchingConfig,
    UOM,
    User,
    UserCompanyAccess,
    database,
)

pytestmark = pytest.mark.database


@pytest.fixture
def dual_role_s2p_scenario(tmp_path: Path, request):
    """Create an isolated app database and seed one dual-role trading scenario."""
    uri = str(configuracion.get("SQLALCHEMY_DATABASE_URI", ""))
    check_database = os.environ.get("CHECK_DATABASE", "").strip().lower() in {"1", "true", "yes", "on"}
    external_postgres = uri.startswith("postgresql")
    if check_database and not external_postgres and not uri.startswith("sqlite"):
        pytest.skip("La prueba aislada de facturas duales requiere SQLite o PostgreSQL.")

    schema_name = f"s2p_dual_{uuid4().hex[:12]}"
    bootstrap_engine = create_engine(uri) if external_postgres else None
    engine_options: Any
    if external_postgres:
        assert bootstrap_engine is not None
        with bootstrap_engine.begin() as connection:
            connection.execute(text(f'CREATE SCHEMA "{schema_name}"'))
        connect_args = (
            {"server_settings": {"search_path": f"{schema_name},public"}}
            if "+pg8000" in uri
            else {"options": f"-csearch_path={schema_name},public"}
        )
        database_uri = uri
        engine_options = {"pool_size": 4, "max_overflow": 0, "connect_args": connect_args}
    else:
        database_uri = f"sqlite:///{tmp_path / 's2p-dual-role.sqlite'}"
        engine_options = {"connect_args": {"check_same_thread": False}}

    application = None

    def cleanup_database():
        """Dispose the test app and drop its isolated PostgreSQL schema."""
        if application is not None:
            with application.app_context():
                database.session.remove()
                database.engine.dispose()
        if bootstrap_engine is not None:
            with bootstrap_engine.begin() as connection:
                connection.execute(text(f'DROP SCHEMA "{schema_name}" CASCADE'))
            bootstrap_engine.dispose()

    request.addfinalizer(cleanup_database)
    app_settings: dict[str, Any] = dict(configuracion)
    app_settings.update(
        {
            "SQLALCHEMY_DATABASE_URI": database_uri,
            "SQLALCHEMY_ENGINE_OPTIONS": cast(Any, engine_options),
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
            "WTF_CSRF_ENABLED": False,
            "TESTING": True,
            "SECRET_KEY": "isolated-dual-role-test",
            "MODO_ESCRITORIO": False,
        }
    )
    application = create_app(app_settings)
    with application.app_context():
        database.create_all()
        database.session.add_all(
            [
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
                Modules(module="sales", default=False, enabled=True),
                Modules(module="purchases", default=False, enabled=True),
                Modules(module="accounting", default=True, enabled=True),
                User(
                    user="admin",
                    name="Administrador de prueba",
                    password=b"unused",
                    classification="admin",
                    active=True,
                    company="cacao",
                ),
                UOM(code="UND", name="Unidad"),
            ]
        )
        database.session.flush()
        admin = database.session.execute(select(User).where(User.user == "admin")).scalar_one()
        database.session.add(UserCompanyAccess(user_id=admin.id, company_code="cacao"))
        database.session.add(
            FiscalYear(
                id="FY2026",
                entity="cacao",
                name="2026",
                year_start_date=date(2026, 1, 1),
                year_end_date=date(2026, 12, 31),
                is_closed=False,
            )
        )
        database.session.flush()
        database.session.add_all(
            [
                AccountingPeriod(
                    id="P2026-05",
                    entity="cacao",
                    fiscal_year_id="FY2026",
                    name="Mayo 2026",
                    start=date(2026, 5, 1),
                    end=date(2026, 5, 31),
                    enabled=True,
                    is_closed=False,
                    status="open",
                ),
                Accounts(
                    entity="cacao",
                    code="1105",
                    name="Cuentas por cobrar",
                    group=False,
                    active=True,
                    enabled=True,
                    classification="asset",
                    account_type="receivable",
                ),
                Accounts(
                    entity="cacao",
                    code="2101",
                    name="Cuentas por pagar",
                    group=False,
                    active=True,
                    enabled=True,
                    classification="liability",
                    account_type="payable",
                ),
                Item(
                    code="ITEM-DUAL",
                    name="Servicio contratado",
                    item_type="service",
                    is_stock_item=False,
                    is_purchase_item=True,
                    default_uom="UND",
                ),
                PurchaseMatchingConfig(
                    company="cacao",
                    matching_type="2-way",
                    require_purchase_order=False,
                    bridge_account_required=False,
                    auto_reconcile=False,
                ),
            ]
        )
        database.session.flush()
        party = Party(
            code="DUAL-TEST",
            name="Proveedor y cliente de la operación",
            tax_id="TAX-DUAL-TEST",
            is_customer=True,
            is_supplier=True,
        )
        database.session.add(party)
        database.session.flush()
        receivable_id = database.session.execute(
            select(Accounts.id).where(Accounts.entity == "cacao", Accounts.code == "1105")
        ).scalar_one()
        payable_id = database.session.execute(
            select(Accounts.id).where(Accounts.entity == "cacao", Accounts.code == "2101")
        ).scalar_one()
        database.session.add_all(
            [
                CompanyParty(
                    company="cacao",
                    party_id=party.id,
                    is_active=True,
                    allow_purchase_invoice_without_order=True,
                    allow_purchase_invoice_without_receipt=True,
                ),
                PartyAccount(
                    party_id=party.id,
                    company="cacao",
                    receivable_account_id=receivable_id,
                    payable_account_id=payable_id,
                ),
            ]
        )
        database.session.commit()
        seed = {
            "party_id": str(party.id),
            "user_id": str(database.session.execute(select(User.id).where(User.user == "admin")).scalar_one()),
            "receivable_id": str(receivable_id),
            "payable_id": str(payable_id),
            "item_code": "ITEM-DUAL",
            "item_name": "Servicio contratado",
            "item_uom": "UND",
        }

    yield application, seed


def test_editar_cliente_dual_conserva_s2p_y_cuentas_ar_ap(dual_role_s2p_scenario):
    """Guardar datos de ventas no bloquea una factura permitida de compras."""
    app, seed = dual_role_s2p_scenario
    client = app.test_client()
    with client.session_transaction() as session:
        session["_user_id"] = seed["user_id"]
        session["_fresh"] = True

    customer_settings_response = client.post(
        f"/sales/customer/{seed['party_id']}/company-settings",
        data={
            "company": "cacao",
            "company_is_active": "on",
            "receivable_account_id": seed["receivable_id"],
        },
    )
    assert customer_settings_response.status_code == 302

    remove_customer_row_response = client.post(f"/sales/customer/{seed['party_id']}/company-settings", data={})
    assert remove_customer_row_response.status_code == 302

    with app.app_context():
        company_settings = database.session.execute(
            select(CompanyParty).where(CompanyParty.party_id == seed["party_id"], CompanyParty.company == "cacao")
        ).scalar_one()
        accounts = database.session.execute(
            select(PartyAccount).where(PartyAccount.party_id == seed["party_id"], PartyAccount.company == "cacao")
        ).scalar_one()
        assert company_settings.is_active is True
        assert company_settings.allow_purchase_invoice_without_order is True
        assert company_settings.allow_purchase_invoice_without_receipt is True
        assert accounts.receivable_account_id == seed["receivable_id"]
        assert accounts.payable_account_id == seed["payable_id"]

    supplier_invoice_no = f"SUP-{uuid4().hex[:10]}"
    purchase_response = client.post(
        "/buying/purchase-invoice/new",
        data={
            "company": "cacao",
            "supplier_id": seed["party_id"],
            "supplier_invoice_no": supplier_invoice_no,
            "posting_date": "2026-05-20",
            "transaction_currency": "NIO",
            "document_type": "purchase_invoice",
            "item_code_0": seed["item_code"],
            "item_name_0": seed["item_name"],
            "qty_0": "2",
            "rate_0": "125",
            "uom_0": seed["item_uom"],
        },
    )
    assert purchase_response.status_code == 302

    with app.app_context():
        invoice = database.session.execute(
            select(PurchaseInvoice).where(PurchaseInvoice.supplier_invoice_no == supplier_invoice_no)
        ).scalar_one()
        invoice_line = database.session.execute(
            select(PurchaseInvoiceItem).where(PurchaseInvoiceItem.purchase_invoice_id == invoice.id)
        ).scalar_one()
        company_settings = database.session.execute(
            select(CompanyParty).where(CompanyParty.party_id == seed["party_id"], CompanyParty.company == "cacao")
        ).scalar_one()
        accounts = database.session.execute(
            select(PartyAccount).where(PartyAccount.party_id == seed["party_id"], PartyAccount.company == "cacao")
        ).scalar_one()

        assert invoice.supplier_id == seed["party_id"]
        assert invoice.docstatus == 0
        assert invoice.total == 250
        assert invoice.outstanding_amount == 250
        assert invoice_line.qty == 2
        assert invoice_line.amount == 250
        assert company_settings.is_active is True
        assert company_settings.allow_purchase_invoice_without_order is True
        assert company_settings.allow_purchase_invoice_without_receipt is True
        assert accounts.receivable_account_id == seed["receivable_id"]
        assert accounts.payable_account_id == seed["payable_id"]

    supplier_settings_response = client.post(
        f"/buying/supplier/{seed['party_id']}/company-settings",
        data={
            "company": "cacao",
            "company_is_active": "on",
            "payable_account_id": seed["payable_id"],
            "allow_purchase_invoice_without_order": "on",
            "allow_purchase_invoice_without_receipt": "on",
        },
    )
    assert supplier_settings_response.status_code == 302

    with app.app_context():
        accounts = database.session.execute(
            select(PartyAccount).where(PartyAccount.party_id == seed["party_id"], PartyAccount.company == "cacao")
        ).scalar_one()
        assert accounts.receivable_account_id == seed["receivable_id"]
        assert accounts.payable_account_id == seed["payable_id"]
