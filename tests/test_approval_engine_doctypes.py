# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Regressions for approval-engine document submission dispatch (#1022)."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest

from cacao_accounting.approval_engine import ApprovalEngine
from cacao_accounting.database import (
    Accounts,
    ApprovalAction,
    ApprovalMatrix,
    ApprovalRequest,
    CacaoConfig,
    GLEntry,
    Item,
    Party,
    SalesInvoice,
    SalesInvoiceItem,
    UOM,
    User,
    database,
)


def _enable_approval_for_admin(doctype: str, admin: User) -> None:
    """Enable a final approval level for the isolated company's admin."""
    database.session.add(CacaoConfig(key="approval_engine_enabled_cacao", value="true"))
    database.session.add(
        ApprovalMatrix(
            company_id="cacao",
            document_type=doctype,
            user_id=admin.id,
            min_amount=0,
            max_amount=None,
            approval_level=1,
            enabled=True,
        )
    )
    database.session.flush()


def test_sales_debit_note_approved_is_submitted_and_posted(entorno_contable_aislado):
    """An approved debit note reaches submitted state and produces its GL evidence."""
    with entorno_contable_aislado.app.app_context():
        customer = database.session.execute(database.select(Party).filter_by(code="CLI001")).scalar_one()
        item = database.session.execute(database.select(Item).filter_by(code="ART01")).scalar_one()
        uom = database.session.execute(database.select(UOM).filter_by(code="UND")).scalar_one()
        income = database.session.execute(database.select(Accounts).filter_by(entity="cacao", code="4101")).scalar_one()
        admin = database.session.execute(database.select(User).filter_by(user="admin")).scalar_one()
        _enable_approval_for_admin("sales_debit_note", admin)

        note = SalesInvoice(
            company="cacao",
            posting_date=date(2026, 5, 15),
            document_date=date(2026, 5, 15),
            document_no=f"ND-APP-{uuid4().hex[:10]}",
            document_type="sales_debit_note",
            customer_id=customer.id,
            customer_name=customer.name,
            transaction_currency="NIO",
            base_currency="NIO",
            exchange_rate=Decimal("1"),
            total=Decimal("10"),
            base_total=Decimal("10"),
            grand_total=Decimal("10"),
            base_grand_total=Decimal("10"),
            outstanding_amount=Decimal("10"),
            base_outstanding_amount=Decimal("10"),
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
                rate=Decimal("10"),
                amount=Decimal("10"),
                base_amount=Decimal("10"),
                income_account_id=income.id,
            )
        )
        database.session.flush()

        with entorno_contable_aislado.app.test_request_context("/"):
            from flask_login import login_user

            login_user(admin, force=True)
            assert ApprovalEngine.handle_submission(note, admin, "Nota de débito") is True

        request = database.session.execute(
            database.select(ApprovalRequest).where(
                ApprovalRequest.document_type == "sales_debit_note",
                ApprovalRequest.document_id == note.id,
            )
        ).scalar_one()
        entries = database.session.execute(database.select(GLEntry).filter_by(voucher_id=note.id)).scalars().all()
        assert request.status == "Approved"
        assert note.docstatus == 1
        assert entries, "El submit aprobado debe generar movimientos del mayor."


def test_doctype_sin_dispatch_falla_sin_marcar_solicitud_aprobada(entorno_contable_aislado):
    """An unsupported configured doctype cannot silently complete its approval."""
    from cacao_accounting.database import Bank, BankAccount, BankTransaction

    with entorno_contable_aislado.app.app_context():
        admin = database.session.execute(database.select(User).filter_by(user="admin")).scalar_one()
        bank = Bank(name=f"Banco {uuid4().hex[:8]}")
        database.session.add(bank)
        database.session.flush()
        account = BankAccount(
            company="cacao",
            bank_id=bank.id,
            account_name="Cuenta de prueba",
            account_no=f"APP-{uuid4().hex[:10]}",
            is_active=True,
        )
        database.session.add(account)
        database.session.flush()
        transaction = BankTransaction(
            bank_account_id=account.id,
            identity_key=f"approval-{uuid4().hex}",
            posting_date=date(2026, 5, 15),
            withdrawal=Decimal("5"),
            description="Movimiento manual para prueba de despacho",
        )
        transaction.company = "cacao"
        database.session.add(transaction)
        database.session.flush()
        request = ApprovalRequest(
            document_type="bank_transaction",
            document_id=transaction.id,
            company_id="cacao",
            requested_by=admin.id,
            current_level=1,
            required_level=1,
            status="Pending Approval",
        )
        database.session.add(request)
        _enable_approval_for_admin("bank_transaction", admin)
        database.session.commit()

        try:
            with pytest.raises(ValueError, match="no tiene flujo de envío"):
                ApprovalEngine.approve(transaction, admin, request=request)
        finally:
            database.session.rollback()

        persisted_request = database.session.get(ApprovalRequest, request.id)
        persisted_transaction = database.session.get(BankTransaction, transaction.id)
        actions = (
            database.session.execute(database.select(ApprovalAction).filter_by(approval_request_id=request.id)).scalars().all()
        )
        assert persisted_request is not None and persisted_request.status == "Pending Approval"
        assert persisted_transaction is not None
        assert actions == []
