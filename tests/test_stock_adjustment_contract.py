# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1891: solo existen ajustes positivos y negativos con efecto contable."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest
from flask_login import login_user

from cacao_accounting.contabilidad.posting_service import post_stock_entry
from cacao_accounting.database import (
    Accounts,
    CompanyDefaultAccount,
    GLEntry,
    Item,
    StockEntry,
    StockEntryItem,
    StockLedgerEntry,
    User,
    Warehouse,
    WarehouseCompanyAccount,
    database,
)
from cacao_accounting.inventario.forms import FormularioEntradaAlmacen
from cacao_accounting.inventario.services import _validate_stock_entry_purpose


def test_el_formulario_solo_ofrece_ajustes_positivos_y_negativos():
    """El propósito genérico ya no es una opción de creación."""
    codigos = {codigo for codigo, _etiqueta in FormularioEntradaAlmacen().purpose.choices}
    assert "adjustment_positive" in codigos
    assert "adjustment_negative" in codigos
    assert "stock_adjustment" not in codigos


def test_el_servicio_rechaza_el_proposito_generico():
    """El límite de confianza rechaza un POST manipulado con el propósito retirado."""
    with pytest.raises(ValueError, match="no es válido"):
        _validate_stock_entry_purpose("stock_adjustment")


def test_las_rutas_de_creacion_generica_ya_no_existen(app, entorno_contable, authenticated_client):
    """Las URLs retiradas no vuelven a habilitar el flujo genérico."""
    client = authenticated_client()
    assert client.get("/inventory/stock-entry/adjustment/new").status_code == 404
    assert client.get("/inventory/stock-entry/adjustment/new-shortcut").status_code == 404


def test_el_historial_generico_es_solo_lectura(app, entorno_contable, authenticated_client):
    """Una fila histórica conserva consulta sin ofrecer creación."""
    with app.app_context():
        entry = StockEntry(
            purpose="stock_adjustment",
            company="cacao",
            posting_date=date(2026, 5, 10),
            document_no=f"HIST-{uuid4().hex[:8]}",
            transaction_currency="NIO",
            base_currency="NIO",
            docstatus=0,
        )
        database.session.add(entry)
        database.session.commit()

    response = authenticated_client().get("/inventory/stock-entry/adjustment/list")
    html = response.get_data(as_text=True)
    assert response.status_code == 200
    assert "Históricos" in html
    assert "/inventory/stock-entry/adjustment/new" not in html


def test_ajuste_positivo_genera_stock_y_gl_balanceado(app, entorno_contable):
    """Un ajuste positivo crea capa de inventario y asiento balanceado."""
    with app.app_context():
        artefacto = f"ADJ-{uuid4().hex[:6].upper()}"
        bodega = f"ADJW-{uuid4().hex[:6].upper()}"
        database.session.add(
            Item(code=artefacto, name="Artículo positivo", item_type="goods", is_stock_item=True, default_uom="UND")
        )
        database.session.add(Warehouse(code=bodega, name="Bodega positiva", company="cacao"))
        database.session.flush()
        inventory_account_id = database.session.execute(
            database.select(Accounts.id).filter_by(entity="cacao", code="1109")
        ).scalar_one()
        adjustment_account_id = database.session.execute(
            database.select(Accounts.id).filter_by(entity="cacao", code="5201")
        ).scalar_one()
        defaults = database.session.execute(database.select(CompanyDefaultAccount).filter_by(company="cacao")).scalar_one()
        for account_id in (inventory_account_id, adjustment_account_id):
            account = database.session.get(Accounts, account_id)
            account.active = True
            account.enabled = True
            account.group = False
        database.session.add(
            WarehouseCompanyAccount(
                warehouse_code=bodega,
                company="cacao",
                inventory_account_id=inventory_account_id,
            )
        )
        defaults.inventory_adjustment_account_id = adjustment_account_id
        database.session.commit()

        entry = StockEntry(
            purpose="adjustment_positive",
            company="cacao",
            posting_date=date(2026, 5, 20),
            to_warehouse=bodega,
            from_warehouse=bodega,
            document_no=f"ADJP-{uuid4().hex[:8]}",
            transaction_currency="NIO",
            base_currency="NIO",
            docstatus=1,
        )
        database.session.add(entry)
        database.session.flush()
        database.session.add(
            StockEntryItem(
                stock_entry_id=entry.id,
                item_code=artefacto,
                source_warehouse=bodega,
                target_warehouse=bodega,
                qty=Decimal("5"),
                uom="UND",
                qty_in_base_uom=Decimal("5"),
                basic_rate=Decimal("10"),
                amount=Decimal("50"),
            )
        )
        database.session.commit()

        with app.test_request_context(f"/inventory/stock-entry/{entry.id}"):
            login_user(database.session.execute(database.select(User).filter_by(user="admin")).scalar_one())
            post_stock_entry(entry)

        movimientos = (
            database.session.execute(database.select(StockLedgerEntry).filter_by(item_code=artefacto)).scalars().all()
        )
        asientos = database.session.execute(database.select(GLEntry).filter_by(voucher_id=entry.id)).scalars().all()
        assert sum((movimiento.qty_change for movimiento in movimientos), Decimal("0")) == Decimal("5")
        assert asientos
        debit = sum((asiento.debit for asiento in asientos), Decimal("0"))
        credit = sum((asiento.credit for asiento in asientos), Decimal("0"))
        assert debit == credit
        por_libro: dict[str, Decimal] = {}
        for asiento in asientos:
            por_libro[asiento.ledger_id] = por_libro.get(asiento.ledger_id, Decimal("0")) + asiento.debit
        assert set(por_libro.values()) == {Decimal("50")}


def test_ajuste_negativo_consume_stock_y_genera_gl(app, entorno_contable):
    """Un ajuste negativo descuenta existencias y registra contrapartida."""
    with app.app_context():
        artefacto = f"ADJ-{uuid4().hex[:6].upper()}"
        bodega = f"ADJW-{uuid4().hex[:6].upper()}"
        database.session.add(
            Item(code=artefacto, name="Artículo negativo", item_type="goods", is_stock_item=True, default_uom="UND")
        )
        database.session.add(Warehouse(code=bodega, name="Bodega negativa", company="cacao"))
        database.session.flush()
        inventory_account_id = database.session.execute(
            database.select(Accounts.id).filter_by(entity="cacao", code="1109")
        ).scalar_one()
        adjustment_account_id = database.session.execute(
            database.select(Accounts.id).filter_by(entity="cacao", code="5201")
        ).scalar_one()
        defaults = database.session.execute(database.select(CompanyDefaultAccount).filter_by(company="cacao")).scalar_one()
        for account_id in (inventory_account_id, adjustment_account_id):
            account = database.session.get(Accounts, account_id)
            account.active = True
            account.enabled = True
            account.group = False
        database.session.add(
            WarehouseCompanyAccount(
                warehouse_code=bodega,
                company="cacao",
                inventory_account_id=inventory_account_id,
            )
        )
        defaults.inventory_adjustment_account_id = adjustment_account_id
        database.session.commit()

        def post_adjustment(purpose: str, qty: str, amount: str, number: str) -> StockEntry:
            entry = StockEntry(
                purpose=purpose,
                company="cacao",
                posting_date=date(2026, 5, 20),
                to_warehouse=bodega,
                from_warehouse=bodega,
                document_no=number,
                transaction_currency="NIO",
                base_currency="NIO",
                docstatus=1,
            )
            database.session.add(entry)
            database.session.flush()
            database.session.add(
                StockEntryItem(
                    stock_entry_id=entry.id,
                    item_code=artefacto,
                    source_warehouse=bodega,
                    target_warehouse=bodega,
                    qty=Decimal(qty),
                    uom="UND",
                    qty_in_base_uom=Decimal(qty),
                    basic_rate=Decimal("10"),
                    amount=Decimal(amount),
                )
            )
            database.session.commit()
            with app.test_request_context(f"/inventory/stock-entry/{entry.id}"):
                login_user(database.session.execute(database.select(User).filter_by(user="admin")).scalar_one())
                post_stock_entry(entry)
            return entry

        post_adjustment("adjustment_positive", "5", "50", f"ADJP-{uuid4().hex[:8]}")
        negative = post_adjustment("adjustment_negative", "2", "20", f"ADJN-{uuid4().hex[:8]}")

        movimientos = (
            database.session.execute(database.select(StockLedgerEntry).filter_by(item_code=artefacto)).scalars().all()
        )
        asientos = database.session.execute(database.select(GLEntry).filter_by(voucher_id=negative.id)).scalars().all()
        assert sum((movimiento.qty_change for movimiento in movimientos), Decimal("0")) == Decimal("3")
        debit = sum((asiento.debit for asiento in asientos), Decimal("0"))
        credit = sum((asiento.credit for asiento in asientos), Decimal("0"))
        assert debit == credit
        por_libro: dict[str, Decimal] = {}
        for asiento in asientos:
            por_libro[asiento.ledger_id] = por_libro.get(asiento.ledger_id, Decimal("0")) + asiento.debit
        assert set(por_libro.values()) == {Decimal("20")}
