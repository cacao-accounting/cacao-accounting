# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""N14: una fila heredada sin `document_type` solo es su tipo base.

Notas de crédito, débito y devoluciones comparten el modelo de factura. Si una
fila histórica no declara subtipo, no debe autorizarse como una nota ni como
una devolución: solo como la factura base del modelo.
"""

from __future__ import annotations

from types import SimpleNamespace

from cacao_accounting.document_flow.repository import document_matches_type


def test_legacy_row_without_document_type_matches_only_the_base_type():
    """Una factura sin subtipo no se confunde con una nota de crédito."""
    legacy_invoice = SimpleNamespace(document_type=None)

    assert document_matches_type("sales_invoice", legacy_invoice) is True
    assert document_matches_type("sales_credit_note", legacy_invoice) is False
    assert document_matches_type("sales_debit_note", legacy_invoice) is False
    assert document_matches_type("sales_return", legacy_invoice) is False


def test_legacy_purchase_row_without_document_type_matches_only_the_base_type():
    """Una compra sin subtipo tampoco se confunde con una nota."""
    legacy_invoice = SimpleNamespace(document_type=None)

    assert document_matches_type("purchase_invoice", legacy_invoice) is True
    assert document_matches_type("purchase_credit_note", legacy_invoice) is False
