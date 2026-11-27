# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 William José Moreno Reyes

"""#1471: fechas ambiguas del extracto se rechazan, no se interpretan por orden."""

from __future__ import annotations

from cacao_accounting.imports.adapters.bank_statement import BankStatementAdapter


def _row(bank_account_id: str, posting_date: str) -> dict:
    return {
        "bank_account_id": bank_account_id,
        "posting_date": posting_date,
        "reference_number": "REF-1471",
        "description": "Movimiento de prueba",
        "deposit": "10",
        "withdrawal": "",
    }


def test_fechas_con_barras_se_rechazan_1471(app, entorno_contable):
    """DD/MM, MM/DD y fechas no ambiguas con barra se rechazan sin interpretar."""
    del entorno_contable
    adapter = BankStatementAdapter()
    with app.app_context():
        for fecha in ("04/05/2026", "13/05/2026", "05/13/2026", "04-05-2026"):
            errors = adapter.validate_row(_row("Cuenta-inexistente", fecha))
            assert any("Fecha bancaria inválida" in error for error in errors), fecha


def test_fecha_iso_conserva_compatibilidad_1471(app, entorno_contable):
    """El formato explícito ISO sigue aceptándose por el validador de fecha."""
    del entorno_contable
    adapter = BankStatementAdapter()
    with app.app_context():
        errors = adapter.validate_row(_row("cuenta-inexistente", "2026-05-04"))
        assert any("Cuenta bancaria no encontrada" in error for error in errors)
        assert not any("Fecha bancaria inválida" in error for error in errors)
