# SPDX-License-Identifier: Apache-2.0
"""#1507: duplicados dentro del mismo lote se rechazan con referencia estable."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from cacao_accounting.database import Bank, BankAccount, Currency, Entity, database
from cacao_accounting.imports.adapters.bank_statement import BankStatementAdapter


def test_bank_statement_duplicate_reference_in_same_batch_rejected(app):
    with app.app_context():
        if database.session.execute(database.select(Currency).filter_by(code="NIO")).scalar_one_or_none() is None:
            database.session.add(Currency(code="NIO", name="Cordoba", decimals=2, active=True, default=False))
        database.session.add(
            Entity(code="E1507", company_name="E1507", name="E1507", tax_id="J0310000001507", currency="NIO", enabled=True)
        )
        bank = Bank(name="Banco1507")
        database.session.add(bank)
        database.session.flush()
        database.session.add(
            BankAccount(id="ba1507", company="E1507", bank_id=bank.id, account_name="A", account_no="1", currency="NIO")
        )
        database.session.commit()

        adapter = BankStatementAdapter()
        doc = [
            {
                "bank_account_id": "ba1507",
                "company_id": "E1507",
                "posting_date": date(2026, 1, 1),
                "reference_number": "REF-1",
                "description": "a",
                "deposit": Decimal("50.0000"),
                "withdrawal": None,
                "import_discriminator": "fp:1",
            },
            {
                "bank_account_id": "ba1507",
                "company_id": "E1507",
                "posting_date": date(2026, 1, 1),
                "reference_number": "REF-1",
                "description": "b",
                "deposit": Decimal("50.0000"),
                "withdrawal": None,
                "import_discriminator": "fp:2",
            },
        ]
        with pytest.raises(ValueError, match="ya existe"):
            adapter.persist_document(doc)
