# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1933: un orden de línea no numérico es error de validación, no 500."""

from __future__ import annotations

import pytest

from cacao_accounting.contabilidad.journal_service import JournalValidationError, _normalize_line


def test_orden_no_numerico_levanta_error_de_validacion():
    """El parser convierte ValueError en JournalValidationError."""
    with pytest.raises(JournalValidationError, match="orden"):
        _normalize_line({"order": "primera", "account": "5101", "debit": "1", "credit": "0"}, 1)
