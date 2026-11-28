# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1729: el filtro de bodega usa las bodegas efectivas de la línea."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import uuid4

from cacao_accounting.database import StockEntry, StockEntryItem, Warehouse, database
from cacao_accounting.reportes.services import OperationalReportFilters, get_inventory_transfers


def test_filtra_por_bodega_efectiva_de_linea_y_encabezado(app, entorno_contable):
    """line.source/target tienen prioridad; el encabezado aplica si la línea no informa."""
    del entorno_contable
    sufijo = uuid4().hex[:5]
    origen_linea = f"LA{sufijo}"
    destino_linea = f"LB{sufijo}"
    origen_cabecera = f"HA{sufijo}"
    with app.app_context():
        database.session.add_all(
            [
                Warehouse(code=origen_linea, name="Origen linea", company="cacao"),
                Warehouse(code=destino_linea, name="Destino linea", company="cacao"),
                Warehouse(code=origen_cabecera, name="Origen cabecera", company="cacao"),
            ]
        )
        database.session.flush()
        entrada = StockEntry(
            company="cacao",
            purpose="material_transfer",
            posting_date=date(2026, 5, 15),
            docstatus=1,
            document_no=f"TR-{sufijo}",
            from_warehouse=origen_cabecera,
            to_warehouse=None,
        )
        database.session.add(entrada)
        database.session.flush()
        database.session.add(
            StockEntryItem(
                stock_entry_id=entrada.id,
                item_code="ART01",
                source_warehouse=origen_linea,
                target_warehouse=destino_linea,
                qty=Decimal("1"),
                qty_in_base_uom=Decimal("1"),
                uom="UND",
                amount=Decimal("1"),
            )
        )
        database.session.commit()
        entrada_id = entrada.id

    try:
        with app.app_context():
            filtros = OperationalReportFilters(company="cacao", warehouse=origen_linea)
            filas = get_inventory_transfers(filtros).rows
            assert len(filas) == 1
            assert filas[0].values["from_warehouse"] == origen_linea

            filtros_destino = OperationalReportFilters(company="cacao", warehouse=destino_linea)
            assert len(get_inventory_transfers(filtros_destino).rows) == 1

            filtros_cabecera = OperationalReportFilters(company="cacao", warehouse=origen_cabecera)
            assert get_inventory_transfers(filtros_cabecera).rows == []
    finally:
        with app.app_context():
            database.session.execute(database.delete(StockEntryItem).where(StockEntryItem.stock_entry_id == entrada_id))
            database.session.execute(database.delete(StockEntry).where(StockEntry.id == entrada_id))
            database.session.execute(
                database.delete(Warehouse).where(Warehouse.code.in_([origen_linea, destino_linea, origen_cabecera]))
            )
            database.session.commit()


def test_usa_bodega_de_cabecera_cuando_la_linea_la_omite(app, entorno_contable):
    """Una línea sin bodegas propias hereda las del encabezado para el filtro."""
    del entorno_contable
    sufijo = uuid4().hex[:5]
    origen = f"HC{sufijo}"
    destino = f"HD{sufijo}"
    with app.app_context():
        database.session.add_all(
            [
                Warehouse(code=origen, name="Origen cabecera", company="cacao"),
                Warehouse(code=destino, name="Destino cabecera", company="cacao"),
            ]
        )
        database.session.flush()
        entrada = StockEntry(
            company="cacao",
            purpose="material_transfer",
            posting_date=date(2026, 5, 15),
            docstatus=1,
            document_no=f"TR-H-{sufijo}",
            from_warehouse=origen,
            to_warehouse=destino,
        )
        database.session.add(entrada)
        database.session.flush()
        database.session.add(
            StockEntryItem(
                stock_entry_id=entrada.id,
                item_code="ART01",
                qty=Decimal("1"),
                qty_in_base_uom=Decimal("1"),
                uom="UND",
                amount=Decimal("1"),
            )
        )
        database.session.commit()
        entrada_id = entrada.id

    try:
        with app.app_context():
            filas = get_inventory_transfers(OperationalReportFilters(company="cacao", warehouse=origen)).rows
            assert len(filas) == 1
            assert filas[0].values["from_warehouse"] == origen
    finally:
        with app.app_context():
            database.session.execute(database.delete(StockEntryItem).where(StockEntryItem.stock_entry_id == entrada_id))
            database.session.execute(database.delete(StockEntry).where(StockEntry.id == entrada_id))
            database.session.execute(database.delete(Warehouse).where(Warehouse.code.in_([origen, destino])))
            database.session.commit()
