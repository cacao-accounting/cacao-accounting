# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1614: el saldo AR/AP respeta el corte histórico del documento."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

from cacao_accounting.document_flow.payment import compute_outstanding_amount


def test_documento_posterior_al_corte_no_aporta_saldo(app):
    """Una factura futura no existe para un corte anterior a su fecha."""
    documento = SimpleNamespace(
        id=str(uuid4()),
        company="cacao",
        document_type="sales_invoice",
        posting_date=date(2026, 12, 1),
        grand_total=Decimal("100"),
        outstanding_amount=Decimal("100"),
        base_grand_total=Decimal("100"),
        base_outstanding_amount=Decimal("100"),
        is_return=False,
    )

    with app.app_context():
        assert compute_outstanding_amount(documento, as_of_date=date(2026, 11, 1)) == Decimal("0")
        assert compute_outstanding_amount(documento, as_of_date=date(2026, 12, 1)) == Decimal("100.0000")
        assert compute_outstanding_amount(documento, as_of_date=date(2027, 1, 1)) == Decimal("100.0000")
