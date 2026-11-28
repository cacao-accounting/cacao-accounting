# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 William José Moreno Reyes

"""#1450: la importación y el guardado conservan bodegas por línea."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from sqlalchemy import select

from cacao_accounting.database import NamingSeries, StockEntry, StockEntryItem, User, Warehouse, database
from cacao_accounting.document_identifiers import ensure_default_naming_series_for_company


def _cliente(app):
    """Cliente autenticado sobre la base aislada del escenario."""
    client = app.test_client()
    with app.app_context():
        admin_id = str(database.session.execute(select(User.id).filter_by(user="admin")).scalar_one())
    with client.session_transaction() as session:
        session["_user_id"] = admin_id
        session["_fresh"] = True
    return client


def _series_id() -> str:
    """Devuelve la serie de stock entry del escenario aislado."""
    ensure_default_naming_series_for_company("cacao", ["stock_entry"])
    database.session.commit()
    return str(
        database.session.execute(select(NamingSeries.id).filter_by(entity_type="stock_entry", company="cacao")).scalar_one()
    )


def _payload(series_id: str, marker: str, targets: tuple[str, str]) -> dict[str, str]:
    """Transferencia con bodegas de línea distintas a las del encabezado."""
    data = {
        "purpose": "material_transfer",
        "company": "cacao",
        "naming_series": series_id,
        "posting_date": "2026-05-15",
        "transaction_currency": "NIO",
        "from_warehouse": "BOD01",
        "to_warehouse": "BOD01",
        "remarks": marker,
    }
    for index, target in enumerate(targets):
        data.update(
            {
                f"item_code_{index}": "ART01",
                f"qty_{index}": "1",
                f"rate_{index}": "10",
                f"uom_{index}": "UND",
                f"source_warehouse_{index}": "BOD01",
                f"target_warehouse_{index}": target,
            }
        )
    return data


def test_grid_publica_bodegas_de_linea_1450():
    """El grid emite los campos source/target que consume el guardado."""
    template = Path(__file__).parents[1] / "cacao_accounting/templates/transaction_form_macros.html"
    content = template.read_text(encoding="utf-8")
    assert ":name=\"'source_warehouse_' + index\"" in content
    assert ":name=\"'target_warehouse_' + index\"" in content
    assert 'x-model="line.source_warehouse"' in content
    assert 'x-model="line.target_warehouse"' in content


def test_transferencia_guarda_bodegas_distintas_por_linea(entorno_contable_aislado):
    """Las bodegas importadas prevalecen sobre el encabezado y persisten."""
    app = entorno_contable_aislado.app
    marker = f"SE-WH-{uuid4().hex[:8]}"
    with app.app_context():
        for code in ("BOD1450B", "BOD1450C"):
            if database.session.execute(select(Warehouse).filter_by(code=code)).scalar_one_or_none() is None:
                database.session.add(Warehouse(code=code, name=code, company="cacao", is_active=True))
        database.session.commit()
        series_id = _series_id()

    client = _cliente(app)
    form = client.get("/inventory/stock-entry/material-transfer/new")
    assert form.status_code == 200
    assert '"showLineWarehouses": true' in form.get_data(as_text=True)

    response = client.post(
        "/inventory/stock-entry/material-transfer/new",
        data=_payload(series_id, marker, ("BOD1450B", "BOD1450C")),
    )

    assert response.status_code == 302
    with app.app_context():
        entry = database.session.execute(select(StockEntry).filter_by(remarks=marker)).scalar_one()
        lines = list(database.session.execute(select(StockEntryItem).filter_by(stock_entry_id=entry.id)).scalars().all())
        assert len(lines) == 2
        assert {line.source_warehouse for line in lines} == {"BOD01"}
        assert {line.target_warehouse for line in lines} == {"BOD1450B", "BOD1450C"}


def test_transferencia_rechaza_bodega_inactiva_por_linea(entorno_contable_aislado):
    """Una bodega inválida no deja una entrada parcialmente guardada."""
    app = entorno_contable_aislado.app
    marker = f"SE-WH-BAD-{uuid4().hex[:8]}"
    with app.app_context():
        database.session.add(Warehouse(code="BOD1450X", name="Bodega inactiva", company="cacao", is_active=False))
        database.session.commit()
        series_id = _series_id()

    response = _cliente(app).post(
        "/inventory/stock-entry/material-transfer/new",
        data=_payload(series_id, marker, ("BOD1450X", "BOD01")),
    )

    assert response.status_code == 200
    assert "La bodega BOD1450X está inactiva." in response.get_data(as_text=True)
    with app.app_context():
        assert database.session.execute(select(StockEntry).filter_by(remarks=marker)).scalar_one_or_none() is None
