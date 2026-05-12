# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

import pytest
from decimal import Decimal
from datetime import date
from cacao_accounting import create_app
from cacao_accounting.config import configuracion
from cacao_accounting.database import database, ComprobanteContable
from cacao_accounting.contabilidad.recurring_journal_service import (
    create_recurring_template,
    approve_recurring_template,
    apply_recurring_template,
    RecurringJournalError,
)


@pytest.fixture()
def app_ctx():
    app = create_app(
        {
            **configuracion,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
            "WTF_CSRF_ENABLED": False,
            "TESTING": True,
        }
    )
    with app.app_context():
        from cacao_accounting.database import Entity, database

        database.create_all()
        database.session.add(
            Entity(
                code="abc",
                name="ABC",
                company_name="ABC",
                tax_id="J0001",
                currency="NIO",
            )
        )
        database.session.commit()
        yield app


def test_recurring_journal_flow(app_ctx):
    with app_ctx.app_context():
        # 1. Crear plantilla
        data = {
            "code": "REC-001",
            "name": "Amortizacion Seguros",
            "company": "abc",
            "ledger_id": "L01",
            "start_date": date(2026, 1, 1),
            "end_date": date(2026, 12, 31),
            "frequency": "monthly",
        }
        items = [
            {"account_code": "6101", "debit": 100, "credit": 0, "description": "Gasto"},
            {"account_code": "1105", "debit": 0, "credit": 100, "description": "Seguro Pagado Anticipado"},
        ]
        template = create_recurring_template(data, items, user_id="admin")
        assert template.status == "draft"

        # 2. Aprobar
        approve_recurring_template(template.id, user_id="admin")
        assert template.status == "approved"

        # 3. Aplicar a un periodo
        app_log = apply_recurring_template(
            template_id=template.id,
            fiscal_year="2026",
            period_name="2026-05",
            application_date=date(2026, 5, 31),
            user_id="admin",
        )
        assert app_log.status == "applied"
        assert app_log.journal_id is not None

        journal = database.session.get(ComprobanteContable, app_log.journal_id)
        assert journal.is_recurrent is True
        assert journal.recurrent_template_id == template.id

        # 4. Evitar duplicados
        with pytest.raises(RecurringJournalError, match="ya fue aplicada"):
            apply_recurring_template(
                template_id=template.id,
                fiscal_year="2026",
                period_name="2026-05",
                application_date=date(2026, 5, 31),
                user_id="admin",
            )


def test_recurring_journal_balance_validation(app_ctx):
    with app_ctx.app_context():
        data = {"code": "REC-ERR", "name": "Error", "company": "abc", "start_date": date.today(), "end_date": date.today()}
        items = [
            {"account_code": "1000", "debit": 100, "credit": 0},
            {"account_code": "2000", "debit": 0, "credit": 99},  # No balancea
        ]
        with pytest.raises(RecurringJournalError, match="balanceada"):
            create_recurring_template(data, items, user_id="admin")


def test_recurring_journal_extended_fields(app_ctx):
    with app_ctx.app_context():
        data = {
            "code": "REC-EXT",
            "name": "Extended Template",
            "company": "abc",
            "start_date": date(2026, 1, 1),
            "end_date": date(2026, 12, 31),
        }
        items = [
            {
                "account_code": "6000",
                "debit": 500,
                "credit": 0,
                "cost_center": "CC1",
                "unit": "U1",
                "project": "P1",
                "party_type": "supplier",
                "party_id": "S1",
                "reference_type": "invoice",
                "reference_name": "INV-001",
                "is_advance": True,
            },
            {"account_code": "1000", "debit": 0, "credit": 500},
        ]
        template = create_recurring_template(data, items, user_id="admin")
        approve_recurring_template(template.id, user_id="admin")

        app_log = apply_recurring_template(
            template_id=template.id,
            fiscal_year="2026",
            period_name="2026-01",
            application_date=date(2026, 1, 31),
            user_id="admin",
        )

        journal = database.session.get(ComprobanteContable, app_log.journal_id)
        from cacao_accounting.database import ComprobanteContableDetalle

        lines = database.session.query(ComprobanteContableDetalle).filter_by(transaction_id=journal.id).all()

        target_line = next(line for line in lines if line.account == "6000")
        assert target_line.cost_center == "CC1"
        assert target_line.unit == "U1"
        assert target_line.project == "P1"
        assert target_line.third_type == "supplier"
        assert target_line.third_code == "S1"
        assert target_line.internal_reference == "invoice"
        assert target_line.internal_reference_id == "INV-001"
        assert target_line.is_advance is True


def test_posting_initializes_outstanding_amount(app_ctx):
    from cacao_accounting.contabilidad.posting import post_document_to_gl
    from cacao_accounting.database import (
        Accounts,
        PartyAccount,
        SalesInvoice,
        SalesInvoiceItem,
        database,
    )

    with app_ctx.app_context():
        receivable_account = Accounts(
            entity="abc",
            code="AR-001",
            name="Cuentas por cobrar",
            active=True,
            enabled=True,
            classification="asset",
        )
        income_account = Accounts(
            entity="abc",
            code="IN-001",
            name="Ventas",
            active=True,
            enabled=True,
            classification="income",
            account_type="income",
        )
        database.session.add_all([receivable_account, income_account])
        database.session.flush()

        party_account = PartyAccount(
            party_id="CUST-001",
            company="abc",
            receivable_account_id=receivable_account.id,
        )
        invoice = SalesInvoice(
            company="abc",
            posting_date=date(2026, 5, 4),
            customer_id="CUST-001",
            customer_name="Cliente prueba",
            docstatus=1,
            document_no="abc-SI-2026-05-00001",
            total=Decimal("150.00"),
            # grand_total and outstanding_amount NOT SET
        )
        database.session.add_all([party_account, invoice])
        database.session.flush()

        item = SalesInvoiceItem(
            sales_invoice_id=invoice.id,
            item_code="ITEM-001",
            item_name="Servicio de prueba",
            qty=Decimal("1"),
            rate=Decimal("150.00"),
            amount=Decimal("150.00"),
            income_account_id=income_account.id,
        )
        database.session.add(item)
        database.session.commit()

        post_document_to_gl(invoice)
        database.session.commit()

        # Verify grand_total and outstanding_amount were initialized
        assert invoice.grand_total == Decimal("150.00")
        assert invoice.outstanding_amount == Decimal("150.00")
