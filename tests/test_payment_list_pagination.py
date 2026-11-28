# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#2042: notas y transferencias conservan ruta y filtros al paginar."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import inspect

from cacao_accounting.database import PaymentEntry, database

FECHA = date(2026, 5, 15)

LISTADOS = [
    ("internal_transfer", "/cash_management/transfer/list"),
    ("debit_note", "/cash_management/payment/debit-note/list"),
    ("credit_note", "/cash_management/payment/credit-note/list"),
]


@pytest.mark.parametrize(("payment_type", "ruta"), LISTADOS)
def test_la_paginacion_conserva_ruta_y_filtros(entorno_contable_aislado, payment_type, ruta):
    """La página siguiente usa su endpoint especializado y mantiene búsqueda y compañía."""
    app = entorno_contable_aislado.app
    admin_id = str(inspect(entorno_contable_aislado.admin_user).identity[0])
    sufijo = uuid4().hex[:8]
    ids: list[str] = []
    with app.app_context():
        for indice in range(11):
            pago = PaymentEntry(
                company="cacao",
                payment_type=payment_type,
                document_no=f"PAG-{sufijo}-{indice:02d}",
                party_name="Filtro paginación",
                posting_date=FECHA,
                transaction_currency="NIO",
                currency="NIO",
                paid_amount=Decimal("1"),
            )
            database.session.add(pago)
            database.session.flush()
            ids.append(pago.id)
        database.session.commit()

    try:
        client = app.test_client()
        with client.session_transaction() as sesion:
            sesion["_user_id"] = admin_id
            sesion["_fresh"] = True
        primera = client.get(f"{ruta}?search={sufijo}&company=cacao")
        segunda = client.get(f"{ruta}?search={sufijo}&company=cacao&page=2")

        assert primera.status_code == 200
        cuerpo = primera.get_data(as_text=True).replace("&amp;", "&")
        assert f"{ruta}?page=2" in cuerpo
        assert "company=cacao" in cuerpo
        assert f"search={sufijo}" in cuerpo
        for otra in {item[1] for item in LISTADOS if item[1] != ruta}:
            assert otra not in cuerpo

        assert segunda.status_code == 200
        assert f"PAG-{sufijo}-10" in segunda.get_data(as_text=True)
    finally:
        with app.app_context():
            database.session.execute(database.delete(PaymentEntry).where(PaymentEntry.id.in_(ids)))
            database.session.commit()
