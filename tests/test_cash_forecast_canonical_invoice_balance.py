# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Regresiones para no usar saldos cacheados en el pronóstico de facturas."""

from __future__ import annotations

# Service helper coverage intentionally exercises its internal projections.
# pylint: disable=protected-access

from datetime import date
from decimal import Decimal
from types import SimpleNamespace

import pytest
from sqlalchemy.exc import OperationalError

from cacao_accounting.bancos import cash_forecast_service
from cacao_accounting.database import CompanyParty, Party, PaymentTerms, database


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


@pytest.mark.usefixtures("entorno_contable")
def test_forecast_places_sales_and_purchase_balances_on_party_due_dates(monkeypatch):
    """AR and AP balances follow active party terms instead of their posting dates."""
    customer_terms = PaymentTerms(name="Forecast NET-60", due_days=60)
    supplier_terms = PaymentTerms(name="Forecast NET-30", due_days=30)
    database.session.add_all([customer_terms, supplier_terms])
    database.session.flush()
    customer_id = database.session.execute(database.select(Party.id).filter_by(code="CLI001")).scalar_one()
    supplier_id = database.session.execute(database.select(Party.id).filter_by(code="PRV001")).scalar_one()
    customer_link = database.session.execute(
        database.select(CompanyParty).filter_by(company="cacao", party_id=customer_id)
    ).scalar_one()
    supplier_link = database.session.execute(
        database.select(CompanyParty).filter_by(company="cacao", party_id=supplier_id)
    ).scalar_one()
    customer_link.payment_terms_id = customer_terms.id
    supplier_link.payment_terms_id = supplier_terms.id

    sales_invoice = SimpleNamespace(
        id="forecast-ar",
        customer_id=customer_id,
        supplier_id=None,
        posting_date=date(2026, 7, 1),
        due_date=None,
        balance=Decimal("100"),
        is_return=False,
    )
    purchase_invoice = SimpleNamespace(
        id="forecast-ap",
        customer_id=None,
        supplier_id=supplier_id,
        posting_date=date(2026, 7, 5),
        due_date=None,
        balance=Decimal("80"),
        is_return=False,
    )
    due_dates = cash_forecast_service._load_invoice_due_dates("cacao", [sales_invoice, purchase_invoice])
    monkeypatch.setattr(
        cash_forecast_service,
        "_invoice_forecast_amount",
        lambda invoice, _currency, _flow_date: (invoice.balance, invoice.balance),
    )

    assert due_dates == {"forecast-ar": date(2026, 8, 30), "forecast-ap": date(2026, 8, 4)}
    assert cash_forecast_service._compute_ar_ap_projections(
        "Projected",
        [sales_invoice],
        [purchase_invoice],
        date(2026, 7, 1),
        date(2026, 7, 31),
        "NIO",
        due_dates,
    ) == (Decimal("0"), Decimal("0"))
    assert cash_forecast_service._compute_ar_ap_projections(
        "Projected",
        [sales_invoice],
        [purchase_invoice],
        date(2026, 8, 1),
        date(2026, 8, 31),
        "NIO",
        due_dates,
    ) == (Decimal("100"), Decimal("80"))
