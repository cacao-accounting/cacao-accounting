# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1784: la capitalización multimoneda es atómica y reintentable por fuente."""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy import delete, select

from cacao_accounting.contabilidad.journal_service import create_journal_draft, submit_journal
from cacao_accounting.contabilidad.project_capitalization_service import ProjectCapitalizationService
from cacao_accounting.database import (
    AccountingPeriod,
    Accounts,
    Book,
    ComprobanteContable,
    CostCenter,
    ExchangeRate,
    GLEntry,
    Project,
    User,
    database,
)


def _admin_id() -> str:
    """Devuelve el administrador del entorno aislado."""
    return str(database.session.execute(select(User.id).where(User.user == "admin")).scalar_one())


def _create_source(project_code: str, cost_center_code: str, reference: str, *, mixed_currency: bool) -> str:
    """Crea y contabiliza una fuente real con gastos del proyecto indicado."""
    lines = [
        {
            "order": 1,
            "account": "5201",
            "debit": "100",
            "credit": "",
            "currency": "NIO",
            "project": project_code,
            "cost_center": cost_center_code,
        }
    ]
    if mixed_currency:
        lines.extend(
            [
                {
                    "order": 2,
                    "account": "5201",
                    "debit": "1",
                    "credit": "",
                    "currency": "USD",
                    "exchange_rate": "36",
                    "project": project_code,
                    "cost_center": cost_center_code,
                },
                {
                    "order": 3,
                    "account": "1101",
                    "debit": "",
                    "credit": "1",
                    "currency": "USD",
                    "exchange_rate": "36",
                },
            ]
        )
        credit_order = 4
    else:
        credit_order = 3
    lines.append({"order": credit_order, "account": "1101", "debit": "", "credit": "100", "currency": "NIO"})
    journal = create_journal_draft(
        {
            "company": "cacao",
            "posting_date": "2026-05-15",
            "books": ["DEFAULT_BOOK"],
            "reference": reference,
            "transaction_currency": "NIO",
            "base_currency": "NIO",
            "lines": lines,
        },
        user_id=_admin_id(),
        assign_identifier=False,
    )
    submit_journal(journal.id, user_id=_admin_id())
    return str(journal.id)


def _capitalization_journals(source_id: str) -> list[ComprobanteContable]:
    """Devuelve los diarios de capitalización vinculados a una fuente."""
    return list(
        database.session.execute(
            select(ComprobanteContable).where(ComprobanteContable.capitalization_origin_id == source_id)
        ).scalars()
    )


def test_fuente_multimoneda_falla_sin_parciales_y_reintenta_completa(entorno_contable_aislado):
    """Una tasa ausente no confirma una moneda ni impide capitalizar la fuente después."""
    app = entorno_contable_aislado.app
    with app.app_context():
        actor_id = _admin_id()
        period = database.session.execute(select(AccountingPeriod).where(AccountingPeriod.id == "P2026-05")).scalar_one()
        expense_account = database.session.execute(
            select(Accounts).where(Accounts.entity == "cacao", Accounts.code == "5201")
        ).scalar_one()
        period_id = period.id
        expense_account_id = expense_account.id
        period_start = period.start
        project_code = "CAP1784"
        cost_center_code = "CC1784"
        cap_account = Accounts(
            entity="cacao",
            code="1201",
            name="Activo capitalizado 1784",
            classification="asset",
            account_type="fixed_asset",
            active=True,
            enabled=True,
            group=False,
        )
        cost_center = CostCenter(
            entity="cacao",
            code=cost_center_code,
            name="Centro capitalización 1784",
            active=True,
            enabled=True,
            group=False,
        )
        database.session.add_all([cap_account, cost_center])
        database.session.flush()
        project = Project(
            entity="cacao",
            code=project_code,
            name="Proyecto capitalizable 1784",
            enabled=True,
            capitalizable=True,
            capitalization_account_id=cap_account.id,
        )
        database.session.add(project)
        database.session.commit()

        mixed_id = _create_source(project_code, cost_center_code, "CAP-MIX-1784", mixed_currency=True)
        single_id = _create_source(project_code, cost_center_code, "CAP-NIO-1784", mixed_currency=False)
        source_currencies = {
            entry.account_currency
            for entry in database.session.execute(
                select(GLEntry).where(GLEntry.voucher_id == mixed_id, GLEntry.account_id == expense_account_id)
            ).scalars()
        }
        assert source_currencies == {"NIO", "USD"}
        mixed_gl_count = database.session.execute(
            select(database.func.count()).select_from(GLEntry).where(GLEntry.voucher_id == mixed_id)
        ).scalar_one()

        database.session.execute(
            delete(ExchangeRate).where((ExchangeRate.origin == "USD") | (ExchangeRate.destination == "USD"))
        )
        database.session.commit()

        service = ProjectCapitalizationService()
        successes, errors = service.run_capitalization("cacao", period_id, actor_id)

        assert successes == 1
        assert len(errors) == 1
        assert mixed_id in errors[0]
        mixed = database.session.get(ComprobanteContable, mixed_id)
        single = database.session.get(ComprobanteContable, single_id)
        assert mixed.capitalized_by_id is None
        assert single.capitalized_by_id is not None
        assert _capitalization_journals(mixed_id) == []
        single_capitals = _capitalization_journals(single_id)
        assert len(single_capitals) == 1
        assert single_capitals[0].status == "submitted"
        all_capitals = list(
            database.session.execute(
                select(ComprobanteContable).where(ComprobanteContable.capitalization_origin_id.in_([mixed_id, single_id]))
            ).scalars()
        )
        assert [capital.id for capital in all_capitals] == [single_capitals[0].id]
        capital_entries = list(
            database.session.execute(
                select(GLEntry).where(GLEntry.voucher_id.in_([capital.id for capital in all_capitals]))
            ).scalars()
        )
        assert {entry.voucher_id for entry in capital_entries} == {single_capitals[0].id}
        assert (
            database.session.execute(
                select(database.func.count()).select_from(GLEntry).where(GLEntry.voucher_id == mixed_id)
            ).scalar_one()
            == mixed_gl_count
        )

        database.session.add_all(
            [
                ExchangeRate(origin="USD", destination="NIO", rate=Decimal("36"), date=period_start),
                ExchangeRate(
                    origin="NIO",
                    destination="USD",
                    rate=(Decimal("1") / Decimal("36")).quantize(Decimal("0.000000001")),
                    date=period_start,
                ),
            ]
        )
        database.session.commit()

        retry_successes, retry_errors = service.run_capitalization("cacao", period_id, actor_id)

        assert retry_successes == 1
        assert retry_errors == []
        database.session.expire_all()
        mixed = database.session.get(ComprobanteContable, mixed_id)
        assert mixed.capitalized_by_id is not None
        mixed_capitals = _capitalization_journals(mixed_id)
        assert len(mixed_capitals) == 2
        assert {capital.transaction_currency for capital in mixed_capitals} == {"NIO", "USD"}
        assert {capital.status for capital in mixed_capitals} == {"submitted"}
        assert mixed.capitalized_by_id in {capital.id for capital in mixed_capitals}
        assert len(_capitalization_journals(single_id)) == 1

        active_books = list(
            database.session.execute(select(Book).where(Book.entity == "cacao", Book.status == "activo")).scalars()
        )
        for capital in mixed_capitals:
            entries = list(database.session.execute(select(GLEntry).where(GLEntry.voucher_id == capital.id)).scalars())
            assert len(entries) == 2 * len(active_books)
            for book in active_books:
                book_entries = [entry for entry in entries if entry.ledger_id == book.id]
                assert sum((entry.debit for entry in book_entries), Decimal("0")) == sum(
                    (entry.credit for entry in book_entries), Decimal("0")
                )
