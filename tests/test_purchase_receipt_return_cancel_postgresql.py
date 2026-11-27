# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 William José Moreno Reyes

"""#2311: devolución concurrente con cancelación de la recepción en PostgreSQL."""

from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from decimal import Decimal
from threading import Barrier
from types import SimpleNamespace
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

from test_purchase_receipt_return_approval import _sembrar_cadena, _sembrar_cuentas

from cacao_accounting import create_app
from cacao_accounting.approval_engine import approved_execution
from cacao_accounting.compras.purchase_reconciliation_service import create_purchase_receipt_return_allocations
from cacao_accounting.config import configuracion
from cacao_accounting.contabilidad.posting_service import cancel_document
from cacao_accounting.database import (
    AccountingPeriod,
    GLEntry,
    Accounts,
    Book,
    CompanyDefaultAccount,
    Currency,
    Entity,
    FiscalYear,
    Item,
    Party,
    PurchaseReceipt,
    PurchaseReceiptReturnAllocation,
    StockLedgerEntry,
    UOM,
    User,
    Warehouse,
    WarehouseCompanyAccount,
    database,
)
from cacao_accounting.internal_control_service import audit_actor

pytestmark = pytest.mark.database


def _isolated_url():
    raw = str(configuracion["SQLALCHEMY_DATABASE_URI"])
    url = make_url(raw)
    if not url.drivername.startswith("postgresql"):
        pytest.skip("Este escenario requiere PostgreSQL.")
    if os.environ.get("CHECK_DATABASE", "").strip().lower() not in {"1", "true", "yes", "on"}:
        pytest.skip("Los motores externos requieren CHECK_DATABASE=true.")
    name = f"return_{uuid4().hex[:10]}"
    admin = create_engine(url.set(database="postgres"))
    with admin.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
        conn.execute(text(f'CREATE DATABASE "{name}"'))
    admin.dispose()
    return url.set(database=name), name


def _drop(url, name: str) -> None:
    admin = create_engine(url.set(database="postgres"))
    try:
        with admin.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
            conn.execute(
                text(
                    "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                    f"WHERE datname = '{name}' AND pid <> pg_backend_pid()"
                )
            )
            conn.execute(text(f'DROP DATABASE IF EXISTS "{name}"'))
    finally:
        admin.dispose()


def _seed(app) -> None:
    with app.app_context():
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
            ]
        )
        database.session.flush()
        book = Book(code="FISCAL", name="Fiscal", entity="cacao", currency="NIO", status="activo", is_primary=True)
        database.session.add(book)
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
        database.session.add(
            AccountingPeriod(
                id="P2026-05",
                entity="cacao",
                fiscal_year_id="FY2026",
                name="Mayo 2026",
                start=date(2026, 5, 1),
                end=date(2026, 5, 31),
                enabled=True,
                is_closed=False,
            )
        )
        accounts = {}
        for code, name, classification, account_type in (
            ("1101", "Caja", "asset", "cash"),
            ("1102", "Bancos", "asset", "bank"),
            ("1105", "CxC", "asset", "receivable"),
            ("1109", "Inventario", "asset", "stock"),
            ("2101", "CxP", "liability", "payable"),
            ("2103", "Puente compras", "liability", "bridge"),
            ("2105", "IVA", "liability", "tax"),
            ("4101", "Ventas", "revenue", "income"),
            ("5101", "Costo", "expense", "expense"),
            ("5201", "Gastos", "expense", "expense"),
        ):
            account = Accounts(
                entity="cacao",
                code=code,
                name=name,
                classification=classification,
                account_type=account_type,
                group=False,
                active=True,
                enabled=True,
            )
            database.session.add(account)
            accounts[code] = account
        database.session.flush()
        database.session.add(
            CompanyDefaultAccount(
                company="cacao",
                default_receivable=accounts["1105"].id,
                default_payable=accounts["2101"].id,
                default_cash=accounts["1101"].id,
                default_bank=accounts["1102"].id,
                default_income=accounts["4101"].id,
                default_expense=accounts["5201"].id,
                bridge_account_id=accounts["2103"].id,
            )
        )
        uom = UOM(code="UND", name="Unidad", is_active=True)
        warehouse = Warehouse(code="BOD01", name="Bodega", company="cacao")
        supplier = Party(code="PRV001", name="Proveedor", is_supplier=True, is_active=True)
        user = User(
            id="admin-2311",
            user="admin",
            name="Admin",
            password=b"x",
            classification="admin",
            active=True,
            company="cacao",
        )
        database.session.add_all([uom, warehouse, supplier, user])
        database.session.flush()
        item = Item(code="ART01", name="Artículo", item_type="goods", is_stock_item=True, default_uom="UND")
        database.session.add(item)
        database.session.flush()
        database.session.add(
            WarehouseCompanyAccount(warehouse_code=warehouse.code, company="cacao", inventory_account_id=accounts["1109"].id)
        )
        database.session.commit()
        database.session.remove()


def test_devolucion_y_cancelacion_no_confirmar_ambas():
    """La devolución y la cancelación compiten por la recepción posteada."""
    url, name = _isolated_url()
    try:
        app = create_app(
            {
                **configuracion,
                "SQLALCHEMY_DATABASE_URI": url.render_as_string(hide_password=False),
                "TESTING": True,
                "SECRET_KEY": "test-2311-cancel",
                "WTF_CSRF_ENABLED": False,
                "MODO_ESCRITORIO": False,
            }
        )
        _seed(app)
        with app.app_context():
            _sembrar_cuentas(SimpleNamespace(app=app))
            datos = _sembrar_cadena(Decimal("3"))
            original = datos["original"]
            devolucion = datos["devolucion"]
            admin = datos["admin"]
            original_id = str(original.id)
            return_id = str(devolucion.id)
            admin_id = str(admin.id)
            database.session.remove()

        barrier = Barrier(2, timeout=30)

        def allocate_return() -> str:
            with app.app_context():
                try:
                    barrier.wait(timeout=10)
                    create_purchase_receipt_return_allocations(return_id)
                    database.session.commit()
                    return "devolucion"
                except Exception:
                    database.session.rollback()
                    return "rechazada"
                finally:
                    database.session.remove()

        def cancel_source() -> str:
            with app.app_context():
                try:
                    barrier.wait(timeout=10)
                    source = database.session.get(PurchaseReceipt, original_id)
                    with audit_actor(admin_id, "Admin"), approved_execution(source, admin_id):
                        cancel_document(
                            source,
                            reason="Cancelación concurrente de prueba",
                            actor_user_id=admin_id,
                            cancellation_date=date(2026, 5, 12),
                        )
                    database.session.commit()
                    return "cancelada"
                except Exception:
                    database.session.rollback()
                    return "rechazada"
                finally:
                    database.session.remove()

        with ThreadPoolExecutor(max_workers=2) as workers:
            results = list(workers.map(lambda fn: fn(), (allocate_return, cancel_source)))

        assert sorted(results) in (["cancelada", "rechazada"], ["devolucion", "rechazada"]), results
        with app.app_context():
            source = database.session.get(PurchaseReceipt, original_id)
            allocations = (
                database.session.execute(
                    database.select(PurchaseReceiptReturnAllocation).where(
                        PurchaseReceiptReturnAllocation.company == "cacao",
                        PurchaseReceiptReturnAllocation.status == "active",
                    )
                )
                .scalars()
                .all()
            )
            if source.docstatus == 2:
                assert allocations == []
                gl = (
                    database.session.execute(
                        database.select(GLEntry).filter_by(
                            company="cacao", voucher_type="purchase_receipt", voucher_id=original_id, is_cancelled=True
                        )
                    )
                    .scalars()
                    .all()
                )
                stock = (
                    database.session.execute(
                        database.select(StockLedgerEntry).filter_by(voucher_id=original_id, is_cancelled=True)
                    )
                    .scalars()
                    .all()
                )
                assert gl, "la cancelación debe dejar contrapartidas GL"
                assert stock, "la cancelación debe revertir el Stock Ledger"
            else:
                assert len(allocations) == 1
            database.session.remove()
    finally:
        _drop(url, name)
