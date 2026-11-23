# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#2043: la lista de transferencias muestra las dos piernas con su moneda."""

from __future__ import annotations

import re
from datetime import date
from decimal import Decimal
from uuid import uuid4

from cacao_accounting.database import Bank, BankAccount, PaymentEntry, database


def test_lista_muestra_piernas_origen_y_destino_con_su_moneda(app, entorno_contable, authenticated_client):
    """Salida en USD y entrada en NIO se presentan por separado, sin sumarse."""
    del entorno_contable
    sufijo = uuid4().hex[:6]
    with app.app_context():
        banco = Bank(name=f"Banco {sufijo}")
        database.session.add(banco)
        database.session.flush()
        destino = BankAccount(
            company="cacao",
            bank_id=banco.id,
            account_name="Cuenta destino",
            account_no=f"D-{sufijo}",
            currency="NIO",
            is_active=True,
        )
        database.session.add(destino)
        database.session.flush()
        transferencia = PaymentEntry(
            company="cacao",
            payment_type="internal_transfer",
            docstatus=1,
            document_no=f"TR-{sufijo}",
            posting_date=date(2026, 5, 15),
            transaction_currency="USD",
            currency="USD",
            base_currency="NIO",
            exchange_rate=Decimal("36.5"),
            paid_amount=Decimal("100"),
            received_amount=Decimal("3650"),
            target_bank_account_id=destino.id,
        )
        database.session.add(transferencia)
        database.session.commit()
        transferencia_id, destino_id, banco_id = transferencia.id, destino.id, banco.id

    try:
        response = authenticated_client("admin").get("/cash_management/transfer/list")

        assert response.status_code == 200
        cuerpo = response.get_data(as_text=True)
        assert re.search(r"100(?:\.0+)?\s*USD", cuerpo)
        assert re.search(r"3650(?:\.0+)?\s*NIO", cuerpo)
        assert "3750" not in cuerpo
    finally:
        with app.app_context():
            database.session.execute(database.delete(PaymentEntry).where(PaymentEntry.id == transferencia_id))
            database.session.execute(database.delete(BankAccount).where(BankAccount.id == destino_id))
            database.session.execute(database.delete(Bank).where(Bank.id == banco_id))
            database.session.commit()
