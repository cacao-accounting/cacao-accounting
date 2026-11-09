# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Una tasa de cierre faltante bloquea la revalorización.

Escenario de negocio (issue #2121): ``_converted_amount`` devolvía cero si no
había tasa, por lo que la corrida publicaba totales parciales en lugar de
bloquearse, contradiciendo la política multimoneda.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from types import SimpleNamespace

import pytest

from cacao_accounting.contabilidad.exchange_revaluation_service import (
    ExchangeRevaluationError,
    ExchangeRevaluationService,
)

FECHA = date(2026, 10, 31)


def test_la_misma_moneda_no_requiere_tasa():
    """Origin igual a destino usa tasa 1 sin consultar la base."""
    servicio = ExchangeRevaluationService()

    assert servicio._converted_amount(Decimal("10"), "NIO", "NIO", FECHA) == Decimal("10.0000")


def test_una_tasa_faltante_propaga_el_error(app):
    """Sin tasa de cierre no se devuelve cero silencioso."""
    with app.app_context():
        servicio = ExchangeRevaluationService()

        with pytest.raises(ExchangeRevaluationError, match="Falta tasa de cierre"):
            servicio._converted_amount(Decimal("10"), "USD", "NIO", FECHA)


def test_los_totales_convertidos_no_absorben_tasas_faltantes(app):
    """El acumulado de totales se bloquea en lugar de subestimar."""
    entrada = SimpleNamespace(
        credit=Decimal("25"),
        debit=Decimal("0"),
        account_id="GANANCIA",
        company_currency="USD",
    )
    resumen = SimpleNamespace(currency="NIO")
    defaults = SimpleNamespace(
        unrealized_exchange_gain_account_id="GANANCIA",
        unrealized_exchange_loss_account_id="PÉRDIDA",
    )

    with app.app_context():
        servicio = ExchangeRevaluationService()

        with pytest.raises(ExchangeRevaluationError, match="Falta tasa de cierre"):
            servicio._converted_totals([entrada], resumen, defaults, FECHA)
