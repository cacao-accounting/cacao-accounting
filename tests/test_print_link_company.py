# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Los enlaces de impresión conservan la compañía del documento.

Escenario de negocio (issue #2055): el botón de impresión no enviaba la
compañía del documento visible. Si la compañía activa del usuario era otra,
el servicio de impresión rechazaba el documento con 404 aunque el usuario
tuviera acceso a ambas compañías.
"""

from __future__ import annotations

from datetime import date

from cacao_accounting.database import SalesRequest, database


def test_el_macro_propaga_la_compania(app):
    """El botón agrega la compañía a la vista previa y al PDF."""
    with app.test_request_context("/sales/sales-request/X"):
        macro = app.jinja_env.get_template("macros.html").module.document_print_button

        html = macro("sales_request", "X", company="OWN")

    assert "company=OWN" in html
    assert "/print/sales_request/X/preview" in html


def test_el_macro_omite_la_compania_cuando_no_hay_contexto(app):
    """Sin compañía explícita no se inventa un parámetro."""
    with app.test_request_context("/sales/sales-request/X"):
        macro = app.jinja_env.get_template("macros.html").module.document_print_button

        html = macro("sales_request", "X")

    assert "company=" not in html


def test_el_detalle_del_pedido_conserva_la_compania(app, authenticated_client):
    """La página de detalle encadena la compañía del registro al botón."""
    with app.app_context():
        pedido = SalesRequest(
            company="cacao",
            posting_date=date(2026, 10, 15),
            docstatus=1,
            customer_name="Cliente Cacao",
        )
        database.session.add(pedido)
        database.session.commit()
        pedido_id = pedido.id

    try:
        client = authenticated_client("admin")
        respuesta = client.get(f"/sales/sales-request/{pedido_id}")

        assert respuesta.status_code == 200
        html = respuesta.get_data(as_text=True)
        assert f"/print/sales_request/{pedido_id}/preview" in html
        assert "company=cacao" in html
    finally:
        with app.app_context():
            database.session.execute(database.delete(SalesRequest).where(SalesRequest.id == pedido_id))
            database.session.commit()
