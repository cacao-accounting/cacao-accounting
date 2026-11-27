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
    posting_date: date | None = None,
) -> SalesInvoice:
    factura = SalesInvoice(
        company=company,
        customer_id=customer_id,
        customer_name="Cliente 1616",
        posting_date=posting_date or date(2026, 5, 15),
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


def _activar_bloqueo_por_vencimiento(party_id: str) -> None:
    """Aísla el bloqueo por vencimiento del límite de crédito del escenario."""
    database.session.execute(
        database.update(CompanyParty).where(CompanyParty.party_id == party_id).values(block_overdue=True, credit_limit=None)
    )
    database.session.commit()


def test_nota_debito_sin_origen_vencida_bloquea_la_venta(credit_scene):
    """Una nota sin factura origen vencida activa el bloqueo de ventas."""
    application, ids = credit_scene
    with application.app_context():
        _activar_bloqueo_por_vencimiento(ids["party"])
        _factura("cacao", ids["party"], f"ND-{ids['sufijo']}", "100", document_type="sales_debit_note")
        database.session.commit()

        with pytest.raises(ValueError, match="facturas vencidas"):
            _validate_credit_limit_and_overdue("cacao", ids["party"], Decimal("10"))


def test_nota_debito_sin_origen_al_dia_no_bloquea_la_venta(credit_scene):
    """La misma nota con fecha corriente no bloquea cuando no está vencida."""
    application, ids = credit_scene
    with application.app_context():
        _activar_bloqueo_por_vencimiento(ids["party"])
        _factura(
            "cacao",
            ids["party"],
            f"ND-{ids['sufijo']}",
            "100",
            document_type="sales_debit_note",
            posting_date=date.today(),
        )
        database.session.commit()

        _validate_credit_limit_and_overdue("cacao", ids["party"], Decimal("10"))


def _post_debit_note_no_source(entorno, *, customer_id: str, suffix: str, posting_date: date, amount: str) -> str:
    from cacao_accounting.approval_engine import approved_execution
    from cacao_accounting.contabilidad.posting_service import submit_document
    from cacao_accounting.database import Accounts, Item, SalesInvoice, SalesInvoiceItem, UOM, User
    from cacao_accounting.internal_control_service import audit_actor

    with entorno.app.app_context():
        actor = database.session.execute(database.select(User).filter_by(user="admin")).scalar_one()
        item = database.session.execute(database.select(Item).filter_by(code="ART01")).scalar_one()
        uom = database.session.execute(database.select(UOM).filter_by(code="UND")).scalar_one()
        income = database.session.execute(database.select(Accounts).filter_by(entity="cacao", code="4101")).scalar_one()
        note = SalesInvoice(
            company="cacao",
            posting_date=posting_date,
            document_date=posting_date,
            document_no=f"ND-FUNC-{suffix}",
            customer_id=customer_id,
            customer_name="Cliente ND",
            document_type="sales_debit_note",
            is_return=False,
            transaction_currency="NIO",
            base_currency="NIO",
            exchange_rate=Decimal("1"),
            total=Decimal(amount),
            base_total=Decimal(amount),
            grand_total=Decimal(amount),
            base_grand_total=Decimal(amount),
            outstanding_amount=Decimal(amount),
            base_outstanding_amount=Decimal(amount),
        )
        database.session.add(note)
        database.session.flush()
        database.session.add(
            SalesInvoiceItem(
                sales_invoice_id=note.id,
                item_code=item.code,
                item_name=item.name,
                qty=Decimal("1"),
                qty_in_base_uom=Decimal("1"),
                uom=uom.code,
                rate=Decimal(amount),
                amount=Decimal(amount),
                base_amount=Decimal(amount),
                income_account_id=income.id,
            )
        )
        database.session.flush()
        with audit_actor(actor.id, actor.name), approved_execution(note, actor.id):
            submit_document(note)
        database.session.commit()
        return note.id


def _create_and_submit_payment(entorno, *, customer_id: str, invoice_id: str, amount: str, posting_date: str) -> str:
    from cacao_accounting.approval_engine import approved_execution
    from cacao_accounting.contabilidad.posting_service import submit_document
    from cacao_accounting.database import PaymentEntry, User
    from cacao_accounting.document_flow.service import create_target_document
    from cacao_accounting.internal_control_service import audit_actor

    with entorno.app.app_context():
        actor = database.session.execute(database.select(User).filter_by(user="admin")).scalar_one()
        result = create_target_document(
            {
                "target_document_type": "payment_entry",
                "company": "cacao",
                "posting_date": posting_date,
                "payment_type": "receive",
                "party_type": "customer",
                "party_id": customer_id,
                "currency": "NIO",
                "base_currency": "NIO",
                "exchange_rate": "1",
                "lines": [
                    {
                        "source_document_type": "sales_invoice",
                        "source_document_id": invoice_id,
                        "allocated_amount": amount,
                    }
                ],
            }
        )
        payment = database.session.get(PaymentEntry, result["target_id"])
        assert payment is not None
        with audit_actor(actor.id, actor.name), approved_execution(payment, actor.id):
            submit_document(payment)
        database.session.commit()
        return payment.id


def test_nota_debito_sin_origen_vencida_bloquea_y_pago_restaura(entorno_contable_aislado):
    """#2289: ND sin origen contabilizada real bloquea por vencimiento; pagos/cancelaci?n restauran."""
    from cacao_accounting.approval_engine import approved_execution
    from cacao_accounting.contabilidad.posting_service import cancel_document
    from cacao_accounting.database import PaymentEntry, SalesInvoice, User
    from cacao_accounting.document_flow.service import compute_outstanding_amount
    from cacao_accounting.internal_control_service import audit_actor

    entorno = entorno_contable_aislado
    with entorno.app.app_context():
        customer = database.session.execute(database.select(Party).filter_by(code="CLI001")).scalar_one()
        customer_id = customer.id
        other = Party(
            code=f"CLIOTR-{uuid4().hex[:6]}",
            name="Cliente Otro",
            is_customer=True,
        )
        database.session.add(other)
        database.session.flush()
        database.session.add(CompanyParty(company="cacao", party_id=other.id, is_active=True, block_overdue=True))
        database.session.execute(
            database.update(CompanyParty)
            .where(CompanyParty.company == "cacao", CompanyParty.party_id == customer_id)
            .values(block_overdue=True, credit_limit=None)
        )
        database.session.commit()
        other_id = other.id

    note_id = _post_debit_note_no_source(
        entorno, customer_id=customer_id, suffix=uuid4().hex[:6], posting_date=date(2026, 5, 10), amount="100"
    )

    with entorno.app.app_context():
        note = database.session.get(SalesInvoice, note_id)
        assert note is not None and note.docstatus == 1
        assert Decimal(str(compute_outstanding_amount(note))) == Decimal("100")
        with pytest.raises(ValueError, match="facturas vencidas|vencidas|Vencida"):
            _validate_credit_limit_and_overdue("cacao", customer_id, Decimal("10"))
        _validate_credit_limit_and_overdue("cacao", other_id, Decimal("10"))

    payment_id = _create_and_submit_payment(
        entorno, customer_id=customer_id, invoice_id=note_id, amount="40", posting_date="2026-05-11"
    )
    with entorno.app.app_context():
        note = database.session.get(SalesInvoice, note_id)
        assert Decimal(str(compute_outstanding_amount(note))) == Decimal("60")
        with pytest.raises(ValueError, match="facturas vencidas|vencidas|Vencida"):
            _validate_credit_limit_and_overdue("cacao", customer_id, Decimal("10"))

    _create_and_submit_payment(entorno, customer_id=customer_id, invoice_id=note_id, amount="60", posting_date="2026-05-12")
    with entorno.app.app_context():
        note = database.session.get(SalesInvoice, note_id)
        assert Decimal(str(compute_outstanding_amount(note))) == Decimal("0")
        _validate_credit_limit_and_overdue("cacao", customer_id, Decimal("10"))

    with entorno.app.app_context():
        actor = database.session.execute(database.select(User).filter_by(user="admin")).scalar_one()
        payment = database.session.get(PaymentEntry, payment_id)
        assert payment is not None
        with audit_actor(actor.id, actor.name), approved_execution(payment, actor.id):
            cancel_document(
                payment,
                reason="Reversi?n prueba #2289",
                actor_user_id=actor.id,
                cancellation_date=date(2026, 5, 11),
            )
        database.session.commit()

    with entorno.app.app_context():
        note = database.session.get(SalesInvoice, note_id)
        assert Decimal(str(compute_outstanding_amount(note))) == Decimal("40")
        with pytest.raises(ValueError, match="facturas vencidas|vencidas|Vencida"):
            _validate_credit_limit_and_overdue("cacao", customer_id, Decimal("10"))
        _validate_credit_limit_and_overdue("otra", customer_id, Decimal("10"))
