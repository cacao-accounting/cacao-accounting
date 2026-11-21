# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#2083: una transferencia interna no alerta como pago duplicado."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from types import SimpleNamespace

from cacao_accounting.bancos import services as bank_services
from cacao_accounting.database import PaymentEntry, database


def test_transferencia_interna_no_busca_pagos_similares(app, entorno_contable, monkeypatch):
    """La alerta de duplicados omite `internal_transfer` antes de consultar."""
    with app.app_context():
        database.session.add(
            PaymentEntry(
                company="cacao",
                payment_type="receive",
                posting_date=date(2026, 5, 15),
                received_amount=Decimal("100"),
                paid_amount=Decimal("0"),
                currency="NIO",
                docstatus=1,
                party_id=None,
            )
        )
        database.session.commit()

    llamadas: list[tuple] = []
    monkeypatch.setattr(bank_services, "flash", lambda *args, **kwargs: llamadas.append(args))
    transferencia = SimpleNamespace(
        payment_type="internal_transfer",
        paid_amount=Decimal("0"),
        received_amount=Decimal("100"),
        posting_date=date(2026, 5, 15),
        company="cacao",
        party_id=None,
        currency="NIO",
        id="TRANSFER-1",
    )

    with app.test_request_context("/"):
        bank_services._warn_duplicate_payment(transferencia)

    assert llamadas == []
