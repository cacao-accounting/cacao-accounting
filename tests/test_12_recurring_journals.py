# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

import json
from datetime import date
from decimal import Decimal

import pytest
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
        from cacao_accounting.database import Accounts, Currency, Entity, Modules, User, database

        database.create_all()
        database.session.add_all(
            [
                Entity(
                    code="abc",
                    name="ABC",
                    company_name="ABC",
                    tax_id="J0001",
                    currency="NIO",
                ),
                Entity(
                    code="cacao",
                    name="Cacao",
                    company_name="Cacao SA",
                    tax_id="J0002",
                    currency="NIO",
                    enabled=True,
                ),
                Modules(module="accounting", default=True, enabled=True),
                User(user="admin", name="Admin", password=b"x", classification="admin", active=True),
                Currency(code="NIO", name="Córdoba", decimals=2, active=True, default=True),
                Accounts(entity="abc", code="6101", name="Gasto", active=True, enabled=True, group=False),
                Accounts(entity="abc", code="1105", name="Seguro pagado", active=True, enabled=True, group=False),
                Accounts(entity="abc", code="6000", name="Gasto extendido", active=True, enabled=True, group=False),
                Accounts(entity="abc", code="1000", name="Caja", active=True, enabled=True, group=False),
            ]
        )
        database.session.commit()
        yield app


def _login(client, user_id: str) -> None:
    with client.session_transaction() as session:
        session["_user_id"] = user_id
        session["_fresh"] = True


def test_recurring_journal_flow(app_ctx):
    with app_ctx.app_context():
        # 1. Crear plantilla
        data = {
            "code": "REC-001",
            "name": "Amortizacion Seguros",
            "company": "abc",
            "ledger_id": "L01",
            "books": ["L01", "L02"],
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
        assert json.loads(template.book_codes) == ["L01", "L02"]

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
        assert json.loads(journal.book_codes) == ["L01", "L02"]

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
        assert target_line.internal_reference is None
        assert target_line.internal_reference_id is None
        assert target_line.is_advance is False


def test_e2e_recurring_journal_monthly_close_creates_visible_postable_lines(app_ctx):
    from cacao_accounting.database import (
        AccountingPeriod,
        Accounts,
        Book,
        ComprobanteContableDetalle,
        FiscalYear,
        GLEntry,
        PeriodCloseCheck,
        PeriodCloseRun,
        RecurringJournalApplication,
        RecurringJournalItem,
        RecurringJournalTemplate,
        User,
        database,
    )

    user = User.query.filter_by(user="admin").first()
    debit_account = Accounts(
        entity="cacao",
        code="52.01.E2E",
        name="Gasto recurrente E2E",
        active=True,
        enabled=True,
        group=False,
    )
    credit_account = Accounts(
        entity="cacao",
        code="11.01.E2E",
        name="Caja recurrente E2E",
        active=True,
        enabled=True,
        group=False,
    )
    book = Book(entity="cacao", code="FISC", name="Fiscal", status="activo", is_primary=True, currency="NIO")
    fiscal_year = FiscalYear(
        entity="cacao",
        name="FY-REC-E2E",
        year_start_date=date(2026, 1, 1),
        year_end_date=date(2026, 12, 31),
    )
    database.session.add_all([debit_account, credit_account, book, fiscal_year])
    database.session.flush()
    period = AccountingPeriod(
        entity="cacao",
        fiscal_year_id=fiscal_year.id,
        name="2026-05",
        start=date(2026, 5, 1),
        end=date(2026, 5, 31),
        enabled=True,
        is_closed=False,
    )
    database.session.add(period)
    database.session.commit()

    client = app_ctx.test_client()
    _login(client, user.id)

    new_template_response = client.get("/accounting/journal/recurring/new")
    assert new_template_response.status_code == 200

    template_items = [
        {
            "account_code": debit_account.id,
            "debit": "250.00",
            "credit": "0",
            "description": "Gasto recurrente E2E",
        },
        {
            "account_code": credit_account.id,
            "debit": "0",
            "credit": "250.00",
            "description": "Pago recurrente E2E",
        },
    ]
    create_response = client.post(
        "/accounting/journal/recurring/new",
        data={
            "code": "REC-E2E-CLOSE",
            "name": "Recurrente E2E cierre",
            "company": "cacao",
            "ledger_id": "FISC",
            "books": ["FISC"],
            "start_date": "2026-05-01",
            "end_date": "2026-12-31",
            "frequency": "monthly",
            "currency": "NIO",
            "items_json": json.dumps(template_items),
        },
        follow_redirects=False,
    )
    template = database.session.execute(database.select(RecurringJournalTemplate).filter_by(code="REC-E2E-CLOSE")).scalar_one()
    persisted_items = (
        database.session.execute(database.select(RecurringJournalItem).filter_by(template_id=template.id)).scalars().all()
    )

    assert create_response.status_code == 302
    assert {item.account_code for item in persisted_items} == {"52.01.E2E", "11.01.E2E"}

    template_view_response = client.get(f"/accounting/journal/recurring/{template.id}")
    approve_response = client.post(f"/accounting/journal/recurring/{template.id}/approve", follow_redirects=False)
    database.session.refresh(template)

    assert template_view_response.status_code == 200
    assert approve_response.status_code == 302
    assert template.status == "approved"

    close_list_response = client.get("/accounting/period-close/monthly")
    close_create_response = client.post(
        "/accounting/period-close/monthly/new",
        data={"period_id": period.id},
        follow_redirects=False,
    )
    close_run = database.session.execute(database.select(PeriodCloseRun).filter_by(period_id=period.id)).scalar_one()
    close_view_response = client.get(f"/accounting/period-close/monthly/{close_run.id}")
    apply_response = client.post(
        f"/accounting/period-close/monthly/{close_run.id}/apply-recurring",
        data={"template_ids": [template.id]},
        follow_redirects=False,
    )

    check = database.session.execute(database.select(PeriodCloseCheck).filter_by(close_run_id=close_run.id)).scalar_one()
    application = database.session.execute(
        database.select(RecurringJournalApplication).filter_by(template_id=template.id)
    ).scalar_one()
    journal = database.session.get(ComprobanteContable, application.journal_id)
    lines = (
        database.session.execute(
            database.select(ComprobanteContableDetalle).filter_by(
                transaction="journal_entry",
                transaction_id=journal.id,
            )
        )
        .scalars()
        .all()
    )

    assert close_list_response.status_code == 200
    assert close_create_response.status_code == 302
    assert close_view_response.status_code == 200
    assert apply_response.status_code == 302
    assert check.check_status == "passed"
    assert application.journal_id
    assert journal.is_recurrent is True
    assert journal.recurrent_template_id == template.id
    assert journal.recurrent_application_id == application.id
    assert len(lines) == 2
    assert {line.account for line in lines} == {"52.01.E2E", "11.01.E2E"}

    journal_view_response = client.get(f"/accounting/journal/{journal.id}")
    assert journal_view_response.status_code == 200
    assert "Gasto recurrente E2E" in journal_view_response.get_data(as_text=True)

    submit_response = client.post(f"/accounting/journal/{journal.id}/submit", follow_redirects=False)
    entries = database.session.execute(database.select(GLEntry).filter_by(voucher_id=journal.id)).scalars().all()
    database.session.refresh(journal)

    assert submit_response.status_code == 302
    assert journal.status == "submitted"
    assert entries


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
