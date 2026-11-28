# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1953: la tabla operativa activa renderiza encabezados localizados.

La prueba HTTP usa una factura real y recorre la ruta activa de ventas por
cliente en español e inglés, exigiendo etiquetas legibles y la ausencia de
claves técnicas como ``customer_id`` o ``amount``.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest

from cacao_accounting.database import SalesInvoice, User, database

RUTA = "/reports/sales-by-customer?company=cacao&accounting_period_from=P2026-05&accounting_period_to=P2026-05"


@pytest.fixture
def factura_venta(app, entorno_contable):
    """Factura posteada mínima para que la tabla tenga filas reales."""
    del entorno_contable
    documento = f"FV-1953-{uuid4().hex[:8]}"
    with app.app_context():
        factura = SalesInvoice(
            company="cacao",
            posting_date=date(2026, 5, 15),
            docstatus=1,
            document_no=documento,
            customer_name="Cliente de Prueba",
            grand_total=Decimal("50"),
            base_grand_total=Decimal("50"),
        )
        database.session.add(factura)
        database.session.commit()
        factura_id = factura.id
    yield
    with app.app_context():
        database.session.execute(database.delete(SalesInvoice).where(SalesInvoice.id == factura_id))
        database.session.commit()


def test_la_tabla_operativa_muestra_encabezados_en_espanol(app, authenticated_client, factura_venta):
    """La ruta activa no imprime las claves técnicas en español."""
    response = authenticated_client("admin").get(RUTA)

    assert response.status_code == 200
    cuerpo = response.get_data(as_text=True)
    assert ">Cliente<" in cuerpo
    assert ">Importe<" in cuerpo
    assert "customer_id" not in cuerpo
    assert ">amount<" not in cuerpo


def test_la_tabla_operativa_muestra_encabezados_en_ingles(app, authenticated_client, reference_users, factura_venta):
    """El mismo camino usa el catálogo inglés cuando el usuario lo selecciona."""
    user_id = str(reference_users["admin"].id)
    with app.app_context():
        usuario = database.session.get(User, user_id)
        anterior = usuario.language
        usuario.language = "en"
        database.session.commit()
    try:
        response = authenticated_client("admin").get(RUTA)
    finally:
        with app.app_context():
            usuario = database.session.get(User, user_id)
            usuario.language = anterior
            database.session.commit()

    assert response.status_code == 200
    cuerpo = response.get_data(as_text=True)
    assert ">Customer<" in cuerpo
    assert ">Amount<" in cuerpo
    assert "customer_id" not in cuerpo
    assert ">amount<" not in cuerpo
