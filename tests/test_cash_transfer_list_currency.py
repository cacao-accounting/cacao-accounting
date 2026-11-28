# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#2043: la lista de transferencias muestra las dos piernas con su moneda y escala."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import uuid4

from cacao_accounting.database import Bank, BankAccount, Currency, PaymentEntry, database


def _sembrar_transferencia(app, sufijo: str, *, moneda_destino: str, pagado: Decimal, recibido: Decimal):
    """Crea una transferencia interna con una cuenta destino de la moneda indicada."""
    with app.app_context():
        banco = Bank(name=f"Banco {sufijo}")
        database.session.add(banco)
        database.session.flush()
        destino = BankAccount(
            company="cacao",
            bank_id=banco.id,
            account_name="Cuenta destino",
            account_no=f"D-{sufijo}",
            currency=moneda_destino,
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
            paid_amount=pagado,
            received_amount=recibido,
            target_bank_account_id=destino.id,
        )
        database.session.add(transferencia)
        database.session.commit()
        return transferencia.id, destino.id, banco.id


def _limpiar(app, ids) -> None:
    """Retira solo las filas creadas por la prueba."""
    transferencia_id, destino_id, banco_id = ids
    with app.app_context():
        database.session.execute(database.delete(PaymentEntry).where(PaymentEntry.id == transferencia_id))
        database.session.execute(database.delete(BankAccount).where(BankAccount.id == destino_id))
        database.session.execute(database.delete(Bank).where(Bank.id == banco_id))
        database.session.commit()


def test_lista_muestra_piernas_origen_y_destino_con_su_moneda(app, entorno_contable, authenticated_client):
    """Salida en USD y entrada en NIO se presentan por separado, sin sumarse."""
    del entorno_contable
    sufijo = uuid4().hex[:6]
    ids = _sembrar_transferencia(app, sufijo, moneda_destino="NIO", pagado=Decimal("100"), recibido=Decimal("3650"))

    try:
        response = authenticated_client("admin").get("/cash_management/transfer/list")

        assert response.status_code == 200
        cuerpo = response.get_data(as_text=True)
        assert "100.00 USD → 3,650.00 NIO" in cuerpo
        assert "3750" not in cuerpo
    finally:
        _limpiar(app, ids)


def test_lista_normaliza_la_escala_de_cada_moneda(app, entorno_contable, authenticated_client):
    """La escala de cada pierna proviene del catálogo, no de los decimales almacenados."""
    del entorno_contable
    sufijo = uuid4().hex[:6]
    moneda_cero = f"J{sufijo}"
    with app.app_context():
        database.session.add(Currency(code=moneda_cero, name="Sin decimales", decimals=0, active=True, default=False))
        database.session.commit()
    ids = _sembrar_transferencia(
        app,
        sufijo,
        moneda_destino=moneda_cero,
        pagado=Decimal("100.5000"),
        recibido=Decimal("12345.0000"),
    )

    try:
        respuesta = authenticated_client("admin").get("/cash_management/transfer/list")

        assert respuesta.status_code == 200
        cuerpo = respuesta.get_data(as_text=True)
        assert f"100.50 USD → 12,345 {moneda_cero}" in cuerpo
        assert "100.5000" not in cuerpo
        assert "12345.0000" not in cuerpo
    finally:
        _limpiar(app, ids)
        with app.app_context():
            database.session.execute(database.delete(Currency).where(Currency.code == moneda_cero))
            database.session.commit()
