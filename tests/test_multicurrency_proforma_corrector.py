# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1817: el corrector de la pro-forma cancela el residual en moneda de compañía."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from cacao_accounting.accounting_engine.common.context import (
    AccountingReferences,
    CalculationContext,
    JournalEntryLineProforma,
)
from cacao_accounting.accounting_engine.orchestrator.mapper import AccountingMapper

TASA = Decimal("36.5")


def _contexto(**referencias: object) -> CalculationContext:
    """Contexto multimoneda de compra con compañía NIO y documento USD."""
    return CalculationContext(
        company_id="cacao",
        document_type="purchase_invoice",
        event_type="confirmation",
        transaction_direction="purchase",
        transaction_date=date(2026, 5, 15),
        posting_date=date(2026, 5, 15),
        party_type="supplier",
        party_id="proveedor-1",
        currency="USD",
        company_currency="NIO",
        exchange_rate=TASA,
        references=AccountingReferences(custom_references=dict(referencias)),
    )


def _descuadre() -> list[JournalEntryLineProforma]:
    """Pro-forma con 100 NIO de residual en moneda de compañía."""
    return [JournalEntryLineProforma(account_id="A1", debit=Decimal("100"), amount_company_currency=Decimal("100"))]


def test_corrector_de_redondeo_cancela_el_residual_real():
    """El corrector debe postear 100 NIO, no 100 escalado por la tasa."""
    contexto = _contexto(default_rounding_account_id="ACC-ROUND")

    proforma = AccountingMapper()._finalize_proforma(contexto, _descuadre())

    corrector = proforma.lines[-1]
    assert corrector.account_id == "ACC-ROUND"
    assert corrector.credit == Decimal("100")
    assert corrector.amount_company_currency == Decimal("100")
    assert corrector.amount_transaction_currency == Decimal("100") / TASA
    assert proforma.is_balanced


def test_corrector_de_anticipo_cancela_el_residual_real():
    """La rama de anticipo conserva la misma escala de compañía."""
    contexto = _contexto(advance_account_id="ACC-ADV", open_payment_amount="50")

    proforma = AccountingMapper()._finalize_proforma(contexto, _descuadre())

    corrector = proforma.lines[-1]
    assert corrector.account_id == "ACC-ADV"
    assert corrector.credit == Decimal("100")
    assert corrector.amount_company_currency == Decimal("100")
    assert proforma.is_balanced


def test_proforma_balanceada_no_agrega_corrector():
    """Sin residual no se inventa una línea correctora."""
    lineas = [
        JournalEntryLineProforma(account_id="A1", debit=Decimal("100"), amount_company_currency=Decimal("100")),
        JournalEntryLineProforma(account_id="A2", credit=Decimal("100"), amount_company_currency=Decimal("100")),
    ]

    proforma = AccountingMapper()._finalize_proforma(_contexto(default_rounding_account_id="ACC-ROUND"), lineas)

    assert len(proforma.lines) == 2
    assert proforma.is_balanced
