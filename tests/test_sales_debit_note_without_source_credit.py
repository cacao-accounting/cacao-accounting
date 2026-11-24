# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1616: las notas de débito sin origen cuentan en el crédito del cliente."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy.pool import StaticPool

from cacao_accounting import create_app
from cacao_accounting.config import configuracion
from cacao_accounting.database import (
    CompanyParty,
    Currency,
    DocumentRelation,
    Entity,
    Party,
    SalesInvoice,
    database,
)
from cacao_accounting.ventas.services import _approved_customer_invoices, _validate_credit_limit_and_overdue


@pytest.fixture
def credit_scene():
    application = create_app(
        {
            **configuracion,
            "SQLALCHEMY_DATABASE_URI": "sqlite://",
            "SQLALCHEMY_ENGINE_OPTIONS": {"poolclass": StaticPool},
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
            "TESTING": True,
            "MODO_ESCRITORIO": True,
        }
    )
    sufijo = uuid4().hex[:6]
    with application.app_context():
        database.create_all()
        database.session.add_all(
            [
                Currency(code="NIO", name="Córdoba", decimals=2, active=True, default=True),
                Entity(
                    code="cacao",
                    name="Cacao",
                    company_name="Cacao SA",
                    tax_id=f"J-{sufijo}",
                    currency="NIO",
                    enabled=True,
                    status="default",
                ),
                Party(code=f"CLI-{sufijo}", name="Cliente 1616", is_customer=True, is_active=True),
            ]
        )
        database.session.flush()
        party = database.session.execute(database.select(Party).filter_by(code=f"CLI-{sufijo}")).scalar_one()
        database.session.add(CompanyParty(company="cacao", party_id=party.id, is_active=True, credit_limit=Decimal("50")))
        database.session.commit()
        ids = {"party": party.id, "sufijo": sufijo}
    yield application, ids
    with application.app_context():
        database.session.remove()
        database.engine.dispose()


def _factura(
    company: str,
    customer_id: str,
    document_no: str,
    total: str,
    *,
    document_type: str = "sales_invoice",
    reversal_of: str | None = None,
) -> SalesInvoice:
    factura = SalesInvoice(
        company=company,
        customer_id=customer_id,
        customer_name="Cliente 1616",
        posting_date=date(2026, 5, 15),
        document_type=document_type,
        docstatus=1,
        status="open",
        document_no=document_no,
        reversal_of=reversal_of,
        transaction_currency="NIO",
        base_currency="NIO",
        total=Decimal(total),
        grand_total=Decimal(total),
        outstanding_amount=Decimal(total),
        base_total=Decimal(total),
        base_grand_total=Decimal(total),
        base_outstanding_amount=Decimal(total),
    )
    database.session.add(factura)
    database.session.flush()
    return factura


def test_nota_debito_sin_origen_bloquea_por_limite(credit_scene):
    """Una nota de débito sin factura origen no puede desaparecer del límite."""
    application, ids = credit_scene
    with application.app_context():
        _factura("cacao", ids["party"], f"ND-{ids['sufijo']}", "100", document_type="sales_debit_note")
        database.session.commit()

        with pytest.raises(ValueError, match="límite de crédito"):
            _validate_credit_limit_and_overdue("cacao", ids["party"], Decimal("10"))


def test_nota_debito_vinculada_no_se_cuenta_dos_veces(credit_scene):
    """La nota con relación activa queda representada por su factura origen."""
    application, ids = credit_scene
    with application.app_context():
        source = _factura("cacao", ids["party"], f"FV-{ids['sufijo']}", "100")
        note = _factura(
            "cacao",
            ids["party"],
            f"ND-{ids['sufijo']}",
            "100",
            document_type="sales_debit_note",
            reversal_of=source.id,
        )
        database.session.add(
            DocumentRelation(
                source_type="sales_invoice",
                source_id=source.id,
                source_item_id=None,
                target_type="sales_debit_note",
                target_id=note.id,
                target_item_id=None,
                company="cacao",
                qty=Decimal("1"),
                rate=Decimal("100"),
                amount=Decimal("100"),
                relation_type="invoice_reversal",
                status="active",
            )
        )
        database.session.commit()

        facturas = _approved_customer_invoices("cacao", ids["party"])
        assert [factura.id for factura in facturas] == [source.id]

        database.session.execute(
            database.update(CompanyParty).where(CompanyParty.party_id == ids["party"]).values(credit_limit=Decimal("250"))
        )
        database.session.commit()
        _validate_credit_limit_and_overdue("cacao", ids["party"], Decimal("10"))
