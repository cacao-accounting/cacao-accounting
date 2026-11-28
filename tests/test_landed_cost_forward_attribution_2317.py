# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 William José Moreno Reyes

"""#2317: las salidas registran qué parte del costo capitalizado consumieron.

La atribución es forward-only: al aplicar una capa de solo valor (landed cost)
sobre la cola FIFO, cada unidad queda marcada con su share. Las salidas nuevas
publican ese share en ``consumed_layers`` para que una cancelación posterior
pueda separar inventario remanente de costo consumido. Los datos históricos sin
esta evidencia siguen bloqueados.
"""

from __future__ import annotations

from decimal import Decimal

from cacao_accounting.contabilidad.posting_service import (
    _fifo_valuation,
    _moving_average_valuation,
    _process_valuation_layer,
)


def _queue_with_landed() -> list:
    """Cola con 10 unidades a 10 y una capa de costo capitalizado de 50."""
    queue, negative, _ = _process_valuation_layer(
        [], Decimal("0"), Decimal("10"), Decimal("10"), Decimal("100"), layer_id="base"
    )
    assert negative == 0
    queue, _, _ = _process_valuation_layer(queue, Decimal("0"), Decimal("0"), Decimal("0"), Decimal("50"), layer_id="landed")
    return queue


def test_fifo_parcial_registra_el_share_capitalizado():
    """Consumir 4 de 10 unidades atribuye 20 del costo capitalizado."""
    cost, rate, _source, composition = _fifo_valuation(_queue_with_landed(), Decimal("4"))

    assert cost == Decimal("60")
    assert rate == Decimal("15")
    assert Decimal(composition[0]["landed_costs"]["landed"]) == Decimal("20")
    assert composition[0]["qty"] == "4"


def test_fifo_total_atribuye_todo_el_costo_capitalizado():
    """Al consumir toda la existencia se atribuye el importe completo."""
    cost, _rate, _source, composition = _fifo_valuation(_queue_with_landed(), Decimal("10"))

    assert cost == Decimal("150")
    assert Decimal(composition[0]["landed_costs"]["landed"]) == Decimal("50")


def test_promedio_movil_reparte_el_costo_por_cantidad():
    """En promedio móvil el share consumido es proporcional a la cantidad."""
    available = _queue_with_landed()
    total = sum((entry[1] for entry in available), Decimal("0"))

    cost, rate, composition = _moving_average_valuation(available, total, Decimal("4"))

    assert cost == Decimal("60")
    assert rate == Decimal("15")
    assert Decimal(composition[0]["landed_costs"]["landed"]) == Decimal("20")


def test_sin_capa_capitalizada_no_se_inventa_atribucion():
    """Una salida sin landed cost no publica landed_costs."""
    queue, _, _ = _process_valuation_layer([], Decimal("0"), Decimal("10"), Decimal("10"), Decimal("100"), layer_id="base")

    _cost, _rate, _source, composition = _fifo_valuation(queue, Decimal("4"))

    assert "landed_costs" not in composition[0]
