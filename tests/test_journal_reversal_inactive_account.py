# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 William José Moreno Reyes

"""#1672: una reversión histórica puede usar una cuenta ya desactivada."""

from __future__ import annotations

from datetime import date
from uuid import uuid4

from sqlalchemy import select

from cacao_accounting.contabilidad.journal_service import (
    JOURNAL_STATUS_SUBMITTED,
    create_journal_draft,
    duplicate_journal_as_reversal_draft,
    submit_journal,
)
from cacao_accounting.database import AccountingPeriod, Accounts, ComprobanteContable, GLEntry, User, database


def _periodo_junio() -> None:
    """Abre el período donde se registra la reversión."""
    if database.session.get(AccountingPeriod, "P2026-06") is None:
        database.session.add(
            AccountingPeriod(
                id="P2026-06",
                entity="cacao",
                fiscal_year_id="FY2026",
                name="Junio 2026",
                start=date(2026, 6, 1),
                end=date(2026, 6, 30),
                enabled=True,
                is_closed=False,
            )
        )
        database.session.commit()


def _payload() -> dict[str, object]:
    """Comprobante original balanceado del escenario."""
    return {
        "company": "cacao",
        "posting_date": "2026-05-15",
        "reference": f"REV-INACTIVA-{uuid4().hex[:8]}",
        "transaction_currency": "NIO",
        "base_currency": "NIO",
        "exchange_rate": "1",
        "lines": [
            {"order": 1, "account": "1101", "debit": "100", "credit": ""},
            {"order": 2, "account": "4101", "debit": "", "credit": "100"},
        ],
    }


def _gl(journal_id: str) -> list[tuple[str, str, object, object, bool]]:
    """Filas GL relevantes para comparar el original antes y después."""
    return [
        (entry.id, str(entry.account_id), entry.debit, entry.credit, bool(entry.is_cancelled))
        for entry in database.session.execute(
            database.select(GLEntry).where(GLEntry.voucher_id == journal_id).order_by(GLEntry.id)
        ).scalars()
    ]


def test_reversion_historica_permite_cuenta_desactivada(entorno_contable_aislado):
    """La reversa se crea y postea sin alterar el asiento original."""
    app = entorno_contable_aislado.app
    with app.app_context():
        _periodo_junio()
        actor_id = database.session.execute(select(User.id).filter_by(user="admin")).scalar_one()
        original = create_journal_draft(_payload(), user_id=actor_id, assign_identifier=False)
        submit_journal(original.id, user_id=actor_id)
        original_gl = _gl(original.id)
        assert original_gl
        cuentas = {
            cuenta.code: cuenta.id
            for cuenta in database.session.execute(
                database.select(Accounts).where(Accounts.entity == "cacao", Accounts.code.in_(["1101", "4101"]))
            ).scalars()
        }

        cuenta = database.session.get(Accounts, cuentas["1101"])
        cuenta.active = False
        database.session.commit()

        reversa = duplicate_journal_as_reversal_draft(
            original.id,
            user_id=actor_id,
            reversal_date_raw=date(2026, 6, 15),
            reason="Corrección de período",
        )
        assert reversa.reversal_of == original.id
        assert reversa.status != JOURNAL_STATUS_SUBMITTED

        submit_journal(reversa.id, user_id=actor_id)
        database.session.refresh(reversa)
        assert reversa.status == JOURNAL_STATUS_SUBMITTED
        reversa_gl = _gl(reversa.id)
        assert len(reversa_gl) == len(original_gl)
        assert {entry[1] for entry in reversa_gl} == set(cuentas.values())
        assert _gl(original.id) == original_gl
        assert database.session.get(ComprobanteContable, original.id).status == JOURNAL_STATUS_SUBMITTED
