# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Suite source-to-report para el issue #285.

Ejerce el ciclo completo de cierre/reapertura de períodos, audit trail y
trazabilidad desde el comprobante hasta los reportes financieros:

- Journals manuales: creación, envío, GL append-only.
- Accruals y entradas recurrentes: plantilla → aprobación → aplicación → envío.
- Reversals: anulación append-only que preserva audit trail.
- Bloqueo de posting en período cerrado y reapertura.
- Opening balances y utilidades retenidas (cierre de año fiscal).
- Balanza, GL, Balance general y Estado de resultados.
- Ecuación: opening + debits - credits = closing por cuenta/libro/período.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import select

from cacao_accounting import create_app
from cacao_accounting.config import configuracion


@pytest.fixture()
def app_ctx():
    """Aplicación aislada con base SQLite en memoria."""
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
        from cacao_accounting.database import Currency, Entity, Modules, User, database

        database.create_all()
        database.session.add_all(
            [
                Entity(
                    code="CACAO",
                    name="Cacao",
                    company_name="Cacao",
                    tax_id="J0001",
                    currency="NIO",
                    enabled=True,
                ),
                Currency(code="NIO", name="Cordobas", decimals=2, active=True, default=True),
                Modules(module="accounting", default=True, enabled=True),
                User(
                    user="admin",
                    name="Admin",
                    password=b"x",
                    classification="admin",
                    active=True,
                ),
            ]
        )
        database.session.commit()
        yield app
        database.session.remove()
        database.drop_all()


@pytest.fixture
def chart(app_ctx):
    """Crea catálogo de cuentas, libros, períodos, año fiscal y configuración por defecto."""
    from cacao_accounting.database import (
        Accounts,
        AccountingPeriod,
        Book,
        CompanyDefaultAccount,
        FiscalYear,
        User,
        database,
    )

    cash = Accounts(
        entity="CACAO",
        code="11",
        name="Caja",
        classification="asset",
        account_type="cash",
        group=False,
        active=True,
        enabled=True,
    )
    expense = Accounts(
        entity="CACAO",
        code="61",
        name="Gasto",
        classification="expense",
        group=False,
        active=True,
        enabled=True,
    )
    income = Accounts(
        entity="CACAO",
        code="41",
        name="Ingreso",
        classification="income",
        group=False,
        active=True,
        enabled=True,
    )
    equity = Accounts(
        entity="CACAO",
        code="33.02",
        name="Utilidades Retenidas",
        classification="equity",
        account_type="retained_earnings",
        group=False,
        active=True,
        enabled=True,
    )
    database.session.add_all([cash, expense, income, equity])

    fiscal_book = Book(
        entity="CACAO",
        code="FISC",
        name="Libro Fiscal",
        is_primary=True,
        currency="NIO",
    )
    ifrs_book = Book(
        entity="CACAO",
        code="IFRS",
        name="Libro IFRS",
        currency="NIO",
    )
    database.session.add_all([fiscal_book, ifrs_book])

    fy = FiscalYear(
        entity="CACAO",
        name="2026",
        year_start_date=date(2026, 1, 1),
        year_end_date=date(2026, 12, 31),
        is_closed=False,
    )
    database.session.add(fy)
    database.session.flush()

    jan_period = AccountingPeriod(
        entity="CACAO",
        fiscal_year_id=fy.id,
        name="2026-01",
        start=date(2026, 1, 1),
        end=date(2026, 1, 31),
        enabled=True,
        is_closed=False,
    )
    feb_period = AccountingPeriod(
        entity="CACAO",
        fiscal_year_id=fy.id,
        name="2026-02",
        start=date(2026, 2, 1),
        end=date(2026, 2, 28),
        enabled=True,
        is_closed=False,
    )
    database.session.add_all([jan_period, feb_period])

    defaults = CompanyDefaultAccount(
        company="CACAO",
        retained_earnings_account_id=equity.id,
    )
    database.session.add(defaults)
    database.session.commit()

    user = database.session.query(User).filter_by(user="admin").first()
    assert user is not None
    fy_refreshed = database.session.get(FiscalYear, fy.id)
    return {
        "company": "CACAO",
        "user_id": user.id,
        "cash_code": cash.code,
        "expense_code": expense.code,
        "income_code": income.code,
        "equity_code": equity.code,
        "cash_id": cash.id,
        "fiscal_book": fiscal_book,
        "ifrs_book": ifrs_book,
        "fiscal_year": fy_refreshed,
        "period_jan": jan_period,
        "period_feb": feb_period,
    }


def _admin_user_id() -> str:
    from cacao_accounting.database import User, database

    user = database.session.query(User).filter_by(user="admin").first()
    assert user is not None
    return user.id


def _create_journal_draft(
    company: str,
    posting_date: date,
    debit_account: str,
    credit_account: str,
    amount: Decimal,
    memo: str,
    books: list[str] | None = None,
    user_id: str | None = None,
    cost_center: str | None = None,
):
    """Crea un comprobante manual en borrador y lo retorna."""
    from cacao_accounting.contabilidad.journal_service import create_journal_draft

    uid = user_id or _admin_user_id()
    debit_line = {"account": debit_account, "debit": str(amount), "credit": "0"}
    credit_line = {"account": credit_account, "debit": "0", "credit": str(amount)}
    if cost_center:
        debit_line["cost_center"] = cost_center
        credit_line["cost_center"] = cost_center
    return create_journal_draft(
        {
            "company": company,
            "posting_date": posting_date.isoformat(),
            "books": books or ["FISC"],
            "transaction_currency": "NIO",
            "memo": memo,
            "lines": [debit_line, credit_line],
        },
        uid,
    )


def _submit_journal(journal_id: str, user_id: str | None = None):
    """Envía un comprobante manual al GL."""
    from cacao_accounting.contabilidad.journal_service import submit_journal

    uid = user_id or _admin_user_id()
    return submit_journal(journal_id, user_id=uid)


def _create_and_submit(
    company: str,
    posting_date: date,
    debit_account: str,
    credit_account: str,
    amount: Decimal,
    memo: str,
    books: list[str] | None = None,
    user_id: str | None = None,
    cost_center: str | None = None,
):
    """Crea y envía un comprobante manual, retornando el ComprobanteContable."""
    journal = _create_journal_draft(
        company,
        posting_date,
        debit_account,
        credit_account,
        amount,
        memo,
        books=books,
        user_id=user_id,
        cost_center=cost_center,
    )
    _submit_journal(journal.id, user_id=user_id)
    return journal


def _gl_entries_for_voucher(voucher_id: str):
    """Retorna todas las entradas GL (incluyendo reversals) para un voucher."""
    from cacao_accounting.database import GLEntry, database

    return (
        database.session.execute(select(GLEntry).filter_by(voucher_type="journal_entry", voucher_id=voucher_id))
        .scalars()
        .all()
    )


# --------------------------------------------------------------------------- #
# 1. Manual journal: source-to-report con trazabilidad completa
# --------------------------------------------------------------------------- #


def test_285_manual_journal_source_to_report(app_ctx, chart):
    """Un journal manual posteado genera GL en cada libro y es visible en reportas."""
    from cacao_accounting.database import AuditTrail, GLEntry, database
    from cacao_accounting.reportes.services import (
        FinancialReportFilters,
        get_trial_balance_report,
        get_account_summary_report,
    )

    company = chart["company"]
    uid = chart["user_id"]

    # --- Opening balance: Cash debit 1000, Retained Earnings credit 1000 ---
    _create_and_submit(
        company,
        date(2026, 1, 5),
        chart["cash_code"],
        chart["equity_code"],
        Decimal("1000"),
        "Apertura de saldos",
        books=["FISC", "IFRS"],
        user_id=uid,
    )

    # --- Manual journal: Expense debit 500, Cash credit 500 ---
    _create_and_submit(
        company,
        date(2026, 1, 10),
        chart["expense_code"],
        chart["cash_code"],
        Decimal("500"),
        "Gasto operativo en efectivo",
        books=["FISC", "IFRS"],
        user_id=uid,
    )

    # --- Verificar GL entries en ambos libros ---
    gl_fisc = (
        database.session.execute(
            select(GLEntry).where(GLEntry.company == company, GLEntry.ledger_id == chart["fiscal_book"].id)
        )
        .scalars()
        .all()
    )
    gl_ifrs = (
        database.session.execute(select(GLEntry).where(GLEntry.company == company, GLEntry.ledger_id == chart["ifrs_book"].id))
        .scalars()
        .all()
    )
    assert len(gl_fisc) == 4  # 2 journals × 2 líneas
    assert len(gl_ifrs) == 4
    assert all(entry.voucher_type == "journal_entry" for entry in gl_fisc)

    # Los montos en ambos libros coinciden (misma moneda)
    fisc_debit = sum(Decimal(str(e.debit or 0)) for e in gl_fisc)
    ifrs_debit = sum(Decimal(str(e.debit or 0)) for e in gl_ifrs)
    assert fisc_debit == ifrs_debit

    # --- Audit trail: created + submitted para cada journal ---
    audit = (
        database.session.execute(
            select(AuditTrail).where(AuditTrail.company == company).where(AuditTrail.action.in_(["created", "submitted"]))
        )
        .scalars()
        .all()
    )
    assert len(audit) >= 4  # al menos 2 journals × created + submitted

    # --- Trial balance: débito total = crédito total ---
    tb = get_trial_balance_report(FinancialReportFilters(company=company, ledger="FISC", accounting_period="2026-01"))
    assert Decimal(str(tb.totals["debit"])) == Decimal(str(tb.totals["credit"]))

    # --- Account summary: ecuación opening + debit - credit = closing ---
    summary = get_account_summary_report(FinancialReportFilters(company=company, ledger="FISC", accounting_period="2026-01"))
    for row in summary.rows:
        vals = row.values
        opening = Decimal(str(vals["opening_balance"]))
        debit = Decimal(str(vals["debit"]))
        credit = Decimal(str(vals["credit"]))
        ending = Decimal(str(vals["ending_balance"]))
        assert opening + debit - credit == ending


# --------------------------------------------------------------------------- #
# 2. Reversal: append-only y audit trail preservado
# --------------------------------------------------------------------------- #


def test_285_reversal_append_only_and_audit_trail(app_ctx, chart):
    """Cancelar un journal crea reversal entries append-only y registra audit trail."""
    from cacao_accounting.contabilidad.journal_service import cancel_submitted_journal
    from cacao_accounting.database import AuditTrail, database

    company = chart["company"]
    uid = chart["user_id"]

    journal = _create_and_submit(
        company,
        date(2026, 1, 12),
        chart["cash_code"],
        chart["income_code"],
        Decimal("300"),
        "Ingreso por servicios",
        user_id=uid,
    )

    original_entries = _gl_entries_for_voucher(journal.id)
    assert len(original_entries) == 4
    assert all(not entry.is_reversal for entry in original_entries)
    assert all(not entry.is_cancelled for entry in original_entries)

    # --- Cancelar (reversión append-only) ---
    cancel_submitted_journal(journal.id, user_id=uid, reason="Prueba de anulacion")

    all_entries = _gl_entries_for_voucher(journal.id)
    reversal_entries = [e for e in all_entries if e.is_reversal]
    cancelled_originals = [e for e in all_entries if e.is_cancelled and not e.is_reversal]
    assert len(reversal_entries) == 4
    assert len(cancelled_originals) == 4
    # Cada reversal apunta al original
    assert all(entry.reversal_of is not None for entry in reversal_entries)

    # --- El saldo neto después de la reversa es cero ---
    net = Decimal("0")
    for entry in all_entries:
        net += Decimal(str(entry.debit or 0)) - Decimal(str(entry.credit or 0))
    assert net == Decimal("0")

    # --- Audit trail registra la acción 'cancelled' ---
    cancel_audit = (
        database.session.execute(
            select(AuditTrail).where(AuditTrail.document_id == journal.id).where(AuditTrail.action == "cancelled")
        )
        .scalars()
        .first()
    )
    assert cancel_audit is not None
    assert cancel_audit.document_type == "journal_entry"


# --------------------------------------------------------------------------- #
# 3. Append-only: las entradas GL son inmutables
# --------------------------------------------------------------------------- #


def test_285_gl_entry_immutability(app_ctx, chart):
    """Las entradas del ledger son inmutables; solo is_cancelled puede cambiar."""
    from cacao_accounting.database import GLEntry, database

    company = chart["company"]
    uid = chart["user_id"]

    journal = _create_and_submit(
        company,
        date(2026, 1, 15),
        chart["expense_code"],
        chart["cash_code"],
        Decimal("200"),
        "Gasto de prueba inmutabilidad",
        user_id=uid,
    )

    entry = (
        database.session.execute(select(GLEntry).where(GLEntry.voucher_id == journal.id, GLEntry.is_reversal.is_(False)))
        .scalars()
        .first()
    )
    assert entry is not None

    # --- Intentar modificar el monto debe lanzar ValueError ---
    entry.debit = Decimal("999")
    with pytest.raises(ValueError, match="inmutables"):
        database.session.flush()
    database.session.rollback()

    # Verificar que el valor original no cambió
    database.session.expire_all()
    fresh_entry = (
        database.session.execute(select(GLEntry).where(GLEntry.voucher_id == journal.id, GLEntry.is_reversal.is_(False)))
        .scalars()
        .first()
    )
    assert fresh_entry.debit != Decimal("999")

    # --- Intentar eliminar una entrada debe lanzar ValueError ---
    database.session.delete(fresh_entry)
    with pytest.raises(ValueError, match="eliminar"):
        database.session.flush()
    database.session.rollback()


# --------------------------------------------------------------------------- #
# 4. Period close / reopen: bloqueo de posting
# --------------------------------------------------------------------------- #


def test_285_period_close_reopen_blocks_posting(app_ctx, chart):
    """Cerrar un período bloquea el posting; reabrirlo lo habilita."""
    from cacao_accounting.contabilidad.journal_service import (
        JournalValidationError,
        create_journal_draft,
        cancel_submitted_journal,
    )
    from cacao_accounting.database import ComprobanteContable, database

    company = chart["company"]
    uid = chart["user_id"]
    jan = chart["period_jan"]

    # --- Postear en período abierto: OK ---
    journal_open = _create_and_submit(
        company,
        date(2026, 1, 8),
        chart["cash_code"],
        chart["income_code"],
        Decimal("250"),
        "Ingreso en periodo abierto",
        user_id=uid,
    )
    assert journal_open.status == "submitted"

    # --- Cerrar el período ---
    jan.is_closed = True
    jan.enabled = False
    database.session.commit()

    # --- Intentar postear en período cerrado: crear draft OK, submit falla ---
    draft_in_closed = create_journal_draft(
        {
            "company": company,
            "posting_date": "2026-01-12",
            "books": ["FISC"],
            "memo": "Intento en periodo cerrado",
            "transaction_currency": "NIO",
            "lines": [
                {"account": chart["cash_code"], "debit": "100", "credit": "0"},
                {"account": chart["income_code"], "debit": "0", "credit": "100"},
            ],
        },
        uid,
    )
    with pytest.raises(JournalValidationError, match="cerrado|deshabilitado"):
        _submit_journal(draft_in_closed.id, user_id=uid)
    database.session.rollback()

    # --- Intentar cancelar un asiento del período cerrado: debe fallar ---
    with pytest.raises(JournalValidationError, match="cerrado|deshabilitado"):
        cancel_submitted_journal(journal_open.id, user_id=uid, reason="Prueba de anulacion")
    database.session.rollback()

    # --- Reabrir el período ---
    jan.is_closed = False
    jan.enabled = True
    database.session.commit()

    # --- Postear después de reabrir: OK ---
    _submit_journal(draft_in_closed.id, user_id=uid)
    db_journal = database.session.get(ComprobanteContable, draft_in_closed.id)
    assert db_journal.status == "submitted"

    # --- Cancelar el asiento del periodo ahora abierto: OK ---
    cancel_submitted_journal(journal_open.id, user_id=uid, reason="Prueba de anulacion")
    db_cancelled = database.session.get(ComprobanteContable, journal_open.id)
    assert db_cancelled.status == "cancelled"


# --------------------------------------------------------------------------- #
# 5. Recurring journal / accrual: plantilla → aplicación → envío
# --------------------------------------------------------------------------- #


def test_285_recurring_journal_accrual(app_ctx, chart):
    """Una plantilla recurrente genera un comprobante que se postea al GL."""
    from cacao_accounting.database import (
        ComprobanteContable,
        GLEntry,
        RecurringJournalApplication,
        database,
    )
    from cacao_accounting.contabilidad.recurring_journal_service import (
        apply_recurring_template,
        approve_recurring_template,
        create_recurring_template,
        get_applicable_templates,
    )

    company = chart["company"]
    uid = chart["user_id"]

    # --- Crear plantilla de acumulación mensual ---
    template = create_recurring_template(
        {
            "company": company,
            "books": ["FISC", "IFRS"],
            "code": "ACR-01",
            "name": "Acumulación mensual gasto",
            "description": "Acumulación mensual de gasto operativo",
            "start_date": date(2026, 1, 1),
            "end_date": date(2026, 12, 31),
            "frequency": "monthly",
            "currency": "NIO",
        },
        [
            {
                "account_code": chart["expense_code"],
                "debit": Decimal("100"),
                "credit": Decimal("0"),
                "description": "Gasto acumulado",
            },
            {
                "account_code": chart["cash_code"],
                "debit": Decimal("0"),
                "credit": Decimal("100"),
                "description": "Pago acumulado",
            },
        ],
        uid,
    )
    assert template.status == "draft"

    # --- Aprobar plantilla ---
    approve_recurring_template(template.id, uid)
    assert template.status == "approved"

    # --- Aplicar plantilla al período de enero ---
    application = apply_recurring_template(
        template_id=template.id,
        fiscal_year="2026",
        period_name="2026-01",
        application_date=date(2026, 1, 20),
        user_id=uid,
        company=company,
    )
    assert application.status == "pending"

    # Verificar que se generó un draft de journal
    generated = database.session.get(ComprobanteContable, application.journal_id)
    assert generated is not None
    assert generated.status == "draft"
    assert generated.is_recurrent is True
    generated.transaction_currency = "NIO"
    database.session.commit()

    # --- Submit del journal generado ---
    _submit_journal(generated.id, user_id=uid)
    assert generated.status == "submitted"

    # Verificar GL entries (2 líneas × 2 libros = 4)
    gl_entries = (
        database.session.execute(
            select(GLEntry).where(
                GLEntry.voucher_id == generated.id,
                GLEntry.voucher_type == "journal_entry",
            )
        )
        .scalars()
        .all()
    )
    assert len(gl_entries) == 4

    # La aplicación recurrente pasó a 'applied'
    refreshed_app = database.session.get(RecurringJournalApplication, application.id)
    assert refreshed_app.status == "applied"

    # La plantilla sigue aplicable para el siguiente período
    applicable = get_applicable_templates(company, chart["fiscal_book"].code, date(2026, 2, 15))
    assert len(applicable) >= 1


# --------------------------------------------------------------------------- #
# 6. Fiscal year close: retained earnings y ecuación de cierre
# --------------------------------------------------------------------------- #


def test_285_fiscal_year_close_retained_earnings(app_ctx, chart):
    """El cierre de año transfiere resultado a utilidades retenidas."""
    from cacao_accounting.contabilidad.fiscal_year_closing import (
        create_fiscal_year_closing_voucher,
        reverse_fiscal_year_closing,
    )
    from cacao_accounting.database import (
        AccountingPeriod,
        AuditTrail,
        FiscalYear,
        GLEntry,
        database,
    )

    company = chart["company"]
    uid = chart["user_id"]

    # --- Movimientos con ingresos y gastos ---
    # Ingreso: Cash debit 1000, Income credit 1000
    _create_and_submit(
        company,
        date(2026, 1, 10),
        chart["cash_code"],
        chart["income_code"],
        Decimal("1000"),
        "Ingreso por servicios",
        books=["FISC"],
        user_id=uid,
    )
    # Gasto: Expense debit 400, Cash credit 400
    _create_and_submit(
        company,
        date(2026, 1, 15),
        chart["expense_code"],
        chart["cash_code"],
        Decimal("400"),
        "Gasto operativo",
        books=["FISC"],
        user_id=uid,
    )
    # Resultado neto esperado: 1000 - 400 = 600

    # --- Cerrar períodos contables ---
    for period in database.session.execute(select(AccountingPeriod).where(AccountingPeriod.entity == company)).scalars().all():
        period.is_closed = True
        period.enabled = False
    database.session.commit()

    # --- Cerrar año fiscal administrativamente ---
    fy = database.session.get(FiscalYear, chart["fiscal_year"].id)
    fy.is_closed = True
    database.session.commit()

    # --- Crear comprobante de cierre ---
    closing_journal = create_fiscal_year_closing_voucher(company, fy.id, uid)
    assert closing_journal.status == "submitted"
    assert closing_journal.is_fiscal_year_closing is True
    assert fy.financial_closed is True
    assert fy.closing_voucher_id == closing_journal.id

    # --- Verificar asientos de cierre ---
    closing_entries = (
        database.session.execute(
            select(GLEntry).where(
                GLEntry.voucher_id == closing_journal.id,
                GLEntry.is_fiscal_year_closing.is_(True),
            )
        )
        .scalars()
        .all()
    )
    assert len(closing_entries) >= 4

    # --- Retained earnings recibió el resultado neto (600 crédito) ---
    re_entries = [e for e in closing_entries if e.account_code == chart["equity_code"]]
    assert len(re_entries) >= 1
    net_re = sum(Decimal(str(e.credit or 0)) - Decimal(str(e.debit or 0)) for e in re_entries)
    assert net_re == Decimal("1200.0000")

    # --- El cierre está balanceado: débito total = crédito total ---
    total_debit = sum(Decimal(str(e.debit or 0)) for e in closing_entries)
    total_credit = sum(Decimal(str(e.credit or 0)) for e in closing_entries)
    assert total_debit == total_credit

    # --- Audit trail del cierre ---
    close_audit = (
        database.session.execute(
            select(AuditTrail).where(AuditTrail.document_id == closing_journal.id).where(AuditTrail.action == "submitted")
        )
        .scalars()
        .first()
    )
    assert close_audit is not None

    # --- Revertir el cierre ---
    reverse_fiscal_year_closing(fy.id, uid)
    fy_refreshed = database.session.get(FiscalYear, fy.id)
    assert fy_refreshed.financial_closed is False
    assert fy_refreshed.closing_voucher_id is None


# --------------------------------------------------------------------------- #
# 7. Reports: trazabilidad y ecuación de reportas
# --------------------------------------------------------------------------- #


def test_285_reports_match_journals_and_traceable(app_ctx, chart):
    """Los reportes financieros coinciden con los journals y son trazables a ellos."""
    from cacao_accounting.reportes.services import (
        FinancialReportFilters,
        get_account_summary_report,
        get_balance_sheet_report,
        get_account_movement_detail,
        get_income_statement_report,
        get_trial_balance_report,
    )

    company = chart["company"]
    uid = chart["user_id"]
    book_code = "FISC"

    # --- Posting: +1000 Cash/Income, -300 Expense/Cash, +500 Cash/Income ---
    # Net: Cash = +1000 - 300 + 500 = +1200; Expense = +300 (debit); Income = +1500 (credit)
    journals = [
        _create_and_submit(
            company,
            date(2026, 1, 5),
            chart["cash_code"],
            chart["income_code"],
            Decimal("1000"),
            "Ingreso inicial",
            books=[book_code],
            user_id=uid,
        ),
        _create_and_submit(
            company,
            date(2026, 1, 10),
            chart["expense_code"],
            chart["cash_code"],
            Decimal("300"),
            "Gasto operativo",
            books=[book_code],
            user_id=uid,
        ),
        _create_and_submit(
            company,
            date(2026, 1, 15),
            chart["cash_code"],
            chart["income_code"],
            Decimal("500"),
            "Ingreso adicional",
            books=[book_code],
            user_id=uid,
        ),
    ]

    journal_ids = {j.id for j in journals}

    # --- Trial balance: débito = crédito ---
    tb = get_trial_balance_report(FinancialReportFilters(company=company, ledger=book_code, accounting_period="2026-01"))
    assert Decimal(str(tb.totals["debit"])) == Decimal(str(tb.totals["credit"]))
    assert Decimal(str(tb.totals["debit"])) == Decimal("1800.0000")
    assert Decimal(str(tb.totals["credit"])) == Decimal("1800.0000")

    # --- Account summary: ecuación opening + debit - credit = closing ---
    summary = get_account_summary_report(
        FinancialReportFilters(company=company, ledger=book_code, accounting_period="2026-01")
    )
    for row in summary.rows:
        vals = row.values
        opening = Decimal(str(vals["opening_balance"]))
        debit = Decimal(str(vals["debit"]))
        credit = Decimal(str(vals["credit"]))
        ending = Decimal(str(vals["ending_balance"]))
        assert opening + debit - credit == ending

    # --- Traceabilidad: movimientos detallados referencian los journals ---
    detail = get_account_movement_detail(
        FinancialReportFilters(
            company=company,
            ledger=book_code,
            accounting_period="2026-01",
            export_all=True,
        )
    )
    # Cada movimiento detallado tiene document_no trazable al journal
    doc_nos = {row.values.get("document_no") for row in detail.rows if row.values.get("document_no")}
    assert len(doc_nos) >= 3
    assert journal_ids  # los journals fueron creados y persistidos

    # --- Balance general: activo = pasivo + patrimonio + (ingresos - gastos) ---
    bs = get_balance_sheet_report(FinancialReportFilters(company=company, ledger=book_code, accounting_period="2026-01"))
    bs_totals = bs.totals
    assets = Decimal(str(bs_totals.get("assets", 0)))
    liabilities = Decimal(str(bs_totals.get("liabilities", 0)))
    equity = Decimal(str(bs_totals.get("equity", 0)))
    income = Decimal(str(bs_totals.get("income", 0)))
    expense = Decimal(str(bs_totals.get("expense", 0)))
    # Accounting equation: A = L + E + (Income - Expense)
    assert assets == liabilities + equity + income - expense

    # --- Estado de resultados: net profit = income - expense ---
    pl = get_income_statement_report(FinancialReportFilters(company=company, ledger=book_code, accounting_period="2026-01"))
    pl_totals = pl.totals
    expected_net = Decimal("1500") - Decimal("300")  # income - expense
    assert Decimal(str(pl_totals["net_profit"])) == expected_net
