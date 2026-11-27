# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Regresiones para no usar saldos cacheados en el pronóstico de facturas."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from types import SimpleNamespace

import pytest
from sqlalchemy.exc import OperationalError

from cacao_accounting.bancos import cash_forecast_service


def test_saldo_legacy_no_sustituye_al_subledger_canonico(monkeypatch) -> None:
    """El pronóstico usa el valor canónico aunque el objeto exponga caches distintos."""
    invoice = SimpleNamespace(
        outstanding_amount=Decimal("900"),
        base_outstanding_amount=Decimal("900"),
        transaction_currency="NIO",
    )
    monkeypatch.setattr(cash_forecast_service, "compute_outstanding_amount", lambda _invoice: Decimal("25"))

    assert cash_forecast_service._invoice_forecast_amount(invoice, "NIO", date(2026, 11, 20)) == (
        Decimal("25"),
        Decimal("25"),
    )


def test_falta_de_document_relation_no_se_oculta_con_cache_legacy(monkeypatch) -> None:
    """La ausencia de la fuente relacional canónica se propaga como error operativo."""
    invoice = SimpleNamespace(
        outstanding_amount=Decimal("900"),
        base_outstanding_amount=Decimal("900"),
        transaction_currency="NIO",
    )
    missing_relation_table = OperationalError(
        "SELECT ... FROM document_relation",
        {},
        RuntimeError("no such table: document_relation"),
    )

    def fail_canonical_lookup(_invoice):
        raise missing_relation_table

    monkeypatch.setattr(cash_forecast_service, "compute_outstanding_amount", fail_canonical_lookup)

    with pytest.raises(OperationalError) as error:
        cash_forecast_service._invoice_forecast_amount(invoice, "NIO", date(2026, 11, 20))

    assert error.value is missing_relation_table
