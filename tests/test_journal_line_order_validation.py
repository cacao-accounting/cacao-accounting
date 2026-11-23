# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1933: un orden de línea no numérico es error de validación, no 500."""

from __future__ import annotations

import json
from uuid import uuid4

import pytest

from cacao_accounting.contabilidad.journal_service import JournalValidationError, _normalize_line


def test_orden_no_numerico_levanta_error_de_validacion():
    """El parser convierte ValueError en JournalValidationError."""
    with pytest.raises(JournalValidationError, match="orden"):
        _normalize_line({"order": "primera", "account": "5101", "debit": "1", "credit": "0"}, 1)


@pytest.mark.parametrize("order", [True, False, 1.9, 2.0, [], {}])
def test_orden_no_entero_no_se_coerce(order):
    """Booleanos, fracciones y otros tipos no deben convertirse silenciosamente."""
    with pytest.raises(JournalValidationError, match="orden"):
        _normalize_line({"order": order, "account": "5101", "debit": "1", "credit": "0"}, 1)


def test_orden_entero_enviado_como_texto_se_acepta():
    """El formato entero enviado por formularios HTML conserva compatibilidad."""
    line = _normalize_line({"order": "2", "account": "5101", "debit": "1", "credit": "0"}, 1)

    assert line.order == 2


def test_endpoint_rechaza_orden_invalido_sin_persistir_y_acepta_orden_valido(entorno_contable_aislado):
    """La ruta valida el payload antes de crear borradores y mantiene el flujo válido."""
    from sqlalchemy import inspect, select

    from cacao_accounting.database import ComprobanteContable, database

    app = entorno_contable_aislado.app
    admin_id = inspect(entorno_contable_aislado.admin_user).identity[0]
    client = app.test_client()
    with client.session_transaction() as session:
        session["_user_id"] = str(admin_id)
        session["_fresh"] = True
    reference = f"ORDER-VALIDATION-{uuid4().hex[:10]}"
    payload = {
        "company": "cacao",
        "posting_date": "2026-05-15",
        "books": ["DEFAULT_BOOK"],
        "reference": reference,
        "transaction_currency": "NIO",
        "base_currency": "NIO",
        "exchange_rate": "1",
        "lines": [
            {"order": "not-an-integer", "account": "1101", "debit": "100", "credit": ""},
            {"order": 2, "account": "4101", "debit": "", "credit": "100"},
        ],
    }

    invalid_response = client.post("/accounting/journal/new", data={"journal_payload": json.dumps(payload)})

    assert invalid_response.status_code == 200
    assert b"orden" in invalid_response.data.lower()
    with app.app_context():
        assert (
            database.session.execute(select(ComprobanteContable.id).where(ComprobanteContable.reference == reference)).first()
            is None
        )

    payload["lines"][0]["order"] = "1"
    valid_response = client.post("/accounting/journal/new", data={"journal_payload": json.dumps(payload)})

    assert valid_response.status_code == 302
    with app.app_context():
        journal = database.session.execute(
            select(ComprobanteContable).where(ComprobanteContable.reference == reference)
        ).scalar_one()
        assert journal.status == "draft"
