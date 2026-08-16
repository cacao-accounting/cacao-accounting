"""Pruebas de herencia logística del flujo O2C."""

from datetime import date
from types import SimpleNamespace

from cacao_accounting.ventas import _sales_logistics_values


def test_sales_logistics_are_inherited_and_default_incoterm_version():
    """La orden de venta conserva los términos de la cotización."""
    source = SimpleNamespace(
        incoterm_code="DAP",
        incoterm_version=None,
        delivery_date=date(2026, 11, 20),
        delivery_place="Bodega del cliente",
        sales_terms="Entrega contra recepción",
    )

    assert _sales_logistics_values(source) == {
        "incoterm_code": "DAP",
        "incoterm_version": "2020",
        "delivery_date": date(2026, 11, 20),
        "delivery_place": "Bodega del cliente",
        "sales_terms": "Entrega contra recepción",
    }
