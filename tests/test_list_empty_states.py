# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 William José Moreno Reyes

"""#2049, #2048, #2046, #2047: estados vacíos traducidos en los listados.

Cada plantilla de listado debe renderizar su mensaje de estado vacío dentro
del ``{% else %}`` del bucle de filas y no debe anunciar una paginación
imposible ("Página 1 de 0") cuando la búsqueda no devuelve registros.
Los mensajes se copian de cada plantilla para no inventar literales.
"""

from __future__ import annotations

from uuid import uuid4

import pytest

MENSAJE_DOCUMENTOS = "No se encontraron documentos para los filtros seleccionados."

LISTADOS = [
    # (#2046) Maestros de ventas e inventario.
    ("/sales/customer/list", "No se encontraron clientes para los filtros seleccionados."),
    ("/inventory/batch/list", "No se encontraron lotes para los filtros seleccionados."),
    ("/inventory/warehouse/list", "No hay bodegas para los filtros o el alcance de compañía actual."),
    # (#2047/#2049/#2048) Listados transaccionales de ventas.
    ("/sales/quotation/list", MENSAJE_DOCUMENTOS),
    ("/sales/sales-invoice/list", MENSAJE_DOCUMENTOS),
    ("/sales/sales-order/list", MENSAJE_DOCUMENTOS),
    ("/sales/sales-request/list", MENSAJE_DOCUMENTOS),
    ("/sales/delivery-note/list", MENSAJE_DOCUMENTOS),
    ("/sales/sales-invoice/debit-note/list", MENSAJE_DOCUMENTOS),
    ("/sales/sales-invoice/return/list", MENSAJE_DOCUMENTOS),
]


def _busqueda_vacia() -> str:
    """Término de búsqueda que no coincide con ningún registro sembrado."""
    return f"SIN-RESULTADOS-{uuid4().hex[:12]}"


@pytest.mark.parametrize(("ruta", "mensaje"), LISTADOS)
def test_listado_vacio_muestra_estado_traducido_y_sin_paginacion_imposible(authenticated_client, ruta, mensaje):
    """La búsqueda sin coincidencias muestra el estado vacío de la plantilla."""
    respuesta = authenticated_client().get(f"{ruta}?search={_busqueda_vacia()}")

    assert respuesta.status_code == 200
    html = respuesta.get_data(as_text=True)
    assert mensaje in html, f"El listado {ruta} debe mostrar su estado vacío traducido."
    assert "Página 1 de 0" not in html, "No debe anunciarse una paginación sin resultados."


def test_nota_debito_y_devolucion_conservan_su_tipo_documental(authenticated_client):
    """Los dos callers del template compartido enlazan al tipo correcto (#2047)."""
    client = authenticated_client()
    busqueda = _busqueda_vacia()

    debito = client.get(f"/sales/sales-invoice/debit-note/list?search={busqueda}").get_data(as_text=True)
    devolucion = client.get(f"/sales/sales-invoice/return/list?search={busqueda}").get_data(as_text=True)

    assert "document_type=sales_debit_note" in debito
    assert "document_type=sales_return" in devolucion


def test_paginacion_de_notas_conserva_su_endpoint(app, entorno_contable, authenticated_client):
    """#2047: la página siguiente de notas no apunta al listado de devoluciones."""
    from datetime import date

    from cacao_accounting.database import PaymentEntry, database

    with app.app_context():
        for index in range(11):
            database.session.add(
                PaymentEntry(
                    company="cacao",
                    payment_type="debit_note",
                    document_no=f"ND-PAG-{index}",
                    party_name="Cliente",
                    posting_date=date(2026, 5, 15),
                    paid_amount=1,
                )
            )
            database.session.add(
                PaymentEntry(
                    company="cacao",
                    payment_type="credit_note",
                    document_no=f"NC-PAG-{index}",
                    party_name="Cliente",
                    posting_date=date(2026, 5, 15),
                    paid_amount=1,
                )
            )
        database.session.commit()

    client = authenticated_client("admin")
    debito = client.get("/cash_management/payment/debit-note/list").get_data(as_text=True).replace("&amp;", "&")
    credito = client.get("/cash_management/payment/credit-note/list").get_data(as_text=True).replace("&amp;", "&")

    assert "/cash_management/payment/debit-note/list?page=2" in debito
    assert "/cash_management/payment/credit-note/list?page=2" in credito
    assert "/cash_management/payment/credit-note/list" not in debito
