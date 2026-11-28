# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 William José Moreno Reyes

"""#2345: una edición inválida de StockEntry no muta cabecera ni líneas."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import select

from cacao_accounting.database import (
    NamingSeries,
    StockEntry,
    StockEntryItem,
    User,
    database,
)
from cacao_accounting.document_identifiers import ensure_default_naming_series_for_company

RUTA = "/inventory/stock-entry/{entry_id}/edit"


@pytest.fixture
def movimiento(entorno_contable_aislado):
    """StockEntry en borrador con una línea persistida y usuario autenticado."""
    application = entorno_contable_aislado.app
    with application.app_context():
        ensure_default_naming_series_for_company("cacao", ["stock_entry"])
        database.session.commit()
        series_id = database.session.execute(
            select(NamingSeries.id).filter_by(entity_type="stock_entry", company="cacao")
        ).scalar_one()
        entry = StockEntry(
            company="cacao",
            purpose="material_receipt",
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
                source_warehouse="BOD01",
                target_warehouse="BOD01",
                qty=Decimal("2"),
                uom="UND",
                qty_in_base_uom=Decimal("2"),
                basic_rate=Decimal("10"),
                amount=Decimal("20"),
            )
        )
        database.session.commit()
        admin_id = str(database.session.execute(select(User.id).filter_by(user="admin")).scalar_one())
        entry_id = entry.id

    client = application.test_client()
    with client.session_transaction() as session:
        session["_user_id"] = admin_id
        session["_fresh"] = True
    return application, client, entry_id, series_id


def _formulario(series_id: str, **extra: str) -> dict[str, str]:
    """Datos del formulario de edición con la línea original."""
    datos = {
        "purpose": "material_receipt",
        "company": "cacao",
        "naming_series": series_id,
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
    datos.update(extra)
    return datos


def _estado(application, entry_id: str) -> dict:
    """Snapshot estable de cabecera y líneas del movimiento."""
    with application.app_context():
        database.session.expire_all()
        entry = database.session.get(StockEntry, entry_id)
        lineas = (
            database.session.execute(select(StockEntryItem).filter_by(stock_entry_id=entry_id).order_by(StockEntryItem.id))
            .scalars()
            .all()
        )
        return {
            "remarks": entry.remarks,
            "posting_date": entry.posting_date,
            "from_warehouse": entry.from_warehouse,
            "to_warehouse": entry.to_warehouse,
            "transaction_currency": entry.transaction_currency,
            "total_amount": Decimal(entry.total_amount),
            "lines": [
                (
                    linea.id,
                    linea.item_code,
                    Decimal(linea.qty),
                    Decimal(linea.qty_in_base_uom),
                    Decimal(linea.basic_rate),
                    Decimal(linea.amount),
                    linea.uom,
                )
                for linea in lineas
            ],
        }


@pytest.mark.parametrize(
    ("campo", "valor"),
    [
        ("qty_0", "abc"),
        ("rate_0", "NaN"),
        ("rate_0", "Infinity"),
        ("qty_0", "-1"),
    ],
)
def test_edicion_invalida_conserva_cabecera_y_lineas(movimiento, campo, valor):
    """Un decimal inválido re-renderiza el formulario sin persistir ningún cambio."""
    application, client, entry_id, series_id = movimiento
    antes = _estado(application, entry_id)

    response = client.post(RUTA.format(entry_id=entry_id), data=_formulario(series_id, **{campo: valor}))

    assert response.status_code == 200
    assert _estado(application, entry_id) == antes


def test_edicion_valida_sigue_persistiendo_la_linea(movimiento):
    """Control positivo: una edición válida actualiza la línea persistida."""
    application, client, entry_id, series_id = movimiento

    response = client.post(
        RUTA.format(entry_id=entry_id),
        data=_formulario(series_id, qty_0="4", rate_0="12", amount_0="48", remarks="Cabecera válida"),
    )

    assert response.status_code == 302
    with application.app_context():
        entry = database.session.get(StockEntry, entry_id)
        linea = database.session.execute(select(StockEntryItem).filter_by(stock_entry_id=entry_id)).scalar_one()
        assert entry.remarks == "Cabecera válida"
        assert Decimal(linea.qty) == Decimal("4")
        assert Decimal(linea.basic_rate) == Decimal("12")
        assert Decimal(linea.amount) == Decimal("48")
