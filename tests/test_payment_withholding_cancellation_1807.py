# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 William José Moreno Reyes

"""#1807: anular un pago también cancela su certificado propio de retención."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import uuid4

from sqlalchemy import select

from cacao_accounting.approval_engine import approved_execution
from cacao_accounting.contabilidad.cancellation_service import active_cancellation_dependencies
from cacao_accounting.contabilidad.posting_service import cancel_document, submit_document
from cacao_accounting.database import (
    Accounts,
    GLEntry,
    Item,
    Party,
    PaymentEntry,
    PurchaseInvoice,
    PurchaseInvoiceItem,
    UOM,
    User,
    WithholdingCertificate,
    database,
)
from cacao_accounting.document_flow.service import create_target_document
from cacao_accounting.internal_control_service import audit_actor

FECHA = date(2026, 5, 15)


def _posted_supplier_payment(app) -> tuple[str, str, str]:
    """Postea una factura de compra y su pago real a proveedor."""
    with app.app_context():
        actor = database.session.execute(select(User).filter_by(user="admin")).scalar_one()
        supplier = database.session.execute(select(Party).filter_by(code="PRV001")).scalar_one()
        item = database.session.execute(select(Item).filter_by(code="ART01")).scalar_one()
        uom = database.session.execute(select(UOM).filter_by(code="UND")).scalar_one()
        expense = database.session.execute(select(Accounts).filter_by(entity="cacao", code="5201")).scalar_one()
        invoice = PurchaseInvoice(
            company="cacao",
            posting_date=FECHA,
            document_no=f"PI-1807-{uuid4().hex[:8]}",
            document_type="purchase_invoice",
            supplier_id=supplier.id,
            supplier_name=supplier.name,
            transaction_currency="NIO",
            base_currency="NIO",
            exchange_rate=Decimal("1"),
            total=Decimal("100"),
            grand_total=Decimal("100"),
            base_grand_total=Decimal("100"),
            outstanding_amount=Decimal("100"),
        )
        database.session.add(invoice)
        database.session.flush()
        database.session.add(
            PurchaseInvoiceItem(
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
            )
        )
        database.session.commit()
        with audit_actor(actor.id, actor.name), approved_execution(invoice, actor.id):
            submit_document(invoice)
        database.session.commit()

        result = create_target_document(
            {
                "target_document_type": "payment_entry",
                "company": "cacao",
                "posting_date": FECHA.isoformat(),
                "payment_type": "pay",
                "party_type": "supplier",
                "party_id": supplier.id,
                "currency": "NIO",
                "base_currency": "NIO",
                "exchange_rate": "1",
                "lines": [
                    {
                        "source_document_type": "purchase_invoice",
                        "source_document_id": invoice.id,
                        "allocated_amount": "100",
                    }
                ],
            }
        )
        payment = database.session.get(PaymentEntry, result["target_id"])
        assert payment is not None
        with audit_actor(actor.id, actor.name), approved_execution(payment, actor.id):
            submit_document(payment)
        database.session.commit()
        return str(payment.id), str(supplier.id), str(actor.id)


def test_anular_pago_cancela_certificado_propio(entorno_contable_aislado):
    """El certificado issued no bloquea la anulación que debe cancelarlo."""
    app = entorno_contable_aislado.app
    payment_id, supplier_id, actor_id = _posted_supplier_payment(app)
    with app.app_context():
        payment = database.session.get(PaymentEntry, payment_id)
        supplier = database.session.get(Party, supplier_id)
        assert payment is not None and supplier is not None
        certificate = WithholdingCertificate(
            company="cacao",
            payment_id=payment.id,
            supplier_id=supplier.id,
            supplier_name=supplier.name,
            certificate_no=f"RET-1807-{uuid4().hex[:8]}",
            posting_date=FECHA,
            document_date=FECHA,
            currency="NIO",
            gross_amount=Decimal("100"),
            withheld_amount=Decimal("10"),
            cash_amount=Decimal("90"),
            lines_json='[{"concept":"ISR","amount":"10"}]',
            status="issued",
            docstatus=1,
        )
        database.session.add(certificate)
        database.session.commit()
        certificate_id = certificate.id

        dependencies = active_cancellation_dependencies(payment, "payment_entry", payment.id)
        assert all(dependency.kind != "withholding_certificate" for dependency in dependencies)

        actor = database.session.get(User, actor_id)
        assert actor is not None
        with audit_actor(actor.id, actor.name), approved_execution(payment, actor.id):
            cancel_document(
                payment,
                reason="Anular pago con retención",
                actor_user_id=actor.id,
                cancellation_date=FECHA,
            )
        database.session.commit()
        database.session.expire_all()

        cancelled_payment = database.session.get(PaymentEntry, payment_id)
        cancelled_certificate = database.session.get(WithholdingCertificate, certificate_id)
        assert cancelled_payment is not None and cancelled_payment.docstatus == 2
        assert cancelled_certificate is not None
        assert (cancelled_certificate.status, cancelled_certificate.docstatus) == ("cancelled", 2)
        assert cancelled_certificate.withheld_amount == Decimal("10")
        reversals = (
            database.session.execute(
                select(GLEntry).where(
                    GLEntry.voucher_type == "payment_entry",
                    GLEntry.voucher_id == payment_id,
                    GLEntry.is_reversal.is_(True),
                )
            )
            .scalars()
            .all()
        )
        assert reversals
