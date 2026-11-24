# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1863: el snapshot de auditoría de StockEntry cubre los campos que muta la edición.

La bitácora de un movimiento de inventario debe conservar el antes y el después
de bodegas, moneda, fechas, cuenta de ajuste, dimensiones y total, además de las
líneas. Esto permite reconciliar cada edición con el cambio real de la cabecera.
"""

import json
from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest
from flask import get_flashed_messages

from cacao_accounting.database import (
    Accounts,
    AuditTrail,
    CostCenter,
    Project,
    StockEntry,
    StockEntryItem,
    Unit,
    Warehouse,
    database,
)
from cacao_accounting.inventario import services as inventory_services


@pytest.fixture
def catalogo_edicion(app, entorno_contable):
    """Siembra una segunda bodega y dimensiones válidas para la edición."""
    sufijo = uuid4().hex[:8].upper()
    with app.app_context():
        database.session.add(Warehouse(code="BOD02", name="Bodega Secundaria", company="cacao", is_active=True))
        cuenta = Accounts(
            entity="cacao", code=f"AJ-{sufijo}", name="Ajuste inventario", active=True, enabled=True, group=False
        )
        centro = CostCenter(
            entity="cacao", code=f"CC{sufijo}", name="Centro inventario", active=True, enabled=True, group=False
        )
        unidad = Unit(entity="cacao", code=f"U{sufijo}", name="Unidad inventario", enabled=True)
        proyecto = Project(entity="cacao", code=f"P{sufijo}", name="Proyecto inventario", enabled=True)
        database.session.add_all([cuenta, centro, unidad, proyecto])
        database.session.commit()
        yield {
            "cuenta": cuenta.id,
            "centro": centro.code,
            "unidad": unidad.code,
            "proyecto": proyecto.code,
        }


def _seed_movimiento(app, purpose: str) -> str:
    """Crea un movimiento borrador con una línea y devuelve su identificador."""
    with app.app_context():
        entry = StockEntry(
            company="cacao",
            purpose=purpose,
            posting_date=date(2026, 5, 15),
            from_warehouse="BOD01",
            to_warehouse="BOD01",
            transaction_currency="NIO",
            base_currency="NIO",
            remarks="Cabecera original",
            total_amount=Decimal("20"),
        )
        database.session.add(entry)
        database.session.flush()
        database.session.add(
            StockEntryItem(
                stock_entry_id=entry.id,
                item_code="ART01",
                qty=Decimal("2"),
                uom="UND",
                qty_in_base_uom=Decimal("2"),
                basic_rate=Decimal("10"),
                amount=Decimal("20"),
            )
        )
        database.session.commit()
        return entry.id


def _editar(app, monkeypatch, entry_id: str, form_data: dict[str, str]):
    """Ejecuta el handler real de edición y devuelve el último AuditTrail."""
    monkeypatch.setattr(inventory_services, "_validate_stock_entry_company", lambda _value, _action: "cacao")
    with app.test_request_context("/inventory/stock-entry/test/edit", method="POST", data=form_data):
        respuesta = inventory_services._handle_stock_entry_edit_post(database.session.get(StockEntry, entry_id))
        assert respuesta is not None, f"La edición falló: {get_flashed_messages()}"
    with app.app_context():
        evento = database.session.execute(
            database.select(AuditTrail)
            .filter_by(document_type="stock_entry", document_id=entry_id, action="updated")
            .order_by(AuditTrail.timestamp.desc(), AuditTrail.id.desc())
            .limit(1)
        ).scalar_one()
        return json.loads(evento.changes_json), json.loads(evento.before_json), json.loads(evento.after_json)


def _formulario_base(purpose: str, **extra: str) -> dict[str, str]:
    """Datos mínimos del formulario con la línea persistida sin cambios."""
    form = {
        "purpose": purpose,
        "company": "cacao",
        "posting_date": "2026-05-16",
        "transaction_currency": "NIO",
        "from_warehouse": "BOD01",
        "to_warehouse": "BOD01",
        "remarks": "Cabecera editada",
        "item_code_0": "ART01",
        "qty_0": "2",
        "uom_0": "UND",
        "rate_0": "10",
        "amount_0": "20",
    }
    form.update(extra)
    return form


def test_edicion_registra_bodegas_moneda_y_fecha(app, catalogo_edicion, monkeypatch):
    """El cambio de bodegas, moneda y fecha queda en before/after por campo."""
    entry_id = _seed_movimiento(app, "material_receipt")
    cambios, antes, despues = _editar(
        app,
        monkeypatch,
        entry_id,
        _formulario_base(
            "material_receipt",
            from_warehouse="BOD02",
            to_warehouse="BOD02",
            transaction_currency="USD",
            posting_date="2026-05-20",
        ),
    )

    assert cambios["from_warehouse"] == {"before": "BOD01", "after": "BOD02"}
    assert cambios["to_warehouse"] == {"before": "BOD01", "after": "BOD02"}
    assert cambios["transaction_currency"] == {"before": "NIO", "after": "USD"}
    assert "base_currency" in antes and "base_currency" in despues
    assert cambios["posting_date"] == {"before": "2026-05-15", "after": "2026-05-20"}
    assert cambios["remarks"] == {"before": "Cabecera original", "after": "Cabecera editada"}
    assert antes["from_warehouse"] != despues["from_warehouse"]
    assert antes["items"] and despues["items"]


def test_edicion_conciliacion_registra_cuenta_dimensiones_y_total(app, catalogo_edicion, monkeypatch):
    """La edición de conciliación registra cuenta ajuste, dimensiones y total."""
    entry_id = _seed_movimiento(app, "stock_reconciliation")
    datos = _formulario_base(
        "stock_reconciliation",
        adjustment_account_id=catalogo_edicion["cuenta"],
        cost_center_code=catalogo_edicion["centro"],
        unit_code=catalogo_edicion["unidad"],
        project_code=catalogo_edicion["proyecto"],
        counted_qty_0="3",
        target_valuation_rate_0="10",
    )
    cambios, antes, despues = _editar(app, monkeypatch, entry_id, datos)

    assert cambios["adjustment_account_id"]["before"] is None
    assert cambios["adjustment_account_id"]["after"] == catalogo_edicion["cuenta"]
    assert cambios["cost_center_code"]["after"] == catalogo_edicion["centro"]
    assert cambios["unit_code"]["after"] == catalogo_edicion["unidad"]
    assert cambios["project_code"]["after"] == catalogo_edicion["proyecto"]
    assert Decimal(cambios["total_amount"]["before"]) == Decimal("20")
    assert Decimal(cambios["total_amount"]["after"]) > Decimal("20")
    assert antes["adjustment_account_id"] != despues["adjustment_account_id"]
    assert antes["cost_center_code"] != despues["cost_center_code"]
