# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1795: el alta de notas desde la lista permite elegir la factura origen.

La lista de notas abría el formulario sin `from_invoice`, por lo que el POST
siempre se rechazaba por falta de factura origen. El flujo ahora muestra un
selector de facturas aprobadas y continúa con la grilla de líneas pendientes.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import uuid4

from cacao_accounting.compras.routes import _note_source_invoices
from cacao_accounting.database import Party, PurchaseInvoice, database


def _factura(app, *, docstatus: int = 1, document_type: str = "purchase_invoice") -> tuple[str, str]:
    """Crea una factura de compra con el estado indicado."""
    with app.app_context():
        sufijo = uuid4().hex[:6].upper()
        proveedor = database.session.execute(database.select(Party).filter_by(code="PRV001")).scalar_one()
        invoice = PurchaseInvoice(
            company="cacao",
            document_no=f"FAC-1795-{sufijo}",
            supplier_id=proveedor.id,
            supplier_name=proveedor.name,
            document_type=document_type,
            docstatus=docstatus,
            posting_date=date(2026, 5, 20),
            transaction_currency="NIO",
            base_currency="NIO",
            exchange_rate=Decimal("1"),
        )
        database.session.add(invoice)
        database.session.commit()
        return invoice.id, invoice.document_no


def test_la_nota_desde_la_lista_ofrece_la_factura_origen(app, entorno_contable, authenticated_client):
    """Sin origen fijado el formulario muestra el selector de facturas aprobadas."""
    del entorno_contable
    _, document_no = _factura(app)

    respuesta = authenticated_client("admin").get("/buying/purchase-invoice/new?document_type=purchase_credit_note")

    cuerpo = respuesta.get_data(as_text=True)
    assert respuesta.status_code == 200
    assert 'name="from_invoice"' in cuerpo
    assert document_no in cuerpo
    assert "Cargar factura" in cuerpo


def test_al_elegir_la_factura_continua_el_flujo_con_sus_lineas(app, entorno_contable, authenticated_client):
    """Con `from_invoice` el formulario mantiene el origen y la grilla de pendientes."""
    del entorno_contable
    invoice_id, _ = _factura(app)

    respuesta = authenticated_client("admin").get(
        f"/buying/purchase-invoice/new?document_type=purchase_credit_note&from_invoice={invoice_id}"
    )

    cuerpo = respuesta.get_data(as_text=True)
    assert respuesta.status_code == 200
    assert f'name="from_invoice" value="{invoice_id}"' in cuerpo
    assert "source_type=purchase_invoice" in cuerpo
    assert f"source_id={invoice_id}" in cuerpo
    assert "Cargar factura" not in cuerpo


def test_solo_se_ofrecen_facturas_aprobadas(app, entorno_contable):
    """La aprobada se ofrece; borradores y notas existentes no son origen válido."""
    del entorno_contable
    _, aprobada = _factura(app)
    _, borrador = _factura(app, docstatus=0)
    _, nota = _factura(app, document_type="purchase_credit_note")

    candidatas = _note_source_invoices("cacao")

    etiquetas = " ".join(candidate["label"] for candidate in candidatas)
    assert aprobada in etiquetas
    assert borrador not in etiquetas
    assert nota not in etiquetas
    assert _note_source_invoices(None) == []
    assert _note_source_invoices("empresa-sin-facturas") == []


def test_el_post_sin_factura_origen_no_crea_la_nota(app, entorno_contable, authenticated_client):
    """La guarda del servicio sigue rechazando una nota sin factura origen."""
    del entorno_contable
    marcador = f"SIN-ORIGEN-{uuid4().hex[:6].upper()}"
    with app.app_context():
        proveedor = database.session.execute(database.select(Party).filter_by(code="PRV001")).scalar_one()
        supplier_id = str(proveedor.id)

    respuesta = authenticated_client("admin").post(
        "/buying/purchase-invoice/new",
        data={
            "document_type": "purchase_credit_note",
            "company": "cacao",
            "posting_date": "2026-05-20",
            "supplier_id": supplier_id,
            "supplier_invoice_no": marcador,
            "currency": "NIO",
        },
    )

    assert respuesta.status_code == 200
    with app.app_context():
        assert (
            database.session.execute(
                database.select(PurchaseInvoice).filter_by(supplier_invoice_no=marcador)
            ).scalar_one_or_none()
            is None
        )
