"""Regression tests for atomic multi-ledger GL posting."""

from datetime import date
from decimal import Decimal
from unittest.mock import Mock, patch

import pytest

from cacao_accounting.accounting_engine.common.context import (
    CalculationContext,
    JournalEntryLineProforma,
    JournalEntryProforma,
)
from cacao_accounting.contabilidad.posting import PostingError


def test_multiledger_proforma_failure_persists_no_partial_entries():
    """A later ledger failure must occur before any GL entry is persisted."""
    from cacao_accounting.accounting_engine import gl_posting_builder

    context = CalculationContext(
        company_id="cacao",
        document_type="sales_invoice",
        event_type="submit",
        transaction_direction="sales",
        transaction_date=date(2026, 1, 1),
        posting_date=date(2026, 1, 1),
        party_type="customer",
        party_id="CUST-001",
        currency="NIO",
        company_currency="NIO",
    )
    first_ledger = Mock(company_currency="NIO")
    second_ledger = Mock(company_currency="USD")
    with (
        patch.object(gl_posting_builder, "_document_contexts", return_value=[first_ledger, second_ledger]),
        patch.object(
            gl_posting_builder,
            "_proforma_for_ledger",
            side_effect=[JournalEntryProforma(), PostingError("Libro secundario inválido")],
        ),
        patch.object(gl_posting_builder, "_add_entries") as add_entries,
    ):
        with pytest.raises(PostingError, match="Libro secundario inválido"):
            gl_posting_builder.post_proforma_to_gl(
                document=Mock(),
                context=context,
                proforma=JournalEntryProforma(
                    lines=[
                        JournalEntryLineProforma(account_id="A", debit=Decimal("1")),
                        JournalEntryLineProforma(account_id="B", credit=Decimal("1")),
                    ],
                    memo="El proforma de entrada sólo habilita el flujo de prueba.",
                ),
            )

    add_entries.assert_not_called()
