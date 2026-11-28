# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 William José Moreno Reyes

"""#1164: el borrador valida cada libro con la tasa efectiva del posting."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import select

from cacao_accounting.contabilidad.journal_service import JournalValidationError, create_journal_draft, submit_journal
from cacao_accounting.database import Accounts, Book, Currency, ExchangeRate, GLEntry, User, database

FECHA = date(2026, 5, 15)
EUR_BOOK = "EUR1164"


def _seed_rates(direct_nio_usd: str) -> str:
    """Configura libro EUR y tasas históricas directas del escenario."""
    for code, name in (("USD", "Dólar"), ("EUR", "Euro")):
        if database.session.execute(select(Currency).filter_by(code=code)).scalar_one_or_none() is None:
            database.session.add(Currency(code=code, name=name, decimals=2, active=True))
    database.session.flush()
    book = database.session.execute(select(Book).filter_by(code=EUR_BOOK)).scalar_one_or_none()
    if book is None:
        book = Book(entity="cacao", code=EUR_BOOK, name="Libro EUR 1164", currency="EUR", status="activo")
        database.session.add(book)
    for account in database.session.execute(select(Accounts).filter(Accounts.code.in_(["1101", "4101"]))).scalars():
        account.active = account.enabled = True
        account.group = False
    for origin, destination, rate in (
        ("USD", "NIO", "36"),
        ("USD", "EUR", "0.9"),
        ("NIO", "USD", direct_nio_usd),
    ):
        existing = database.session.execute(
            select(ExchangeRate).filter_by(origin=origin, destination=destination, date=FECHA)
        ).scalar_one_or_none()
        if existing is None:
            database.session.add(ExchangeRate(origin=origin, destination=destination, rate=Decimal(rate), date=FECHA))
        else:
            existing.rate = Decimal(rate)
    database.session.commit()
    return str(book.id)


def _payload() -> dict[str, object]:
    """Cabecera USD/base NIO con una línea en moneda base y tasa explícita ajena."""
    return {
        "company": "cacao",
        "posting_date": FECHA.isoformat(),
        "books": ["DEFAULT_BOOK", EUR_BOOK],
        "transaction_currency": "USD",
        "base_currency": "NIO",
        "exchange_rate": "36",
        "lines": [
            {"order": 1, "account": "1101", "debit": "36", "credit": "", "currency": "NIO", "exchange_rate": "999"},
            {"order": 2, "account": "4101", "debit": "", "credit": "1", "currency": "USD", "exchange_rate": "777"},
        ],
    }


def _admin_id() -> str:
    """Devuelve el administrador del entorno aislado."""
    return str(database.session.execute(select(User.id).filter_by(user="admin")).scalar_one())


def test_tasas_cruzadas_inconsistentes_rechazan_borrador(entorno_contable_aislado):
    """Una tasa directa incoherente con la cabecera no pasa solo por balancear NIO."""
    app = entorno_contable_aislado.app
    with app.app_context():
        _seed_rates("0.02")
        with pytest.raises(JournalValidationError, match="no esta balanceado por libro"):
            create_journal_draft(_payload(), user_id=_admin_id(), assign_identifier=False)


def test_tasas_consistentes_postean_gl_balanceado_en_dos_libros(entorno_contable_aislado):
    """Con tasas directas coherentes, el mismo asiento balancea NIO y EUR."""
    app = entorno_contable_aislado.app
    with app.app_context():
        eur_book_id = _seed_rates(str((Decimal("1") / Decimal("36")).quantize(Decimal("0.000000001"))))
        journal = create_journal_draft(_payload(), user_id=_admin_id(), assign_identifier=False)
        submit_journal(journal.id, user_id=_admin_id())
        entries = list(database.session.execute(select(GLEntry).filter_by(voucher_id=journal.id)).scalars().all())
        default_book_id = database.session.execute(select(Book.id).filter_by(code="DEFAULT_BOOK")).scalar_one()
        assert len(entries) == 4
        for book_id, expected in ((default_book_id, Decimal("36")), (eur_book_id, Decimal("0.9"))):
            book_entries = [entry for entry in entries if entry.ledger_id == book_id]
            assert len(book_entries) == 2
            assert sum((entry.debit for entry in book_entries), Decimal("0")) == expected
            assert sum((entry.credit for entry in book_entries), Decimal("0")) == expected
