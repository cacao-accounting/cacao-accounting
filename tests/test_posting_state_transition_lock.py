# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William Jose Moreno Reyes

"""Pruebas de regresión del bloqueo de documentos antes de transiciones de estado.

Cubre el fix ``fix(posting): lock documents before state transitions``:
``submit_document`` y ``cancel_document`` deben bloquear (``SELECT ... FOR
UPDATE``) y refrescar la fila persistida del documento ANTES de validar su
``docstatus``, de modo que dos procesos concurrentes no puedan aprobar ni
anular el mismo documento dos veces.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from cacao_accounting import create_app
from cacao_accounting.config import configuracion


@pytest.fixture()
def app_ctx():
    """Aplicación Flask aislada con compañía y libro primario."""
    app = create_app(
        {
            **configuracion,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
            "WTF_CSRF_ENABLED": False,
            "TESTING": True,
        }
    )
    with app.app_context():
        from cacao_accounting.database import Book, Entity, database

        database.create_all()
        database.session.add_all(
            [
                Entity(code="cacao", name="Cacao", company_name="Cacao", tax_id="J0001", currency="NIO"),
                Book(code="PRIMARY", name="Libro principal", entity="cacao", currency="NIO", is_primary=True),
            ]
        )
        database.session.commit()
        yield app


def _persist_invoice(docstatus: int):
    """Persiste una factura de venta simple con el docstatus indicado."""
    from cacao_accounting.database import SalesInvoice, database

    invoice = SalesInvoice(company="cacao", posting_date=date(2026, 5, 4), customer_id="UNKNOWN", docstatus=docstatus)
    database.session.add(invoice)
    database.session.commit()
    return invoice


def _record_execute(monkeypatch):
    """Intercepta ``session.execute`` registrando los SELECT emitidos."""
    from cacao_accounting.database import database

    statements: list[str] = []
    original_execute = database.session.execute

    def recording_execute(statement, *args, **kwargs):
        statements.append(str(statement))
        return original_execute(statement, *args, **kwargs)

    monkeypatch.setattr(database.session, "execute", recording_execute)
    return statements


def _locked_sales_invoice_selects(statements) -> list[str]:
    from cacao_accounting.database import SalesInvoice

    return [s for s in statements if "FOR UPDATE" in s.upper() and SalesInvoice.__tablename__ in s]


def test_lock_requires_persisted_document(app_ctx):
    """Un documento sin id persistido no puede cambiar de estado."""
    from cacao_accounting.contabilidad.posting_service import PostingError, _lock_document_for_transition
    from cacao_accounting.database import SalesInvoice

    draft = SalesInvoice(company="cacao", posting_date=date(2026, 5, 4), customer_id="UNKNOWN")
    with pytest.raises(PostingError, match="persistido"):
        _lock_document_for_transition(draft)


def test_lock_rejects_document_missing_in_database(app_ctx):
    """Si la fila fue eliminada por otro proceso, la transición se rechaza."""
    from cacao_accounting.contabilidad.posting_service import PostingError, _lock_document_for_transition
    from cacao_accounting.database import database

    invoice = _persist_invoice(docstatus=0)
    database.session.delete(invoice)
    database.session.commit()

    with pytest.raises(PostingError, match="no existe"):
        _lock_document_for_transition(invoice)


def test_lock_returns_fresh_instance_of_same_model(app_ctx):
    """El lock relee la fila por id y devuelve una instancia adjunta a la sesión."""
    from cacao_accounting.contabilidad.posting_service import _lock_document_for_transition

    invoice = _persist_invoice(docstatus=0)
    locked = _lock_document_for_transition(invoice)
    assert type(locked) is type(invoice)
    assert locked.id == invoice.id


def test_submit_document_locks_row_before_state_validation(app_ctx, monkeypatch):
    """El bloqueo ocurre antes de validar el docstatus en submit."""
    from cacao_accounting.contabilidad.posting import PostingError, submit_document
    from cacao_accounting.database import SalesInvoice, database

    invoice = _persist_invoice(docstatus=1)
    statements = _record_execute(monkeypatch)

    with pytest.raises(PostingError, match="Solo se puede aprobar un documento en borrador"):
        submit_document(invoice)
    database.session.rollback()

    locked = _locked_sales_invoice_selects(statements)
    assert locked, "submit_document debe emitir SELECT ... FOR UPDATE sobre el documento"
    # El lock precede a cualquier otra consulta contra la tabla del documento.
    table = SalesInvoice.__tablename__
    first_invoice_query = next(s for s in statements if table in s)
    assert "FOR UPDATE" in first_invoice_query.upper()


def test_cancel_document_locks_row_before_state_validation(app_ctx, monkeypatch):
    """El bloqueo ocurre antes de validar el docstatus en cancel."""
    from cacao_accounting.contabilidad.posting import PostingError, cancel_document
    from cacao_accounting.database import database

    invoice = _persist_invoice(docstatus=0)
    statements = _record_execute(monkeypatch)

    with pytest.raises(PostingError, match="Solo se puede cancelar un documento aprobado"):
        cancel_document(invoice)
    database.session.rollback()

    assert _locked_sales_invoice_selects(statements), "cancel_document debe emitir SELECT ... FOR UPDATE sobre el documento"


def test_submit_and_cancel_roundtrip_operates_on_locked_row(app_ctx):
    """Aprobar y anular un comprobante funciona sobre la fila bloqueada."""
    from cacao_accounting.contabilidad.posting import cancel_document, submit_document
    from cacao_accounting.database import (
        Accounts,
        ComprobanteContable,
        ComprobanteContableDetalle,
        GLEntry,
        database,
    )

    bank_account = Accounts(
        entity="cacao",
        code="BANK-LCK",
        name="Banco prueba",
        active=True,
        enabled=True,
        classification="asset",
        account_type="bank",
    )
    income_account = Accounts(
        entity="cacao",
        code="INC-LCK",
        name="Ingresos prueba",
        active=True,
        enabled=True,
        classification="income",
        account_type="income",
    )
    database.session.add_all([bank_account, income_account])
    database.session.flush()

    journal = ComprobanteContable(entity="cacao", date=date(2026, 5, 4), memo="Roundtrip con lock")
    database.session.add(journal)
    database.session.flush()
    database.session.add_all(
        [
            ComprobanteContableDetalle(
                entity="cacao",
                account=bank_account.code,
                date=journal.date,
                transaction="journal_entry",
                transaction_id=journal.id,
                value=Decimal("100.00"),
                memo="Débito banco",
            ),
            ComprobanteContableDetalle(
                entity="cacao",
                account=income_account.code,
                date=journal.date,
                transaction="journal_entry",
                transaction_id=journal.id,
                value=Decimal("-100.00"),
                memo="Crédito ingreso",
            ),
        ]
    )
    database.session.commit()

    entries = submit_document(journal)
    database.session.commit()
    assert len(entries) == 2
    assert journal.docstatus == 1

    reversals = cancel_document(journal)
    database.session.commit()
    assert len(reversals) == 2
    database.session.expire(journal)
    assert journal.docstatus == 2

    all_entries = (
        database.session.execute(database.select(GLEntry).filter_by(voucher_type="journal_entry", voucher_id=journal.id))
        .scalars()
        .all()
    )
    assert sum(entry.debit for entry in all_entries) == sum(entry.credit for entry in all_entries)


def test_double_submit_rejected_after_lock(app_ctx):
    """Reaprobar un documento ya aprobado falla aunque la sesión esté expirada."""
    from cacao_accounting.contabilidad.posting import PostingError, submit_document
    from cacao_accounting.database import Accounts, ComprobanteContable, ComprobanteContableDetalle, database

    bank_account = Accounts(
        entity="cacao",
        code="BANK-DUP",
        name="Banco duplicado",
        active=True,
        enabled=True,
        classification="asset",
        account_type="bank",
    )
    income_account = Accounts(
        entity="cacao",
        code="INC-DUP",
        name="Ingresos duplicado",
        active=True,
        enabled=True,
        classification="income",
        account_type="income",
    )
    database.session.add_all([bank_account, income_account])
    database.session.flush()

    journal = ComprobanteContable(entity="cacao", date=date(2026, 5, 4), memo="Doble aprobación")
    database.session.add(journal)
    database.session.flush()
    database.session.add_all(
        [
            ComprobanteContableDetalle(
                entity="cacao",
                account=bank_account.code,
                date=journal.date,
                transaction="journal_entry",
                transaction_id=journal.id,
                value=Decimal("50.00"),
            ),
            ComprobanteContableDetalle(
                entity="cacao",
                account=income_account.code,
                date=journal.date,
                transaction="journal_entry",
                transaction_id=journal.id,
                value=Decimal("-50.00"),
            ),
        ]
    )
    database.session.commit()

    submit_document(journal)
    database.session.commit()
    database.session.expire_all()

    with pytest.raises(PostingError, match="Solo se puede aprobar un documento en borrador"):
        submit_document(journal)
