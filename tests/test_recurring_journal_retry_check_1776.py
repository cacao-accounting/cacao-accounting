# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1776: el reintento mensual recupera aplicaciones pendientes y cierra el check."""

from __future__ import annotations

import re
from datetime import date
from decimal import Decimal

from cacao_accounting.database import (
    AccountingPeriod,
    Book,
    ComprobanteContable,
    PeriodCloseCheck,
    PeriodCloseRun,
    RecurringJournalApplication,
    User,
    RecurringJournalItem,
    RecurringJournalTemplate,
    database,
)


def _plantilla(env, code: str, *, con_lineas: bool) -> str:
    """Crea una plantilla aprobada, balanceada o sin líneas."""
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
        if con_lineas:
            database.session.add_all(
                [
                    RecurringJournalItem(
                        template_id=template.id,
                        account_code="5101",
                        debit=Decimal("100"),
                        credit=Decimal("0"),
                        description="debito",
                    ),
                    RecurringJournalItem(
                        template_id=template.id,
                        account_code="1101",
                        debit=Decimal("0"),
                        credit=Decimal("100"),
                        description="credito",
                    ),
                ]
            )
        database.session.commit()
        return str(template.id)


def _cliente(env):
    """Cliente autenticado como administrador de la app aislada."""
    client = env.app.test_client()
    with env.app.app_context():
        admin_id = database.session.execute(database.select(User).filter_by(user="admin")).scalar_one().id
    with client.session_transaction() as session:
        session["_user_id"] = str(admin_id)
        session["_fresh"] = True
    return client


def _ids_en_formulario(html: str) -> list[str]:
    """Lee los template_ids que el asistente envía en el reintento."""
    return re.findall(r'name="template_ids" value="([^"]+)"', html)


def test_falla_reintento_y_check(entorno_contable_aislado):
    """Tras un fallo parcial, el reintento recupera la pendiente y el check pasa."""
    env = entorno_contable_aislado
    bueno = _plantilla(env, "RETRY-OK", con_lineas=True)
    malo = _plantilla(env, "RETRY-BAD", con_lineas=False)
    with env.app.app_context():
        period = database.session.execute(
            database.select(AccountingPeriod).filter_by(entity="cacao", name="Mayo 2026")
        ).scalar_one()
        run = PeriodCloseRun(company="cacao", period_id=period.id, run_status="open")
        database.session.add(run)
        database.session.commit()
        run_id = str(run.id)

    client = _cliente(env)
    primera = client.post(
        f"/accounting/period-close/monthly/{run_id}/apply-recurring",
        data={"template_ids": [bueno, malo]},
        follow_redirects=True,
    )
    assert primera.status_code == 200
    with env.app.app_context():
        pendiente = database.session.execute(
            database.select(RecurringJournalApplication).filter_by(template_id=bueno, status="pending")
        ).scalar_one()
        diario = database.session.get(ComprobanteContable, pendiente.journal_id)
        assert diario is not None and diario.status == "draft"
        check = database.session.execute(
            database.select(PeriodCloseCheck).filter_by(close_run_id=run_id, check_type="apply_recurring_journals")
        ).scalar_one()
        assert check.check_status == "failed"

    pagina = client.get(f"/accounting/period-close/monthly/{run_id}")
    assert pagina.status_code == 200
    cuerpo = pagina.get_data(as_text=True)
    assert "Aplicada" not in cuerpo.split("RETRY-OK")[1].split("</tr>")[0]
    assert "text-bg-info" in cuerpo, "la aplicación recuperable debe distinguirse de la completada"
    assert bueno in _ids_en_formulario(cuerpo), "la pendiente debe reenviarse en el reintento"

    with env.app.app_context():
        database.session.get(RecurringJournalTemplate, malo).is_completed = True
        database.session.commit()

    reintento = client.post(
        f"/accounting/period-close/monthly/{run_id}/apply-recurring",
        data={"template_ids": [bueno]},
        follow_redirects=True,
    )
    assert reintento.status_code == 200
    with env.app.app_context():
        aplicacion = database.session.execute(
            database.select(RecurringJournalApplication).filter_by(template_id=bueno)
        ).scalar_one()
        assert aplicacion.status == "applied"
        diario = database.session.get(ComprobanteContable, aplicacion.journal_id)
        assert diario is not None and diario.status == "submitted"
        checks = (
            database.session.execute(
                database.select(PeriodCloseCheck)
                .filter_by(close_run_id=run_id, check_type="apply_recurring_journals")
                .order_by(PeriodCloseCheck.created)
            )
            .scalars()
            .all()
        )
        assert checks[-1].check_status == "passed"
