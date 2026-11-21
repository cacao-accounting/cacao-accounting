# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1144: el plan AR/AP rechaza claves de idempotencia repetidas.

Una clave repetida dentro de la misma solicitud duplicaba el importe
planificado mientras el ejecutor aplicaba una sola línea. El plan debe
rechazarla antes de calcular importes.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from cacao_accounting import create_app
from cacao_accounting.config import configuracion
from cacao_accounting.database import database
from cacao_accounting.contabilidad.arap_allocation import (
    AllocationIdempotencyError,
    AllocationPlanner,
    AllocationRequest,
    ARAPOpenItem,
    OpenItemResolver,
)


@pytest.fixture
def allocation_scenario():
    """Create an open item worth 100 in its document currency."""
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
    item = ARAPOpenItem(
        document_id="INV-1",
        document_type="sales_invoice",
        currency="NIO",
        outstanding=Decimal("100"),
    )
    planner = AllocationPlanner(OpenItemResolver([item]))

    yield app, planner

    with app.app_context():
        database.session.remove()
        database.engine.dispose()


def _request(amount: str, key: str | None) -> AllocationRequest:
    """Build one allocation request for the test item."""
    return AllocationRequest(document_id="INV-1", amount=Decimal(amount), idempotency_key=key)


def test_duplicate_idempotency_keys_are_rejected(allocation_scenario):
    """Two lines with the same key cannot both enter the plan."""
    app, planner = allocation_scenario

    with app.app_context():
        with pytest.raises(AllocationIdempotencyError):
            planner.plan(
                Decimal("100"),
                "NIO",
                [_request("50", "PAY-1"), _request("50", "PAY-1")],
            )


def test_distinct_keys_plan_the_full_amount(allocation_scenario):
    """Distinct keys keep the documented multi-line plan."""
    app, planner = allocation_scenario

    with app.app_context():
        plan = planner.plan(
            Decimal("100"),
            "NIO",
            [_request("50", "PAY-1"), _request("50", "PAY-2")],
        )

    assert len(plan.lines) == 2
    assert plan.allocated_source_amount == Decimal("100")
    assert plan.remaining_source_amount == Decimal("0")


def test_repeated_key_already_applied_is_an_idempotent_replay(allocation_scenario):
    """Keys already applied are skipped, not counted twice nor rejected."""
    app, planner = allocation_scenario

    with app.app_context():
        plan = planner.plan(
            Decimal("100"),
            "NIO",
            [_request("50", "PAY-1"), _request("50", "PAY-1")],
            existing_keys={"PAY-1"},
        )

    assert plan.lines == ()
    assert plan.allocated_source_amount == Decimal("0")
