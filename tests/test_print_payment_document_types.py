# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#2131: los tipos documentales de pago existen en el registro de impresión."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from cacao_accounting.printing.registry import get_printable_document, init_printing_registry
from cacao_accounting.printing.validation import _document_type


@pytest.mark.parametrize(
    ("payment_type", "esperado"),
    [
        ("internal_transfer", "bank_transfer"),
        ("receive", "cash_receipt"),
        ("pay", "payment_entry"),
    ],
)
def test_tipo_de_pago_esta_registrado(payment_type: str, esperado: str):
    """El contexto de validación no puede apuntar a un tipo inexistente."""
    init_printing_registry()
    documento = SimpleNamespace(__tablename__="payment_entry", payment_type=payment_type)

    tipo = _document_type(documento)

    assert tipo == esperado
    assert get_printable_document(tipo) is not None
