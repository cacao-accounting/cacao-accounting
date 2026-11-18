# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1254: la conciliación bancaria no mezcla pendientes de Compras sin permiso.

La herramienta de banca solo entrega filas `purchase_reconciliation` cuando la
llamada también tiene `payables.reports.read` y acceso a la compañía.
"""

from __future__ import annotations

from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import pytest

from cacao_accounting import create_app
from cacao_accounting.config import configuracion
from cacao_accounting.database import Currency, Entity, Modules, database
from cacao_accounting.query_tools.context import QueryContext
from cacao_accounting.query_tools.handlers.advanced import get_banking_reconciliation_status


@pytest.fixture
def banking_purchase_scope_scenario(monkeypatch):
    """Create the modules and inject one pending purchase receipt row."""
    app = create_app(
        {
            **configuracion,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
            "WTF_CSRF_ENABLED": False,
            "TESTING": True,
            "MODO_ESCRITORIO": False,
        }
    )
    suffix = uuid4().hex[:6]
    pending = SimpleNamespace(
        purchase_receipt_id=f"PR-{suffix}",
        purchase_receipt_item_id=f"PRI-{suffix}",
        pending_amount=Decimal("75"),
        status="pending",
    )

    with app.app_context():
        database.create_all()
        database.session.add_all(
            [
                Currency(code="NIO", name="Córdoba", decimals=2, active=True, default=True),
                Modules(module="cash", default=False, enabled=True),
                Modules(module="purchases", default=False, enabled=True),
                Entity(
                    code="alpha",
                    name="Alpha",
                    company_name=f"Alpha {suffix}",
                    tax_id=f"TAX-{suffix}",
                    currency="NIO",
                    enabled=True,
                    status="default",
                ),
            ]
        )
        database.session.commit()

    from cacao_accounting.reportes import services as report_services

    monkeypatch.setattr(report_services, "get_purchase_reconciliation_pending", lambda **_kwargs: [pending])
    yield app, pending

    with app.app_context():
        database.session.remove()
        database.engine.dispose()


def _context(permissions: set[str]) -> QueryContext:
    """Build a service-principal context for the Alpha company."""
    return QueryContext(
        user_id="service",
        company_ids=["alpha"],
        permissions=permissions,
        is_service_principal=True,
    )


def test_banking_report_hides_purchase_pending_without_payables_permission(banking_purchase_scope_scenario):
    """A banking-only call receives no purchase receipt rows or totals."""
    app, _pending = banking_purchase_scope_scenario

    with app.app_context():
        result = get_banking_reconciliation_status.handler(
            context=_context({"banking.reports.read"}),
            company_id="alpha",
        )

    assert all(item.get("recon_type") != "purchase_reconciliation" for item in result["items"])
    assert Decimal(str(result["summary"]["purchase_pending_amount"])) == Decimal("0")


def test_banking_report_includes_purchase_pending_with_payables_permission(banking_purchase_scope_scenario):
    """The combined authorization keeps the purchase rows and total."""
    app, pending = banking_purchase_scope_scenario

    with app.app_context():
        result = get_banking_reconciliation_status.handler(
            context=_context({"banking.reports.read", "payables.reports.read"}),
            company_id="alpha",
        )

    purchase_rows = [item for item in result["items"] if item.get("recon_type") == "purchase_reconciliation"]
    assert len(purchase_rows) == 1
    assert purchase_rows[0]["source_id"] == pending.purchase_receipt_item_id
    assert Decimal(str(result["summary"]["purchase_pending_amount"])) == Decimal("75")


def test_banking_report_hides_purchase_pending_when_purchases_module_is_disabled(banking_purchase_scope_scenario):
    """A permission string is not enough if the Compras module is disabled."""
    app, _pending = banking_purchase_scope_scenario

    with app.app_context():
        purchases = database.session.execute(database.select(Modules).filter_by(module="purchases")).scalar_one()
        purchases.enabled = False
        database.session.commit()
        result = get_banking_reconciliation_status.handler(
            context=_context({"banking.reports.read", "payables.reports.read"}),
            company_id="alpha",
        )

    assert all(item.get("recon_type") != "purchase_reconciliation" for item in result["items"])
    assert Decimal(str(result["summary"]["purchase_pending_amount"])) == Decimal("0")
