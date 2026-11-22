# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1684: el ledger AR/AP expone solo su esquema explícito.

Los synonyms `amount`, `signed_amount` y `transaction_currency` no tenían
consumidores y confundían el contrato real de `ARAPLedgerEntry`.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from cacao_accounting.database import ARAPLedgerEntry, Party, database


def test_arap_ledger_no_expone_sinonimos():
    """El mapper no publica los alias retirados."""
    atributos = set(ARAPLedgerEntry.__mapper__.attrs.keys())

    assert {"document_amount", "currency"} <= atributos
    assert not {"amount", "signed_amount", "transaction_currency"} & atributos


def test_arap_ledger_persiste_las_columnas_explicitas(app, entorno_contable):
    """Una fila nueva conserva monto y moneda en sus columnas canónicas."""
    with app.app_context():
        party_id = database.session.execute(database.select(Party).filter_by(code="CLI001")).scalar_one().id
        registro = ARAPLedgerEntry(
            company="cacao",
            ledger_type="ar",
            party_type="customer",
            party_id=party_id,
            document_type="sales_invoice",
            document_id="INV-1684",
            document_no="FAC-1684",
            posting_date=date(2026, 5, 15),
            event_type="invoice",
            currency="NIO",
            document_amount=Decimal("125.5000"),
        )
        database.session.add(registro)
        database.session.commit()

        guardado = database.session.get(ARAPLedgerEntry, registro.id)
        assert guardado is not None
        assert guardado.document_amount == Decimal("125.5000")
        assert guardado.currency == "NIO"
        assert not hasattr(guardado, "amount")
        assert not hasattr(guardado, "signed_amount")
        assert not hasattr(guardado, "transaction_currency")
