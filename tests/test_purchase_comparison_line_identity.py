# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#2141: la identidad de línea del comparativo no incluye la cantidad."""

from __future__ import annotations

from decimal import Decimal
from datetime import date
from uuid import uuid4

from cacao_accounting import create_app
from cacao_accounting.compras.purchase_request_comparison_service import (
    _request_item_offer_line,
    purchase_request_comparison_recommendations,
)
from cacao_accounting.config import configuracion
from cacao_accounting.database import (
    Currency,
    Entity,
    Item,
    Modules,
    PurchaseRequest,
    PurchaseRequestItem,
    SupplierQuotation,
    SupplierQuotationItem,
    UOM,
    Warehouse,
    database,
)


def _solicitud(**overrides) -> PurchaseRequestItem:
    """Línea de solicitud con cantidad 5."""
    datos = {
        "item_code": "ART01",
        "uom": "UND",
        "warehouse": "BOD01",
        "description": "Tornillo",
        "qty": Decimal("5"),
    }
    datos.update(overrides)
    return PurchaseRequestItem(**datos)


def _oferta(**overrides) -> SupplierQuotationItem:
    """Línea de oferta con la misma identidad comercial."""
    datos = {
        "item_code": "ART01",
        "uom": "UND",
        "warehouse": "BOD01",
        "description": "Tornillo",
        "qty": Decimal("8"),
    }
    datos.update(overrides)
    return SupplierQuotationItem(**datos)


def test_oferta_con_cantidad_mayor_cubre_la_linea_solicitada():
    """Solicitud 5 y oferta 8 se emparejan por artículo, UOM, bodega y descripción."""
    solicitud = _solicitud()
    oferta = _oferta()

    assert _request_item_offer_line(solicitud, 0, {"of-1": [oferta]}, "of-1") is oferta


def test_identidad_comercial_distinta_no_empareja():
    """Cambiar artículo, UOM, bodega o descripción rompe la cobertura."""
    solicitud = _solicitud()

    for oferta in (
        _oferta(item_code="ART02"),
        _oferta(uom="CAJ"),
        _oferta(warehouse="BOD02"),
        _oferta(description="Tuerca"),
    ):
        assert _request_item_offer_line(solicitud, 0, {"of-1": [oferta]}, "of-1") is None


def test_flujo_de_recomendaciones_empareja_oferta_mayor():
    """La recomendación activa acepta una oferta de 8 para una solicitud de 5."""
    sufijo = uuid4().hex[:6]
    app = create_app(
        {
            **configuracion,
            "SQLALCHEMY_DATABASE_URI": "sqlite://",
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
            "WTF_CSRF_ENABLED": False,
            "TESTING": True,
            "MODO_ESCRITORIO": True,
        }
    )
    with app.app_context():
        database.create_all()
        database.session.add_all(
            [
                Currency(code="NIO", name="Córdoba", decimals=2, active=True, default=True),
                Entity(
                    code="cacao",
                    name="Cacao",
                    company_name=f"Cacao {sufijo}",
                    tax_id=f"J-{sufijo}",
                    currency="NIO",
                    enabled=True,
                    status="default",
                ),
                Modules(module="purchases", default=False, enabled=True),
            ]
        )
        database.session.flush()
        database.session.add(UOM(code="UND", name="Unidad", is_active=True))
        database.session.flush()
        database.session.add(
            Item(
                code="ART01",
                name="Tornillo",
                item_type="goods",
                is_stock_item=False,
                default_uom="UND",
            )
        )
        database.session.add(Warehouse(code="BOD01", name="Bodega", company="cacao", is_active=True))
        database.session.flush()
        solicitud = PurchaseRequest(
            company="cacao",
            posting_date=date(2026, 5, 15),
            docstatus=1,
            document_no=f"PR-{sufijo}",
        )
        database.session.add(solicitud)
        database.session.flush()
        linea_solicitud = PurchaseRequestItem(
            purchase_request_id=solicitud.id,
            item_code="ART01",
            uom="UND",
            warehouse="BOD01",
            description="Tornillo",
            qty=Decimal("5"),
        )
        oferta = SupplierQuotation(
            company="cacao",
            posting_date=date(2026, 5, 15),
            docstatus=1,
            document_no=f"SQ-{sufijo}",
            supplier_name="Proveedor",
        )
        database.session.add_all([linea_solicitud, oferta])
        database.session.flush()
        linea_oferta = SupplierQuotationItem(
            supplier_quotation_id=oferta.id,
            item_code="ART01",
            uom="UND",
            warehouse="BOD01",
            description="Tornillo",
            qty=Decimal("8"),
            qty_in_base_uom=Decimal("8"),
            rate=Decimal("10"),
            base_rate=Decimal("10"),
        )
        database.session.add(linea_oferta)
        database.session.commit()

        filas = purchase_request_comparison_recommendations(solicitud, [oferta])

    assert len(filas) == 1
    recomendada = filas[0]["recommended"]
    assert recomendada is not None
    assert recomendada["offer"].id == oferta.id
    assert recomendada["line"].id == linea_oferta.id
    assert filas[0]["by_offer"][oferta.id]["line"].qty == Decimal("8")
