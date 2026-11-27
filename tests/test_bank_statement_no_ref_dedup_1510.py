# SPDX-License-Identifier: Apache-2.0
"""#1510: movimientos sin referencia no se deduplican por fecha+importe."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from cacao_accounting.database import Bank, BankAccount, BankTransaction, Currency, Entity, database
from cacao_accounting.imports.adapters.bank_statement import BankStatementAdapter


def test_bank_statement_without_reference_allows_same_day_amount(app):
    with app.app_context():
        if database.session.execute(database.select(Currency).filter_by(code="NIO")).scalar_one_or_none() is None:
            database.session.add(Currency(code="NIO", name="Cordoba", decimals=2, active=True, default=False))
        database.session.add(
            Entity(code="E1", company_name="E1", name="E1", tax_id="J0310000000001", currency="NIO", enabled=True)
        )
        bank = Bank(name="Banco")
        database.session.add(bank)
        database.session.flush()
        database.session.add(
            BankAccount(id="ba1", company="E1", bank_id=bank.id, account_name="A", account_no="1", currency="NIO")
        )
        database.session.commit()

        adapter = BankStatementAdapter()
        doc = [
            {
                "bank_account_id": "ba1",
                "company_id": "E1",
                "posting_date": date(2026, 1, 1),
                "reference_number": "",
                "description": "fee1",
                "deposit": None,
                "withdrawal": Decimal("50.0000"),
                "import_discriminator": "fp:1",
            },
            {
                "bank_account_id": "ba1",
                "company_id": "E1",
                "posting_date": date(2026, 1, 1),
                "reference_number": "",
                "description": "fee2",
                "deposit": None,
                "withdrawal": Decimal("50.0000"),
                "import_discriminator": "fp:2",
            },
        ]
        adapter.persist_document(doc)
        database.session.commit()

        count = database.session.execute(database.select(database.func.count(BankTransaction.id))).scalar()
        assert count == 2
