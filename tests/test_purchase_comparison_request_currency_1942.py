# SPDX-License-Identifier: Apache-2.0
"""#1942: comparativo de solicitud expone moneda original, funcional y TC."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import uuid4

from cacao_accounting.database import (
    DocumentRelation,
    ExchangeRate,
    Item,
    PurchaseRequest,
    PurchaseRequestComparison,
    PurchaseRequestComparisonOffer,
    PurchaseRequestItem,
    SupplierQuotation,
    SupplierQuotationItem,
    database,
)


def test_comparativo_solicitud_muestra_moneda_funcional_y_equivalente(app, entorno_contable, authenticated_client):
    suffix = uuid4().hex[:6]
    with app.app_context():
        if database.session.execute(database.select(Item).filter_by(code="ART01")).scalar_one_or_none() is None:
            database.session.add(
                Item(
                    code="ART01",
                    name="Articulo comparativo",
                    item_type="goods",
                    is_stock_item=True,
                    is_purchase_item=True,
                    is_sale_item=True,
                    default_uom="UND",
                )
            )
        database.session.add(
            ExchangeRate(
                origin="USD",
                destination="NIO",
                rate=Decimal("36.5000"),
                date=date(2026, 5, 15),
            )
        )
        request = PurchaseRequest(
            company="cacao",
            document_no=f"REQ-1942-{suffix}",
            requested_by="admin",
            posting_date=date(2026, 5, 15),
            docstatus=1,
        )
        database.session.add(request)
        database.session.flush()
        req_item = PurchaseRequestItem(
            purchase_request_id=request.id,
            item_code="ART01",
            item_name="Articulo comparativo",
            qty=Decimal("1"),
            uom="UND",
        )
        database.session.add(req_item)
        comparison = PurchaseRequestComparison(
            company="cacao",
            purchase_request_id=request.id,
            document_no=f"CMP-1942-{suffix}",
            posting_date=date(2026, 5, 15),
            status="draft",
        )
        quotation = SupplierQuotation(
            company="cacao",
            posting_date=date(2026, 5, 15),
            docstatus=1,
            document_no=f"SC-USD-{suffix}",
            supplier_name=f"Proveedor USD {suffix}",
            transaction_currency="USD",
            base_currency="NIO",
            exchange_rate=Decimal("36.5000"),
            grand_total=Decimal("5.00"),
        )
        database.session.add_all([comparison, quotation])
        database.session.flush()
        sq_item = SupplierQuotationItem(
            supplier_quotation_id=quotation.id,
            item_code="ART01",
            item_name="Articulo comparativo",
            qty=Decimal("1"),
            uom="UND",
            rate=Decimal("5.00"),
            amount=Decimal("5.00"),
            base_rate=Decimal("182.5000"),
            base_amount=Decimal("182.5000"),
        )
        database.session.add(sq_item)
        database.session.flush()
        database.session.add(
            PurchaseRequestComparisonOffer(
                comparison_id=comparison.id,
                supplier_quotation_id=quotation.id,
            )
        )
        database.session.add(
            DocumentRelation(
                source_type="purchase_request",
                source_id=request.id,
                source_item_id=req_item.id,
                target_type="supplier_quotation",
                target_id=quotation.id,
                target_item_id=sq_item.id,
                company="cacao",
                qty=Decimal("1"),
                qty_in_base_uom=Decimal("1"),
                uom="UND",
                relation_type="quotation",
                status="active",
            )
        )
        database.session.commit()
        comparison_id = comparison.id

    body = authenticated_client().get(f"/buying/request-for-quotation/comparison/{comparison_id}").get_data(as_text=True)

    assert "Moneda funcional de comparaci" in body
    assert "NIO" in body
    assert "USD 5.00" in body
    assert "NIO 182.50" in body or "NIO 182.5000" in body
    assert "36.5" in body or "36.5000" in body
