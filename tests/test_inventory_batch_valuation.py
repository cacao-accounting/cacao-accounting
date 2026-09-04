# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Regresión #791: el lote es una dimensión de primer nivel del almacén.

Una salida (nota de entrega) que selecciona un lote específico debe valorarse
con el costo de las capas de entrada de ese lote, no con la cola FIFO global
del artículo ni con el promedio movil entre todos los lotes.

Escenario: dos lotes del mismo articulo a costos distintos (LOTE-A @100 y
LOTE-B @120), entrega de 5 unidades del LOTE-B. El COGS debe ser 5 * 120 = 600
independientemente del metodo de valuacion de la compania.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from cacao_accounting import create_app
from cacao_accounting.config import configuracion

COMPANY = "cacao"


@pytest.fixture(params=["fifo", "moving_average"])
def env(request):
    """App aislada SQLite en memoria con el metodo de valuacion del parametro."""
    app = create_app(
        {
            **configuracion,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
            "WTF_CSRF_ENABLED": False,
            "TESTING": True,
        }
    )
    with app.app_context():
        from cacao_accounting.database import database

        database.create_all()
        method = request.param
        from cacao_accounting.database import (
            AccountingPeriod,
            Accounts,
            Batch,
            Book,
            CompanyDefaultAccount,
            Currency,
            Entity,
            Item,
            Modules,
            PartyAccount,
            UOM,
            Warehouse,
            WarehouseCompanyAccount,
        )

        database.session.add_all(
            [
                Entity(
                    code=COMPANY,
                    name="Cacao",
                    company_name="Cacao SA",
                    tax_id="J0001",
                    currency="NIO",
                    valuation_method=method,
                ),
                Currency(code="NIO", name="Cordobas", decimals=2, active=True, default=True),
                Modules(module="accounting", default=True, enabled=True),
                Modules(module="purchases", default=True, enabled=True),
                Modules(module="inventory", default=True, enabled=True),
                Modules(module="sales", default=True, enabled=True),
                Book(entity=COMPANY, code="GENERAL", name="General", status="activo", is_primary=True, currency="NIO"),
                AccountingPeriod(
                    entity=COMPANY,
                    name="2026-05",
                    enabled=True,
                    is_closed=False,
                    start=date(2026, 5, 1),
                    end=date(2026, 5, 31),
                ),
                UOM(code="UND", name="Unidad", is_active=True),
                Item(
                    code="ART-B",
                    name="Articulo lote",
                    item_type="product",
                    is_stock_item=True,
                    default_uom="UND",
                    is_purchase_item=True,
                    is_sale_item=True,
                    is_active=True,
                    has_batch=True,
                    default_warehouse_id="WW",
                ),
                Warehouse(code="WW", name="Principal", company=COMPANY, is_active=True),
            ]
        )
        database.session.flush()

        def acct(code, name, classification, atype=None):
            return Accounts(
                entity=COMPANY,
                code=code,
                name=name,
                active=True,
                enabled=True,
                group=False,
                classification=classification,
                account_type=atype,
            )

        inv_acct = acct("1201", "Inventario", "asset", "regional_inventory")
        bridge = acct("2201", "Puente Compras", "liability")
        exp = acct("6001", "Gastos", "expense")
        income = acct("4000", "Ingresos", "income", "income")
        ar = acct("1105", "Clientes", "asset", "receivable")
        cogs = acct("5001", "Costo de Venta", "expense")
        database.session.add_all([inv_acct, bridge, exp, income, ar, cogs])
        database.session.flush()
        database.session.add_all(
            [
                CompanyDefaultAccount(
                    company=COMPANY,
                    bridge_account_id=bridge.id,
                    default_expense=exp.id,
                    default_income=income.id,
                    default_receivable=ar.id,
                    default_cogs=cogs.id,
                ),
                PartyAccount(party_id="SUPP-1", company=COMPANY, payable_account_id=None),
                PartyAccount(party_id="CUST-1", company=COMPANY, receivable_account_id=ar.id),
                WarehouseCompanyAccount(
                    warehouse_code="WW", company=COMPANY, inventory_account_id=inv_acct.id, is_active=True
                ),
                Batch(item_code="ART-B", batch_no="LOTE-A", is_active=True),
                Batch(item_code="ART-B", batch_no="LOTE-B", is_active=True),
            ]
        )
        database.session.commit()
        yield request.param
        database.session.remove()
        database.drop_all()


def test_batch_outflow_valued_with_own_batch_cost(env):
    """El COGS de una salida de un lote especifico usa el costo de ese lote."""
    from cacao_accounting.contabilidad.posting_service import submit_document
    from cacao_accounting.database import (
        Batch,
        DeliveryNote,
        DeliveryNoteItem,
        PurchaseReceipt,
        PurchaseReceiptItem,
        StockLedgerEntry,
        database,
    )

    del env
    batch_a = database.session.execute(database.select(Batch).filter_by(batch_no="LOTE-A")).scalar_one()
    batch_b = database.session.execute(database.select(Batch).filter_by(batch_no="LOTE-B")).scalar_one()

    def receipt(qty, rate, bid, day):
        r = PurchaseReceipt(
            company=COMPANY,
            posting_date=day,
            supplier_id="SUPP-1",
            transaction_currency="NIO",
            base_currency="NIO",
            exchange_rate=Decimal("1"),
            docstatus=0,
        )
        database.session.add(r)
        database.session.flush()
        database.session.add(
            PurchaseReceiptItem(
                purchase_receipt_id=r.id,
                item_code="ART-B",
                item_name="Articulo lote",
                qty=qty,
                uom="UND",
                warehouse="WW",
                rate=rate,
                amount=qty * rate,
                batch_id=bid,
            )
        )
        database.session.commit()
        submit_document(r)
        database.session.commit()

    def delivery(qty, bid, day):
        d = DeliveryNote(
            company=COMPANY,
            posting_date=day,
            customer_id="CUST-1",
            transaction_currency="NIO",
            base_currency="NIO",
            exchange_rate=Decimal("1"),
            docstatus=0,
        )
        database.session.add(d)
        database.session.flush()
        database.session.add(
            DeliveryNoteItem(
                delivery_note_id=d.id,
                item_code="ART-B",
                item_name="Articulo lote",
                qty=qty,
                uom="UND",
                warehouse="WW",
                rate=Decimal("150"),
                amount=qty * Decimal("150"),
                batch_id=bid,
            )
        )
        database.session.commit()
        submit_document(d)
        database.session.commit()
        return database.session.execute(
            database.select(StockLedgerEntry).where(
                StockLedgerEntry.company == COMPANY,
                StockLedgerEntry.item_code == "ART-B",
                StockLedgerEntry.voucher_type == "delivery_note",
                StockLedgerEntry.voucher_id == d.id,
            )
        ).scalar_one()

    receipt(Decimal("10"), Decimal("100"), batch_a.id, date(2026, 5, 1))
    receipt(Decimal("10"), Decimal("120"), batch_b.id, date(2026, 5, 2))

    outflow = delivery(Decimal("5"), batch_b.id, date(2026, 5, 5))
    # Costo propio del LOTE-B: 5 * 120 = 600, no la capa antigua (100) ni el promedio (110).
    assert -Decimal(str(outflow.stock_value_difference)) == Decimal("600")
    assert outflow.batch_id == batch_b.id
