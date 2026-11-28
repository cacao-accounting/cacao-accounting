# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 William José Moreno Reyes

"""#1672: una reversión histórica puede usar una cuenta ya desactivada."""

from __future__ import annotations

from copy import deepcopy
from datetime import date
from uuid import uuid4

import pytest
from sqlalchemy import select

from cacao_accounting.contabilidad.journal_service import (
    JOURNAL_STATUS_SUBMITTED,
    JournalValidationError,
    create_journal_draft,
    duplicate_journal_as_reversal_draft,
    serialize_journal_for_form,
    submit_journal,
    update_journal_draft,
)
from cacao_accounting.database import (
    AccountingPeriod,
    Accounts,
    ComprobanteContable,
    ComprobanteContableDetalle,
    Currency,
    GLEntry,
    User,
    database,
)


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
            {"order": 1, "account": "1101", "debit": "100", "credit": "", "currency": "USD"},
            {"order": 2, "account": "4101", "debit": "", "credit": "3650", "currency": "NIO"},
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
    """A reversal can use the original inactive account and currency."""
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
        moneda_usd = database.session.execute(select(Currency).where(Currency.code == "USD")).scalar_one()
        moneda_usd.active = False
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


def test_edicion_reversa_rechaza_otra_moneda_inactiva_y_conserva_borrador(entorno_contable_aislado):
    """La excepción histórica solo admite la moneda exacta de la línea fuente."""
    app = entorno_contable_aislado.app
    with app.app_context():
        _periodo_junio()
        actor_id = database.session.execute(select(User.id).filter_by(user="admin")).scalar_one()
        original = create_journal_draft(_payload(), user_id=actor_id, assign_identifier=False)
        submit_journal(original.id, user_id=actor_id)
        usd = database.session.execute(select(Currency).where(Currency.code == "USD")).scalar_one()
        eur = database.session.execute(select(Currency).where(Currency.code == "EUR")).scalar_one_or_none()
        if eur is None:
            eur = Currency(code="EUR", name="Euro", decimals=2, active=True, default=False)
            database.session.add(eur)
        usd.active = False
        eur.active = False
        database.session.commit()

        reversal = duplicate_journal_as_reversal_draft(
            original.id,
            user_id=actor_id,
            reversal_date_raw=date(2026, 6, 15),
            reason="Corrección de período",
        )
        before = serialize_journal_for_form(reversal)
        edited = deepcopy(before)
        edited["lines"][0]["currency"] = "EUR"
        edited["lines"][0]["exchange_rate"] = "40"

        with pytest.raises(JournalValidationError, match="moneda debe coincidir"):
            update_journal_draft(reversal.id, edited, actor_id)

        database.session.expire_all()
        persisted = database.session.get(ComprobanteContable, reversal.id)
        assert persisted is not None
        assert serialize_journal_for_form(persisted) == before
        assert (
            database.session.execute(select(GLEntry.id).where(GLEntry.voucher_id == reversal.id)).scalar_one_or_none() is None
        )

        valid = deepcopy(before)
        valid["memo"] = "Reversión histórica con moneda fuente inactiva"
        actualizada = update_journal_draft(reversal.id, valid, actor_id)
        database.session.refresh(actualizada)
        assert actualizada.memo == valid["memo"]
        monedas = database.session.execute(
            select(ComprobanteContableDetalle.currency_id)
            .filter_by(transaction_id=reversal.id)
            .order_by(ComprobanteContableDetalle.order)
        ).scalars()
        assert list(monedas) == ["USD", "NIO"]


def test_edicion_reversa_legacy_usa_moneda_de_cabecera(entorno_contable_aislado):
    """Una línea fuente sin currency_id conserva la moneda efectiva de la cabecera."""
    app = entorno_contable_aislado.app
    with app.app_context():
        _periodo_junio()
        actor_id = database.session.execute(select(User.id).filter_by(user="admin")).scalar_one()
        payload = _payload()
        payload["transaction_currency"] = "USD"
        payload["exchange_rate"] = "36.5"
        payload["lines"][1]["currency"] = "USD"
        payload["lines"][1]["credit"] = "100"
        original = create_journal_draft(payload, user_id=actor_id, assign_identifier=False)
        submit_journal(original.id, user_id=actor_id)
        source_line = database.session.execute(
            select(ComprobanteContableDetalle).filter_by(transaction_id=original.id, order=1)
        ).scalar_one()
        source_line.currency_id = None
        database.session.commit()

        reversal = duplicate_journal_as_reversal_draft(
            original.id,
            user_id=actor_id,
            reversal_date_raw=date(2026, 6, 15),
            reason="Compatibilidad histórica",
        )
        payload = serialize_journal_for_form(reversal)
        payload["memo"] = "Edición legacy sin cambio de moneda"

        actualizada = update_journal_draft(reversal.id, payload, actor_id)

        assert actualizada.memo == payload["memo"]
        monedas = database.session.execute(
            select(ComprobanteContableDetalle.currency_id)
            .filter_by(transaction_id=reversal.id)
            .order_by(ComprobanteContableDetalle.order)
        ).scalars()
        assert list(monedas) == ["USD", "USD"]
