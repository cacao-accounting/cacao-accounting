# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""La exportación neutraliza fórmulas precedidas por controles.

Escenario de negocio (issue #1664): una descripción importada como
``"\\n=1+1"`` llegaba al CSV sin prefijo de texto; las hojas de cálculo pueden
interpretar el salto de línea y ejecutar la fórmula.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from cacao_accounting.reportes.helpers import _spreadsheet_value


@pytest.mark.parametrize(
    "valor",
    ["=1+1", "+cmd", "-2+3", "@SUM(A1)", "\n=1+1", "\r=1+1", "\t+cmd", " \u00a0@SUM(A1)", "\ufeff=1+1"],
)
def test_neutraliza_formulas_con_prefijos_de_control(valor):
    """El apóstrofo queda como primer carácter de la celda."""
    resultado = _spreadsheet_value(valor)

    assert isinstance(resultado, str)
    assert resultado.startswith("'")
    assert resultado[1:] == valor


def test_conserva_texto_normal_y_valores_no_texto():
    """No altera descripciones legítimas ni tipos numéricos."""
    assert _spreadsheet_value("Pago de servicios") == "Pago de servicios"
    assert _spreadsheet_value("Fecha 2026-10-15") == "Fecha 2026-10-15"
    assert _spreadsheet_value(Decimal("12.50")) == Decimal("12.50")
    assert _spreadsheet_value(None) is None
