"""Pruebas de herencia logística del flujo O2C."""

from datetime import date
from pathlib import Path
from types import SimpleNamespace

from cacao_accounting.ventas import _sales_logistics_values

PROJECT_ROOT = Path(__file__).resolve().parents[1]


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


def test_sales_forms_bind_sales_terms_field():
    """Los formularios O2C no deben enviar el campo de compras."""
    template_root = PROJECT_ROOT / "cacao_accounting/ventas/templates/ventas"
    for filename in ("cotizacion_nuevo.html", "orden_venta_nuevo.html", "entrega_nuevo.html", "factura_venta_nuevo.html"):
        content = (template_root / filename).read_text(encoding="utf-8")
        assert 'terms_field="sales_terms"' in content
