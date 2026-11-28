# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 William José Moreno Reyes

"""#1471: fechas ambiguas del extracto se rechazan, no se interpretan por orden."""

from __future__ import annotations

from datetime import date

import pytest

from cacao_accounting.imports.adapters.bank_statement import BankStatementAdapter
from cacao_accounting.imports.utils.dates import parse_import_date


def _row(bank_account_id: str, posting_date: str) -> dict:
    return {
        "bank_account_id": bank_account_id,
        "posting_date": posting_date,
        "reference_number": "REF-1471",
        "description": "Movimiento de prueba",
        "deposit": "10",
        "withdrawal": "",
    }


def test_fecha_ambigua_se_rechaza_1471(app, entorno_contable):
    """Una fecha válida como DD/MM y MM/DD no se interpreta por orden."""
    del entorno_contable
    adapter = BankStatementAdapter()
    with app.app_context():
        for fecha in ("04/05/2026", "04-05-2026"):
            errors = adapter.validate_row(_row("Cuenta-inexistente", fecha))
            assert any("Fecha bancaria inválida" in error for error in errors), fecha
    with pytest.raises(ValueError):
        parse_import_date("04/05/2026", field="fecha bancaria")


@pytest.mark.parametrize(
    ("value", "expected"),
    [("13/05/2026", date(2026, 5, 13)), ("05/13/2026", date(2026, 5, 13))],
)
def test_fecha_no_ambigua_se_conserva_1471(app, entorno_contable, value: str, expected: date):
    """DD/MM y MM/DD siguen admitidos cuando solo uno es válido."""
    del entorno_contable
    assert parse_import_date(value, field="fecha bancaria") == expected
    adapter = BankStatementAdapter()
    with app.app_context():
        errors = adapter.validate_row(_row("Cuenta-inexistente", value))
        assert any("Cuenta bancaria no encontrada" in error for error in errors)
        assert not any("Fecha bancaria inválida" in error for error in errors)


def test_fecha_iso_conserva_compatibilidad_1471(app, entorno_contable):
    """El formato explícito ISO sigue aceptándose por el validador de fecha."""
    del entorno_contable
    adapter = BankStatementAdapter()
    with app.app_context():
        errors = adapter.validate_row(_row("cuenta-inexistente", "2026-05-04"))
        assert any("Cuenta bancaria no encontrada" in error for error in errors)
        assert not any("Fecha bancaria inválida" in error for error in errors)
