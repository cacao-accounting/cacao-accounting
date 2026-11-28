# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1316: anular un diario no puede dejar una conciliación apuntando a su GL.

La partida bancaria apunta a la línea GL; si esa línea se cancela, el
movimiento seguiría consumido. La anulación debe bloquearse mientras la
asignación siga activa.
"""

from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import select

from cacao_accounting.contabilidad.cancellation_service import active_cancellation_dependencies
from cacao_accounting.contabilidad.journal_service import (
    JournalValidationError,
    cancel_submitted_journal,
    create_journal_draft,
    submit_journal,
)
from cacao_accounting.database import (
    Bank,
    BankAccount,
    BankTransaction,
    GLEntry,
    Reconciliation,
    ReconciliationItem,
    User,
    database,
)

FECHA = date(2026, 5, 15)


def _journal() -> str:
    """Crea y postea un diario con una línea GL en la cuenta de caja."""
    actor_id = str(database.session.execute(select(User.id).filter_by(user="admin")).scalar_one())
    journal = create_journal_draft(
        {
            "company": "cacao",
            "posting_date": "2026-05-15",
            "books": ["DEFAULT_BOOK"],
            "transaction_currency": "NIO",
            "lines": [
                {"order": 1, "account": "1101", "debit": "100", "credit": ""},
                {"order": 2, "account": "4101", "debit": "", "credit": "100"},
            ],
        },
        user_id=actor_id,
        assign_identifier=False,
    )
    submit_journal(journal.id, user_id=actor_id)
    return str(journal.id)


def _reconciliation(journal_id: str, *, status: str = "reconciled") -> str:
    """Crea el movimiento bancario y su partida contra la línea GL del diario."""
    gl_entry = (
        database.session.execute(select(GLEntry).where(GLEntry.voucher_id == journal_id).order_by(GLEntry.id))
        .scalars()
        .first()
    )
    bank = Bank(name="Banco 1316", is_active=True)
    database.session.add(bank)
    database.session.flush()
    account = BankAccount(
        bank_id=bank.id,
        company="cacao",
        account_name="Cuenta 1316",
        account_no="ACC-1316",
        currency="NIO",
    )
    database.session.add(account)
    database.session.flush()
    transaction = BankTransaction(
        identity_key="BANK-1316",
        bank_account_id=account.id,
        posting_date=FECHA,
        deposit=Decimal("100"),
        is_reconciled=True,
    )
    database.session.add(transaction)
    database.session.flush()
    reconciliation = Reconciliation(company="cacao", recon_date=FECHA, recon_type="bank")
    database.session.add(reconciliation)
    database.session.flush()
    item = ReconciliationItem(
        reconciliation_id=reconciliation.id,
        reference_type="bank_transaction",
        reference_id=transaction.id,
        amount=Decimal("100"),
        allocated_amount=Decimal("100"),
        reconciliation_date=FECHA,
        status=status,
        source_type="bank_transaction",
        source_id=transaction.id,
        target_type="gl_entry",
        target_id=str(gl_entry.id),
        company="cacao",
        bank_account_id=account.id,
        currency="NIO",
        direction="deposit",
    )
    database.session.add(item)
    database.session.commit()
    return str(item.id)


def test_dependencia_detecta_conciliacion_contra_linea_gl(entorno_contable_aislado):
    """La dependencia aparece para el diario aunque el destino sea la línea GL."""
    from cacao_accounting.database import ComprobanteContable

    app = entorno_contable_aislado.app
    with app.app_context():
        journal_id = _journal()
        _reconciliation(journal_id)
        journal = database.session.get(ComprobanteContable, journal_id)

        dependencies = active_cancellation_dependencies(journal, "journal_entry", journal_id)

        assert [(dependency.kind, dependency.detail) for dependency in dependencies] == [
            ("conciliacion bancaria", "reconciliation_item")
        ]


def test_dependencia_ignora_partidas_canceladas(entorno_contable_aislado):
    """Una partida cancelada no bloquea la anulación."""
    from cacao_accounting.database import ComprobanteContable

    app = entorno_contable_aislado.app
    with app.app_context():
        journal_id = _journal()
        _reconciliation(journal_id, status="cancelled")
        journal = database.session.get(ComprobanteContable, journal_id)

        assert not active_cancellation_dependencies(journal, "journal_entry", journal_id)


def test_anulacion_del_diario_se_bloquea_con_conciliacion_activa(entorno_contable_aislado):
    """cancel_submitted_journal rechaza y conserva el GL activo."""
    app = entorno_contable_aislado.app
    with app.app_context():
        journal_id = _journal()
        _reconciliation(journal_id)
        actor_id = str(database.session.execute(select(User.id).filter_by(user="admin")).scalar_one())

        with pytest.raises(JournalValidationError, match="efectos activos"):
            cancel_submitted_journal(journal_id, user_id=actor_id, reason="Prueba de bloqueo")

        active = (
            database.session.execute(
                select(GLEntry.id).where(GLEntry.voucher_id == journal_id, GLEntry.is_cancelled.is_(False))
            )
            .scalars()
            .all()
        )
        assert active
