# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#2140: un comparativo finalizado admite una única adjudicación."""

import pytest
from datetime import date

from sqlalchemy.exc import IntegrityError

from cacao_accounting.database import Entity, PurchaseQuotation, PurchaseQuotationAward, database

SUFFIX = "2140A"


def test_award_unico_por_comparativo(app):
    """Dos adjudicaciones sobre el mismo comparativo violan la restricción única (#2140)."""
    with app.app_context():
        database.session.add(
            Entity(
                code="A2140",
                name="Compras 2140",
                company_name="Compras 2140 SA",
                tax_id="A2140",
                currency="NIO",
                enabled=True,
                status="default",
            )
        )
        database.session.flush()
        rfq = PurchaseQuotation(company="A2140", posting_date=date(2026, 5, 15), docstatus=1, document_no=f"RFQ-{SUFFIX}")
        database.session.add(rfq)
        database.session.flush()
        database.session.add(PurchaseQuotationAward(purchase_quotation_id=rfq.id, company="A2140", status="finalized"))
        database.session.commit()
        with pytest.raises(IntegrityError):
            database.session.add(PurchaseQuotationAward(purchase_quotation_id=rfq.id, company="A2140", status="finalized"))
            database.session.flush()
        database.session.rollback()
        awards = (
            database.session.execute(database.select(PurchaseQuotationAward).filter_by(purchase_quotation_id=rfq.id))
            .scalars()
            .all()
        )
        assert len(awards) == 1
