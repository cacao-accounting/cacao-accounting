# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1870 #2344: shortcuts y edición de StockEntry conservan título del propósito."""

from __future__ import annotations

from datetime import date
from uuid import uuid4

import pytest

from cacao_accounting.database import StockEntry, User, database


def test_shortcut_material_receipt_muestra_titulo_especifico(app, authenticated_client):
    client = authenticated_client("admin")
    response = client.get("/inventory/stock-entry/material-receipt/new")
    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert "Nueva Recepción de Material" in body
    assert "Nueva Entrada de Almacén - " not in body


def test_shortcut_inventory_issue_muestra_titulo_especifico(app, authenticated_client):
    client = authenticated_client("admin")
    response = client.get("/inventory/stock-entry/inventory-issue/new")
    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert "Nuevo Ajuste Negativo de Inventario" in body


def test_edicion_conciliacion_usa_titulo_editar(app, authenticated_client):
    with app.app_context():
        entry = StockEntry(
            company="cacao",
            purpose="stock_reconciliation",
            posting_date=date(2026, 5, 15),
            transaction_currency="NIO",
            base_currency="NIO",
            document_no=f"SR-{uuid4().hex[:8]}",
            docstatus=0,
        )
        database.session.add(entry)
        database.session.commit()
        entry_id = entry.id
    client = authenticated_client("admin")
    response = client.get(f"/inventory/stock-entry/{entry_id}/edit")
    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert "Editar Conciliación de Inventario" in body
    assert "Nueva Conciliación de Inventario - " not in body


PROPOSITOS = {
    "material_receipt": (
        "/inventory/stock-entry/material-receipt/new",
        "Nueva Recepción de Material",
        "Editar Recepción de Material",
        "New Material Receipt",
        "Edit Material Receipt",
    ),
    "material_issue": (
        "/inventory/stock-entry/material-issue/new",
        "Nueva Salida de Material",
        "Editar Salida de Material",
        "New Material Issue",
        "Edit Material Issue",
    ),
    "material_transfer": (
        "/inventory/stock-entry/material-transfer/new",
        "Nueva Transferencia de Material",
        "Editar Transferencia de Material",
        "New Material Transfer",
        "Edit Material Transfer",
    ),
    "stock_reconciliation": (
        "/inventory/stock-entry/reconciliation/new",
        "Nueva Conciliación de Inventario",
        "Editar Conciliación de Inventario",
        "New Inventory Reconciliation",
        "Edit Inventory Reconciliation",
    ),
    "adjustment_positive": (
        "/inventory/stock-entry/adjustment-positive/new",
        "Nuevo Ajuste Positivo de Inventario",
        "Editar Ajuste Positivo de Inventario",
        "New Positive Inventory Adjustment",
        "Edit Positive Inventory Adjustment",
    ),
    "adjustment_negative": (
        "/inventory/stock-entry/inventory-issue/new",
        "Nuevo Ajuste Negativo de Inventario",
        "Editar Ajuste Negativo de Inventario",
        "New Negative Inventory Adjustment",
        "Edit Negative Inventory Adjustment",
    ),
}


def _crear_entrada(app, purpose: str) -> str:
    """Crea un StockEntry en borrador para el propósito indicado."""
    with app.app_context():
        entry = StockEntry(
            company="cacao",
            purpose=purpose,
            posting_date=date(2026, 5, 15),
            transaction_currency="NIO",
            base_currency="NIO",
            document_no=f"SE-{uuid4().hex[:8]}",
            docstatus=0,
        )
        database.session.add(entry)
        database.session.commit()
        return entry.id


def _eliminar_entrada(app, entry_id: str) -> None:
    """Retira el borrador temporal de la base compartida del worker."""
    with app.app_context():
        entry = database.session.get(StockEntry, entry_id)
        if entry is not None:
            database.session.delete(entry)
            database.session.commit()


@pytest.mark.parametrize("purpose", sorted(PROPOSITOS))
def test_alta_de_cada_proposito_muestra_titulo_especifico(app, authenticated_client, purpose):
    """El alta de cada propósito usa su título traducido y no el genérico."""
    ruta, esperado_nuevo, _, _, _ = PROPOSITOS[purpose]
    response = authenticated_client("admin").get(ruta)

    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert f"<title>{esperado_nuevo} - Cacao Accounting</title>" in body
    assert esperado_nuevo in body


@pytest.mark.parametrize("purpose", sorted(PROPOSITOS))
def test_edicion_de_cada_proposito_no_se_presenta_como_nueva(app, authenticated_client, purpose):
    """La edición identifica la operación y nunca aparece como alta."""
    _, esperado_nuevo, esperado_edicion, _, _ = PROPOSITOS[purpose]
    entry_id = _crear_entrada(app, purpose)
    try:
        response = authenticated_client("admin").get(f"/inventory/stock-entry/{entry_id}/edit")
        assert response.status_code == 200
        body = response.get_data(as_text=True)
        assert f"<title>{esperado_edicion} - Cacao Accounting</title>" in body
        assert f"{esperado_nuevo} - Cacao Accounting" not in body
    finally:
        _eliminar_entrada(app, entry_id)


def _con_idioma_ingles(app, reference_users):
    """Cambia el idioma del administrador y devuelve el valor anterior."""
    with app.app_context():
        usuario = database.session.get(User, str(reference_users["admin"].id))
        anterior = usuario.language
        usuario.language = "en"
        database.session.commit()
    return anterior


def _restaurar_idioma(app, reference_users, anterior):
    """Restaura el idioma del administrador de prueba."""
    with app.app_context():
        usuario = database.session.get(User, str(reference_users["admin"].id))
        usuario.language = anterior
        database.session.commit()


@pytest.mark.parametrize("purpose", sorted(PROPOSITOS))
def test_titulos_de_alta_y_edicion_en_ingles(app, authenticated_client, reference_users, purpose):
    """Los títulos de pantalla y documento salen del catálogo inglés."""
    ruta, _, _, esperado_nuevo, esperado_edicion = PROPOSITOS[purpose]
    entry_id = _crear_entrada(app, purpose)
    anterior = _con_idioma_ingles(app, reference_users)
    try:
        client = authenticated_client("admin")
        alta = client.get(ruta)
        assert alta.status_code == 200
        assert f"<title>{esperado_nuevo} - Cacao Accounting</title>" in alta.get_data(as_text=True)

        edicion = client.get(f"/inventory/stock-entry/{entry_id}/edit")
        assert edicion.status_code == 200
        cuerpo = edicion.get_data(as_text=True)
        assert f"<title>{esperado_edicion} - Cacao Accounting</title>" in cuerpo
        assert f"<title>{esperado_nuevo} - Cacao Accounting</title>" not in cuerpo
    finally:
        _restaurar_idioma(app, reference_users, anterior)
        _eliminar_entrada(app, entry_id)
