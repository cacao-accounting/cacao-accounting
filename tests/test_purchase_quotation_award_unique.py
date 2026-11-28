# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William Jos? Moreno Reyes

"""#2140/#2294: un comparativo finalizado admite una ?nica adjudicaci?n, aislado."""

from datetime import date

import pytest
from sqlalchemy.exc import IntegrityError

from cacao_accounting import create_app
from cacao_accounting.config import configuracion
from cacao_accounting.database import Currency, Entity, PurchaseQuotation, PurchaseQuotationAward, database


@pytest.fixture
def isolated_app():
    app = create_app(
        {
            **configuracion,
            "TESTING": True,
            "WTF_CSRF_ENABLED": False,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
        }
    )
    with app.app_context():
        database.create_all()
        database.session.add(Currency(code="NIO", name="C?rdoba", decimals=2, active=True, default=True))
        database.session.add(
            Entity(
                code="A2140",
                name="Compras 2140",
                company_name="Compras 2140 SA",
                tax_id="A2140",
                currency="NIO",
                enabled=True,
            )
        )
        database.session.commit()
    yield app
    with app.app_context():
        database.session.remove()
        database.engine.dispose()


def test_award_unico_por_comparativo(isolated_app):
    """Dos adjudicaciones sobre el mismo comparativo violan la restricci?n ?nica (#2140)."""
    with isolated_app.app_context():
        rfq = PurchaseQuotation(company="A2140", posting_date=date(2026, 5, 15), docstatus=1, document_no="RFQ-2140A")
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
