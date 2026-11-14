# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 William José Moreno Reyes

"""Business authorization, reservation and status invariants for petty cash replenishment."""

from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor, TimeoutError
from datetime import date
from decimal import Decimal
from threading import Event
from uuid import uuid4

import pytest
from sqlalchemy.exc import IntegrityError


from cacao_accounting import create_app
from cacao_accounting.auth import proteger_passwd
from cacao_accounting.auth.permisos import Permisos
from cacao_accounting.database.helpers import obtener_id_modulo_por_nombre
from cacao_accounting.bancos.services import (
    cancel_petty_cash_expense,
    create_petty_cash_expense,
    create_default_petty_cash,
    create_petty_cash_replenishment,
    create_petty_cash_voucher,
    post_petty_cash_reconciliation_adjustment,
    replenish_petty_cash,
    set_petty_cash_default,
    set_petty_cash_replenishment_status,
    set_petty_cash_voucher_status,
)
from cacao_accounting.document_identifiers import (
    IdentifierConfigurationError,
    enforce_single_default_series,
    ensure_default_naming_series_for_company,
    ensure_global_naming_series,
    generate_entity_code,
)
from cacao_accounting.config import configuracion
from cacao_accounting.database import (
    Accounts,
    AccountingPeriod,
    Book,
    CacaoConfig,
    ComprobanteContable,
    CostCenter,
    Currency,
    Entity,
    FiscalYear,
    GLEntry,
    Modules,
    NamingSeries,
    PaymentEntry,
    PettyCashAccount,
    PettyCashExpense,
    PettyCashReplenishment,
    PettyCashReconciliation,
    PettyCashVoucher,
    Roles,
    RolesAccess,
    RolesUser,
    User,
    UserCompanyAccess,
    database,
)

PASSWORD = "cash-approval-test-2026"


pytestmark = pytest.mark.database


@pytest.fixture
def replenishment_app(tmp_path):
    """Build Cloud roles and real replenishment rows in an isolated database."""
    database_uri = str(configuracion["SQLALCHEMY_DATABASE_URI"])
    if database_uri.startswith("sqlite"):
        database_uri = f"sqlite:///{tmp_path / 'replenishment-approval.sqlite'}"
    elif os.environ.get("CHECK_DATABASE", "").strip().lower() not in {"1", "true", "yes", "on"}:
        pytest.skip("Los motores externos requieren CHECK_DATABASE=true y una base dedicada.")
    application = create_app(
        {
            **configuracion,
            "SQLALCHEMY_DATABASE_URI": database_uri,
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
            "WTF_CSRF_ENABLED": False,
            "TESTING": True,
            "MODO_ESCRITORIO": False,
        }
    )
    with application.app_context():
        database.create_all()
        company = f"E{uuid4().hex[:8]}"
        currency = f"N{company[1:]}"
        user_ids = {role: f"{role[:4]}-{uuid4().hex[:8]}" for role in ("preparer", "editor", "approver")}
        cash_module = database.session.execute(database.select(Modules).filter_by(module="cash")).scalar_one_or_none()
        if cash_module is None:
            try:
                with database.session.begin_nested():
                    cash_module = Modules(module="cash", default=False, enabled=True)
                    database.session.add(cash_module)
                    database.session.flush()
            except IntegrityError:
                cash_module = database.session.execute(database.select(Modules).filter_by(module="cash")).scalar_one()
        cash_module.enabled = True
        database.session.add_all(
            [
                Currency(code=currency, name="Córdoba", decimals=2, active=True, default=False),
                Entity(
                    code=company,
                    name=f"Empresa {company}",
                    company_name=f"Empresa {company} SA",
                    tax_id=f"TAX-{company}",
                    currency=currency,
                    enabled=True,
                    status="activo",
                ),
                User(
                    id=user_ids["preparer"],
                    user=user_ids["preparer"],
                    name="Solicitante",
                    password=proteger_passwd(PASSWORD),
                    active=True,
                ),
                User(
                    id=user_ids["editor"],
                    user=user_ids["editor"],
                    name="Editor",
                    password=proteger_passwd(PASSWORD),
                    active=True,
                ),
                User(
                    id=user_ids["approver"],
                    user=user_ids["approver"],
                    name="Autorizador",
                    password=proteger_passwd(PASSWORD),
                    active=True,
                ),
                CacaoConfig(key=f"approval_require_different_approver_{company}", value="true"),
            ]
        )
        database.session.flush()
        module_id = cash_module.id
        editor_role = Roles(name=f"cash-editor-{company}", note="Editar reposiciones")
        approver_role = Roles(name=f"cash-approver-{company}", note="Autorizar reposiciones")
        database.session.add_all([editor_role, approver_role])
        database.session.flush()
        database.session.add_all(
            [
                RolesAccess(rol_id=editor_role.id, module_id=module_id, access=True, edit=True),
                RolesAccess(rol_id=approver_role.id, module_id=module_id, access=True, approve=True),
                RolesUser(user_id=user_ids["editor"], role_id=editor_role.id, active=True),
                RolesUser(user_id=user_ids["approver"], role_id=approver_role.id, active=True),
                UserCompanyAccess(user_id=user_ids["preparer"], company_code=company),
                UserCompanyAccess(user_id=user_ids["editor"], company_code=company),
                UserCompanyAccess(user_id=user_ids["approver"], company_code=company),
            ]
        )
        account = Accounts(
            code=f"PC-{company}",
            name=f"Caja chica {company}",
            entity=company,
            group=False,
            active=True,
            enabled=True,
            account_type="petty_cash",
        )
        database.session.add(account)
        database.session.flush()
        fund = PettyCashAccount(
            company=company,
            account_id=account.id,
            name=f"Fondo {company}",
            currency=currency,
            float_amount=Decimal("1000"),
            is_default=True,
            is_active=True,
        )
        database.session.add(fund)
        database.session.flush()
        rows = {
            requester: PettyCashReplenishment(
                company=company,
                petty_cash_id=fund.id,
                request_date=date(2026, 10, 20),
                amount=Decimal("100"),
                status="solicitado",
                requested_by=user_ids[requester],
                docstatus=1,
            )
            for requester in ("preparer", "approver")
        }
        database.session.add_all(rows.values())
        database.session.commit()
        ids = {
            "company": company,
            "preparer_user": user_ids["preparer"],
            "editor_user": user_ids["editor"],
            "approver_user": user_ids["approver"],
            "replenishment_by_preparer": rows["preparer"].id,
            "replenishment_by_approver": rows["approver"].id,
        }

    yield application, ids
    with application.app_context():
        database.session.remove()
        database.engine.dispose()


def _authenticated_client(application, user_id: str):
    """Return a Flask test client authenticated as one seeded role holder."""
    client = application.test_client()
    with client.session_transaction() as session:
        session["_user_id"] = user_id
        session["_fresh"] = True
    return client


def _prepare_delivered_expense_voucher(application, ids: dict[str, str]) -> dict[str, object]:
    """Prepare a delivered voucher and the accounting references needed to post its expense."""
    company = ids["company"]
    expense_code = f"EX{company[1:]}"
    cost_center_code = f"C{company[1:]}"
    posting_date = date(2026, 10, 20)

    with application.app_context():
        fund = database.session.execute(database.select(PettyCashAccount).filter_by(company=company)).scalar_one()
        accounting_module = database.session.execute(
            database.select(Modules).filter_by(module="accounting")
        ).scalar_one_or_none()
        if accounting_module is None:
            accounting_module = Modules(module="accounting", default=True, enabled=True)
            database.session.add(accounting_module)
            database.session.flush()
        accounting_module.enabled = True

        editor_role = database.session.execute(database.select(Roles).filter_by(name=f"cash-editor-{company}")).scalar_one()
        cash_module_id = obtener_id_modulo_por_nombre("cash")
        cash_access = database.session.execute(
            database.select(RolesAccess).filter_by(rol_id=editor_role.id, module_id=cash_module_id)
        ).scalar_one()
        cash_access.create = True
        cash_access.view = True
        accounting_access = database.session.execute(
            database.select(RolesAccess).filter_by(rol_id=editor_role.id, module_id=accounting_module.id)
        ).scalar_one_or_none()
        if accounting_access is None:
            database.session.add(
                RolesAccess(
                    rol_id=editor_role.id,
                    module_id=accounting_module.id,
                    access=True,
                    create=True,
                    approve=True,
                    set_null=True,
                )
            )
        else:
            accounting_access.access = True
            accounting_access.create = True
            accounting_access.approve = True
            accounting_access.set_null = True

        database.session.add_all(
            [
                Accounts(
                    code=expense_code,
                    name="Suministros de oficina",
                    entity=company,
                    group=False,
                    active=True,
                    enabled=True,
                    classification="expense",
                    account_type="expense",
                ),
                CostCenter(
                    code=cost_center_code,
                    name="Administración",
                    entity=company,
                    active=True,
                    enabled=True,
                ),
                Book(
                    entity=company,
                    code=f"B{company[1:9]}",
                    name="Libro principal de gastos",
                    status="activo",
                    currency=fund.currency,
                    is_primary=True,
                ),
            ]
        )
        fiscal_year = FiscalYear(
            entity=company,
            name="2026",
            year_start_date=date(2026, 1, 1),
            year_end_date=date(2026, 12, 31),
            is_closed=False,
        )
        database.session.add(fiscal_year)
        database.session.flush()
        database.session.add(
            AccountingPeriod(
                entity=company,
                fiscal_year_id=fiscal_year.id,
                name="Octubre 2026",
                status="open",
                enabled=True,
                is_closed=False,
                start=date(2026, 10, 1),
                end=date(2026, 10, 31),
            )
        )
        voucher = create_petty_cash_voucher(
            company=company,
            petty_cash_id=fund.id,
            posted_date=posting_date,
            delivered_to="María Pérez",
            concept="Compra de útiles de oficina",
            amount=Decimal("75.00"),
            cost_center_code=cost_center_code,
        )
        set_petty_cash_voucher_status(voucher, "entregado")
        database.session.commit()
        result = {
            "company": company,
            "expense_code": expense_code,
            "cost_center_code": cost_center_code,
            "posting_date": posting_date,
            "voucher_id": voucher.id,
            "fund_id": fund.id,
            "cash_module_id": cash_module_id,
        }
    return result


def _post_prepared_petty_cash_expense(application, scenario: dict[str, object], actor_id: str) -> str:
    """Post the prepared voucher through the same domain service used by the form."""
    with application.app_context():
        expense = create_petty_cash_expense(
            company=str(scenario["company"]),
            petty_cash_id=str(scenario["fund_id"]),
            expense_account_code=str(scenario["expense_code"]),
            concept="Compra de útiles de oficina",
            amount=Decimal("75.00"),
            cost_center_code=str(scenario["cost_center_code"]),
            posted_date=scenario["posting_date"],
            voucher_id=str(scenario["voucher_id"]),
            beneficiary="María Pérez",
            actor_id=actor_id,
        )
        return str(expense.id)


def test_replenishment_approval_requires_authority_and_different_actor(replenishment_app):
    """An editor cannot approve; separation applies only when company policy asks."""
    application, ids = replenishment_app
    editor_response = _authenticated_client(application, ids["editor_user"]).post(
        f"/cash_management/petty-cash-replenishment/{ids['replenishment_by_preparer']}/status",
        data={"status": "aprobado"},
    )
    assert editor_response.status_code == 403
    with application.app_context():
        permissions = Permisos(obtener_id_modulo_por_nombre("cash"), ids["approver_user"])
        assert permissions.autorizar is True
        assert permissions.tiene_acceso_compania(ids["company"]) is True

    approver_response = _authenticated_client(application, ids["approver_user"]).post(
        f"/cash_management/petty-cash-replenishment/{ids['replenishment_by_preparer']}/status",
        data={"status": "aprobado"},
    )
    assert approver_response.status_code == 302
    with application.app_context():
        approved_replenishment = database.session.get(PettyCashReplenishment, ids["replenishment_by_preparer"])
        assert approved_replenishment is not None
        assert approved_replenishment.status == "aprobado"
        assert approved_replenishment.approved_by == ids["approver_user"]

        replenishment = database.session.get(PettyCashReplenishment, ids["replenishment_by_approver"])
        assert replenishment is not None
        with pytest.raises(ValueError, match="autorización de Caja Chica"):
            set_petty_cash_replenishment_status(replenishment, "aprobado", actor_id=ids["editor_user"])
        database.session.rollback()
        replenishment = database.session.get(PettyCashReplenishment, ids["replenishment_by_approver"])
        assert replenishment is not None
        assert replenishment.status == "solicitado"
        assert replenishment.approved_by is None

        with pytest.raises(ValueError, match="persona distinta"):
            set_petty_cash_replenishment_status(
                database.session.get(PettyCashReplenishment, ids["replenishment_by_approver"]),
                "aprobado",
                actor_id=ids["approver_user"],
            )
        database.session.rollback()
        replenishment = database.session.get(PettyCashReplenishment, ids["replenishment_by_approver"])
        assert replenishment is not None
        assert replenishment.status == "solicitado"
        assert replenishment.approved_by is None

        database.session.execute(
            database.update(CacaoConfig)
            .where(CacaoConfig.key == f"approval_require_different_approver_{ids['company']}")
            .values(value="false")
        )
        database.session.commit()
        approved = set_petty_cash_replenishment_status(
            database.session.get(PettyCashReplenishment, ids["replenishment_by_approver"]),
            "aprobado",
            actor_id=ids["approver_user"],
        )
        assert approved.status == "aprobado"
        assert approved.approved_by == ids["approver_user"]


def test_delivered_voucher_form_posts_expense_and_reconciles_gl(replenishment_app):
    """Liquidating a delivered voucher through the form creates one balanced expense."""
    application, ids = replenishment_app
    scenario = _prepare_delivered_expense_voucher(application, ids)
    company = str(scenario["company"])
    expense_code = str(scenario["expense_code"])
    cost_center_code = str(scenario["cost_center_code"])
    posting_date = date.fromisoformat(str(scenario["posting_date"]))
    voucher_id = str(scenario["voucher_id"])
    fund_id = str(scenario["fund_id"])
    with application.app_context():
        cash_permissions = Permisos(str(scenario["cash_module_id"]), ids["editor_user"])
        assert cash_permissions.crear is True
        assert cash_permissions.tiene_acceso_compania(company) is True

    client = _authenticated_client(application, ids["editor_user"])
    form_response = client.get(f"/cash_management/petty-cash-expense/new?voucher_id={voucher_id}")
    assert form_response.status_code == 200, form_response.get_data(as_text=True)
    form_html = form_response.get_data(as_text=True)
    assert "Compra de útiles de oficina" in form_html
    assert "María Pérez" in form_html
    assert "75.00" in form_html

    response = client.post(
        "/cash_management/petty-cash-expense/new",
        data={
            "company": company,
            "petty_cash_id": fund_id,
            "voucher_id": voucher_id,
            "posting_date": posting_date.isoformat(),
            "beneficiary": "María Pérez",
            "concept": "Compra de útiles de oficina",
            "expense_account_code": expense_code,
            "amount": "75.00",
            "cost_center_code": cost_center_code,
        },
    )
    assert response.status_code == 302, response.get_data(as_text=True)

    with application.app_context():
        voucher = database.session.get(PettyCashVoucher, voucher_id)
        assert voucher is not None and voucher.voucher_status == "liquidado"
        expense = database.session.execute(database.select(PettyCashExpense).filter_by(voucher_id=voucher_id)).scalar_one()
        assert expense.docstatus == 1
        assert expense.amount == Decimal("75.0000")
        journal = database.session.get(ComprobanteContable, expense.journal_id)
        assert journal is not None and journal.status == "submitted"
        entries = (
            database.session.execute(
                database.select(GLEntry)
                .filter_by(company=company, voucher_type="journal_entry", voucher_id=journal.id)
                .where(GLEntry.is_cancelled.is_(False))
            )
            .scalars()
            .all()
        )
        assert len(entries) == 2
        assert sum((entry.debit for entry in entries), Decimal("0")) == Decimal("75.0000")
        assert sum((entry.credit for entry in entries), Decimal("0")) == Decimal("75.0000")
        assert {(entry.account_code, entry.debit, entry.credit) for entry in entries} == {
            (expense_code, Decimal("75.0000"), Decimal("0.0000")),
            (f"PC-{company}", Decimal("0.0000"), Decimal("75.0000")),
        }


def test_posted_voucher_cannot_be_cancelled_while_expense_is_active(replenishment_app):
    """An active posted expense must be reversed before its voucher can be cancelled."""
    application, ids = replenishment_app
    scenario = _prepare_delivered_expense_voucher(application, ids)
    expense_id = _post_prepared_petty_cash_expense(application, scenario, ids["editor_user"])
    with application.app_context():
        voucher = database.session.get(PettyCashVoucher, str(scenario["voucher_id"]))
        assert voucher is not None and voucher.expense_id == expense_id
        voucher.voucher_status = "entregado"
        database.session.commit()
        with pytest.raises(ValueError, match="gasto contabilizado activo"):
            set_petty_cash_voucher_status(voucher, "cancelado")
        connection = database.session.connection()
        assert not connection.connection.driver_connection.in_transaction
        persisted_voucher = database.session.get(PettyCashVoucher, str(scenario["voucher_id"]))
        persisted_expense = database.session.get(PettyCashExpense, expense_id)
        assert persisted_voucher is not None and persisted_voucher.voucher_status == "entregado"
        assert persisted_voucher.expense_id == expense_id
        assert persisted_expense is not None and persisted_expense.docstatus == 1


def test_missing_voucher_releases_sqlite_write_transaction(replenishment_app):
    """A failed row lock must release SQLite's writer reservation."""
    application, _ids = replenishment_app
    with application.app_context():
        missing_voucher = PettyCashVoucher(id="missing-petty-cash-voucher")
        with pytest.raises(ValueError, match="documento no existe"):
            set_petty_cash_voucher_status(missing_voucher, "cancelado")
        connection = database.session.connection()
        assert not connection.connection.driver_connection.in_transaction


def test_petty_cash_expense_cancellation_reverses_gl_and_reopens_voucher(replenishment_app):
    """A successful cancellation preserves original GL rows and reopens its voucher."""
    application, ids = replenishment_app
    scenario = _prepare_delivered_expense_voucher(application, ids)
    expense_id = _post_prepared_petty_cash_expense(application, scenario, ids["editor_user"])
    company = str(scenario["company"])
    voucher_id = str(scenario["voucher_id"])
    posting_date = date.fromisoformat(str(scenario["posting_date"]))

    with application.app_context():
        expense = database.session.get(PettyCashExpense, expense_id)
        assert expense is not None and expense.journal_id
        journal_id = str(expense.journal_id)
        original_entries = (
            database.session.execute(
                database.select(GLEntry).filter_by(company=company, voucher_type="journal_entry", voucher_id=journal_id)
            )
            .scalars()
            .all()
        )
        assert len(original_entries) == 2
        original_snapshot = {
            entry.id: (
                entry.account_id,
                entry.debit,
                entry.credit,
                entry.debit_in_account_currency,
                entry.credit_in_account_currency,
                entry.account_currency,
                entry.company_currency,
                entry.exchange_rate,
                entry.ledger_id,
            )
            for entry in original_entries
        }
        original_amounts = [(entry.account_id, entry.debit, entry.credit) for entry in original_entries]

        cancel_petty_cash_expense(
            expense,
            reason="Compra duplicada",
            actor_id=ids["editor_user"],
            cancellation_date=posting_date,
        )

    with application.app_context():
        expense = database.session.get(PettyCashExpense, expense_id)
        voucher = database.session.get(PettyCashVoucher, voucher_id)
        journal = database.session.get(ComprobanteContable, journal_id)
        entries = (
            database.session.execute(
                database.select(GLEntry).filter_by(company=company, voucher_type="journal_entry", voucher_id=journal_id)
            )
            .scalars()
            .all()
        )
        originals = [entry for entry in entries if not entry.is_reversal]
        reversals = [entry for entry in entries if entry.is_reversal]
        assert expense is not None and expense.docstatus == 2
        assert voucher is not None and voucher.voucher_status == "entregado" and voucher.expense_id is None
        assert journal is not None and journal.status == "cancelled"
        assert len(originals) == len(reversals) == 2
        assert all(entry.is_cancelled for entry in originals)
        assert {
            entry.id: (
                entry.account_id,
                entry.debit,
                entry.credit,
                entry.debit_in_account_currency,
                entry.credit_in_account_currency,
                entry.account_currency,
                entry.company_currency,
                entry.exchange_rate,
                entry.ledger_id,
            )
            for entry in originals
        } == original_snapshot
        assert all(not entry.is_cancelled for entry in reversals)
        assert sum((entry.debit for entry in entries if not entry.is_cancelled), Decimal("0")) == Decimal("75.0000")
        assert sum((entry.credit for entry in entries if not entry.is_cancelled), Decimal("0")) == Decimal("75.0000")
        assert all(
            any(
                reversal.account_id == account_id and reversal.debit == credit and reversal.credit == debit
                for reversal in reversals
            )
            for account_id, debit, credit in original_amounts
        )


def test_petty_cash_expense_creation_rolls_back_gl_if_subledger_insert_fails(replenishment_app):
    """A failed expense insert leaves its delivered voucher and GL untouched."""
    application, ids = replenishment_app
    scenario = _prepare_delivered_expense_voucher(application, ids)
    company = str(scenario["company"])
    voucher_id = str(scenario["voucher_id"])

    with application.app_context():
        if database.engine.dialect.name != "sqlite":
            pytest.skip("La inyección de fallo usa un trigger efímero de SQLite.")
        database.session.remove()
        with database.engine.begin() as connection:
            connection.exec_driver_sql(
                "CREATE TRIGGER reject_petty_cash_expense_insert "
                "BEFORE INSERT ON petty_cash_expense "
                "BEGIN SELECT RAISE(ABORT, 'injected subledger insert failure'); END"
            )

    try:
        with application.app_context():
            before_journals = (
                database.session.execute(database.select(ComprobanteContable.id).where(ComprobanteContable.entity == company))
                .scalars()
                .all()
            )
            before_gl = database.session.execute(database.select(GLEntry.id).where(GLEntry.company == company)).scalars().all()
            with pytest.raises(IntegrityError, match="injected subledger insert failure"):
                _post_prepared_petty_cash_expense(application, scenario, ids["editor_user"])
            database.session.remove()

        with application.app_context():
            voucher = database.session.get(PettyCashVoucher, voucher_id)
            expenses = (
                database.session.execute(database.select(PettyCashExpense).filter_by(voucher_id=voucher_id)).scalars().all()
            )
            journals = (
                database.session.execute(database.select(ComprobanteContable.id).where(ComprobanteContable.entity == company))
                .scalars()
                .all()
            )
            gl_entries = (
                database.session.execute(database.select(GLEntry.id).where(GLEntry.company == company)).scalars().all()
            )
            assert voucher is not None and voucher.voucher_status == "entregado" and voucher.expense_id is None
            assert expenses == []
            assert journals == before_journals
            assert gl_entries == before_gl
    finally:
        with application.app_context():
            database.session.remove()
            with database.engine.begin() as connection:
                connection.exec_driver_sql("DROP TRIGGER IF EXISTS reject_petty_cash_expense_insert")


def test_petty_cash_expense_cancellation_rolls_back_gl_if_subledger_update_fails(replenishment_app):
    """A failed cancellation update keeps the posted expense, voucher and GL active."""
    application, ids = replenishment_app
    scenario = _prepare_delivered_expense_voucher(application, ids)
    expense_id = _post_prepared_petty_cash_expense(application, scenario, ids["editor_user"])
    company = str(scenario["company"])
    voucher_id = str(scenario["voucher_id"])
    posting_date = date.fromisoformat(str(scenario["posting_date"]))

    with application.app_context():
        if database.engine.dialect.name != "sqlite":
            pytest.skip("La inyección de fallo usa un trigger efímero de SQLite.")
        expense = database.session.get(PettyCashExpense, expense_id)
        assert expense is not None and expense.journal_id
        journal_id = str(expense.journal_id)
        original_entries = (
            database.session.execute(
                database.select(GLEntry).filter_by(company=company, voucher_type="journal_entry", voucher_id=journal_id)
            )
            .scalars()
            .all()
        )
        assert len(original_entries) == 2
        database.session.remove()
        with database.engine.begin() as connection:
            connection.exec_driver_sql(
                "CREATE TRIGGER reject_petty_cash_expense_update "
                "BEFORE UPDATE ON petty_cash_expense "
                "BEGIN SELECT RAISE(ABORT, 'injected subledger update failure'); END"
            )

    try:
        with application.app_context():
            expense = database.session.get(PettyCashExpense, expense_id)
            assert expense is not None
            with pytest.raises(IntegrityError, match="injected subledger update failure"):
                cancel_petty_cash_expense(
                    expense,
                    reason="Compra duplicada",
                    actor_id=ids["editor_user"],
                    cancellation_date=posting_date,
                )
            database.session.remove()

        with application.app_context():
            expense = database.session.get(PettyCashExpense, expense_id)
            voucher = database.session.get(PettyCashVoucher, voucher_id)
            journal = database.session.get(ComprobanteContable, journal_id)
            entries = (
                database.session.execute(
                    database.select(GLEntry).filter_by(company=company, voucher_type="journal_entry", voucher_id=journal_id)
                )
                .scalars()
                .all()
            )
            assert expense is not None and expense.docstatus == 1
            assert voucher is not None and voucher.voucher_status == "liquidado" and voucher.expense_id == expense_id
            assert journal is not None and journal.status == "submitted"
            assert len(entries) == 2
            assert all(not entry.is_cancelled and not entry.is_reversal for entry in entries)
            assert {(entry.id, entry.debit, entry.credit) for entry in entries} == {
                (entry.id, entry.debit, entry.credit) for entry in original_entries
            }
    finally:
        with application.app_context():
            database.session.remove()
            with database.engine.begin() as connection:
                connection.exec_driver_sql("DROP TRIGGER IF EXISTS reject_petty_cash_expense_update")


def test_concurrent_default_selection_keeps_one_fund(replenishment_app):
    """Concurrent operators leave one selected default for the company."""
    application, ids = replenishment_app
    with application.app_context():
        company = ids["company"]
        fund = database.session.execute(database.select(PettyCashAccount).filter_by(company=company)).scalar_one()
        alternatives = [
            PettyCashAccount(
                company=company,
                account_id=fund.account_id,
                name=f"Fondo concurrente {number} {company}",
                currency=fund.currency,
                float_amount=Decimal("100"),
                is_default=False,
                is_active=True,
            )
            for number in (1, 2)
        ]
        database.session.add_all(alternatives)
        database.session.commit()
        default_ids = [row.id for row in alternatives]

    from threading import Barrier

    start = Barrier(2)

    def select_default(fund_id: str) -> None:
        """Run one real default-selection transaction in its own session."""
        with application.app_context():
            try:
                target = database.session.get(PettyCashAccount, fund_id)
                assert target is not None
                start.wait(timeout=5)
                set_petty_cash_default(target)
            finally:
                database.session.remove()

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(select_default, fund_id) for fund_id in default_ids]
        for future in futures:
            future.result(timeout=15)

    with application.app_context():
        defaults = (
            database.session.execute(database.select(PettyCashAccount).filter_by(company=ids["company"], is_default=True))
            .scalars()
            .all()
        )
        assert len(defaults) == 1
        assert defaults[0].id in default_ids


def test_concurrent_naming_series_activation_keeps_one_default(replenishment_app):
    """Concurrent series activation leaves one default in its company scope."""
    application, ids = replenishment_app
    with application.app_context():
        company = ids["company"]
        alternatives = [
            NamingSeries(
                name=f"Concurrente {number} {company}",
                entity_type="sales_invoice",
                company=company,
                prefix_template=f"S{number}-",
                is_active=True,
                is_default=False,
            )
            for number in (1, 2)
        ]
        database.session.add_all(alternatives)
        database.session.commit()
        series_ids = [row.id for row in alternatives]

    from threading import Barrier

    start = Barrier(2)

    def activate_default(series_id: str) -> None:
        """Run one series activation in its own transaction and session."""
        with application.app_context():
            try:
                series = database.session.get(NamingSeries, series_id)
                assert series is not None
                start.wait(timeout=5)
                enforce_single_default_series(series.entity_type, series.company, exclude_id=series.id)
                series.is_default = True
                database.session.commit()
            finally:
                database.session.remove()

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(activate_default, series_id) for series_id in series_ids]
        for future in futures:
            future.result(timeout=15)

    with application.app_context():
        defaults = (
            database.session.execute(
                database.select(NamingSeries).filter_by(entity_type="sales_invoice", company=ids["company"], is_default=True)
            )
            .scalars()
            .all()
        )
        assert len(defaults) == 1
        assert defaults[0].id in series_ids


def test_inactive_default_blocks_automatic_duplicate_series(replenishment_app):
    """Document numbering fails closed instead of duplicating an inactive default."""
    application, ids = replenishment_app
    with application.app_context():
        inactive_default = NamingSeries(
            name=f"Inactiva {ids['company']}",
            entity_type="sales_invoice",
            company=ids["company"],
            prefix_template="SI-",
            is_active=False,
            is_default=True,
        )
        database.session.add(inactive_default)
        database.session.commit()

        with pytest.raises(IdentifierConfigurationError, match="serie seleccionada.*inactiva"):
            generate_entity_code("sales_invoice", "invoice-test", company=ids["company"])

        defaults = (
            database.session.execute(
                database.select(NamingSeries).filter_by(entity_type="sales_invoice", company=ids["company"], is_default=True)
            )
            .scalars()
            .all()
        )
        assert [row.id for row in defaults] == [inactive_default.id]


def test_concurrent_automatic_series_bootstrap_creates_one_default(replenishment_app):
    """Concurrent document setup creates one usable default series."""
    application, ids = replenishment_app
    from threading import Barrier

    start = Barrier(2)

    def ensure_series() -> None:
        """Run automatic series setup in an independent session."""
        with application.app_context():
            try:
                start.wait(timeout=5)
                ensure_default_naming_series_for_company(ids["company"], ["concurrent_invoice"])
                database.session.commit()
            finally:
                database.session.remove()

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(ensure_series) for _ in range(2)]
        for future in futures:
            future.result(timeout=15)

    with application.app_context():
        defaults = (
            database.session.execute(
                database.select(NamingSeries).filter_by(
                    entity_type="concurrent_invoice", company=ids["company"], is_default=True, is_active=True
                )
            )
            .scalars()
            .all()
        )
        assert len(defaults) == 1


def test_concurrent_global_series_bootstrap_creates_one_default(replenishment_app):
    """Concurrent global setup creates one default for company-less entities."""
    application, _ids = replenishment_app
    from threading import Barrier

    start = Barrier(2)

    def ensure_global_series() -> None:
        """Run global series setup in an independent session."""
        with application.app_context():
            try:
                start.wait(timeout=5)
                ensure_global_naming_series(["concurrent_global"])
                database.session.commit()
            finally:
                database.session.remove()

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(ensure_global_series) for _ in range(2)]
        for future in futures:
            future.result(timeout=15)

    with application.app_context():
        defaults = (
            database.session.execute(
                database.select(NamingSeries).filter_by(entity_type="concurrent_global", company=None, is_default=True)
            )
            .scalars()
            .all()
        )
        assert len(defaults) == 1


def test_concurrent_petty_cash_setup_creates_one_default(replenishment_app):
    """Concurrent company setup returns one petty cash default."""
    application, ids = replenishment_app
    with application.app_context():
        fund = database.session.execute(database.select(PettyCashAccount).filter_by(company=ids["company"])).scalar_one()
        fund.is_default = False
        database.session.commit()

    from threading import Barrier

    start = Barrier(2)

    def ensure_petty_cash():
        """Run company setup in an independent session."""
        with application.app_context():
            try:
                start.wait(timeout=5)
                return create_default_petty_cash(ids["company"])
            finally:
                database.session.remove()

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(ensure_petty_cash) for _ in range(2)]
        for future in futures:
            assert future.result(timeout=15) is not None

    with application.app_context():
        defaults = (
            database.session.execute(database.select(PettyCashAccount).filter_by(company=ids["company"], is_default=True))
            .scalars()
            .all()
        )
        assert len(defaults) == 1


def test_concurrent_reconciliation_adjustment_posts_one_journal(replenishment_app):
    """Two independent adjustments publish one journal and retain its pointer."""
    application, ids = replenishment_app
    with application.app_context():
        company = ids["company"]
        fund = database.session.execute(database.select(PettyCashAccount).filter_by(company=company)).scalar_one()
        accounting_module = database.session.execute(
            database.select(Modules).filter_by(module="accounting")
        ).scalar_one_or_none()
        if accounting_module is None:
            accounting_module = Modules(module="accounting", default=False, enabled=True)
            database.session.add(accounting_module)
            database.session.flush()
        approver_role = database.session.execute(
            database.select(Roles).filter_by(name=f"cash-approver-{company}")
        ).scalar_one()
        database.session.add(
            RolesAccess(
                rol_id=approver_role.id,
                module_id=accounting_module.id,
                access=True,
                create=True,
                edit=True,
                approve=True,
                validate=True,
            )
        )
        expense_account = Accounts(
            code=f"ADJ-{company}",
            name="Ajuste de caja",
            entity=company,
            group=False,
            active=True,
            enabled=True,
            account_type="expense",
        )
        cost_center_code = f"CC{company[1:]}"
        cost_center = CostCenter(code=cost_center_code, name="Caja chica", entity=company, active=True, enabled=True)
        book = Book(
            entity=company,
            code=f"B{company[1:9]}",
            name="Libro principal",
            status="activo",
            currency=fund.currency,
            is_primary=True,
        )
        reconciliation = PettyCashReconciliation(
            company=company,
            petty_cash_id=fund.id,
            reconciliation_date=date(2026, 10, 20),
            posting_date=date(2026, 10, 20),
            ledger_balance=Decimal("100"),
            expected_cash=Decimal("100"),
            counted_cash=Decimal("90"),
            explained_amount=Decimal("90"),
            difference=Decimal("-10"),
            explanation="Diferencia verificada durante el cierre de caja.",
            status="conciliado",
            docstatus=1,
            transaction_currency=fund.currency,
        )
        database.session.add_all([expense_account, cost_center, book, reconciliation])
        database.session.commit()
        reconciliation_id = reconciliation.id
        cash_account_id = fund.account_id
        adjustment_account_id = expense_account.id
        if database.engine.dialect.name == "sqlite":
            database.session.connection().exec_driver_sql(
                "CREATE TRIGGER fail_reconciliation_adjustment "
                "BEFORE UPDATE OF adjustment_journal_id ON petty_cash_reconciliation "
                "WHEN NEW.adjustment_journal_id IS NOT NULL "
                "BEGIN SELECT RAISE(ABORT, 'forced adjustment persistence failure'); END"
            )

            with pytest.raises(IntegrityError, match="forced adjustment persistence failure"):
                post_petty_cash_reconciliation_adjustment(
                    database.session.get(PettyCashReconciliation, reconciliation_id),
                    adjustment_account_code=f"ADJ-{company}",
                    cost_center_code=cost_center_code,
                    actor_id=ids["approver_user"],
                )

            database.session.connection().exec_driver_sql("DROP TRIGGER fail_reconciliation_adjustment")
            assert database.session.get(PettyCashReconciliation, reconciliation_id).adjustment_journal_id is None
            assert (
                database.session.execute(
                    database.select(ComprobanteContable.id).filter_by(entity=company, voucher_type="journal_entry")
                ).first()
                is None
            )
            assert (
                database.session.execute(
                    database.select(GLEntry.id).filter_by(company=company, voucher_type="journal_entry")
                ).first()
                is None
            )
            database.session.commit()

    from threading import Barrier

    start = Barrier(2)

    def post_adjustment() -> str:
        """Run the complete journal posting flow in an independent session."""
        with application.app_context():
            try:
                reconciliation = database.session.get(PettyCashReconciliation, reconciliation_id)
                assert reconciliation is not None
                start.wait(timeout=5)
                try:
                    journal = post_petty_cash_reconciliation_adjustment(
                        reconciliation,
                        adjustment_account_code=f"ADJ-{ids['company']}",
                        cost_center_code=f"CC{ids['company'][1:]}",
                        actor_id=ids["approver_user"],
                    )
                    return f"posted:{journal.id}"
                except ValueError as exc:
                    return f"rejected:{exc}"
            finally:
                database.session.remove()

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(post_adjustment) for _ in range(2)]
        results = [future.result(timeout=30) for future in futures]

    assert sum(result.startswith("posted:") for result in results) == 1, results
    with application.app_context():
        reconciliation = database.session.get(PettyCashReconciliation, reconciliation_id)
        assert reconciliation is not None
        assert reconciliation.adjustment_journal_id
        journal = database.session.get(ComprobanteContable, reconciliation.adjustment_journal_id)
        assert journal is not None
        assert journal.status == "submitted"
        gl_entries = (
            database.session.execute(database.select(GLEntry).filter_by(voucher_type="journal_entry", voucher_id=journal.id))
            .scalars()
            .all()
        )
        assert len(gl_entries) == 2
        amounts_by_account = {
            entry.account_id: (Decimal(str(entry.debit)), Decimal(str(entry.credit))) for entry in gl_entries
        }
        assert amounts_by_account == {
            adjustment_account_id: (Decimal("10"), Decimal("0")),
            cash_account_id: (Decimal("0"), Decimal("10")),
        }
        assert sum((Decimal(str(entry.debit)) for entry in gl_entries), Decimal("0")) == Decimal("10")
        assert sum((Decimal(str(entry.credit)) for entry in gl_entries), Decimal("0")) == Decimal("10")


def test_replenishment_cannot_skip_payment_to_reimbursed_status(replenishment_app):
    """Only the posted bank debit note can complete a replenishment."""
    application, ids = replenishment_app
    with application.app_context():
        replenishment = database.session.get(PettyCashReplenishment, ids["replenishment_by_preparer"])
        assert replenishment is not None
        replenishment.status = "aprobado"
        database.session.commit()

        with pytest.raises(ValueError, match="Transición de reposición no válida"):
            set_petty_cash_replenishment_status(replenishment, "reembolsado", actor_id=ids["approver_user"])

        database.session.rollback()
        replenishment = database.session.get(PettyCashReplenishment, ids["replenishment_by_preparer"])
        assert replenishment is not None
        assert replenishment.status == "aprobado"
        assert replenishment.bank_debit_note_id is None
        assert (
            database.session.execute(database.select(PaymentEntry.id).where(PaymentEntry.company == ids["company"])).first()
            is None
        )


def test_replenishment_waits_for_sqlite_writer_and_rechecks_committed_status(replenishment_app):
    """A waiting SQLite writer sees a completed reimbursement before creating another payment."""
    application, ids = replenishment_app
    with application.app_context():
        if database.engine.dialect.name != "sqlite":
            pytest.skip("La prueba verifica la reserva de escritor específica de SQLite.")

        replenishment = database.session.get(PettyCashReplenishment, ids["replenishment_by_preparer"])
        assert replenishment is not None
        replenishment.status = "aprobado"
        database.session.commit()
        database.session.connection().exec_driver_sql("BEGIN IMMEDIATE")
        replenishment = database.session.get(PettyCashReplenishment, ids["replenishment_by_preparer"])
        assert replenishment is not None
        replenishment.status = "reembolsado"
        database.session.flush()
        started = Event()

        def second_replenishment_attempt():
            with application.app_context():
                started.set()
                current = database.session.get(PettyCashReplenishment, ids["replenishment_by_preparer"])
                assert current is not None
                replenish_petty_cash(current, bank_account_id="unused")

        with ThreadPoolExecutor(max_workers=1) as executor:
            attempt = executor.submit(second_replenishment_attempt)
            assert started.wait(timeout=5)
            with pytest.raises(TimeoutError):
                attempt.result(timeout=0.1)

            database.session.commit()
            with pytest.raises(ValueError, match="Solo se puede reponer una solicitud aprobada"):
                attempt.result(timeout=5)

    with application.app_context():
        assert (
            database.session.execute(database.select(PaymentEntry.id).where(PaymentEntry.company == ids["company"])).first()
            is None
        )
        replenishment = database.session.get(PettyCashReplenishment, ids["replenishment_by_preparer"])
        assert replenishment is not None
        assert replenishment.status == "reembolsado"


def test_replenishment_waits_for_sqlite_writer_and_rechecks_claimed_expense(replenishment_app):
    """A competing request sees the first reservation after its SQLite transaction commits."""
    application, ids = replenishment_app
    with application.app_context():
        if database.engine.dialect.name != "sqlite":
            pytest.skip("La intercalación verifica la reserva de escritor específica de SQLite.")
        fund = database.session.execute(database.select(PettyCashAccount).filter_by(company=ids["company"])).scalar_one()
        expense = PettyCashExpense(
            company=ids["company"],
            petty_cash_id=fund.id,
            posting_date=date(2026, 10, 19),
            amount=Decimal("100"),
            concept="Compra operativa",
            expense_account_code=f"EXP-{ids['company']}",
            docstatus=1,
        )
        previous_request = PettyCashReplenishment(
            company=ids["company"],
            petty_cash_id=fund.id,
            request_date=date(2026, 10, 20),
            amount=Decimal("100"),
            status="borrador",
            docstatus=0,
        )
        database.session.add_all([expense, previous_request])
        database.session.commit()
        expense_id = expense.id
        previous_request_id = previous_request.id
        fund_id = fund.id

        database.session.connection().exec_driver_sql("BEGIN IMMEDIATE")
        expense.replenishment_id = previous_request_id
        database.session.flush()
        started = Event()

        def competing_request():
            with application.app_context():
                stale_expense = database.session.get(PettyCashExpense, expense_id)
                assert stale_expense is not None
                assert stale_expense.replenishment_id is None
                started.set()
                create_petty_cash_replenishment(
                    company=ids["company"],
                    petty_cash_id=fund_id,
                    expense_ids=[expense_id],
                    request_date=date(2026, 10, 21),
                    actor_id=ids["preparer_user"],
                )

        with ThreadPoolExecutor(max_workers=1) as executor:
            request = executor.submit(competing_request)
            assert started.wait(timeout=5)
            with pytest.raises(TimeoutError):
                request.result(timeout=0.1)

            database.session.commit()
            with pytest.raises(ValueError, match="no estan disponibles"):
                request.result(timeout=5)

        assert expense.replenishment_id == previous_request_id
        assert (
            database.session.execute(
                database.select(database.func.count(PettyCashReplenishment.id)).filter_by(company=ids["company"])
            ).scalar_one()
            == 3
        )


def test_expense_cancellation_waits_for_sqlite_reservation(replenishment_app):
    """A cancellation that loaded an unreserved expense must see a concurrent claim."""
    application, ids = replenishment_app
    with application.app_context():
        if database.engine.dialect.name != "sqlite":
            pytest.skip("La intercalación verifica la reserva de escritor específica de SQLite.")
        fund = database.session.execute(database.select(PettyCashAccount).filter_by(company=ids["company"])).scalar_one()
        expense = PettyCashExpense(
            company=ids["company"],
            petty_cash_id=fund.id,
            posting_date=date(2026, 10, 19),
            amount=Decimal("100"),
            concept="Compra operativa",
            expense_account_code=f"EXP-{ids['company']}",
            docstatus=1,
        )
        prior_request = PettyCashReplenishment(
            company=ids["company"],
            petty_cash_id=fund.id,
            request_date=date(2026, 10, 20),
            amount=Decimal("100"),
            status="borrador",
            docstatus=0,
        )
        database.session.add_all([expense, prior_request])
        database.session.commit()
        expense_id = expense.id

        database.session.connection().exec_driver_sql("BEGIN IMMEDIATE")
        expense.replenishment_id = prior_request.id
        database.session.flush()
        started = Event()

        def competing_cancellation():
            with application.app_context():
                stale_expense = database.session.get(PettyCashExpense, expense_id)
                assert stale_expense is not None
                assert stale_expense.replenishment_id is None
                started.set()
                cancel_petty_cash_expense(stale_expense, actor_id=ids["preparer_user"])

        with ThreadPoolExecutor(max_workers=1) as executor:
            cancellation = executor.submit(competing_cancellation)
            assert started.wait(timeout=5)
            with pytest.raises(TimeoutError):
                cancellation.result(timeout=0.1)

            database.session.commit()
            with pytest.raises(ValueError, match="gasto reservado en una reposición"):
                cancellation.result(timeout=5)

        assert expense.docstatus == 1
        assert expense.replenishment_id == prior_request.id
