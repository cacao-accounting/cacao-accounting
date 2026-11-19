# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""La revalorización histórica ignora corridas posteriores a su corte.

Escenario de negocio (issue #2120): ``_active_revaluation_balance`` sumaba
todas las corridas posted del documento/libro, incluso con fecha posterior al
``as_of_date`` del candidato, generando diferencias falsas en backfills.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from types import SimpleNamespace

from cacao_accounting.contabilidad.exchange_revaluation_service import ExchangeRevaluationService
from cacao_accounting.database import (
    Accounts,
    Book,
    ExchangeRevaluation,
    ExchangeRevaluationItem,
    GLEntry,
    database,
)


def _sembrar(application, run_date: date, document_no: str, account_id: str | None = None):
    with application.app_context():
        libro = (
            database.session.execute(
                database.select(Book).filter_by(entity="cacao").order_by(Book.is_primary.desc(), Book.code.asc())
            )
            .scalars()
            .first()
        )
        assert libro is not None
        if account_id is None:
            cuenta = Accounts(
                code=f"1101-{document_no}",
                name="Cuenta por cobrar",
                entity="cacao",
                group=False,
                active=True,
                enabled=True,
                account_type="receivable",
            )
            database.session.add(cuenta)
            database.session.flush()
        else:
            cuenta = database.session.get(Accounts, account_id)
        run = ExchangeRevaluation(
            company="cacao",
            status="posted",
            docstatus=1,
            run_date=run_date,
            month=run_date.month,
            year=run_date.year,
            currency="NIO",
            document_no=document_no,
        )
        database.session.add(run)
        database.session.flush()
        entry = GLEntry(
            posting_date=run_date,
            company="cacao",
            ledger_id=libro.id,
            account_id=cuenta.id,
            debit=Decimal("100"),
            credit=Decimal("0"),
            voucher_type="exchange_revaluation",
            voucher_id=document_no,
            is_cancelled=False,
        )
        database.session.add(entry)
        database.session.flush()
        database.session.add(
            ExchangeRevaluationItem(
                revaluation_id=run.id,
                reference_type="sales_invoice",
                reference_id="INV-1",
                source_document_type="sales_invoice",
                source_document_id="INV-1",
                account_id=cuenta.id,
                ledger_id=libro.id,
                open_amount_original=Decimal("100"),
                journal_line_id=entry.id,
            )
        )
        database.session.commit()
        return libro.id, cuenta.id


def test_el_saldo_solo_suma_corridas_hasta_el_corte(app):
    """Una corrida posterior al as_of_date no entra en el saldo previo."""
    libro_id, cuenta_id = _sembrar(app, date(2026, 9, 30), "REV-SEP")
    _sembrar(app, date(2026, 11, 30), "REV-NOV", account_id=cuenta_id)

    with app.app_context():
        libro = database.session.get(Book, libro_id)
        candidato = SimpleNamespace(
            source_document_type="sales_invoice",
            source_document_id="INV-1",
            account_id=cuenta_id,
            normal_balance="debit",
            open_amount_original=Decimal("100"),
            total_amount_original=Decimal("100"),
            as_of_date=date(2026, 10, 31),
        )
        saldo = ExchangeRevaluationService()._active_revaluation_balance(candidato, libro)

        assert saldo == Decimal("100.0000")


def test_reejecucion_historica_anula_tambien_la_corrida_posterior(app, monkeypatch):
    """Al volver a un período anterior no queda activa una corrida futura."""
    from cacao_accounting.database import ExchangeRevaluation

    _sembrar(app, date(2026, 9, 30), "REV-SEP-REV")
    _sembrar(app, date(2026, 11, 30), "REV-NOV-REV")
    llamadas: list[tuple[date, date]] = []

    with app.app_context():
        nuestros = set(
            database.session.execute(
                database.select(ExchangeRevaluation.id).where(
                    ExchangeRevaluation.document_no.in_(["REV-SEP-REV", "REV-NOV-REV"])
                )
            ).scalars()
        )

    def void_simulado(self, *, run_id, reversal_date, **_kwargs):
        run = database.session.get(ExchangeRevaluation, run_id)
        run.status = "voided"
        if run_id in nuestros:
            llamadas.append((run.run_date, reversal_date))

    monkeypatch.setattr(ExchangeRevaluationService, "void", void_simulado)
    with app.app_context():
        ExchangeRevaluationService()._reverse_prior_period_runs("cacao", date(2026, 9, 30), None)
        assert len(llamadas) == 2
        assert {fecha for fecha, _ in llamadas} == {date(2026, 9, 30), date(2026, 11, 30)}
        futura = next(item for item in llamadas if item[0] == date(2026, 11, 30))
        assert futura[1] >= futura[0]
        posted = (
            database.session.execute(
                database.select(ExchangeRevaluation).where(
                    ExchangeRevaluation.id.in_(nuestros),
                    ExchangeRevaluation.status == "posted",
                )
            )
            .scalars()
            .all()
        )
        assert posted == []
