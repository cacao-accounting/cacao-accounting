# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Convert accounting-engine proformas into persisted GL entries."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from cacao_accounting.accounting_engine.common.context import CalculationContext, JournalEntryProforma
from cacao_accounting.contabilidad.posting import (
    PostingError,
    _add_entries,
    _create_gl_entry,
    _document_contexts,
)
from cacao_accounting.database import GLEntry


def post_proforma_to_gl(
    *,
    document: Any,
    context: CalculationContext,
    proforma: JournalEntryProforma,
    ledger_code: str | None = None,
) -> list[GLEntry]:
    """Persist a balanced pro-forma as real `GLEntry` rows."""
    if not proforma.lines:
        return []
    if not proforma.is_balanced:
        raise PostingError("El asiento pro-forma no balancea y no puede contabilizarse.")
    entries: list[GLEntry] = []
    for ledger_context in _document_contexts(document, ledger_code=ledger_code):
        for line in proforma.lines:
            account_id = str(line.account_id or "").strip()
            if not account_id:
                raise PostingError("Falta una cuenta contable requerida para contabilizar el asiento.")
            debit = Decimal(line.debit or Decimal("0"))
            credit = Decimal(line.credit or Decimal("0"))
            debit_in_account_currency = line.amount_transaction_currency if debit > 0 else None
            credit_in_account_currency = line.amount_transaction_currency if credit > 0 else None
            entries.append(
                _create_gl_entry(
                    context=ledger_context,
                    account_id=account_id,
                    debit=debit,
                    credit=credit,
                    debit_in_account_currency=debit_in_account_currency,
                    credit_in_account_currency=credit_in_account_currency,
                    party_type=context.party_type if line.party_id else None,
                    party_id=line.party_id,
                    cost_center_code=line.cost_center_id,
                    project_code=line.project_id,
                    entry_remarks=line.description or proforma.memo,
                )
            )
    return _add_entries(entries)
