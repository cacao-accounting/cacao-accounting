# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#2351: la descripción importada se persiste en la línea del documento.

El mapeador JavaScript ya copiaba ``description`` a la fila importada; estas
regresiones completan el guardado HTTP real y leen la línea persistida.
"""

from datetime import date
from decimal import Decimal
from uuid import uuid4

from sqlalchemy import select

from cacao_accounting.database import (
    Item,
    Modules,
    NamingSeries,
    Party,
    PurchaseOrder,
    PurchaseOrderItem,
    SalesInvoice,
    SalesInvoiceItem,
    SalesOrder,
    SalesOrderItem,
    SalesQuotation,
    SalesQuotationItem,
    User,
    UserCompanyAccess,
    database,
)
from cacao_accounting.document_identifiers import ensure_default_naming_series_for_company

FECHA = date(2026, 5, 15)
_DOCUMENT_TYPES = ("sales_quotation", "sales_order", "sales_invoice", "purchase_order")


def _prepare_shared_state(entorno_contable) -> None:
    """Habilita módulos, acceso y series que el alta HTTP comparte con la suite."""
    with entorno_contable.app.app_context():
        for module in ("sales", "purchases"):
            row = database.session.execute(select(Modules).filter_by(module=module)).scalar_one_or_none()
            if row is None:
                database.session.add(Modules(module=module, default=False, enabled=True))
            else:
                row.enabled = True
        admin_id = database.session.execute(select(User.id).filter_by(user="admin")).scalar_one()
        access = database.session.execute(
            select(UserCompanyAccess).filter_by(user_id=admin_id, company_code="cacao")
        ).scalar_one_or_none()
        if access is None:
            database.session.add(UserCompanyAccess(user_id=admin_id, company_code="cacao"))
        database.session.commit()
        ensure_default_naming_series_for_company("cacao", list(_DOCUMENT_TYPES))
        database.session.commit()


def _item(*, sale: bool, purchase: bool) -> str:
    """Crea un artículo único habilitado para el flujo indicado."""
    code = f"IMP{uuid4().hex[:8]}"
    database.session.add(
        Item(
            code=code,
            name=f"Artículo catálogo {code}",
            item_type="service",
            is_stock_item=False,
            is_sale_item=sale,
            is_purchase_item=purchase,
            default_uom="UND",
            standard_rate=Decimal("10"),
        )
    )
    database.session.commit()
    return code


def _customer_id() -> str:
    """Devuelve el cliente sembrado por el entorno contable."""
    return str(database.session.execute(select(Party.id).filter_by(code="CLI001")).scalar_one())


def _supplier_id() -> str:
    """Devuelve el proveedor sembrado por el entorno contable."""
    return str(database.session.execute(select(Party.id).filter_by(code="PRV001")).scalar_one())


def _sales_form(item_code: str, customer_id: str, description: str, marker: str) -> dict[str, str]:
    """Construye el POST de venta con la fila que produce el importador."""
    return {
        "company": "cacao",
        "currency": "NIO",
        "posting_date": FECHA.isoformat(),
        "customer_id": customer_id,
        "remarks": marker,
        "item_code_0": item_code,
        "item_name_0": f"Nombre catálogo {item_code}",
        "description_0": description,
        "qty_0": "1",
        "rate_0": "10",
        "uom_0": "UND",
    }


def _assert_sales_description(model, item_model, foreign_key: str, marker: str, description: str) -> None:
    """Comprueba que la línea persistida conserva la descripción importada."""
    document = database.session.execute(select(model).where(model.remarks == marker)).scalar_one()
    line = database.session.execute(select(item_model).where(getattr(item_model, foreign_key) == document.id)).scalar_one()
    assert line.description == description
    assert line.item_name == f"Nombre catálogo {line.item_code}"


def test_cotizacion_persiste_la_descripcion_importada(entorno_contable, authenticated_client):
    """La cotización de venta guarda la descripción de la fila importada."""
    _prepare_shared_state(entorno_contable)
    app = entorno_contable.app
    with app.app_context():
        item_code = _item(sale=True, purchase=False)
        customer_id = _customer_id()
    marker = f"COT-{uuid4().hex[:8]}"
    description = "Detalle importado de la cotización"

    response = authenticated_client("admin").post(
        "/sales/quotation/new",
        data=_sales_form(item_code, customer_id, description, marker),
    )

    assert response.status_code == 302
    with app.app_context():
        _assert_sales_description(SalesQuotation, SalesQuotationItem, "sales_quotation_id", marker, description)


def test_orden_de_venta_persiste_la_descripcion_importada(entorno_contable, authenticated_client):
    """La orden de venta guarda la descripción aunque su modelo no la tuviera."""
    _prepare_shared_state(entorno_contable)
    app = entorno_contable.app
    with app.app_context():
        item_code = _item(sale=True, purchase=False)
        customer_id = _customer_id()
    marker = f"SOV-{uuid4().hex[:8]}"
    description = "Detalle importado de la orden de venta"

    response = authenticated_client("admin").post(
        "/sales/sales-order/new",
        data=_sales_form(item_code, customer_id, description, marker),
    )

    assert response.status_code == 302
    with app.app_context():
        _assert_sales_description(SalesOrder, SalesOrderItem, "sales_order_id", marker, description)


def test_factura_de_venta_persiste_la_descripcion_importada(entorno_contable, authenticated_client):
    """La factura de venta guarda la descripción de la fila importada."""
    _prepare_shared_state(entorno_contable)
    app = entorno_contable.app
    with app.app_context():
        item_code = _item(sale=True, purchase=False)
        customer_id = _customer_id()
    marker = f"SIV-{uuid4().hex[:8]}"
    description = "Detalle importado de la factura de venta"

    response = authenticated_client("admin").post(
        "/sales/sales-invoice/new",
        data=_sales_form(item_code, customer_id, description, marker),
    )

    assert response.status_code == 302
    with app.app_context():
        _assert_sales_description(SalesInvoice, SalesInvoiceItem, "sales_invoice_id", marker, description)


def test_orden_de_compra_persiste_la_descripcion_importada(entorno_contable, authenticated_client):
    """La orden de compra conserva la descripción específica de la línea."""
    _prepare_shared_state(entorno_contable)
    app = entorno_contable.app
    with app.app_context():
        item_code = _item(sale=False, purchase=True)
        supplier_id = _supplier_id()
        series_id = (
            database.session.execute(
                select(NamingSeries.id)
                .where(NamingSeries.entity_type == "purchase_order", NamingSeries.is_active.is_(True))
                .order_by(NamingSeries.company.is_(None))
            )
            .scalars()
            .first()
        )
        assert series_id is not None
    marker = f"PO-{uuid4().hex[:8]}"
    description = "Detalle importado de la orden de compra"

    response = authenticated_client("admin").post(
        "/buying/purchase-order/new",
        data={
            "company": "cacao",
            "supplier_id": supplier_id,
            "posting_date": FECHA.isoformat(),
            "naming_series": series_id,
            "transaction_currency": "NIO",
            "remarks": marker,
            "item_code_0": item_code,
            "item_name_0": f"Nombre catálogo {item_code}",
            "description_0": description,
            "qty_0": "1",
            "rate_0": "10",
            "uom_0": "UND",
        },
    )

    assert response.status_code == 302
    with app.app_context():
        order = database.session.execute(select(PurchaseOrder).where(PurchaseOrder.remarks == marker)).scalar_one()
        line = database.session.execute(
            select(PurchaseOrderItem).where(PurchaseOrderItem.purchase_order_id == order.id)
        ).scalar_one()
        assert line.description == description
        assert line.item_name == f"Nombre catálogo {item_code}"
