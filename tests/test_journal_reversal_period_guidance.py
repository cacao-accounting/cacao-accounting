# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 William José Moreno Reyes

"""#761: la guía de reversión usa períodos contables reales."""

from __future__ import annotations

from datetime import date

from cacao_accounting.contabilidad.journal_service import create_journal_draft, submit_journal
from cacao_accounting.database import AccountingPeriod, User, database


def test_guia_de_reversion_distingue_periodos_personalizados_en_el_mismo_mes(entorno_contable_aislado):
    """Un corte fiscal dentro del mes se representa como dos períodos distintos en la vista."""
    entorno = entorno_contable_aislado
    app = entorno.app
    with app.app_context():
        original_period = database.session.execute(
            database.select(AccountingPeriod).where(
                AccountingPeriod.entity == "cacao",
                AccountingPeriod.start <= date(2026, 5, 10),
                AccountingPeriod.end >= date(2026, 5, 10),
            )
        ).scalar_one()
        original_period.end = date(2026, 5, 15)
        next_period = AccountingPeriod(
            entity="cacao",
            fiscal_year_id=original_period.fiscal_year_id,
            name="Mayo 16-31 2026",
            status="open",
            enabled=True,
            is_closed=False,
            start=date(2026, 5, 16),
            end=date(2026, 5, 31),
        )
        database.session.add(next_period)
        database.session.flush()
        actor = database.session.execute(database.select(User).filter_by(user="admin")).scalar_one()
        actor_id = str(actor.id)
        auth_version = actor.auth_version
        journal = create_journal_draft(
            {
                "company": "cacao",
                "posting_date": "2026-05-10",
                "reference": "REVERSAL-PERIOD-GUIDANCE",
                "transaction_currency": "NIO",
                "base_currency": "NIO",
                "exchange_rate": "1",
                "lines": [
                    {"order": 1, "account": "1101", "debit": "100", "credit": ""},
                    {"order": 2, "account": "4101", "debit": "", "credit": "100"},
                ],
            },
            user_id=actor_id,
            assign_identifier=False,
        )
        submit_journal(journal.id, user_id=actor_id)
        journal_id = str(journal.id)
        period_ids = {str(original_period.id), str(next_period.id)}

    client = app.test_client()
    with client.session_transaction() as session:
        session["_user_id"] = actor_id
        session["_auth_version"] = auth_version
        session["_fresh"] = True
    response = client.get(f"/accounting/journal/{journal_id}")

    assert response.status_code == 200
    page = response.get_data(as_text=True)
    assert "periodForDate" in page
    assert "selectedPeriod.id === originalPeriod.id" in page
    assert "slice(0, 7)" not in page
    assert all(period_id in page for period_id in period_ids)
    assert '"start": "2026-05-01"' in page
    assert '"end": "2026-05-15"' in page
    assert '"start": "2026-05-16"' in page
    assert '"end": "2026-05-31"' in page
