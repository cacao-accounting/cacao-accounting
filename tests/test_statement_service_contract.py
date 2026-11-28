# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1046: un único flujo de importación bancaria mantenido.

El servicio conserva matching, autoconciliación y ajuste por diferencia; el
importador legacy y sus helpers de parsing ya no deben reaparecer.
"""

from __future__ import annotations

from cacao_accounting.bancos import statement_service
from cacao_accounting.imports.adapters.bank_statement import BankStatementAdapter


def test_servicio_conserva_las_funciones_activas():
    """Matching, autoconciliación y ajuste siguen disponibles."""
    for nombre in ("apply_bank_matching_rule", "auto_reconcile_bank_transaction", "create_bank_difference_journal"):
        assert callable(getattr(statement_service, nombre)), nombre


def test_servicio_no_reintroduce_el_importador_legacy():
    """No vuelven el importador retirado ni sus helpers de parsing."""
    for retirado in ("import_bank_statement", "_parse_bank_statement_row", "_decimal_value", "_parse_date"):
        assert not hasattr(statement_service, retirado), retirado


def test_el_adaptador_vigente_es_el_unico_importador():
    """El adaptador del asistente compartido sigue siendo el flujo activo."""
    assert callable(BankStatementAdapter)
