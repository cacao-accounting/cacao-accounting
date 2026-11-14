# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Render awarded suppliers by human-readable name within the active RFQ scope."""

from uuid import uuid4

from sqlalchemy import delete

from cacao_accounting.database import (
    Entity,
    Item,
    Party,
    PurchaseQuotation,
    PurchaseQuotationAward,
    PurchaseQuotationAwardItem,
    PurchaseQuotationItem,
    SupplierQuotation,
    SupplierQuotationItem,
    UOM,
    database,
)


def test_award_view_shows_supplier_names_and_hides_out_of_scope_references(app, reference_users):
    """Names resolve per awarded quotation and foreign or missing RFQ references stay hidden."""
    with app.app_context():
        suffix = uuid4().hex[:10]
        company = database.session.execute(database.select(Entity).filter_by(code="cacao")).scalar_one()
        other_company = database.session.execute(database.select(Entity).filter_by(code="alpha")).scalar_one()
        uom = UOM(code=f"U{suffix}", name="Unidad")
        item = Item(
            code=f"AWARD-{suffix}",
            name="Artículo de prueba",
            item_type="goods",
            is_stock_item=False,
            default_uom=uom.code,
        )
        party = Party(code=f"SUP-{suffix}", name="Proveedor desde tercero", is_supplier=True)
        award_rfq = PurchaseQuotation(company=company.code, document_no=f"RFQ-{suffix}")
        unrelated_rfq = PurchaseQuotation(company=company.code, document_no=f"OTHER-{suffix}")
        database.session.add(uom)
        database.session.flush()
        database.session.add_all([item, party, award_rfq, unrelated_rfq])
        database.session.flush()

        purchase_line = PurchaseQuotationItem(
            purchase_quotation_id=award_rfq.id,
            item_code=item.code,
            qty=2,
        )
        quotations = [
            SupplierQuotation(
                company=company.code,
                purchase_quotation_id=award_rfq.id,
                supplier_id=party.id,
                supplier_name="Nombre histórico de cotización",
                document_no=f"SQ-1-{suffix}",
                docstatus=1,
            ),
            SupplierQuotation(
                company=company.code,
                purchase_quotation_id=award_rfq.id,
                supplier_id=party.id,
                supplier_name=None,
                document_no=f"SQ-2-{suffix}",
                docstatus=1,
            ),
            SupplierQuotation(
                company=company.code,
                purchase_quotation_id=unrelated_rfq.id,
                supplier_id=party.id,
                supplier_name="Proveedor de otra solicitud",
                document_no=f"SQ-3-{suffix}",
                docstatus=0,
            ),
            SupplierQuotation(
                company=other_company.code,
                purchase_quotation_id=award_rfq.id,
                supplier_id=party.id,
                supplier_name="Proveedor de otra compañía",
                document_no=f"SQ-4-{suffix}",
                docstatus=0,
            ),
        ]
        database.session.add_all([purchase_line, *quotations])
        database.session.flush()

        quote_lines = [
            SupplierQuotationItem(
                supplier_quotation_id=quotation.id,
                item_code=item.code,
                qty=2,
                rate=10,
                amount=20,
            )
            for quotation in quotations
        ]
        award = PurchaseQuotationAward(purchase_quotation_id=award_rfq.id, company=company.code, status="finalized")
        database.session.add_all([*quote_lines, award])
        database.session.flush()
        award_lines = [
            PurchaseQuotationAwardItem(
                award_id=award.id,
                purchase_quotation_item_id=purchase_line.id,
                supplier_quotation_id=quotation.id,
                supplier_quotation_item_id=quote_line.id,
                item_code=item.code,
                qty=2,
                rate=10,
                amount=20,
            )
            for quotation, quote_line in zip(quotations, quote_lines, strict=True)
        ]
        database.session.add_all(award_lines)
        database.session.commit()

        rfq_id = award_rfq.id
        quote_ids = [quotation.id for quotation in quotations]
        quote_line_ids = [quote_line.id for quote_line in quote_lines]
        award_id = award.id
        purchase_line_id = purchase_line.id
        purchase_quotation_ids = [award_rfq.id, unrelated_rfq.id]
        unrelated_rfq_id = unrelated_rfq.id
        item_code = item.code
        uom_code = uom.code
        party_id = party.id
        user_id = reference_users["admin"].id

    client = app.test_client()
    with client.session_transaction() as session:
        session["_user_id"] = user_id
        session["_fresh"] = True
    try:
        response = client.get(f"/buying/request-for-quotation/{rfq_id}/offers")
        page = response.get_data(as_text=True)

        assert response.status_code == 200, page
        assert "Nombre histórico de cotización" in page
        assert "Proveedor desde tercero" in page
        assert "Proveedor de otra solicitud" not in page
        assert "Proveedor de otra compañía" not in page
        assert all(f">{quote_id}<" not in page for quote_id in quote_ids)
        assert f'<a href="/buying/supplier-quotation/{quote_ids[0]}">Ver</a>' in page
        assert f'<a href="/buying/supplier-quotation/{quote_ids[1]}">Ver</a>' in page

        no_award_response = client.get(f"/buying/request-for-quotation/{unrelated_rfq_id}/offers")
        assert no_award_response.status_code == 200
        assert "Líneas adjudicadas" not in no_award_response.get_data(as_text=True)
    finally:
        with app.app_context():
            database.session.execute(delete(PurchaseQuotationAwardItem).where(PurchaseQuotationAwardItem.award_id == award_id))
            database.session.execute(delete(PurchaseQuotationAward).where(PurchaseQuotationAward.id == award_id))
            database.session.execute(delete(SupplierQuotationItem).where(SupplierQuotationItem.id.in_(quote_line_ids)))
            database.session.execute(delete(SupplierQuotation).where(SupplierQuotation.id.in_(quote_ids)))
            database.session.execute(delete(PurchaseQuotationItem).where(PurchaseQuotationItem.id == purchase_line_id))
            database.session.execute(delete(PurchaseQuotation).where(PurchaseQuotation.id.in_(purchase_quotation_ids)))
            database.session.execute(delete(Party).where(Party.id == party_id))
            database.session.execute(delete(Item).where(Item.code == item_code))
            database.session.execute(delete(UOM).where(UOM.code == uom_code))
            database.session.commit()
