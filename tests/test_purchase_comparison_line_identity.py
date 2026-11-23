# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#2141: la identidad de línea del comparativo no incluye la cantidad."""

from __future__ import annotations

from decimal import Decimal

from cacao_accounting.compras.purchase_request_comparison_service import _request_item_offer_line
from cacao_accounting.database import PurchaseRequestItem, SupplierQuotationItem


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
