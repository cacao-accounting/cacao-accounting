# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

from __future__ import annotations

import json
from datetime import date

import pytest

from cacao_accounting import create_app
from cacao_accounting.config import configuracion


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
        from cacao_accounting.database import Entity, Modules, User, database

        database.create_all()
        database.session.add_all(
            [
                Entity(code="cacao", name="Cacao", company_name="Cacao", tax_id="J0001", currency="NIO", enabled=True),
                Modules(module="accounting", default=True, enabled=True),
                User(user="admin", name="Admin", password=b"x", classification="admin", active=True),
            ]
        )
        database.session.commit()
        yield app


def _login(client, user_id: str) -> None:
    with client.session_transaction() as session:
        session["_user_id"] = user_id
        session["_fresh"] = True


def test_create_journal_draft_preserves_lines_and_does_not_post_gl(app_ctx):
    from cacao_accounting.contabilidad.journal_service import create_journal_draft
    from cacao_accounting.database import (
        Accounts,
        Bank,
        BankAccount,
        ComprobanteContableDetalle,
        GLEntry,
        database,
    )

    debit_account = Accounts(entity="cacao", code="EXP-001", name="Gasto", active=True, enabled=True, group=False)
    credit_account = Accounts(entity="cacao", code="CASH-001", name="Caja", active=True, enabled=True, group=False)
    bank = Bank(name="Banco Demo", is_active=True)
    database.session.add_all([debit_account, credit_account, bank])
    database.session.commit()
    bank_account = BankAccount(
        bank_id=bank.id,
        company="cacao",
        account_name="Cuenta operativa",
        account_no="001",
        currency="NIO",
        is_active=True,
    )
    database.session.add(bank_account)
    database.session.commit()

    journal = create_journal_draft(
        {
            "company": "cacao",
            "posting_date": "2026-05-06",
            "memo": "Registro manual",
            "lines": [
                {
                    "account": debit_account.id,
                    "cost_center": "MAIN",
                    "project": "PRJ",
                    "debit": "100.00",
                    "credit": "0",
                    "remarks": "Debe",
                },
                {
                    "account": credit_account.id,
                    "party_type": "supplier",
                    "party": "SUP-001",
                    "debit": "0",
                    "credit": "100.00",
                    "reference_type": "purchase_invoice",
                    "reference_name": "PI-001",
                    "is_advance": True,
                    "bank_account": bank_account.id,
                },
            ],
        },
        user_id="user-1",
    )

    lines = (
        database.session.execute(database.select(ComprobanteContableDetalle).filter_by(transaction_id=journal.id))
        .scalars()
        .all()
    )
    gl_entries = database.session.execute(database.select(GLEntry).filter_by(voucher_id=journal.id)).scalars().all()

    assert journal.status == "draft"
    assert len(lines) == 2
    assert lines[0].account == "EXP-001"
    assert lines[0].cost_center == "MAIN"
    assert lines[0].project == "PRJ"
    assert lines[1].third_type == "supplier"
    assert lines[1].is_advance is True
    assert lines[1].bank_account_id == bank_account.id
    assert gl_entries == []


def test_journal_service_rejects_unbalanced_and_double_sided_lines(app_ctx):
    from cacao_accounting.contabilidad.journal_service import JournalValidationError, create_journal_draft

    with pytest.raises(JournalValidationError, match="positivos"):
        create_journal_draft(
            {
                "company": "cacao",
                "posting_date": "2026-05-06",
                "lines": [{"account": "EXP-001", "debit": "10", "credit": "5"}],
            },
            user_id="user-1",
        )

    with pytest.raises(JournalValidationError, match="balanceado"):
        create_journal_draft(
            {
                "company": "cacao",
                "posting_date": "2026-05-06",
                "lines": [
                    {"account": "EXP-001", "debit": "10", "credit": "0"},
                    {"account": "CASH-001", "debit": "0", "credit": "9"},
                ],
            },
            user_id="user-1",
        )


def test_journal_service_requires_cost_center_for_expense_accounts(app_ctx):
    from cacao_accounting.contabilidad.journal_service import JournalValidationError, create_journal_draft
    from cacao_accounting.database import Accounts, database

    expense_account = Accounts(
        entity="cacao",
        code="EXP-CC",
        name="Gasto con centro",
        active=True,
        enabled=True,
        group=False,
        account_type="expense",
    )
    offset_account = Accounts(entity="cacao", code="CASH-CC", name="Caja", active=True, enabled=True, group=False)
    database.session.add_all([expense_account, offset_account])
    database.session.commit()

    with pytest.raises(JournalValidationError, match="centro de costo"):
        create_journal_draft(
            {
                "company": "cacao",
                "posting_date": "2026-05-06",
                "lines": [
                    {"account": expense_account.id, "debit": "10.00", "credit": "0"},
                    {"account": offset_account.id, "debit": "0", "credit": "10.00"},
                ],
            },
            user_id="user-1",
        )


def test_journal_service_allows_non_expense_accounts_without_cost_center(app_ctx):
    from cacao_accounting.contabilidad.journal_service import create_journal_draft
    from cacao_accounting.database import Accounts, database

    asset_account = Accounts(
        entity="cacao",
        code="AST-001",
        name="Caja general",
        active=True,
        enabled=True,
        group=False,
        account_type="cash",
    )
    offset_account = Accounts(entity="cacao", code="CAP-001", name="Capital", active=True, enabled=True, group=False)
    database.session.add_all([asset_account, offset_account])
    database.session.commit()

    journal = create_journal_draft(
        {
            "company": "cacao",
            "posting_date": "2026-05-06",
            "lines": [
                {"account": asset_account.id, "debit": "10.00", "credit": "0"},
                {"account": offset_account.id, "debit": "0", "credit": "10.00"},
            ],
        },
        user_id="user-1",
    )

    assert journal.status == "draft"


def test_journal_new_route_renders_new_backend_form(app_ctx):
    from cacao_accounting.database import User

    user = User.query.filter_by(user="admin").first()
    client = app_ctx.test_client()
    _login(client, user.id)

    response = client.get("/accounting/journal/new")
    html = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "journalEntryForm" in html
    assert "smartSelect" in html
    assert 'doctype: "company"' in html
    assert 'entity_type: "journal_entry"' in html
    assert "loadOnFilterChange: true" in html
    assert 'requiredFilters: ["company"]' in html
    assert 'doctype: "currency"' in html
    assert 'name="csrf_token"' in html
    assert "Buscar cuenta bancaria" not in html
    assert "/accounting/gl/new" not in html


def test_journal_new_closing_query_prefills_closing_stage(app_ctx):
    from cacao_accounting.database import User

    user = User.query.filter_by(user="admin").first()
    client = app_ctx.test_client()
    _login(client, user.id)

    response = client.get("/accounting/journal/new?isclosing=true")
    html = response.get_data(as_text=True)

    assert response.status_code == 200
    assert '"is_closing": true' in html


def test_journal_post_creates_draft_without_gl_entries(app_ctx):
    from cacao_accounting.database import Accounts, Book, ComprobanteContable, GLEntry, User, database

    debit_account = Accounts(entity="cacao", code="EXP-002", name="Gasto", active=True, enabled=True, group=False)
    credit_account = Accounts(entity="cacao", code="CASH-002", name="Caja", active=True, enabled=True, group=False)
    fiscal_book = Book(entity="cacao", code="FISC", name="Fiscal", status="activo", is_primary=True)
    ifrs_book = Book(entity="cacao", code="IFRS", name="IFRS", status="activo")
    database.session.add_all([debit_account, credit_account, fiscal_book, ifrs_book])
    database.session.commit()

    user = User.query.filter_by(user="admin").first()
    client = app_ctx.test_client()
    _login(client, user.id)
    payload = {
        "company": "cacao",
        "posting_date": "2026-05-06",
        "books": ["FISC", "IFRS"],
        "memo": "Desde vista",
        "lines": [
            {"account": debit_account.id, "debit": "25.00", "credit": "0"},
            {"account": credit_account.id, "debit": "0", "credit": "25.00"},
        ],
    }

    response = client.post("/accounting/journal/new", data={"journal_payload": json.dumps(payload)})
    journal = database.session.execute(database.select(ComprobanteContable).filter_by(memo="Desde vista")).scalar_one()
    gl_entries = database.session.execute(database.select(GLEntry).filter_by(voucher_id=journal.id)).scalars().all()

    assert response.status_code == 302
    assert journal.status == "draft"
    assert journal.book == "FISC"
    assert journal.book_codes == '["FISC", "IFRS"]'
    assert gl_entries == []


def test_journal_books_endpoint_returns_only_active_books(app_ctx):
    from cacao_accounting.database import Book, User, database

    database.session.add_all(
        [
            Book(entity="cacao", code="FISC", name="Fiscal", status="activo", is_primary=True),
            Book(entity="cacao", code="IFRS", name="IFRS", status=None),
            Book(entity="cacao", code="TAX", name="Tax", status="inactivo"),
        ]
    )
    database.session.commit()

    user = User.query.filter_by(user="admin").first()
    client = app_ctx.test_client()
    _login(client, user.id)

    response = client.get("/accounting/journal/books?company=cacao")
    payload = response.get_json()

    assert response.status_code == 200
    assert [item["value"] for item in payload["results"]] == ["FISC", "IFRS"]


def test_submit_journal_posts_only_selected_books(app_ctx):
    from cacao_accounting.contabilidad.journal_service import create_journal_draft, submit_journal
    from cacao_accounting.database import Accounts, Book, GLEntry, database

    debit_account = Accounts(entity="cacao", code="EXP-003", name="Gasto", active=True, enabled=True, group=False)
    credit_account = Accounts(entity="cacao", code="CASH-003", name="Caja", active=True, enabled=True, group=False)
    fiscal_book = Book(entity="cacao", code="FISC", name="Fiscal", status="activo", is_primary=True)
    ifrs_book = Book(entity="cacao", code="IFRS", name="IFRS", status="activo")
    database.session.add_all(
        [
            debit_account,
            credit_account,
            fiscal_book,
            ifrs_book,
            Book(entity="cacao", code="TAX", name="Tax", status="inactivo"),
        ]
    )
    database.session.commit()

    journal = create_journal_draft(
        {
            "company": "cacao",
            "posting_date": "2026-05-06",
            "books": ["IFRS"],
            "lines": [
                {"account": debit_account.id, "debit": "10.00", "credit": "0"},
                {"account": credit_account.id, "debit": "0", "credit": "10.00"},
            ],
        },
        user_id="user-1",
    )

    entries = submit_journal(journal.id)

    assert len(entries) == 2
    posted_entries = database.session.execute(database.select(GLEntry).filter_by(voucher_id=journal.id)).scalars().all()
    assert len(posted_entries) == 2
    assert {entry.ledger_id for entry in posted_entries} == {ifrs_book.id}


def test_submit_journal_without_selected_books_posts_all_active_books(app_ctx):
    from cacao_accounting.contabilidad.journal_service import create_journal_draft, submit_journal
    from cacao_accounting.database import Accounts, Book, GLEntry, database

    debit_account = Accounts(entity="cacao", code="EXP-004", name="Gasto", active=True, enabled=True, group=False)
    credit_account = Accounts(entity="cacao", code="CASH-004", name="Caja", active=True, enabled=True, group=False)
    fiscal_book = Book(entity="cacao", code="FISC", name="Fiscal", status="activo", is_primary=True)
    ifrs_book = Book(entity="cacao", code="IFRS", name="IFRS", status="activo")
    database.session.add_all(
        [
            debit_account,
            credit_account,
            fiscal_book,
            ifrs_book,
            Book(entity="cacao", code="TAX", name="Tax", status="inactivo"),
        ]
    )
    database.session.commit()

    journal = create_journal_draft(
        {
            "company": "cacao",
            "posting_date": "2026-05-06",
            "books": [],
            "lines": [
                {"account": debit_account.id, "debit": "15.00", "credit": "0"},
                {"account": credit_account.id, "debit": "0", "credit": "15.00"},
            ],
        },
        user_id="user-1",
    )

    submit_journal(journal.id)

    posted_entries = database.session.execute(database.select(GLEntry).filter_by(voucher_id=journal.id)).scalars().all()
    assert len(posted_entries) == 4
    assert {entry.ledger_id for entry in posted_entries} == {fiscal_book.id, ifrs_book.id}


def test_submit_journal_allows_manual_closing_in_closed_period(app_ctx):
    from cacao_accounting.contabilidad.journal_service import create_journal_draft, submit_journal
    from cacao_accounting.database import Accounts, AccountingPeriod, Book, GLEntry, database

    debit_account = Accounts(entity="cacao", code="EXP-006", name="Gasto", active=True, enabled=True, group=False)
    credit_account = Accounts(entity="cacao", code="CASH-006", name="Caja", active=True, enabled=True, group=False)
    fiscal_book = Book(entity="cacao", code="FISC", name="Fiscal", status="activo", is_primary=True)
    database.session.add_all(
        [
            debit_account,
            credit_account,
            fiscal_book,
            AccountingPeriod(
                entity="cacao",
                fiscal_year_id=None,
                name="Mayo 2026",
                status="closed",
                enabled=True,
                is_closed=True,
                start=date(2026, 5, 1),
                end=date(2026, 5, 31),
            ),
        ]
    )
    database.session.commit()

    journal = create_journal_draft(
        {
            "company": "cacao",
            "posting_date": "2026-05-06",
            "books": ["FISC"],
            "is_closing": True,
            "lines": [
                {"account": debit_account.id, "debit": "20.00", "credit": "0"},
                {"account": credit_account.id, "debit": "0", "credit": "20.00"},
            ],
        },
        user_id="user-1",
    )

    entries = submit_journal(journal.id)
    posted_entries = database.session.execute(database.select(GLEntry).filter_by(voucher_id=journal.id)).scalars().all()

    assert len(entries) == 2
    assert len(posted_entries) == 2
    assert all(entry.ledger_id == fiscal_book.id for entry in posted_entries)


def test_submit_journal_rejects_missing_exchange_rate_for_foreign_currency(app_ctx):
    from cacao_accounting.contabilidad.journal_service import create_journal_draft, submit_journal, JournalValidationError
    from cacao_accounting.database import Accounts, Book, database

    debit_account = Accounts(entity="cacao", code="EXP-007", name="Gasto", active=True, enabled=True, group=False)
    credit_account = Accounts(entity="cacao", code="CASH-007", name="Caja", active=True, enabled=True, group=False)
    fiscal_book = Book(entity="cacao", code="FISC", name="Fiscal", currency="NIO", status="activo", is_primary=True)
    database.session.add_all([debit_account, credit_account, fiscal_book])
    database.session.commit()

    journal = create_journal_draft(
        {
            "company": "cacao",
            "posting_date": "2026-05-06",
            "books": ["FISC"],
            "transaction_currency": "USD",
            "lines": [
                {"account": debit_account.id, "debit": "10.00", "credit": "0"},
                {"account": credit_account.id, "debit": "0", "credit": "10.00"},
            ],
        },
        user_id="user-1",
    )

    with pytest.raises(JournalValidationError, match="No existe tipo de cambio registrado"):
        submit_journal(journal.id)


def test_submit_journal_converts_foreign_currency_to_book_currency(app_ctx):
    from decimal import Decimal
    from cacao_accounting.contabilidad.journal_service import create_journal_draft, submit_journal
    from cacao_accounting.database import Accounts, Book, ExchangeRate, GLEntry, database

    debit_account = Accounts(entity="cacao", code="EXP-008", name="Gasto", active=True, enabled=True, group=False)
    credit_account = Accounts(entity="cacao", code="CASH-008", name="Caja", active=True, enabled=True, group=False)
    fiscal_book = Book(entity="cacao", code="FISC", name="Fiscal", currency="NIO", status="activo", is_primary=True)
    database.session.add_all(
        [
            debit_account,
            credit_account,
            fiscal_book,
            ExchangeRate(origin="USD", destination="NIO", rate="36.00", date=date(2026, 5, 6)),
        ]
    )
    database.session.commit()

    journal = create_journal_draft(
        {
            "company": "cacao",
            "posting_date": "2026-05-06",
            "books": ["FISC"],
            "transaction_currency": "USD",
            "lines": [
                {"account": debit_account.id, "debit": "10.00", "credit": "0"},
                {"account": credit_account.id, "debit": "0", "credit": "10.00"},
            ],
        },
        user_id="user-1",
    )

    submit_journal(journal.id)

    posted_entries = database.session.execute(database.select(GLEntry).filter_by(voucher_id=journal.id)).scalars().all()
    assert len(posted_entries) == 2
    debit_entry = next(entry for entry in posted_entries if entry.debit > 0)
    credit_entry = next(entry for entry in posted_entries if entry.credit > 0)

    assert debit_entry.account_currency == "USD"
    assert debit_entry.debit_in_account_currency == Decimal("10.00")
    assert debit_entry.debit == Decimal("360.0000") or debit_entry.debit == Decimal("360.00")
    assert credit_entry.credit_in_account_currency == Decimal("10.00")
    assert credit_entry.credit == Decimal("360.0000") or credit_entry.credit == Decimal("360.00")


def test_submit_journal_allows_cash_account_in_manual_entry(app_ctx):
    from cacao_accounting.contabilidad.journal_service import create_journal_draft
    from cacao_accounting.database import Accounts, Book, ComprobanteContable, User, database

    cash_account = Accounts(entity="cacao", code="11.01.001.001", name="Caja General", active=True, enabled=True, group=False)
    capital_account = Accounts(entity="cacao", code="31.01", name="Capital Social", active=True, enabled=True, group=False)
    fiscal_book = Book(entity="cacao", code="FISC", name="Fiscal", status="activo", is_primary=True)
    database.session.add_all([cash_account, capital_account, fiscal_book])
    database.session.commit()

    journal = create_journal_draft(
        {
            "company": "cacao",
            "posting_date": "2026-05-09",
            "books": ["FISC"],
            "memo": "Asiento manual con caja",
            "lines": [
                {"account": cash_account.id, "debit": "10.00", "credit": "0"},
                {"account": capital_account.id, "debit": "0", "credit": "10.00"},
            ],
        },
        user_id="user-1",
    )

    user = User.query.filter_by(user="admin").first()
    client = app_ctx.test_client()
    _login(client, user.id)

    response = client.post(f"/accounting/journal/{journal.id}/submit", follow_redirects=False)
    updated = database.session.get(ComprobanteContable, journal.id)

    assert response.status_code == 302
    assert updated.status == "submitted"


def test_journal_service_rejects_mixed_line_currencies(app_ctx):
    from cacao_accounting.contabilidad.journal_service import JournalValidationError, create_journal_draft
    from cacao_accounting.database import Accounts, database

    debit_account = Accounts(entity="cacao", code="EXP-009", name="Gasto", active=True, enabled=True, group=False)
    credit_account = Accounts(entity="cacao", code="CASH-009", name="Caja", active=True, enabled=True, group=False)
    database.session.add_all([debit_account, credit_account])
    database.session.commit()

    with pytest.raises(JournalValidationError, match="moneda"):
        create_journal_draft(
            {
                "company": "cacao",
                "posting_date": "2026-05-06",
                "transaction_currency": "USD",
                "lines": [
                    {"account": debit_account.id, "debit": "10.00", "credit": "0", "currency": "USD"},
                    {"account": credit_account.id, "debit": "0", "credit": "10.00", "currency": "NIO"},
                ],
            },
            user_id="user-1",
        )


def test_submit_journal_persists_advance_and_bank_account_on_gl_entries(app_ctx):
    from cacao_accounting.contabilidad.journal_service import create_journal_draft, submit_journal
    from cacao_accounting.database import Bank, BankAccount, Accounts, Book, GLEntry, database

    debit_account = Accounts(entity="cacao", code="EXP-010", name="Gasto", active=True, enabled=True, group=False)
    credit_account = Accounts(entity="cacao", code="CASH-010", name="Caja", active=True, enabled=True, group=False)
    fiscal_book = Book(entity="cacao", code="FISC", name="Fiscal", status="activo", is_primary=True)
    bank = Bank(name="Banco GL", is_active=True)
    database.session.add_all([debit_account, credit_account, fiscal_book, bank])
    database.session.commit()
    bank_account = BankAccount(
        bank_id=bank.id,
        company="cacao",
        account_name="Cuenta GL",
        account_no="010",
        currency="NIO",
        is_active=True,
    )
    database.session.add(bank_account)
    database.session.commit()

    journal = create_journal_draft(
        {
            "company": "cacao",
            "posting_date": "2026-05-06",
            "books": ["FISC"],
            "lines": [
                {
                    "account": debit_account.id,
                    "cost_center": "MAIN",
                    "debit": "10.00",
                    "credit": "0",
                    "is_advance": True,
                    "bank_account": bank_account.id,
                },
                {"account": credit_account.id, "debit": "0", "credit": "10.00"},
            ],
        },
        user_id="user-1",
    )

    submit_journal(journal.id)

    posted_entries = database.session.execute(database.select(GLEntry).filter_by(voucher_id=journal.id)).scalars().all()
    debit_entry = next(entry for entry in posted_entries if entry.debit > 0)
    assert debit_entry.is_advance is True
    assert debit_entry.bank_account_id == bank_account.id


def test_entity_creation_uses_setup_defaults_and_creates_required_book_cost_center_and_series(app_ctx):
    from cacao_accounting.database import (
        AccountingPeriod,
        Book,
        CompanyDefaultAccount,
        CostCenter,
        Currency,
        Entity,
        NamingSeries,
        User,
        database,
    )

    database.session.add(Currency(code="NIO", name="Córdoba", decimals=2, active=True, default=True))
    database.session.commit()

    user = database.session.execute(database.select(User).filter_by(user="admin")).scalar_one()
    client = app_ctx.test_client()
    _login(client, user.id)

    response = client.post(
        "/accounting/entity/new",
        data={
            "id": "mapco",
            "razon_social": "Mapping Company",
            "nombre_comercial": "Mapping Company",
            "id_fiscal": "J-MAP",
            "pais": "NI",
            "idioma": "es",
            "moneda": "NIO",
            "tipo_entidad": "Sociedad Anonima",
            "catalogo": "preexistente",
            "catalogo_origen": "base_es.csv",
        },
    )

    assert response.status_code == 302

    entity = database.session.execute(database.select(Entity).filter_by(code="mapco")).scalar_one()
    book = database.session.execute(database.select(Book).filter_by(entity="mapco", code="FISC")).scalar_one()
    cost_center = database.session.execute(database.select(CostCenter).filter_by(entity="mapco", code="MAIN")).scalar_one()
    period = (
        database.session.execute(database.select(AccountingPeriod).filter_by(entity="mapco").order_by(AccountingPeriod.start))
        .scalars()
        .all()
    )
    series = database.session.execute(
        database.select(NamingSeries).filter_by(company="mapco", entity_type="journal_entry")
    ).scalar_one_or_none()
    defaults = database.session.execute(database.select(CompanyDefaultAccount).filter_by(company="mapco")).scalar_one_or_none()

    assert entity.country == "NI"
    assert entity.currency == "NIO"
    assert book.currency == "NIO"
    assert cost_center.default is True
    assert len(period) == 12
    assert series is not None
    assert defaults is not None


def test_search_select_supports_journal_doctypes_and_filters(app_ctx):
    from cacao_accounting.database import AccountingPeriod, Book, CostCenter, Project, Unit, User, database

    from cacao_accounting.database import Currency

    database.session.add_all(
        [
            Currency(code="NIO", name="Córdoba", decimals=2, active=True, default=True),
            Book(code="FISC", name="Fiscal", entity="cacao", is_primary=True),
            AccountingPeriod(
                entity="cacao",
                name="2026-05",
                enabled=True,
                is_closed=False,
                start=date(2026, 5, 1),
                end=date(2026, 5, 31),
            ),
            CostCenter(code="MAIN", name="Principal", entity="cacao", active=True, enabled=True, group=False),
            Unit(code="HQ", name="Central", entity="cacao"),
            Project(code="PRJ", name="Proyecto", entity="cacao", enabled=True, start=date(2026, 1, 1)),
        ]
    )
    database.session.commit()

    user = User.query.filter_by(user="admin").first()
    client = app_ctx.test_client()
    _login(client, user.id)

    assert client.get("/api/search-select?doctype=company&q=Cacao").json["results"][0]["value"] == "cacao"
    assert client.get("/api/search-select?doctype=book&q=Fiscal&company=cacao").json["results"][0]["value"] == "FISC"
    assert client.get("/api/search-select?doctype=currency&q=NIO").json["results"][0]["value"] == "NIO"
    assert client.get("/api/search-select?doctype=cost_center&q=Principal&company=cacao").json["results"][0]["value"] == "MAIN"
    assert client.get("/api/search-select?doctype=unit&q=Central&company=cacao").json["results"][0]["value"] == "HQ"
    assert client.get("/api/search-select?doctype=project&q=Proyecto&company=cacao").json["results"][0]["value"] == "PRJ"
    assert (
        client.get("/api/search-select?doctype=accounting_period&q=2026&company=cacao").json["results"][0]["value"]
        == "2026-05"
    )
    assert client.get("/api/search-select?doctype=report_status&q=conta").json["results"][0]["value"] == "submitted"
    assert client.get("/api/search-select?doctype=book&q=Fiscal&bad_filter=x").status_code == 400


def test_form_preferences_are_persisted_per_user(app_ctx):
    from cacao_accounting.database import User, database
    from cacao_accounting.form_preferences import get_form_preference

    user_a = User.query.filter_by(user="admin").first()
    user_b = User(user="other", name="Other", password=b"x", classification="admin", active=True)
    database.session.add(user_b)
    database.session.commit()

    client = app_ctx.test_client()
    _login(client, user_a.id)
    payload = {
        "schema_version": 1,
        "columns": [{"field": "account", "label": "Cuenta", "width": 4, "visible": True, "required": True}],
    }

    saved = client.put("/api/form-preferences/accounting.journal_entry/draft", json=payload)
    read_a = client.get("/api/form-preferences/accounting.journal_entry/draft")
    read_b = get_form_preference(user_b.id, "accounting.journal_entry", "draft")

    assert saved.status_code == 200
    assert read_a.json["columns"][0]["width"] == 4
    assert read_b["columns"][0]["width"] == 3


def test_journal_edit_route_rehydrates_draft_and_updates_books(app_ctx):
    from cacao_accounting.contabilidad.journal_service import create_journal_draft
    from cacao_accounting.database import Accounts, Book, User, database

    debit_account = Accounts(entity="cacao", code="EXP-005", name="Gasto", active=True, enabled=True, group=False)
    credit_account = Accounts(entity="cacao", code="CASH-005", name="Caja", active=True, enabled=True, group=False)
    database.session.add_all(
        [
            debit_account,
            credit_account,
            Book(entity="cacao", code="FISC", name="Fiscal", status="activo", is_primary=True),
            Book(entity="cacao", code="IFRS", name="IFRS", status="activo"),
        ]
    )
    database.session.commit()

    journal = create_journal_draft(
        {
            "company": "cacao",
            "posting_date": "2026-05-06",
            "books": ["FISC", "IFRS"],
            "memo": "Borrador editable",
            "lines": [
                {"account": debit_account.id, "debit": "20.00", "credit": "0"},
                {"account": credit_account.id, "debit": "0", "credit": "20.00"},
            ],
        },
        user_id="user-1",
    )

    user = User.query.filter_by(user="admin").first()
    client = app_ctx.test_client()
    _login(client, user.id)

    response = client.get(f"/accounting/journal/edit/{journal.id}")
    html = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "Borrador editable" in html
    assert '"books": ["FISC", "IFRS"]' in html
    assert f"/accounting/journal/{journal.id}" in html
    assert '"order": 1' in html
    assert '"order": 2' in html

    update_payload = {
        "company": "cacao",
        "posting_date": "2026-05-07",
        "books": ["IFRS"],
        "memo": "Borrador actualizado",
        "lines": [
            {"account": debit_account.id, "debit": "30.00", "credit": "0"},
            {"account": credit_account.id, "debit": "0", "credit": "30.00"},
        ],
    }
    update_response = client.post(
        f"/accounting/journal/edit/{journal.id}",
        data={"journal_payload": json.dumps(update_payload)},
        follow_redirects=False,
    )

    updated_journal = database.session.get(type(journal), journal.id)
    assert update_response.status_code == 302
    assert updated_journal.book == "IFRS"
    assert updated_journal.book_codes == '["IFRS"]'
    assert updated_journal.memo == "Borrador actualizado"


def test_reject_journal_draft_changes_status_without_gl_entries(app_ctx):
    from cacao_accounting.contabilidad.journal_service import create_journal_draft
    from cacao_accounting.database import Accounts, Book, ComprobanteContable, GLEntry, User, database

    debit_account = Accounts(entity="cacao", code="EXP-REJ", name="Gasto", active=True, enabled=True, group=False)
    credit_account = Accounts(entity="cacao", code="CASH-REJ", name="Caja", active=True, enabled=True, group=False)
    database.session.add_all(
        [
            debit_account,
            credit_account,
            Book(entity="cacao", code="FISC", name="Fiscal", status="activo", is_primary=True),
        ]
    )
    database.session.commit()

    journal = create_journal_draft(
        {
            "company": "cacao",
            "posting_date": "2026-05-07",
            "books": ["FISC"],
            "memo": "Borrador por rechazar",
            "lines": [
                {"account": debit_account.id, "debit": "15.00", "credit": "0"},
                {"account": credit_account.id, "debit": "0", "credit": "15.00"},
            ],
        },
        user_id="user-1",
    )

    user = User.query.filter_by(user="admin").first()
    client = app_ctx.test_client()
    _login(client, user.id)

    response = client.post(f"/accounting/journal/{journal.id}/reject", follow_redirects=False)
    updated = database.session.get(ComprobanteContable, journal.id)
    gl_entries = database.session.execute(database.select(GLEntry).filter_by(voucher_id=journal.id)).scalars().all()

    assert response.status_code == 302
    assert updated.status == "rejected"
    assert gl_entries == []


def test_journal_detail_shows_readable_labels_and_detail_action(app_ctx):
    from cacao_accounting.contabilidad.journal_service import create_journal_draft
    from cacao_accounting.database import Accounts, Book, CostCenter, User, database

    debit_account = Accounts(entity="cacao", code="11.01.001.001", name="Caja General", active=True, enabled=True, group=False)
    credit_account = Accounts(entity="cacao", code="31.01", name="Capital Social", active=True, enabled=True, group=False)
    center = CostCenter(entity="cacao", code="ADM", name="Administración", active=True, enabled=True, group=False)
    fiscal_book = Book(entity="cacao", code="FISC", name="Fiscal", currency="NIO", status="activo", is_primary=True)
    database.session.add_all([debit_account, credit_account, center, fiscal_book])
    database.session.commit()

    journal = create_journal_draft(
        {
            "company": "cacao",
            "posting_date": "2026-05-08",
            "books": ["FISC"],
            "transaction_currency": "NIO",
            "memo": "Vista legible",
            "lines": [
                {"account": debit_account.id, "cost_center": center.code, "debit": "55.00", "credit": "0"},
                {"account": credit_account.id, "debit": "0", "credit": "55.00"},
            ],
        },
        user_id="user-1",
    )

    user = User.query.filter_by(user="admin").first()
    client = app_ctx.test_client()
    _login(client, user.id)

    response = client.get(f"/accounting/journal/{journal.id}")
    html = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "Ver detalle" in html
    assert "Ver panel" not in html
    assert "11.01.001.001 - Caja General" in html
    assert "ADM - Administración" in html
    assert "FISC - Fiscal (NIO)" in html
    assert "NIO" in html


def test_duplicate_journal_creates_new_draft(app_ctx):
    from cacao_accounting.contabilidad.journal_service import create_journal_draft, submit_journal
    from cacao_accounting.database import Accounts, Book, ComprobanteContable, ComprobanteContableDetalle, User, database

    debit_account = Accounts(entity="cacao", code="EXP-DUP", name="Gasto Duplicable", active=True, enabled=True, group=False)
    credit_account = Accounts(entity="cacao", code="CASH-DUP", name="Caja Duplicable", active=True, enabled=True, group=False)
    fiscal_book = Book(entity="cacao", code="FISC", name="Fiscal", status="activo", is_primary=True)
    database.session.add_all([debit_account, credit_account, fiscal_book])
    database.session.commit()

    journal = create_journal_draft(
        {
            "company": "cacao",
            "posting_date": "2026-05-08",
            "books": ["FISC"],
            "memo": "Original duplicable",
            "lines": [
                {"account": debit_account.id, "debit": "70.00", "credit": "0"},
                {"account": credit_account.id, "debit": "0", "credit": "70.00"},
            ],
        },
        user_id="user-1",
    )
    submit_journal(journal.id)

    user = User.query.filter_by(user="admin").first()
    client = app_ctx.test_client()
    _login(client, user.id)

    response = client.post(f"/accounting/journal/{journal.id}/duplicate", follow_redirects=False)
    drafts = (
        database.session.execute(database.select(ComprobanteContable).filter(ComprobanteContable.memo.like("Duplicado de%")))
        .scalars()
        .all()
    )
    duplicated = drafts[-1]
    duplicated_lines = (
        database.session.execute(database.select(ComprobanteContableDetalle).filter_by(transaction_id=duplicated.id))
        .scalars()
        .all()
    )

    assert response.status_code == 302
    assert f"/accounting/journal/edit/{duplicated.id}" in response.headers.get("Location", "")
    assert drafts
    assert any(item.status == "draft" for item in drafts)
    assert duplicated_lines
    assert duplicated.document_no is None

    edit_payload = {
        "company": "cacao",
        "posting_date": "2026-06-10",
        "books": ["FISC"],
        "naming_series_id": journal.naming_series_id,
        "memo": "Duplicado editado en junio",
        "lines": [
            {"account": debit_account.id, "debit": "70.00", "credit": "0"},
            {"account": credit_account.id, "debit": "0", "credit": "70.00"},
        ],
    }
    edit_response = client.post(
        f"/accounting/journal/edit/{duplicated.id}",
        data={"journal_payload": json.dumps(edit_payload)},
        follow_redirects=False,
    )
    duplicated_updated = database.session.get(ComprobanteContable, duplicated.id)

    assert edit_response.status_code == 302
    assert duplicated_updated.document_no is not None
    assert "-06-" in duplicated_updated.document_no


def test_revert_journal_creates_reversed_draft_and_redirects_to_edit(app_ctx):
    from cacao_accounting.contabilidad.journal_service import create_journal_draft, submit_journal
    from cacao_accounting.database import Accounts, Book, ComprobanteContable, ComprobanteContableDetalle, User, database

    debit_account = Accounts(entity="cacao", code="EXP-REV", name="Gasto Revertible", active=True, enabled=True, group=False)
    credit_account = Accounts(entity="cacao", code="CASH-REV", name="Caja Revertible", active=True, enabled=True, group=False)
    fiscal_book = Book(entity="cacao", code="FISC", name="Fiscal", status="activo", is_primary=True)
    database.session.add_all([debit_account, credit_account, fiscal_book])
    database.session.commit()

    journal = create_journal_draft(
        {
            "company": "cacao",
            "posting_date": "2026-05-08",
            "books": ["FISC"],
            "memo": "Original revertible",
            "lines": [
                {"account": debit_account.id, "debit": "90.00", "credit": "0"},
                {"account": credit_account.id, "debit": "0", "credit": "90.00"},
            ],
        },
        user_id="user-1",
    )
    submit_journal(journal.id)

    user = User.query.filter_by(user="admin").first()
    client = app_ctx.test_client()
    _login(client, user.id)

    response = client.post(f"/accounting/journal/{journal.id}/revert", follow_redirects=False)
    reversed_journal = (
        database.session.execute(database.select(ComprobanteContable).filter(ComprobanteContable.memo.like("Reversión de%")))
        .scalars()
        .first()
    )
    reversed_lines = (
        database.session.execute(
            database.select(ComprobanteContableDetalle)
            .filter_by(transaction_id=reversed_journal.id)
            .order_by(ComprobanteContableDetalle.order.asc())
        )
        .scalars()
        .all()
    )

    assert response.status_code == 302
    assert reversed_journal is not None
    assert reversed_journal.status == "draft"
    assert reversed_journal.document_no is None
    assert f"/accounting/journal/edit/{reversed_journal.id}" in response.headers.get("Location", "")
    assert reversed_lines[0].value == -90
    assert reversed_lines[1].value == 90
