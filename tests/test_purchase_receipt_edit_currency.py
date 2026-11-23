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
