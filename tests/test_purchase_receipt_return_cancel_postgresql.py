# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 William José Moreno Reyes

"""#2311: devolución concurrente con cancelación de la recepción confirmada.

La carrera se ejerce en PostgreSQL (Tier 1) sobre una base desechable y en MySQL
(Tier 2) sobre la base de pruebas configurada, con compañía y códigos únicos.

Este módulo además expone los helpers de aislamiento y siembra que reutilizan los
demás casos de lock sobre motor real (#2306, #2353, #2355): ``_isolated_url``
crea la base PostgreSQL desechable, ``_seed`` deja la compañía con el plan
contable completo y ``_drop`` la destruye. Cambiar sus firmas rompe la
colección de esos módulos, por eso su contrato queda cubierto en
``tests/test_concurrency_seed_contract.py``.
"""

from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from decimal import Decimal
from threading import Barrier
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
    DocumentTransition,
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


def _preparar(motor: str) -> tuple[object, str | None, str]:
    """Resuelve la URI del motor y un sufijo único para el escenario."""
    url = make_url(str(configuracion["SQLALCHEMY_DATABASE_URI"]))
    if os.environ.get("CHECK_DATABASE", "").strip().lower() not in {"1", "true", "yes", "on"}:
        pytest.skip("Los motores externos requieren CHECK_DATABASE=true.")
    if motor == "postgresql":
        if not url.drivername.startswith("postgresql"):
            pytest.skip("Esta variante requiere PostgreSQL.")
        name = f"return_{uuid4().hex[:10]}"
        admin = create_engine(url.set(database="postgres"))
        with admin.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
            conn.execute(text(f'CREATE DATABASE "{name}"'))
        admin.dispose()
        return url.set(database=name), name, uuid4().hex[:6].upper()
    if motor == "mysql":
        if not url.drivername.startswith("mysql"):
            pytest.skip("Esta variante requiere MySQL.")
        # El usuario de CI solo tiene privilegios sobre la base configurada:
        # el aislamiento se logra con compañía y códigos únicos por ejecución.
        return url, None, uuid4().hex[:6].upper()
    raise ValueError(f"Motor no soportado: {motor}")


def _isolated_url():
    """Devuelve la URI y el nombre de una base PostgreSQL desechable.

    Los casos de lock de #2306, #2353 y #2355 compiten por filas reales, así
    que cada uno necesita su propia base; se apoya en ``_preparar`` para no
    duplicar las comprobaciones del motor.
    """
    url, name, _ = _preparar("postgresql")
    return url, name


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


def _identificadores(sufijo: str | None = None) -> dict[str, str]:
    """Códigos de la compañía que siembra ``_seed``.

    Con sufijo los códigos son exclusivos de la ejecución, requisito para
    compartir la base de pruebas de MySQL, donde el usuario de CI no puede
    crear esquemas. Sin sufijo se conservan los códigos históricos (compañía
    ``cacao``, moneda NIO, libro FISCAL, almacén BOD01) que los casos de lock
    de #2306, #2353 y #2355 dan por sentados; cada uno corre sobre su propia
    base desechable, así que no necesita nombres únicos.
    """
    if sufijo is None:
        return {
            "company": "cacao",
            "entity_name": "Cacao",
            "company_name": "Cacao SA",
            "tax_id": "J0001",
            "currency": "NIO",
            "currency_name": "Córdoba",
            "book": "FISCAL",
            "fiscal_year": "FY2026",
            "period": "P2026-05",
            "uom": "UND",
            "warehouse": "BOD01",
            "supplier": "PRV001",
            "item": "ART01",
            "user": "admin",
            "user_id": "admin-2311",
        }
    return {
        "company": f"R{sufijo}",
        "entity_name": f"Cacao {sufijo}",
        "company_name": f"Cacao {sufijo} SA",
        "tax_id": f"J{sufijo}",
        "currency": f"C{sufijo}",
        "currency_name": f"Moneda {sufijo}",
        "book": f"L{sufijo}",
        "fiscal_year": f"FY{sufijo}",
        "period": f"P{sufijo}",
        "uom": f"U{sufijo}",
        "warehouse": f"W{sufijo}",
        "supplier": f"PRV{sufijo}",
        "item": f"IT{sufijo}",
        "user": f"admin-{sufijo}",
        "user_id": f"adm-{sufijo}",
    }


def _seed(app, sufijo: str | None = None) -> dict[str, str]:
    """Siembra la compañía del caso con el plan contable completo.

    ``sufijo`` aísla los códigos cuando la base se comparte; sin él se siembra
    el escenario histórico descrito en ``_identificadores``.
    """
    ids = _identificadores(sufijo)
    company = ids["company"]
    currency = ids["currency"]
    uom_code = ids["uom"]
    warehouse_code = ids["warehouse"]
    supplier_code = ids["supplier"]
    user_id = ids["user_id"]
    with app.app_context():
        database.create_all()
        database.session.add_all(
            [
                Currency(code=currency, name=ids["currency_name"], decimals=2, active=True, default=True),
                Entity(
                    code=company,
                    name=ids["entity_name"],
                    company_name=ids["company_name"],
                    tax_id=ids["tax_id"],
                    currency=currency,
                    enabled=True,
                    status="default",
                ),
            ]
        )
        database.session.flush()
        database.session.add(
            Book(
                code=ids["book"],
                name="Fiscal",
                entity=company,
                currency=currency,
                status="activo",
                is_primary=True,
            )
        )
        database.session.add(
            FiscalYear(
                id=ids["fiscal_year"],
                entity=company,
                name="2026",
                year_start_date=date(2026, 1, 1),
                year_end_date=date(2026, 12, 31),
                is_closed=False,
            )
        )
        database.session.flush()
        database.session.add(
            AccountingPeriod(
                id=ids["period"],
                entity=company,
                fiscal_year_id=ids["fiscal_year"],
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
                entity=company,
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
                company=company,
                default_receivable=accounts["1105"].id,
                default_payable=accounts["2101"].id,
                default_cash=accounts["1101"].id,
                default_bank=accounts["1102"].id,
                default_income=accounts["4101"].id,
                default_expense=accounts["5201"].id,
                bridge_account_id=accounts["2103"].id,
            )
        )
        uom = UOM(code=uom_code, name="Unidad", is_active=True)
        warehouse = Warehouse(code=warehouse_code, name="Bodega", company=company)
        supplier = Party(code=supplier_code, name="Proveedor", is_supplier=True, is_active=True)
        user = User(
            id=user_id,
            user=ids["user"],
            name="Admin",
            password=b"x",
            classification="admin",
            active=True,
            company=company,
        )
        database.session.add_all([uom, warehouse, supplier, user])
        database.session.flush()
        item = Item(
            code=ids["item"],
            name="Artículo",
            item_type="goods",
            is_stock_item=True,
            default_uom=uom_code,
        )
        database.session.add(item)
        database.session.flush()
        database.session.add(
            WarehouseCompanyAccount(
                warehouse_code=warehouse.code,
                company=company,
                inventory_account_id=accounts["1109"].id,
            )
        )
        database.session.commit()
        resultado = {
            "company": company,
            "currency": currency,
            "book": ids["book"],
            "warehouse_code": warehouse_code,
            "warehouse_id": warehouse.id,
            "supplier_id": supplier.id,
            "item_id": item.id,
            "uom_id": uom.id,
            "admin_id": user.id,
        }
        database.session.remove()
    return resultado


@pytest.mark.parametrize("motor", ["postgresql", "mysql"])
def test_devolucion_y_cancelacion_no_confirmar_ambas(motor: str) -> None:
    """La devolución y la cancelación compiten por la recepción posteada."""
    url, name, sufijo = _preparar(motor)
    try:
        app = create_app(
            {
                **configuracion,
                "SQLALCHEMY_DATABASE_URI": url.render_as_string(hide_password=False),
                "TESTING": True,
                "SECRET_KEY": "test-2311",
                "WTF_CSRF_ENABLED": False,
                "MODO_ESCRITORIO": False,
            }
        )
        semilla = _seed(app, sufijo)
        company = semilla["company"]
        with app.app_context():
            _sembrar_cuentas(app, company=company, warehouse_code=semilla["warehouse_code"])
            datos = _sembrar_cadena(
                Decimal("3"),
                company=company,
                currency=semilla["currency"],
                supplier_id=semilla["supplier_id"],
                item_id=semilla["item_id"],
                uom_id=semilla["uom_id"],
                warehouse_id=semilla["warehouse_id"],
                admin_id=semilla["admin_id"],
            )
            original_id = str(datos["original"].id)
            return_id = str(datos["devolucion"].id)
            admin_id = str(datos["admin"].id)
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
                        PurchaseReceiptReturnAllocation.company == company,
                        PurchaseReceiptReturnAllocation.status == "active",
                    )
                )
                .scalars()
                .all()
            )
            gl = (
                database.session.execute(
                    database.select(GLEntry).filter_by(
                        company=company, voucher_type="purchase_receipt", voucher_id=original_id, is_cancelled=True
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
            transiciones = (
                database.session.execute(
                    database.select(DocumentTransition).where(
                        DocumentTransition.company == company,
                        DocumentTransition.source_type == "purchase_receipt",
                        DocumentTransition.source_id == original_id,
                        DocumentTransition.transition_type == "cancellation",
                    )
                )
                .scalars()
                .all()
            )
            if source.docstatus == 2:
                assert allocations == []
                assert gl, "la cancelación debe dejar contrapartidas GL"
                assert stock, "la cancelación debe revertir el Stock Ledger"
                assert transiciones, "la cancelación debe quedar trazada"
            else:
                assert source.docstatus == 1
                assert len(allocations) == 1
                assert gl == [], "la cancelación rechazada no debe dejar GL parcial"
                assert stock == [], "la cancelación rechazada no debe dejar Stock Ledger parcial"
                assert transiciones == [], "la cancelación rechazada no debe dejar transición parcial"
                # El perdedor no puede reintentar y crear una segunda allocation.
                try:
                    create_purchase_receipt_return_allocations(return_id)
                    database.session.commit()
                except Exception:
                    database.session.rollback()
                allocations_after = (
                    database.session.execute(
                        database.select(PurchaseReceiptReturnAllocation).where(
                            PurchaseReceiptReturnAllocation.company == company,
                            PurchaseReceiptReturnAllocation.status == "active",
                        )
                    )
                    .scalars()
                    .all()
                )
                assert len(allocations_after) == 1
            database.session.remove()
    finally:
        if name is not None:
            _drop(url, name)
