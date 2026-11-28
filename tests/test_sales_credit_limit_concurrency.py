# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 William José Moreno Reyes

"""#2299: el límite de crédito se serializa por compañía y cliente."""

from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from decimal import Decimal
from threading import Barrier
from time import sleep
from uuid import uuid4

import pytest

from cacao_accounting import create_app
from cacao_accounting.config import configuracion
from cacao_accounting.approval_engine import ApprovalEngine
from cacao_accounting.database import (
    ApprovalMatrix,
    ApprovalRequest,
    AuditTrail,
    CacaoConfig,
    CompanyParty,
    Currency,
    Entity,
    Party,
    Item,
    Modules,
    SalesOrder,
    SalesOrderItem,
    UOM,
    User,
    UserCompanyAccess,
    database,
)
from cacao_accounting.ventas.services import _validate_credit_limit_and_overdue

pytestmark = pytest.mark.database

FECHA = date(2026, 5, 15)


def _app(tmp_path):
    """Usa un archivo SQLite propio o la base externa dedicada de CI."""
    uri = str(configuracion["SQLALCHEMY_DATABASE_URI"])
    if uri.startswith("sqlite"):
        uri = f"sqlite:///{tmp_path / 'credit-limit.sqlite'}"
    elif os.environ.get("CHECK_DATABASE", "").strip().lower() not in {"1", "true", "yes", "on"}:
        pytest.skip("Los motores externos requieren CHECK_DATABASE=true.")
    return create_app(
        {
            **configuracion,
            "SQLALCHEMY_DATABASE_URI": uri,
            "SQLALCHEMY_ENGINE_OPTIONS": {
                **configuracion.get("SQLALCHEMY_ENGINE_OPTIONS", {}),
                "pool_size": 4,
                "max_overflow": 0,
            },
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
            "WTF_CSRF_ENABLED": False,
            "TESTING": True,
            "SECRET_KEY": "test-2299",
            "MODO_ESCRITORIO": False,
        }
    )


def _cleanup_case(case: dict) -> None:
    """Elimina únicamente las filas sembradas por el caso en una base externa."""
    company = case.get("company")
    if not company:
        return
    orders = case.get("orders", [])
    database.session.execute(database.delete(ApprovalRequest).where(ApprovalRequest.company_id == company))
    database.session.execute(database.delete(ApprovalMatrix).where(ApprovalMatrix.company_id == company))
    database.session.execute(database.delete(CacaoConfig).where(CacaoConfig.key == f"approval_engine_enabled_{company}"))
    if orders:
        database.session.execute(database.delete(AuditTrail).where(AuditTrail.document_id.in_(orders)))
        database.session.execute(database.delete(SalesOrderItem).where(SalesOrderItem.sales_order_id.in_(orders)))
    database.session.execute(database.delete(SalesOrder).where(SalesOrder.company == company))
    database.session.execute(database.delete(UserCompanyAccess).where(UserCompanyAccess.company_code == company))
    users = case.get("users", [])
    if users:
        database.session.execute(database.delete(User).where(User.id.in_(users)))
    database.session.execute(database.delete(CompanyParty).where(CompanyParty.company == company))
    database.session.execute(database.delete(Party).where(Party.id == case["customer"]))
    database.session.execute(database.delete(Item).where(Item.code == case["item"]))
    database.session.execute(database.delete(Entity).where(Entity.code == company))
    database.session.execute(database.delete(Currency).where(Currency.code == case["currency"]))
    database.session.execute(database.delete(UOM).where(UOM.code == case["uom"]))
    database.session.commit()


@pytest.fixture
def credit_app(tmp_path):
    """App dedicada; en motores externos limpia solo las filas del caso."""
    app = _app(tmp_path)
    yield app
    case = app.config.pop("_credit_case", {})
    with app.app_context():
        try:
            _cleanup_case(case)
        finally:
            database.session.remove()
            database.engine.dispose()


def _seed(app, suffix: str) -> tuple[str, str, list[str]]:
    company = f"E{suffix}"
    with app.app_context():
        database.create_all()
        module = database.session.execute(database.select(Modules).filter_by(module="sales")).scalar_one_or_none()
        if module is None:
            database.session.add(Modules(module="sales", default=False, enabled=True))
        else:
            module.enabled = True
        database.session.add_all(
            [
                Currency(code=f"C{suffix}", name="Moneda", decimals=2, active=True, default=False),
                UOM(code=f"U{suffix}", name="Unidad", is_active=True),
                Entity(
                    code=company,
                    name=f"Empresa {suffix}",
                    company_name=f"Empresa {suffix} SA",
                    tax_id=f"T{suffix}",
                    currency=f"C{suffix}",
                    enabled=True,
                    status="default",
                ),
            ]
        )
        database.session.flush()
        customer = Party(code=f"CLI{suffix}", name="Cliente", is_customer=True, is_active=True)
        database.session.add(customer)
        database.session.flush()
        database.session.add(
            CompanyParty(company=company, party_id=customer.id, credit_limit=Decimal("100"), block_overdue=False)
        )
        orders = [
            SalesOrder(
                company=company,
                posting_date=FECHA,
                docstatus=0,
                document_no=f"SO-{suffix}-{index}",
                customer_id=customer.id,
                customer_name=customer.name,
                transaction_currency=f"C{suffix}",
                base_currency=f"C{suffix}",
                exchange_rate=Decimal("1"),
                grand_total=Decimal("60"),
                base_total=Decimal("60"),
                status="open",
            )
            for index in (1, 2)
        ]
        database.session.add_all(orders)
        database.session.flush()
        item = Item(
            code=f"IT{suffix}",
            name="Artículo",
            item_type="service",
            is_stock_item=False,
            is_sale_item=True,
            is_purchase_item=False,
            default_uom=f"U{suffix}",
            is_active=True,
        )
        database.session.add(item)
        database.session.flush()
        database.session.add_all(
            [
                SalesOrderItem(
                    sales_order_id=order.id,
                    item_code=item.code,
                    item_name=item.name,
                    qty=Decimal("1"),
                    qty_in_base_uom=Decimal("1"),
                    uom=f"U{suffix}",
                    rate=Decimal("60"),
                    amount=Decimal("60"),
                )
                for order in orders
            ]
        )
        database.session.commit()
        result = (company, customer.id, [order.id for order in orders])
        app.config["_credit_case"] = {
            "company": company,
            "customer": customer.id,
            "item": item.code,
            "currency": f"C{suffix}",
            "uom": f"U{suffix}",
            "orders": [order.id for order in orders],
            "users": [],
        }
        database.session.remove()
        return result


def test_aprobaciones_diferidas_no_superan_el_limite(credit_app):
    """El flujo real de ApprovalEngine respeta el lock de crédito."""
    app = credit_app
    with app.app_context():
        database.session.remove()
    suffix = uuid4().hex[:6].upper()
    company, customer_id, order_ids = _seed(app, suffix)
    admin_id = f"adm-{suffix}"
    requester_id = f"req-{suffix}"
    with app.app_context():
        database.session.add_all(
            [
                User(
                    id=admin_id,
                    user=f"admin_{suffix}",
                    name="Admin",
                    password=b"x",
                    classification="admin",
                    active=True,
                    company=company,
                ),
                User(
                    id=requester_id,
                    user=f"requester_{suffix}",
                    name="Solicitante",
                    password=b"x",
                    classification="user",
                    active=True,
                    company=company,
                ),
                UserCompanyAccess(user_id=admin_id, company_code=company),
            ]
        )
        database.session.flush()
        database.session.add_all(
            [
                CacaoConfig(key=f"approval_engine_enabled_{company}", value="true"),
                ApprovalMatrix(
                    company_id=company,
                    document_type="sales_order",
                    user_id=admin_id,
                    min_amount=Decimal("0"),
                    max_amount=None,
                    approval_level=1,
                    enabled=True,
                ),
            ]
        )
        database.session.commit()
        app.config["_credit_case"]["users"] = [admin_id, requester_id]
        requester = database.session.get(User, requester_id)
        for order_id in order_ids:
            order = database.session.get(SalesOrder, order_id)
            assert ApprovalEngine.request_approval(order, actor=requester) is not None
            database.session.commit()
        database.session.remove()

    barrier = Barrier(2, timeout=30)

    def approve(order_id: str) -> str:
        with app.app_context():
            try:
                barrier.wait(timeout=10)
                order = database.session.get(SalesOrder, order_id)
                request = database.session.execute(
                    database.select(ApprovalRequest).filter_by(document_id=order_id, status="Pending Approval")
                ).scalar_one()
                admin = database.session.get(User, admin_id)
                ApprovalEngine.approve(order, admin, request=request)
                database.session.commit()
                return "aprobada"
            except ValueError:
                database.session.rollback()
                return "rechazada"
            finally:
                database.session.remove()

    with ThreadPoolExecutor(max_workers=2) as workers:
        results = list(workers.map(approve, order_ids))
    assert sorted(results) == ["aprobada", "rechazada"], results
    with app.app_context():
        approved = (
            database.session.execute(database.select(SalesOrder).filter_by(company=company, docstatus=1)).scalars().all()
        )
        assert len(approved) == 1
        approved_id = approved[0].id
        rejected_id = next(order_id for order_id in order_ids if order_id != approved_id)
        requests_by_document = {
            row.document_id: row
            for row in database.session.execute(
                database.select(ApprovalRequest).where(ApprovalRequest.document_id.in_(order_ids))
            ).scalars()
        }
        assert requests_by_document[approved_id].status == "Approved"
        assert requests_by_document[rejected_id].status in {"Pending Approval", "Rejected"}
        rechazada = database.session.get(SalesOrder, rejected_id)
        assert rechazada.docstatus == 0


def test_dos_aprobaciones_no_superan_el_limite(credit_app):
    """Dos documentos de 60 con límite 100 no pueden confirmarse ambos."""
    app = credit_app
    suffix = uuid4().hex[:6].upper()
    company, customer_id, order_ids = _seed(app, suffix)
    barrier = Barrier(2, timeout=30)

    def approve(order_id: str) -> str:
        with app.app_context():
            try:
                barrier.wait(timeout=10)
                order = database.session.get(SalesOrder, order_id)
                _validate_credit_limit_and_overdue(company, customer_id, Decimal("60"), current_document=order)
                # Mantiene abierta la transacción para que la otra sesión
                # intente validar mientras el lock sigue tomado.
                sleep(0.5)
                order.docstatus = 1
                database.session.commit()
                return "aprobada"
            except ValueError:
                database.session.rollback()
                return "rechazada"
            finally:
                database.session.remove()

    with ThreadPoolExecutor(max_workers=2) as workers:
        results = list(workers.map(approve, order_ids))
    assert sorted(results) == ["aprobada", "rechazada"], results
    with app.app_context():
        approved = (
            database.session.execute(database.select(SalesOrder).filter_by(company=company, docstatus=1)).scalars().all()
        )
        assert len(approved) == 1
