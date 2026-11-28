# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1757: la pro-forma de landed cost refleja el prorrateo y queda balanceada."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import select

from cacao_accounting.accounting_engine.document_builders import _build_import_landed_cost_context
from cacao_accounting.accounting_engine.orchestrator.event_orchestrator import BusinessEventOrchestrator
from cacao_accounting.accounting_engine.orchestrator.mapper import AccountingMapper
from cacao_accounting.contabilidad.posting_service import PostingError, post_import_landed_cost
from cacao_accounting.internal_control_service import audit_actor
from cacao_accounting.database import (
    Accounts,
    CompanyDefaultAccount,
    GLEntry,
    ImportLandedCost,
    ImportLandedCostCharge,
    ImportLandedCostItem,
    Item,
    LandedCostAllocation,
    PurchaseInvoice,
    UOM,
    User,
    Warehouse,
    WarehouseCompanyAccount,
    database,
)


def _crear_escenario(env, *, con_cuenta_inventario: bool, con_redondeo: bool = False) -> dict[str, str]:
    """Crea un costo importado real con o sin cuenta de inventario por bodega."""
    sufijo = uuid4().hex[:6]
    with env.app.app_context():
        inventario = Accounts(
            entity="cacao", code=f"INV{sufijo}", name="Inventario", classification="asset", account_type="stock"
        )
        puente = Accounts(
            entity="cacao", code=f"PUE{sufijo}", name="Puente", classification="liability", account_type="payable"
        )
        cargo = Accounts(entity="cacao", code=f"CAR{sufijo}", name="Cargo", classification="expense", account_type="expense")
        redondeo = Accounts(
            entity="cacao", code=f"RED{sufijo}", name="Redondeo", classification="expense", account_type="expense"
        )
        bodega = Warehouse(code=f"W{sufijo}", name="Bodega", company="cacao", is_active=True)
        unidad = UOM(code=f"U{sufijo}", name="Unidad", is_active=True)
        database.session.add_all([inventario, puente, cargo, redondeo, bodega, unidad])
        if not con_cuenta_inventario:
            # Aisla el rechazo por cuenta de inventario de restricciones de tipo
            # ajenas al voucher import_landed_cost.
            for cuenta in (inventario, puente, cargo, redondeo):
                cuenta.account_type = None
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
        if con_cuenta_inventario:
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
            defaults = CompanyDefaultAccount(company="cacao")
            database.session.add(defaults)
        defaults.bridge_account_id = puente.id
        if con_redondeo:
            defaults.default_rounding_account_id = redondeo.id
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
            docstatus=1,
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
        return {
            "landed_id": str(landed.id),
            "inventario_id": str(inventario.id),
            "puente_id": str(puente.id),
            "redondeo_id": str(redondeo.id),
        }


def test_landed_cost_debita_inventario_por_el_prorrateo_y_balancea(entorno_contable_aislado):
    """Un cargo de 10 sobre línea de 100 genera Dr inventario 10 / Cr puente 10."""
    env = entorno_contable_aislado
    ids = _crear_escenario(env, con_cuenta_inventario=True)
    with env.app.app_context():
        landed = database.session.get(ImportLandedCost, ids["landed_id"])
        context = _build_import_landed_cost_context(landed)
        resultados = BusinessEventOrchestrator().handle_event(context)
        proforma = AccountingMapper().map_to_proforma(
            context,
            resultados["fiscal"],
            resultados["landed_cost"],
        )

    debitos = {(line.account_id, line.debit) for line in proforma.lines if line.debit > 0}
    creditos = {(line.account_id, line.credit) for line in proforma.lines if line.credit > 0}

    assert proforma.is_balanced
    assert (ids["inventario_id"], Decimal("10")) in debitos
    assert (ids["puente_id"], Decimal("10")) in creditos
    assert all(amount != Decimal("100") for _, amount in debitos)


def test_landed_cost_sin_cuenta_inventario_rechaza_posting_sin_evidencia(entorno_contable_aislado):
    """Una cuenta de redondeo no puede sustituir la cuenta de inventario ausente."""
    env = entorno_contable_aislado
    ids = _crear_escenario(env, con_cuenta_inventario=False, con_redondeo=True)
    with env.app.app_context():
        landed = database.session.get(ImportLandedCost, ids["landed_id"])
        defaults = database.session.execute(database.select(CompanyDefaultAccount).filter_by(company="cacao")).scalar_one()
        assert defaults is not None and defaults.default_rounding_account_id == ids["redondeo_id"]
        admin = database.session.execute(select(User).filter_by(user="admin")).scalar_one()

        with audit_actor(str(admin.id), "Prueba de costo importado"):
            with pytest.raises(PostingError, match="Falta la cuenta de inventario"):
                post_import_landed_cost(landed)

        entradas = (
            database.session.execute(select(GLEntry).filter_by(voucher_type="import_landed_cost", voucher_id=ids["landed_id"]))
            .scalars()
            .all()
        )
        asignaciones = (
            database.session.execute(
                select(LandedCostAllocation).filter_by(
                    document_type="import_landed_cost",
                    document_id=ids["landed_id"],
                )
            )
            .scalars()
            .all()
        )
        assert entradas == []
        assert asignaciones == []
        assert landed.docstatus == 1
