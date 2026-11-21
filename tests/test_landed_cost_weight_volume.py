# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1758: prorrateo por peso y volumen del costo de importación."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest

from cacao_accounting.accounting_engine.common.context import ItemContext
from cacao_accounting.accounting_engine.landed_cost.engine import LandedCostEngine
from cacao_accounting.compras.services import (
    _landed_cost_dimension,
    _save_import_landed_cost_charges,
    _save_import_landed_cost_items,
)
from cacao_accounting.contabilidad.posting_service import PostingError, _post_with_calculation_engine_payload
from cacao_accounting.database import ImportLandedCost, ImportLandedCostItem, Item, PurchaseInvoice, UOM, database


def _item(line_id: str, weight: str, volume: str = "0") -> ItemContext:
    """Construye una línea de inventario con dimensiones explícitas."""
    return ItemContext(
        line_id=line_id,
        item_id=line_id,
        description=line_id,
        quantity=Decimal("1"),
        unit_price=Decimal("10"),
        gross_amount=Decimal("10"),
        net_amount=Decimal("10"),
        weight=Decimal(weight),
        volume=Decimal(volume),
    )


@pytest.mark.parametrize(
    ("method", "first_dimension", "second_dimension", "first_share", "second_share"),
    [
        ("by_weight", "2", "3", Decimal("40"), Decimal("60")),
        ("by_volume", "1", "4", Decimal("20"), Decimal("80")),
    ],
)
def test_el_motor_prorratea_por_peso_y_volumen(method, first_dimension, second_dimension, first_share, second_share):
    """La distribución usa la dimensión correspondiente y conserva el total."""
    items = [
        _item("A", first_dimension, first_dimension),
        _item("B", second_dimension, second_dimension),
    ]
    result = LandedCostEngine().calculate(
        items,
        [],
        [{"amount": Decimal("100"), "concept": "Flete", "allocation_method": method}],
        allocation_method=method,
    )

    costos = {allocation.item_line_id: allocation.final_inventory_cost for allocation in result.allocations}
    assert costos["A"] == Decimal("10") + first_share
    assert costos["B"] == Decimal("10") + second_share
    assert sum(costos.values(), Decimal("0")) == Decimal("120")


def test_el_motor_rechaza_una_base_vacia():
    """Sin dimensión positiva no se elige una línea arbitraria."""
    with pytest.raises(ValueError, match="base positiva"):
        LandedCostEngine().calculate(
            [_item("A", "0"), _item("B", "0")],
            [],
            [{"amount": Decimal("100"), "concept": "Flete", "allocation_method": "by_weight"}],
            allocation_method="by_weight",
        )


@pytest.mark.parametrize("raw_value", ["NaN", "no-numérico"])
def test_dimension_invalida_se_rechaza_como_error_de_validacion(app, raw_value):
    """Entradas manipuladas no dejan escapar InvalidOperation ni valores no finitos."""
    with app.app_context():
        with pytest.raises(ValueError):
            _landed_cost_dimension({"weight": raw_value}, None, "weight")


@pytest.mark.parametrize("raw_amount", ["NaN", "Infinity", "no-numérico"])
def test_importe_invalido_de_cargo_se_rechaza(app, entorno_contable, raw_amount):
    """Cargos manipulados no aceptan valores no finitos ni escapan como 500."""
    with app.app_context():
        document = _seed_landed_cost()
        with app.test_request_context(
            method="POST",
            data={"charge_concept_0": "Flete", "charge_amount_0": raw_amount},
        ):
            with pytest.raises(ValueError):
                _save_import_landed_cost_charges(document)


def _seed_landed_cost() -> ImportLandedCost:
    """Crea un documento borrador para probar la persistencia de dimensiones."""
    invoice = PurchaseInvoice(
        company="cacao",
        document_type="purchase_invoice",
        document_no=f"PI-{uuid4().hex[:8]}",
        posting_date=date(2026, 5, 20),
        docstatus=1,
    )
    database.session.add(invoice)
    database.session.flush()
    documento = ImportLandedCost(
        purchase_invoice_id=invoice.id,
        company="cacao",
        posting_date=date(2026, 5, 20),
        document_type="import_landed_cost",
        allocation_method="by_weight",
        exchange_rate=Decimal("1"),
    )
    database.session.add(documento)
    database.session.commit()
    return documento


def test_persiste_peso_y_volumen_por_linea(app, entorno_contable):
    """La línea conserva la dimensión y la unidad usadas en el documento."""
    with app.app_context():
        codigo = f"DIM-{uuid4().hex[:6].upper()}"
        database.session.add(
            Item(
                code=codigo,
                name="Artículo con dimensiones",
                item_type="goods",
                is_stock_item=True,
                default_uom="UND",
                weight=Decimal("2.5"),
                weight_uom="UND",
                volume=Decimal("0.5"),
                volume_uom="UND",
            )
        )
        database.session.commit()
        documento = _seed_landed_cost()

        with app.test_request_context(
            method="POST",
            data={
                "item_item_code_0": codigo,
                "item_qty_0": "2",
                "item_uom_0": "UND",
                "item_rate_0": "10",
                "item_weight_0": "",
                "item_weight_uom_0": "",
                "item_volume_0": "3",
                "item_volume_uom_0": "UND",
            },
        ):
            _save_import_landed_cost_items(documento)
            database.session.commit()

        linea = database.session.execute(
            database.select(ImportLandedCostItem).filter_by(import_landed_cost_id=documento.id)
        ).scalar_one()
        assert linea.weight == Decimal("2.5")
        assert linea.weight_uom == "UND"
        assert linea.volume == Decimal("3")
        assert linea.volume_uom == "UND"


def test_rechaza_unidades_mixtas(app, entorno_contable):
    """Peso o volumen con unidades distintas no producen una base ambigua."""
    with app.app_context():
        for code in ("U-KG", "U-LB"):
            exists = database.session.execute(database.select(UOM).filter_by(code=code)).scalar_one_or_none()
            if exists is None:
                database.session.add(UOM(code=code, name=code))
        for code in ("MIX-A", "MIX-B"):
            exists = database.session.execute(database.select(Item).filter_by(code=code)).scalar_one_or_none()
            if exists is None:
                database.session.add(Item(code=code, name=code, item_type="goods", is_stock_item=True, default_uom="UND"))
        database.session.commit()
        documento = _seed_landed_cost()

        with app.test_request_context(
            method="POST",
            data={
                "item_item_code_0": "MIX-A",
                "item_qty_0": "1",
                "item_uom_0": "UND",
                "item_rate_0": "10",
                "item_weight_0": "1",
                "item_weight_uom_0": "U-KG",
                "item_weight_uom_1": "U-LB",
                "item_item_code_1": "MIX-B",
                "item_qty_1": "1",
                "item_uom_1": "UND",
                "item_rate_1": "10",
                "item_weight_1": "2",
            },
        ):
            with pytest.raises(ValueError, match="misma unidad de peso"):
                _save_import_landed_cost_items(documento)
            database.session.rollback()


def test_error_del_motor_se_traduce_a_posting_error(monkeypatch):
    """Un fallo de base del motor no escapa como ValueError/500."""
    from cacao_accounting.accounting_engine import document_builders
    from cacao_accounting.accounting_engine.orchestrator import event_orchestrator

    class _Boom:
        def handle_event(self, _context):
            raise ValueError("No existe una base positiva")

    monkeypatch.setattr(document_builders, "build_calculation_context", lambda _document: object())
    monkeypatch.setattr(event_orchestrator, "BusinessEventOrchestrator", _Boom)

    with pytest.raises(PostingError, match="base positiva"):
        _post_with_calculation_engine_payload(object())


def test_el_formulario_habilita_las_dimensiones(client, reference_users):
    """El costo de importación activa las columnas de peso y volumen."""
    with client.session_transaction() as session:
        session["_user_id"] = str(reference_users["admin"].id)
        session["_fresh"] = True

    response = client.get("/buying/import-landed-cost/new?company=alpha&posting_date=2026-10-31")

    assert response.status_code == 200
    assert '"enableDimensions": true' in response.get_data(as_text=True)
