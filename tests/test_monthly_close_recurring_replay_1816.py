# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 William José Moreno Reyes

"""#1816: el replay de recurrentes sin pendientes no bloquea el cierre."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import uuid4

from sqlalchemy import inspect, select

from cacao_accounting.contabilidad.recurring_journal_service import apply_recurring_template
from cacao_accounting.contabilidad.services import finalize_monthly_close
from cacao_accounting.database import (
    AccountingPeriod,
    Book,
    ComprobanteContable,
    GLEntry,
    PeriodCloseCheck,
    PeriodCloseRun,
    RecurringJournalApplication,
    RecurringJournalItem,
    RecurringJournalTemplate,
    User,
    database,
)


def _plantilla(env, code: str) -> str:
    """Crea una plantilla aprobada y balanceada para el período de prueba."""
    with env.app.app_context():
        book = database.session.execute(database.select(Book).filter_by(entity="cacao", code="DEFAULT_BOOK")).scalar_one()
        template = RecurringJournalTemplate(
            company="cacao",
            ledger_id=book.id,
            code=code,
            name=code,
            start_date=date(2026, 1, 1),
            end_date=date(2026, 12, 31),
            frequency="monthly",
            currency="NIO",
            status="approved",
            docstatus=1,
        )
        database.session.add(template)
        database.session.flush()
        database.session.add_all(
            [
                RecurringJournalItem(
                    template_id=template.id,
                    account_code="5101",
                    debit=Decimal("100"),
                    credit=Decimal("0"),
                    description="débito recurrente",
                ),
                RecurringJournalItem(
                    template_id=template.id,
                    account_code="1101",
                    debit=Decimal("0"),
                    credit=Decimal("100"),
                    description="crédito recurrente",
                ),
            ]
        )
        database.session.commit()
        return str(template.id)


def _cierre(env, period_name: str = "Mayo 2026") -> tuple[str, str]:
    """Obtiene el período aislado y crea su corrida de cierre."""
    with env.app.app_context():
        period = database.session.execute(
            database.select(AccountingPeriod).filter_by(entity="cacao", name=period_name)
        ).scalar_one()
        run = PeriodCloseRun(company="cacao", period_id=period.id, run_status="open")
        database.session.add(run)
        database.session.commit()
        return str(inspect(run).identity[0]), str(period.id)


def _cliente(env):
    """Autentica al administrador de la aplicación aislada."""
    client = env.app.test_client()
    with env.app.app_context():
        admin_id = database.session.execute(select(User).filter_by(user="admin")).scalar_one().id
    with client.session_transaction() as session:
        session["_user_id"] = str(admin_id)
        session["_fresh"] = True
    return client


def _ultimo_check(run_id: str) -> PeriodCloseCheck:
    """Devuelve el resultado más reciente del paso de recurrentes."""
    return database.session.execute(
        select(PeriodCloseCheck)
        .filter_by(close_run_id=run_id, check_type="apply_recurring_journals")
        .order_by(PeriodCloseCheck.created.desc(), PeriodCloseCheck.id.desc())
        .limit(1)
    ).scalar_one()


def _aplicaciones(period_id: str, template_id: str) -> list[RecurringJournalApplication]:
    """Obtiene las aplicaciones persistidas de una plantilla y período."""
    return list(
        database.session.execute(
            select(RecurringJournalApplication).filter_by(
                accounting_period_id=period_id,
                template_id=template_id,
            )
        )
        .scalars()
        .all()
    )


def test_replay_sin_ids_no_duplica_recurrentes_ni_gl(entorno_contable_aislado):
    """Una segunda ejecución sin plantillas pendientes registra un no-op."""
    env = entorno_contable_aislado
    template_id = _plantilla(env, f"REPLAY-{uuid4().hex[:6]}")
    run_id, period_id = _cierre(env)
    client = _cliente(env)
    endpoint = f"/accounting/period-close/monthly/{run_id}/apply-recurring"

    first = client.post(endpoint, data={"template_ids": [template_id]}, follow_redirects=False)
    assert first.status_code == 302
    with env.app.app_context():
        application = _aplicaciones(period_id, template_id)[0]
        journal_id = application.journal_id
        assert application.status == "applied"
        assert journal_id is not None
        original_entries = list(
            database.session.execute(
                select(GLEntry).filter_by(
                    voucher_type="journal_entry",
                    voucher_id=journal_id,
                    is_cancelled=False,
                )
            )
            .scalars()
            .all()
        )
        assert len(original_entries) == 2
        assert sum(entry.debit for entry in original_entries) == Decimal("100")
        assert sum(entry.credit for entry in original_entries) == Decimal("100")
        assert _ultimo_check(run_id).check_status == "passed"

    replay = client.post(endpoint, data={}, follow_redirects=False)
    assert replay.status_code == 302
    with env.app.app_context():
        applications = _aplicaciones(period_id, template_id)
        assert len(applications) == 1
        assert applications[0].journal_id == journal_id
        assert database.session.execute(select(ComprobanteContable.id).filter_by(id=journal_id)).scalar_one() == journal_id
        replayed_entries = list(
            database.session.execute(
                select(GLEntry).filter_by(
                    voucher_type="journal_entry",
                    voucher_id=journal_id,
                    is_cancelled=False,
                )
            )
            .scalars()
            .all()
        )
        assert [(entry.id, entry.debit, entry.credit) for entry in replayed_entries] == [
            (entry.id, entry.debit, entry.credit) for entry in original_entries
        ]
        check = _ultimo_check(run_id)
        assert check.check_status == "skipped"
        assert "Plantillas aplicadas: 0" in check.message

        database.session.add_all(
            [
                PeriodCloseCheck(
                    close_run_id=run_id,
                    check_type="exchange_revaluation",
                    check_status="passed",
                    message="Sin revalorizaciones pendientes.",
                ),
                PeriodCloseCheck(
                    close_run_id=run_id,
                    check_type="project_capitalization",
                    check_status="passed",
                    message="Sin capitalizaciones pendientes.",
                ),
            ]
        )
        database.session.commit()
        admin_id = database.session.execute(select(User).filter_by(user="admin")).scalar_one().id
        closed_run = finalize_monthly_close(run_id, admin_id)
        assert closed_run.run_status == "closed"
        closed_period = database.session.get(AccountingPeriod, period_id)
        assert closed_period is not None and closed_period.is_closed is True


def test_descubrimiento_no_excluye_aplicaciones_de_otro_periodo(entorno_contable_aislado):
    """El fallback omite solo la aplicación vigente del período que se cierra."""
    env = entorno_contable_aislado
    template_id = _plantilla(env, f"OTRO-{uuid4().hex[:6]}")
    suffix = uuid4().hex[:6]
    with env.app.app_context():
        period = AccountingPeriod(
            entity="cacao",
            fiscal_year_id="FY2026",
            name=f"Abril 1816 {suffix}",
            start=date(2026, 4, 1),
            end=date(2026, 4, 30),
            enabled=True,
            is_closed=False,
        )
        database.session.add(period)
        database.session.commit()
        admin = database.session.execute(select(User).filter_by(user="admin")).scalar_one()
        application = apply_recurring_template(
            template_id,
            "FY2026",
            period.name,
            date(2026, 4, 30),
            str(admin.id),
            company="cacao",
            submit=True,
        )
        assert application.status == "applied"
        application_id = str(inspect(application).identity[0])
        april_period_id = str(period.id)
        database.session.commit()

    run_id, may_period_id = _cierre(env)
    response = _cliente(env).post(
        f"/accounting/period-close/monthly/{run_id}/apply-recurring",
        data={},
        follow_redirects=False,
    )

    assert response.status_code == 302
    with env.app.app_context():
        assert len(_aplicaciones(may_period_id, template_id)) == 1
        assert len(_aplicaciones(april_period_id, template_id)) == 1
        original = database.session.get(RecurringJournalApplication, application_id)
        current = _aplicaciones(may_period_id, template_id)[0]
        assert original is not None and original.status == "applied"
        assert current.status == "applied"
        assert current.journal_id != original.journal_id
        assert _ultimo_check(run_id).check_status == "passed"


def test_descubrimiento_conserva_aplicaciones_pendientes(entorno_contable_aislado):
    """El fallback recupera una aplicación pendiente en lugar de omitirla."""
    env = entorno_contable_aislado
    template_id = _plantilla(env, f"PENDING-{uuid4().hex[:6]}")
    run_id, period_id = _cierre(env)
    with env.app.app_context():
        admin = database.session.execute(select(User).filter_by(user="admin")).scalar_one()
        pending = apply_recurring_template(
            template_id,
            "FY2026",
            "Mayo 2026",
            date(2026, 5, 31),
            str(admin.id),
            company="cacao",
        )
        assert pending.status == "pending"
        journal_id = pending.journal_id
        assert journal_id is not None

    response = _cliente(env).post(
        f"/accounting/period-close/monthly/{run_id}/apply-recurring",
        data={},
        follow_redirects=False,
    )

    assert response.status_code == 302
    with env.app.app_context():
        applications = _aplicaciones(period_id, template_id)
        assert len(applications) == 1
        assert applications[0].status == "applied"
        assert applications[0].journal_id == journal_id
        journal = database.session.get(ComprobanteContable, journal_id)
        assert journal is not None and journal.status == "submitted"
        entries = list(
            database.session.execute(
                select(GLEntry).filter_by(
                    voucher_type="journal_entry",
                    voucher_id=journal_id,
                    is_cancelled=False,
                )
            )
            .scalars()
            .all()
        )
        assert len(entries) == 2
        assert _ultimo_check(run_id).check_status == "passed"
