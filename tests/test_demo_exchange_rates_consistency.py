# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#2170: las tasas demo son consistentes entre USD, EUR y NIO."""

from __future__ import annotations

from decimal import Decimal

from cacao_accounting.datos.dev.data import _make_tasas_de_cambio


def test_tasa_directa_usd_eur_concuerda_con_las_tasas_a_nio():
    """La conversión directa y la triangular deben dar el mismo importe."""
    rates = {(item.origin, item.destination): Decimal(str(item.rate)) for item in _make_tasas_de_cambio()}

    usd_to_nio = rates[("USD", "NIO")]
    eur_to_nio = rates[("EUR", "NIO")]
    usd_to_eur = rates[("USD", "EUR")]

    assert usd_to_eur == (usd_to_nio / eur_to_nio).quantize(Decimal("0.000000001"))
    assert usd_to_eur < 1
    assert usd_to_eur != Decimal("1.0954")
    assert abs((usd_to_eur * eur_to_nio) - usd_to_nio) < Decimal("0.000001")


def test_las_tasas_demo_comparten_la_fecha_de_referencia():
    """Los tres pares se publican a la misma fecha para poder triangular."""
    rates = _make_tasas_de_cambio()

    assert len({item.date for item in rates}) == 1
