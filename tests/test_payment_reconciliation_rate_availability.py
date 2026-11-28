# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 William José Moreno Reyes

"""#1099: la conciliación multimoneda exige una tasa registrada.

Con monedas distintas entre documento y pago, la conciliación debe usar una
tasa positiva respaldada por una tasa registrada para la fecha; si falta, se
bloquea en vez de aceptar cualquier tasa arbitraria.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from cacao_accounting.document_flow import DocumentFlowError
from cacao_accounting.document_flow.payment import _require_available_reconciliation_rate

FECHA = date(2026, 5, 15)


def test_misma_moneda_no_requiere_tasa(entorno_contable):
    """Misma moneda es tasa 1 sin consultar el catálogo."""
    assert _require_available_reconciliation_rate("NIO", "NIO", Decimal("0"), FECHA) == Decimal("1")


def test_tasa_cero_se_rechaza(entorno_contable):
    """Una tasa no positiva no es válida para monedas distintas."""
    with pytest.raises(DocumentFlowError, match="tasa positiva"):
        _require_available_reconciliation_rate("USD", "NIO", Decimal("0"), FECHA)


def test_tasa_disponible_se_conserva(entorno_contable):
    """Una tasa declarada con respaldo registrado se conserva como efectiva."""
    tasa = _require_available_reconciliation_rate("USD", "NIO", Decimal("36.5"), FECHA)
    assert tasa == Decimal("36.5")


def test_tasa_inversa_disponible_se_acepta(entorno_contable):
    """El par inverso (NIO→USD) también respalda la conciliación."""
    tasa = _require_available_reconciliation_rate("NIO", "USD", Decimal("0.027397260"), FECHA)
    assert tasa > 0


def test_tasa_ausente_bloquea_la_conciliacion(entorno_contable):
    """Sin tasa registrada para el par, la conciliación se bloquea."""
    with pytest.raises(DocumentFlowError, match="No existe una tasa registrada"):
        _require_available_reconciliation_rate("EUR", "NIO", Decimal("1"), FECHA)


def test_tasa_divergente_usa_la_tasa_vigente(entorno_contable):
    """Una tasa declarada distinta no prevalece: se aplica la resuelta."""
    efectiva = _require_available_reconciliation_rate("USD", "NIO", Decimal("99"), FECHA)
    assert efectiva == Decimal("36.5")
