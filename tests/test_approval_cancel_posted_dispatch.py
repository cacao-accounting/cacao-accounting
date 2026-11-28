# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1642: aprobar una anulacion ejecuta el cancel real del documento."""

from __future__ import annotations

from datetime import date
from types import SimpleNamespace

import pytest

from cacao_accounting import approval_engine
from cacao_accounting.approval_engine import ApprovalEngine


@pytest.mark.parametrize("doctype", ["import_landed_cost", "sales_debit_note"])
def test_cancel_posted_ejecuta_el_despacho_real(monkeypatch, doctype):
    """El dispatcher deja de ignorar costos de importacion y notas de debito."""
    llamadas: list[tuple[str, str]] = []

    def cancelar(tipo, documento, **_kwargs):
        llamadas.append((tipo, documento.id))

    monkeypatch.setattr(approval_engine, "_cancel_posted_document", cancelar)
    documento = SimpleNamespace(id=f"doc-{doctype}")
    usuario = SimpleNamespace(id="user-1")

    ApprovalEngine._execute_cancel(
        doctype,
        documento,
        usuario,
        reason="Anulacion aprobada",
        cancellation_date=date(2026, 5, 15),
        requested_at=None,
    )

    assert llamadas == [(doctype, f"doc-{doctype}")]


def test_tipos_estan_en_el_conjunto_de_documentos_posteados():
    """La validacion de motivo y el dispatcher reconocen ambos tipos."""
    assert "import_landed_cost" in approval_engine._POSTED_CANCEL_DOCTYPES
    assert "sales_debit_note" in approval_engine._POSTED_CANCEL_DOCTYPES
