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
    GLEntry,
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
    """Tras un fallo parcial, la válida queda en GL y la corregida pasa el check."""
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
        period_id = str(period.id)

    client = _cliente(env)
    primera = client.post(
        f"/accounting/period-close/monthly/{run_id}/apply-recurring",
        data={"template_ids": [bueno, malo]},
        follow_redirects=True,
    )
    assert primera.status_code == 200
    with env.app.app_context():
        aplicacion_buena = database.session.execute(
            database.select(RecurringJournalApplication).filter_by(template_id=bueno, status="applied")
        ).scalar_one()
        diario_bueno = database.session.get(ComprobanteContable, aplicacion_buena.journal_id)
        assert diario_bueno is not None and diario_bueno.status == "submitted"
        entradas_buenas = list(
            database.session.execute(
                database.select(GLEntry).filter_by(
                    voucher_type="journal_entry", voucher_id=diario_bueno.id, is_cancelled=False
                )
            )
            .scalars()
            .all()
        )
        assert len(entradas_buenas) == 2
        check = database.session.execute(
            database.select(PeriodCloseCheck).filter_by(close_run_id=run_id, check_type="apply_recurring_journals")
        ).scalar_one()
        assert check.check_status == "failed"

    pagina = client.get(f"/accounting/period-close/monthly/{run_id}")
    assert pagina.status_code == 200
    cuerpo = pagina.get_data(as_text=True)
    assert "Aplicada" in cuerpo.split("RETRY-OK")[1].split("</tr>")[0]
    ids_reintento = _ids_en_formulario(cuerpo)
    assert bueno not in ids_reintento, "la aplicación completada no debe reenviarse"
    assert malo in ids_reintento, "la plantilla fallida debe permanecer disponible"

    with env.app.app_context():
        database.session.add_all(
            [
                RecurringJournalItem(
                    template_id=malo,
                    account_code="5101",
                    debit=Decimal("100"),
                    credit=Decimal("0"),
                    description="debito corregido",
                ),
                RecurringJournalItem(
                    template_id=malo,
                    account_code="1101",
                    debit=Decimal("0"),
                    credit=Decimal("100"),
                    description="credito corregido",
                ),
            ]
        )
        database.session.commit()

    reintento = client.post(
        f"/accounting/period-close/monthly/{run_id}/apply-recurring",
        data={"template_ids": [malo]},
        follow_redirects=True,
    )
    assert reintento.status_code == 200
    with env.app.app_context():
        aplicaciones = list(
            database.session.execute(
                database.select(RecurringJournalApplication).filter_by(company="cacao", accounting_period_id=period_id)
            )
            .scalars()
            .all()
        )
        assert len(aplicaciones) == 2
        assert all(aplicacion.status == "applied" for aplicacion in aplicaciones)
        aplicacion_mala = next(aplicacion for aplicacion in aplicaciones if aplicacion.template_id == malo)
        diario_malo = database.session.get(ComprobanteContable, aplicacion_mala.journal_id)
        assert diario_malo is not None and diario_malo.status == "submitted"
        entradas_malas = list(
            database.session.execute(
                database.select(GLEntry).filter_by(voucher_type="journal_entry", voucher_id=diario_malo.id, is_cancelled=False)
            )
            .scalars()
            .all()
        )
        assert len(entradas_malas) == 2
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


def test_primer_lote_valido_contabiliza_y_aprueba_check(entorno_contable_aislado):
    """#1776: el primer intento válido no deja comprobantes en borrador."""
    env = entorno_contable_aislado
    plantilla = _plantilla(env, "FIRST-OK", con_lineas=True)
    with env.app.app_context():
        period = database.session.execute(
            database.select(AccountingPeriod).filter_by(entity="cacao", name="Mayo 2026")
        ).scalar_one()
        run = PeriodCloseRun(company="cacao", period_id=period.id, run_status="open")
        database.session.add(run)
        database.session.commit()
        run_id = str(run.id)
        period_id = str(period.id)

    client = _cliente(env)
    for _intento in range(2):
        respuesta = client.post(
            f"/accounting/period-close/monthly/{run_id}/apply-recurring",
            data={"template_ids": [plantilla]},
            follow_redirects=True,
        )
        assert respuesta.status_code == 200
        with env.app.app_context():
            aplicaciones = list(
                database.session.execute(
                    database.select(RecurringJournalApplication).filter_by(
                        company="cacao", accounting_period_id=period_id, template_id=plantilla
                    )
                )
                .scalars()
                .all()
            )
            assert len(aplicaciones) == 1
            aplicacion = aplicaciones[0]
            assert aplicacion.status == "applied"
            diario = database.session.get(ComprobanteContable, aplicacion.journal_id)
            assert diario is not None and diario.status == "submitted"
            entradas = list(
                database.session.execute(
                    database.select(GLEntry).filter_by(voucher_type="journal_entry", voucher_id=diario.id, is_cancelled=False)
                )
                .scalars()
                .all()
            )
            assert len(entradas) == 2
            assert sum(entry.debit for entry in entradas) == sum(entry.credit for entry in entradas) == Decimal("100")
            check = database.session.execute(
                database.select(PeriodCloseCheck)
                .filter_by(close_run_id=run_id, check_type="apply_recurring_journals")
                .order_by(PeriodCloseCheck.created.desc(), PeriodCloseCheck.id.desc())
                .limit(1)
            ).scalar_one()
            assert check.check_status == "passed"
