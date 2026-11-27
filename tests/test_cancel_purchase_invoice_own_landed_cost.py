# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 William José Moreno Reyes

"""#1210: a purchase invoice can reverse its own capitalized tax cost."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import uuid4

from cacao_accounting.approval_engine import approved_execution
from cacao_accounting.contabilidad.cancellation_service import active_cancellation_dependencies
from cacao_accounting.contabilidad.posting_service import cancel_document, submit_document
from cacao_accounting.database import (
    Accounts,
    Item,
    LandedCostAllocation,
    Party,
    PurchaseInvoice,
    PurchaseInvoiceItem,
    StockBin,
    StockValuationLayer,
    Tax,
    TaxTemplate,
    TaxTemplateItem,
    UOM,
    User,
    Warehouse,
    database,
)
from cacao_accounting.fiscal_persistence_service import calculate_document_total_with_taxes
from cacao_accounting.internal_control_service import audit_actor


def test_purchase_invoice_cancels_own_capitalized_tax_cost(entorno_contable_aislado):
    """Posting and cancelling an invoice preserves its allocation and reverses stock value."""
    app = entorno_contable_aislado.app
    suffix = uuid4().hex[:8]
    posting_date = date(2026, 5, 15)
    with app.app_context():
        item = database.session.execute(database.select(Item).filter_by(code="ART01")).scalar_one()
        uom = database.session.execute(database.select(UOM).filter_by(code="UND")).scalar_one()
        warehouse_code = database.session.execute(database.select(Warehouse.code).filter_by(company="cacao")).scalar_one()
        supplier = database.session.execute(database.select(Party).filter_by(code="PRV001")).scalar_one()
        expense = database.session.execute(database.select(Accounts).filter_by(entity="cacao", code="5201")).scalar_one()
        tax_account = database.session.execute(database.select(Accounts).filter_by(entity="cacao", code="2105")).scalar_one()
        baseline_value = Decimal("1000")
        database.session.add(
            StockBin(
                company="cacao",
                item_code=item.code,
                warehouse=warehouse_code,
                actual_qty=Decimal("10"),
                stock_value=baseline_value,
                valuation_rate=Decimal("100"),
            )
        )
        tax = Tax(
            id=f"CAP-{suffix}",
            name=f"Impuesto capitalizable {suffix}",
            rate=Decimal("10"),
            tax_type="percentage",
            applies_to="purchase",
            account_id=tax_account.id,
            is_charge=False,
            is_capitalizable=True,
            is_active=True,
        )
        template = TaxTemplate(
            name=f"Plantilla capitalizable {suffix}",
            company="cacao",
            template_type="buying",
            currency="NIO",
            is_active=True,
        )
        database.session.add_all([tax, template])
        database.session.flush()
        database.session.add(
            TaxTemplateItem(
                tax_template_id=template.id,
                tax_id=tax.id,
                sequence=10,
                calculation_base="net_document",
                behavior="additive",
                is_inclusive=False,
            )
        )
        invoice = PurchaseInvoice(
            company="cacao",
            posting_date=posting_date,
            document_no=f"PI-CAP-{suffix}",
            document_type="purchase_invoice",
            supplier_id=supplier.id,
            supplier_name=supplier.name,
            tax_template_id=template.id,
            transaction_currency="NIO",
            base_currency="NIO",
            exchange_rate=Decimal("1"),
        )
        database.session.add(invoice)
        database.session.flush()
        line = PurchaseInvoiceItem(
            purchase_invoice_id=invoice.id,
            item_code=item.code,
            item_name=item.name,
            qty=Decimal("1"),
            qty_in_base_uom=Decimal("1"),
            uom=uom.code,
            rate=Decimal("100"),
            amount=Decimal("100"),
            base_amount=Decimal("100"),
            expense_account_id=expense.id,
            warehouse=warehouse_code,
        )
        database.session.add(line)
        database.session.flush()
        document_total = calculate_document_total_with_taxes(invoice, Decimal("100"), [line])
        invoice.total = invoice.base_total = document_total
        invoice.grand_total = invoice.base_grand_total = document_total
        invoice.outstanding_amount = invoice.base_outstanding_amount = document_total
        database.session.commit()
        invoice_id = invoice.id
        actor = database.session.execute(database.select(User).filter_by(user="admin")).scalar_one()

        with audit_actor(actor.id, actor.name), approved_execution(invoice, actor.id):
            submit_document(invoice)
        database.session.commit()

        allocation = database.session.execute(
            database.select(LandedCostAllocation).filter_by(document_type="purchase_invoice", document_id=invoice_id)
        ).scalar_one()
        assert allocation.allocated_amount == Decimal("10")
        assert active_cancellation_dependencies(invoice, "purchase_invoice", invoice_id) == []
        capitalized_layer = database.session.get(StockValuationLayer, allocation.stock_valuation_layer_id)
        assert capitalized_layer is not None
        assert capitalized_layer.stock_value_difference == Decimal("10")
        stock_bin = database.session.execute(
            database.select(StockBin).filter_by(company="cacao", item_code=item.code, warehouse=warehouse_code)
        ).scalar_one()
        assert stock_bin.stock_value == baseline_value + Decimal("10")

        with audit_actor(actor.id, actor.name), approved_execution(invoice, actor.id):
            cancel_document(
                invoice,
                reason="Anular factura con costo capitalizado propio",
                actor_user_id=actor.id,
                cancellation_date=posting_date,
            )
        database.session.commit()

        assert database.session.get(PurchaseInvoice, invoice_id).docstatus == 2
        saved_allocation = database.session.get(LandedCostAllocation, allocation.id)
        assert saved_allocation is not None
        assert saved_allocation.allocated_amount == Decimal("10")
        saved_layer = database.session.get(StockValuationLayer, capitalized_layer.id)
        assert saved_layer is not None
        assert saved_layer.stock_value_difference == Decimal("10")
        stock_bin = database.session.execute(
            database.select(StockBin).filter_by(company="cacao", item_code=item.code, warehouse=warehouse_code)
        ).scalar_one()
        assert stock_bin.stock_value == baseline_value
        reversal_layers = (
            database.session.execute(
                database.select(StockValuationLayer).where(
                    StockValuationLayer.voucher_type == "purchase_invoice",
                    StockValuationLayer.voucher_id == invoice_id,
                    StockValuationLayer.id != capitalized_layer.id,
                )
            )
            .scalars()
            .all()
        )
        assert len(reversal_layers) == 1
        assert reversal_layers[0].stock_value_difference == Decimal("-10")
