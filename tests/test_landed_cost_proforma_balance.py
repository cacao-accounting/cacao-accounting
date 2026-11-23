# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1757: la pro-forma de landed cost refleja el prorrateo y queda balanceada."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import uuid4

from cacao_accounting.accounting_engine.document_builders import _build_import_landed_cost_context
from cacao_accounting.accounting_engine.orchestrator.event_orchestrator import BusinessEventOrchestrator
from cacao_accounting.accounting_engine.orchestrator.mapper import AccountingMapper
from cacao_accounting.database import (
    Accounts,
    CompanyDefaultAccount,
    ImportLandedCost,
    ImportLandedCostCharge,
    ImportLandedCostItem,
    Item,
    PurchaseInvoice,
    UOM,
    Warehouse,
    WarehouseCompanyAccount,
    database,
)


def test_landed_cost_debita_inventario_por_el_prorrateo_y_balancea(app, entorno_contable):
    """Un cargo de 10 sobre línea de 100 genera Dr inventario 10 / Cr puente 10."""
    del entorno_contable
    sufijo = uuid4().hex[:6]
    with app.app_context():
        inventario = Accounts(
            entity="cacao", code=f"INV{sufijo}", name="Inventario", classification="asset", account_type="stock"
        )
        puente = Accounts(
            entity="cacao", code=f"PUE{sufijo}", name="Puente", classification="liability", account_type="payable"
        )
        cargo = Accounts(entity="cacao", code=f"CAR{sufijo}", name="Cargo", classification="expense", account_type="expense")
        bodega = Warehouse(code=f"W{sufijo}", name="Bodega", company="cacao", is_active=True)
        unidad = UOM(code=f"U{sufijo}", name="Unidad", is_active=True)
        database.session.add_all([inventario, puente, cargo, bodega, unidad])
        database.session.commit()
        articulo = Item(
            code=f"ART{sufijo}",
            name="Artículo",
            item_type="goods",
            is_stock_item=True,
            default_uom=unidad.code,
        )
        database.session.add(articulo)
        database.session.flush()
        database.session.add(
            WarehouseCompanyAccount(
                warehouse_code=bodega.code,
                company="cacao",
                inventory_account_id=inventario.id,
                is_active=True,
            )
        )
        defaults = database.session.execute(
            database.select(CompanyDefaultAccount).filter_by(company="cacao")
        ).scalar_one_or_none()
        if defaults is None:
            database.session.add(CompanyDefaultAccount(company="cacao", bridge_account_id=puente.id))
        else:
            defaults.bridge_account_id = puente.id
        factura = PurchaseInvoice(
            company="cacao",
            posting_date=date(2026, 5, 15),
            document_type="purchase_invoice",
            transaction_currency="NIO",
            base_currency="NIO",
        )
        database.session.add(factura)
        database.session.flush()
        landed = ImportLandedCost(
            company="cacao",
            purchase_invoice_id=factura.id,
            posting_date=date(2026, 5, 15),
            allocation_method="by_value",
            transaction_currency="NIO",
            base_currency="NIO",
        )
        database.session.add(landed)
        database.session.flush()
        database.session.add_all(
            [
                ImportLandedCostItem(
                    import_landed_cost_id=landed.id,
                    item_code=articulo.code,
                    item_name="Artículo",
                    qty=Decimal("1"),
                    uom=unidad.code,
                    rate=Decimal("100"),
                    amount=Decimal("100"),
                    warehouse=bodega.code,
                ),
                ImportLandedCostCharge(
                    import_landed_cost_id=landed.id,
                    concept="Flete",
                    charge_type="charge",
                    amount=Decimal("10"),
                    accounting_treatment="capitalizable_inventory_cost",
                    account_id=cargo.id,
                ),
            ]
        )
        database.session.commit()

        context = _build_import_landed_cost_context(landed)
        resultados = BusinessEventOrchestrator().handle_event(context)
        proforma = AccountingMapper().map_to_proforma(
            context,
            resultados["fiscal"],
            resultados["landed_cost"],
        )
        inventario_id = inventario.id
        puente_id = puente.id

    debitos = {(line.account_id, line.debit) for line in proforma.lines if line.debit > 0}
    creditos = {(line.account_id, line.credit) for line in proforma.lines if line.credit > 0}

    assert proforma.is_balanced
    assert (inventario_id, Decimal("10")) in debitos
    assert (puente_id, Decimal("10")) in creditos
    assert all(amount != Decimal("100") for _, amount in debitos)
