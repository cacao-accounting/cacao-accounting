# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 William José Moreno Reyes

"""#1759: el prorrateo conserva el total sin asignar costos negativos."""

from __future__ import annotations

from decimal import Decimal

from cacao_accounting.accounting_engine.common.context import ItemContext
from cacao_accounting.accounting_engine.landed_cost.engine import LandedCostEngine


def _item(line_id: str, net_amount: Decimal = Decimal("100")) -> ItemContext:
    """Construye un contexto de inventario equivalente para el motor."""
    return ItemContext(
        line_id=line_id,
        item_id=line_id,
        description=f"Item {line_id}",
        quantity=Decimal("1"),
        unit_price=net_amount,
        gross_amount=net_amount,
        net_amount=net_amount,
    )


def _allocate(items, charge: Decimal, method: str):
    """Ejecuta un cargo capitalizable con la precisión de inventario."""
    return LandedCostEngine().calculate(
        items,
        [],
        capitalizable_charges=[{"amount": charge, "concept": "Cargo", "allocation_method": method}],
        allocation_method=method,
        rounding_policy={"precision": 4},
    )


def test_prorrateo_igual_no_genera_residuo_negativo():
    """Cuatro participaciones que redondean hacia arriba conservan un total positivo."""
    result = _allocate([_item("A"), _item("B"), _item("C"), _item("D")], Decimal("0.0002"), "equal")

    amounts = [allocation.allocated_costs[0]["amount"] for allocation in result.allocations]
    assert amounts == [Decimal("0.0001"), Decimal("0.0001"), Decimal("0.0000"), Decimal("0.0000")]
    assert all(amount >= 0 for amount in amounts)
    assert sum(amounts, Decimal("0")) == Decimal("0.0002")
    assert result.inventory_value_total == Decimal("400.0002")


def test_prorrateo_por_valor_conserva_total_y_unidades_enteras():
    """El resto mayor se asigna a la mayor fracción sin exceder el cargo."""
    result = _allocate(
        [_item("A", Decimal("1")), _item("B", Decimal("2")), _item("C", Decimal("3"))],
        Decimal("0.0001"),
        "by_value",
    )

    amounts = [allocation.allocated_costs[0]["amount"] for allocation in result.allocations]
    assert amounts == [Decimal("0.0000"), Decimal("0.0000"), Decimal("0.0001")]
    assert all(amount >= 0 for amount in amounts)
    assert sum(amounts, Decimal("0")) == Decimal("0.0001")
    assert result.inventory_value_total == Decimal("6.0001")
