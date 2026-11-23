# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 William José Moreno Reyes

"""#1822: la edición de recepción persiste la moneda y recalcula base/tasa."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import uuid4

from cacao_accounting.database import (
    CompanyParty,
    Currency,
    DocumentRelation,
    Party,
    PurchaseInvoice,
    PurchaseInvoiceItem,
    PurchaseReceipt,
    PurchaseReceiptItem,
    database,
)


def _limpiar(recepcion_id: str) -> None:
    """Elimina la recepción de prueba y sus hijos."""
    database.session.execute(
        database.delete(PurchaseReceiptItem).where(PurchaseReceiptItem.purchase_receipt_id == recepcion_id)
    )
    database.session.execute(
        database.delete(DocumentRelation).where(
            database.or_(
                database.and_(
                    DocumentRelation.source_type == "purchase_receipt",
                    DocumentRelation.source_id == recepcion_id,
                ),
                database.and_(
                    DocumentRelation.target_type == "purchase_receipt",
                    DocumentRelation.target_id == recepcion_id,
                ),
            )
        )
    )
    database.session.delete(database.session.get(PurchaseReceipt, recepcion_id))
    database.session.commit()


def _limpiar_factura(factura_id: str) -> None:
    """Elimina la factura de prueba y sus hijos."""
    database.session.execute(database.delete(PurchaseInvoiceItem).where(PurchaseInvoiceItem.purchase_invoice_id == factura_id))
    database.session.execute(
        database.delete(DocumentRelation).where(
            database.or_(
                database.and_(
                    DocumentRelation.source_type == "purchase_invoice",
                    DocumentRelation.source_id == factura_id,
                ),
                database.and_(
                    DocumentRelation.target_type == "purchase_invoice",
                    DocumentRelation.target_id == factura_id,
                ),
            )
        )
    )
    database.session.delete(database.session.get(PurchaseInvoice, factura_id))
    database.session.commit()


def _recepcion() -> PurchaseReceipt:
    """Crea una recepción en borrador con proveedor vinculado a la compañía."""
    sufijo = uuid4().hex[:6]
    moneda = database.session.execute(database.select(Currency).filter_by(code="USD")).scalar_one_or_none()
    if moneda is None:
        database.session.add(Currency(code="USD", name="Dólar", decimals=2, active=True))
        database.session.flush()
    else:
        moneda.active = True
    proveedor = Party(code=f"PRV-{sufijo}", name="Proveedor", is_supplier=True, is_active=True)
    database.session.add(proveedor)
    database.session.flush()
    database.session.add(CompanyParty(company="cacao", party_id=proveedor.id, is_active=True))
    recepcion = PurchaseReceipt(
        company="cacao",
        posting_date=date(2026, 5, 15),
        docstatus=0,
        document_no=f"PR-{sufijo}",
        supplier_id=proveedor.id,
        supplier_name=proveedor.name,
        transaction_currency="NIO",
        base_currency="NIO",
        exchange_rate=Decimal("1"),
    )
    database.session.add(recepcion)
    database.session.commit()
    return recepcion


def _recepcion_con_linea() -> PurchaseReceipt:
    """Crea una recepción en borrador con una línea activa."""
    recepcion = _recepcion()
    database.session.add(
        PurchaseReceiptItem(
            purchase_receipt_id=recepcion.id,
            item_code="ART01",
            item_name="Artículo",
            qty=Decimal("1"),
            qty_in_base_uom=Decimal("1"),
            uom="UND",
            rate=Decimal("10"),
            amount=Decimal("10"),
        )
    )
    database.session.commit()
    return recepcion


def _factura() -> PurchaseInvoice:
    """Crea una factura de compra en borrador con proveedor vinculado."""
    sufijo = uuid4().hex[:6]
    proveedor = Party(code=f"PRV-F-{sufijo}", name="Proveedor factura", is_supplier=True, is_active=True)
    database.session.add(proveedor)
    database.session.flush()
    database.session.add(CompanyParty(company="cacao", party_id=proveedor.id, is_active=True))
    factura = PurchaseInvoice(
        company="cacao",
        posting_date=date(2026, 5, 15),
        docstatus=0,
        document_no=f"PI-{sufijo}",
        document_type="purchase_invoice",
        supplier_id=proveedor.id,
        supplier_name=proveedor.name,
        transaction_currency="NIO",
        base_currency="NIO",
        exchange_rate=Decimal("1"),
    )
    database.session.add(factura)
    database.session.commit()
    return factura


def test_edicion_cambia_moneda_y_recalcula_base_y_tasa(app, authenticated_client, entorno_contable):
    """Cambiar NIO→USD persiste USD, base NIO y la tasa histórica."""
    with app.app_context():
        recepcion = _recepcion()
        recepcion_id = recepcion.id
        proveedor_id = recepcion.supplier_id
        moneda = database.session.execute(database.select(Currency).filter_by(code="USD")).scalar_one_or_none()
        assert moneda is not None and moneda.active is True

    client = authenticated_client("admin")
    response = client.post(
        f"/buying/purchase-receipt/{recepcion_id}/edit",
        data={
            "supplier_id": proveedor_id,
            "company": "cacao",
            "posting_date": "2026-05-15",
            "transaction_currency": "USD",
            "remarks": "Moneda cambiada",
            "to_warehouse": "BOD01",
            "item_code_0": "ART01",
            "qty_0": "1",
            "uom_0": "UND",
            "rate_0": "10",
            "warehouse_0": "BOD01",
        },
    )

    assert response.status_code == 302
    with app.app_context():
        actualizada = database.session.get(PurchaseReceipt, recepcion_id)
        try:
            assert actualizada.transaction_currency == "USD"
            assert actualizada.base_currency == "NIO"
            assert actualizada.exchange_rate == Decimal("36.5")
            assert actualizada.remarks == "Moneda cambiada"
        finally:
            _limpiar(recepcion_id)


def test_formulario_de_edicion_precarga_la_moneda(app, authenticated_client, entorno_contable):
    """El initialHeader de la edición incluye la moneda persistida."""
    with app.app_context():
        recepcion = _recepcion()
        recepcion_id = recepcion.id

    body = authenticated_client("admin").get(f"/buying/purchase-receipt/{recepcion_id}/edit").get_data(as_text=True)

    assert '"currency": "NIO"' in body
    with app.app_context():
        _limpiar(recepcion_id)


def test_formulario_de_factura_precarga_la_moneda(app, authenticated_client, entorno_contable):
    """El initialHeader de la factura incluye la moneda persistida."""
    with app.app_context():
        factura = _factura()
        factura_id = factura.id

    body = authenticated_client("admin").get(f"/buying/purchase-invoice/{factura_id}/edit").get_data(as_text=True)

    assert '"currency": "NIO"' in body
    with app.app_context():
        _limpiar_factura(factura_id)


def test_moneda_inactiva_rechaza_sin_500_y_conserva_la_recepcion(app, authenticated_client, entorno_contable):
    """Una moneda inactiva devuelve feedback y no deja cambios parciales."""
    with app.app_context():
        recepcion = _recepcion_con_linea()
        recepcion_id = recepcion.id
        proveedor_id = recepcion.supplier_id
        sufijo = uuid4().hex[:6]
        codigo_inactivo = f"Z{sufijo}"
        database.session.add(Currency(code=codigo_inactivo, name="Moneda inactiva", decimals=2, active=False))
        database.session.commit()

    response = authenticated_client("admin").post(
        f"/buying/purchase-receipt/{recepcion_id}/edit",
        data={
            "supplier_id": proveedor_id,
            "company": "cacao",
            "posting_date": "2026-05-15",
            "transaction_currency": codigo_inactivo,
            "remarks": "No debe persistir",
            "to_warehouse": "BOD01",
            "item_code_0": "ART01",
            "qty_0": "1",
            "uom_0": "UND",
            "rate_0": "10",
            "warehouse_0": "BOD01",
        },
    )

    assert response.status_code == 302
    with app.app_context():
        actual = database.session.get(PurchaseReceipt, recepcion_id)
        try:
            assert actual.transaction_currency == "NIO"
            assert actual.remarks != "No debe persistir"
            linea = database.session.execute(
                database.select(PurchaseReceiptItem).filter_by(purchase_receipt_id=recepcion_id)
            ).scalar_one()
            assert linea.is_superseded is False
        finally:
            _limpiar(recepcion_id)
