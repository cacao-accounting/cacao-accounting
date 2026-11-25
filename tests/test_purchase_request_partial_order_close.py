# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1606: una orden parcial no cierra la solicitud de compra."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy.pool import StaticPool

from cacao_accounting import create_app
from cacao_accounting.compras.purchase_request_comparison_service import (
    purchase_request_comparison_covered_item_ids,
    purchase_request_is_ready_to_close,
    purchase_request_line_closure_reasons,
)
from cacao_accounting.config import configuracion
from cacao_accounting.database import (
    Currency,
    DocumentRelation,
    Entity,
    Item,
    PurchaseOrder,
    PurchaseOrderItem,
    PurchaseRequest,
    PurchaseRequestComparison,
    PurchaseRequestComparisonLine,
    PurchaseRequestItem,
    SupplierQuotation,
    UOM,
    database,
)


@pytest.fixture
def request_order_scene():
    application = create_app(
        {
            **configuracion,
            "SQLALCHEMY_DATABASE_URI": "sqlite://",
            "SQLALCHEMY_ENGINE_OPTIONS": {"poolclass": StaticPool},
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
            "TESTING": True,
            "MODO_ESCRITORIO": True,
        }
    )
    sufijo = uuid4().hex[:6]
    with application.app_context():
        database.create_all()
        database.session.add_all(
            [
                Currency(code="NIO", name="Córdoba", decimals=2, active=True, default=True),
                Entity(
                    code="cacao",
                    name="Cacao",
                    company_name="Cacao SA",
                    tax_id=f"J-{sufijo}",
                    currency="NIO",
                    enabled=True,
                    status="default",
                ),
                UOM(code="UND", name="Unidad"),
            ]
        )
        database.session.flush()
        database.session.add(
            Item(
                code="ART01",
                name="Artículo de prueba",
                item_type="goods",
                is_stock_item=False,
                is_purchase_item=True,
                default_uom="UND",
            )
        )
        database.session.flush()
        solicitud = PurchaseRequest(company="cacao", posting_date=date(2026, 5, 15), docstatus=1, status="open")
        database.session.add(solicitud)
        database.session.flush()
        solicitud_linea = PurchaseRequestItem(
            purchase_request_id=solicitud.id,
            item_code="ART01",
            item_name="Artículo de prueba",
            qty=Decimal("10"),
            uom="UND",
            qty_in_base_uom=Decimal("10"),
            rate=Decimal("10"),
            amount=Decimal("100"),
        )
        database.session.add(solicitud_linea)
        database.session.commit()
        ids = {"request": solicitud.id, "request_item": solicitud_linea.id}
    yield application, ids
    with application.app_context():
        database.session.remove()
        database.engine.dispose()


def _agregar_orden(application, ids, cantidad: str, *, docstatus: int = 1) -> None:
    with application.app_context():
        orden = PurchaseOrder(company="cacao", posting_date=date(2026, 5, 15), docstatus=docstatus, status="open")
        database.session.add(orden)
        database.session.flush()
        linea = PurchaseOrderItem(
            purchase_order_id=orden.id,
            item_code="ART01",
            item_name="Artículo de prueba",
            qty=Decimal(cantidad),
            uom="UND",
            qty_in_base_uom=Decimal(cantidad),
            rate=Decimal("10"),
            amount=Decimal(cantidad) * Decimal("10"),
        )
        database.session.add(linea)
        database.session.flush()
        database.session.add(
            DocumentRelation(
                source_type="purchase_request",
                source_id=ids["request"],
                source_item_id=ids["request_item"],
                target_type="purchase_order",
                target_id=orden.id,
                target_item_id=linea.id,
                company="cacao",
                qty=Decimal(cantidad),
                qty_in_base_uom=Decimal(cantidad),
                uom="UND",
                rate=Decimal("10"),
                amount=Decimal(cantidad) * Decimal("10"),
                relation_type="order",
                status="active",
            )
        )
        database.session.commit()


def _agregar_comparativo_finalizado(application, ids) -> None:
    """Finaliza un comparativo sin generar la orden de compra de la línea."""
    suffix = uuid4().hex[:6]
    with application.app_context():
        quotation = SupplierQuotation(
            company="cacao",
            posting_date=date(2026, 5, 15),
            docstatus=1,
            document_no=f"SC-{suffix}",
            supplier_name=f"Proveedor {suffix}",
            transaction_currency="NIO",
        )
        comparison = PurchaseRequestComparison(
            company="cacao",
            purchase_request_id=ids["request"],
            document_no=f"CMP-{suffix}",
            posting_date=date(2026, 5, 15),
            status="finalized",
        )
        database.session.add_all([quotation, comparison])
        database.session.flush()
        database.session.add(
            PurchaseRequestComparisonLine(
                comparison_id=comparison.id,
                purchase_request_item_id=ids["request_item"],
                selected_supplier_quotation_id=quotation.id,
            )
        )
        database.session.commit()


def test_comparativo_finalizado_sin_orden_no_cierra_la_solicitud(request_order_scene):
    """Finalizar el comparativo no sustituye la orden que cubre la cantidad."""
    application, ids = request_order_scene
    _agregar_comparativo_finalizado(application, ids)

    with application.app_context():
        solicitud = database.session.get(PurchaseRequest, ids["request"])
        assert purchase_request_is_ready_to_close(solicitud) is False
        assert purchase_request_line_closure_reasons(solicitud) == {}


def test_orden_en_borrador_no_cubre_la_solicitud(request_order_scene):
    """Una OC en borrador no consume la cantidad pendiente de la solicitud."""
    application, ids = request_order_scene
    _agregar_comparativo_finalizado(application, ids)
    _agregar_orden(application, ids, "10", docstatus=0)

    with application.app_context():
        solicitud = database.session.get(PurchaseRequest, ids["request"])
        assert purchase_request_comparison_covered_item_ids(solicitud) == set()
        assert purchase_request_is_ready_to_close(solicitud) is False


def test_comparativo_finalizado_cierra_cuando_la_orden_cubre_la_linea(request_order_scene):
    """El comparativo acredita cobertura solo después de cubrir la cantidad."""
    application, ids = request_order_scene
    _agregar_comparativo_finalizado(application, ids)
    _agregar_orden(application, ids, "10")

    with application.app_context():
        solicitud = database.session.get(PurchaseRequest, ids["request"])
        assert purchase_request_comparison_covered_item_ids(solicitud) == {ids["request_item"]}
        assert purchase_request_is_ready_to_close(solicitud) is True
        assert ids["request_item"] in purchase_request_line_closure_reasons(solicitud)


def test_orden_parcial_no_cierra_la_solicitud(request_order_scene):
    """Mientras haya cantidad pendiente, la solicitud no está lista para cerrar."""
    application, ids = request_order_scene
    _agregar_orden(application, ids, "4")

    with application.app_context():
        solicitud = database.session.get(PurchaseRequest, ids["request"])
        assert purchase_request_is_ready_to_close(solicitud) is False


def test_ordenes_que_cubren_la_cantidad_cierran_la_solicitud(request_order_scene):
    """Al cubrir las 10 unidades, la solicitud queda lista para cerrar."""
    application, ids = request_order_scene
    _agregar_orden(application, ids, "4")
    _agregar_orden(application, ids, "6")

    with application.app_context():
        solicitud = database.session.get(PurchaseRequest, ids["request"])
        assert purchase_request_is_ready_to_close(solicitud) is True
