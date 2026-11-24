# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1672: ninguna cuenta inactiva recibe movimientos nuevos.

El importador hace un prechequeo, pero la cuenta puede cambiar de estado entre
la validación y el posteo. Estas regresiones cubren el servicio contable que
crea el borrador y la operación final que genera las líneas GL.
"""

from __future__ import annotations

from uuid import uuid4

import pytest
from sqlalchemy import select

from cacao_accounting.contabilidad.journal_service import (
    JournalValidationError,
    create_journal_draft,
    submit_journal,
)
from cacao_accounting.contabilidad.posting_service import PostingError
from cacao_accounting.database import Accounts, GLEntry, User, database


@pytest.fixture(autouse=True)
def cuentas_operativas(app, entorno_contable):
    """Asegura cuentas hoja activas y restaura su estado al terminar."""
    del entorno_contable
    with app.app_context():
        cuentas = list(
            database.session.execute(
                select(Accounts).where(Accounts.entity == "cacao", Accounts.code.in_(["1101", "4101"]))
            ).scalars()
        )
        estado = [(cuenta.id, cuenta.active, cuenta.enabled) for cuenta in cuentas]
        for cuenta in cuentas:
            cuenta.active = True
            cuenta.enabled = True
        database.session.commit()
    yield
    with app.app_context():
        for cuenta_id, activa, habilitada in estado:
            cuenta = database.session.get(Accounts, cuenta_id)
            if cuenta is not None:
                cuenta.active = activa
                cuenta.enabled = habilitada
        database.session.commit()


def _payload() -> dict[str, object]:
    """Comprobante balanceado en moneda local con las cuentas del escenario."""
    return {
        "company": "cacao",
        "posting_date": "2026-05-15",
        "reference": f"CUENTA-ESTADO-{uuid4().hex[:8]}",
        "transaction_currency": "NIO",
        "base_currency": "NIO",
        "exchange_rate": "1",
        "lines": [
            {"order": 1, "account": "1101", "debit": "100", "credit": ""},
            {"order": 2, "account": "4101", "debit": "", "credit": "100"},
        ],
    }


def _actor_id() -> str:
    """Usuario administrador del entorno contable."""
    return database.session.execute(select(User.id).where(User.user == "admin")).scalar_one()


@pytest.mark.parametrize("field", ["active", "enabled"])
def test_borrador_rechaza_cuenta_inactiva_o_deshabilitada(app, entorno_contable, field):
    """Una cuenta desactivada no puede incorporarse a un borrador nuevo."""
    del entorno_contable
    with app.app_context():
        cuenta = database.session.execute(select(Accounts).filter_by(entity="cacao", code="1101")).scalar_one()
        anterior = getattr(cuenta, field)
        try:
            setattr(cuenta, field, False)
            database.session.flush()

            with pytest.raises(JournalValidationError, match="activa, habilitada"):
                create_journal_draft(_payload(), user_id=_actor_id(), assign_identifier=False)
        finally:
            setattr(cuenta, field, anterior)
            database.session.rollback()


def test_posteo_revalida_la_cuenta_despues_de_crear_el_borrador(app, entorno_contable):
    """Desactivar la cuenta entre borrador y posteo bloquea el asiento completo."""
    del entorno_contable
    with app.app_context():
        actor_id = _actor_id()
        journal = create_journal_draft(_payload(), user_id=actor_id, assign_identifier=False)
        journal_id = journal.id
        cuenta = database.session.execute(select(Accounts).filter_by(entity="cacao", code="1101")).scalar_one()
        anterior = cuenta.active
        try:
            cuenta.active = False
            database.session.flush()

            with pytest.raises((JournalValidationError, PostingError), match="activa, habilitada"):
                submit_journal(journal_id, user_id=actor_id)
        finally:
            cuenta.active = anterior
            database.session.rollback()

        assert database.session.execute(select(GLEntry).where(GLEntry.voucher_id == journal_id)).scalars().all() == []
