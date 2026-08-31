"""Pruebas para metadatos logísticos y landed costs estimados."""

from datetime import date
from types import SimpleNamespace

import pytest

from cacao_accounting.compras import _landed_cost_snapshot, _logistics_values
from cacao_accounting.logistics import copy_logistics, ensure_compatible_logistics, logistics_values, validate_incoterm


def test_logistics_values_normalizes_date_and_default_incoterm_version():
    """Los valores del formulario se normalizan para persistencia."""
    values = _logistics_values(
        form={
            "incoterm_code": "CIF",
            "incoterm_version": "",
            "delivery_date": "2026-09-30",
            "delivery_place": "Puerto de Corinto",
            "purchase_terms": "Seguro incluido",
        }
    )

    assert values == {
        "incoterm_code": "CIF",
        "incoterm_version": "2020",
        "delivery_date": date(2026, 9, 30),
        "delivery_place": "Puerto de Corinto",
        "purchase_terms": "Seguro incluido",
    }


def test_logistics_values_can_be_inherited_from_source():
    """La cotización de proveedor puede iniciar con datos del RFQ."""
    source = SimpleNamespace(
        incoterm_code="FOB",
        incoterm_version="2020",
        delivery_date=date(2026, 10, 1),
        delivery_place="Managua",
        purchase_terms="Entrega parcial permitida",
    )

    assert _logistics_values(source) == {
        "incoterm_code": "FOB",
        "incoterm_version": "2020",
        "delivery_date": date(2026, 10, 1),
        "delivery_place": "Managua",
        "purchase_terms": "Entrega parcial permitida",
    }


def test_logistics_values_rejects_invalid_delivery_date():
    with pytest.raises(ValueError, match="fecha de entrega"):
        logistics_values(form={"delivery_date": "30/09/2026"}, terms_field="purchase_terms")


def test_logistics_values_prefers_form_values_over_source_values():
    source = SimpleNamespace(delivery_place="Bodega origen", purchase_terms="Condiciones origen")

    values = logistics_values(
        source=source,
        form={"delivery_place": "Bodega destino", "purchase_terms": "Condiciones destino"},
        terms_field="purchase_terms",
    )

    assert values["delivery_place"] == "Bodega destino"
    assert values["purchase_terms"] == "Condiciones destino"


def test_landed_cost_snapshot_validates_and_compacts_estimates():
    """Los landed costs estimados se conservan como snapshot JSON."""
    result = _landed_cost_snapshot(
        form={"landed_cost_estimates_json": '[{"concept": "Flete", "amount": "125.50", "currency": "USD"}]'}
    )

    assert result == '[{"concept":"Flete","amount":"125.50","currency":"USD"}]'


def test_copy_logistics_propagates_source_snapshot(monkeypatch):
    """El mismo copiador sirve para cada salto del document flow."""
    monkeypatch.setattr("cacao_accounting.logistics.validate_incoterm", lambda values, allowed_codes=None: None)
    source = SimpleNamespace(
        incoterm_code="CIF",
        incoterm_version="2020",
        delivery_date=date(2026, 12, 1),
        delivery_place="Puerto de entrada",
        purchase_terms="Seguro incluido",
    )
    target = SimpleNamespace()

    copy_logistics(target, source, terms_field="purchase_terms")

    assert target.__dict__ == source.__dict__


def test_logistics_terms_field_is_restricted():
    """Solo los nombres de términos de compras y ventas son válidos."""
    with pytest.raises(ValueError, match="Campo de términos"):
        logistics_values(form={"terms": "no válido"}, terms_field="terms")


def test_incoterm_validation_accepts_injected_catalog_without_database_session():
    """La validación puede ejecutarse con un catálogo inyectado."""
    validate_incoterm({"incoterm_code": "X1", "incoterm_version": "2020"}, allowed_codes={"X1"})
    with pytest.raises(ValueError):
        validate_incoterm({"incoterm_code": "CIF", "incoterm_version": "2020"}, allowed_codes={"X1"})


def test_incompatible_logistics_are_rejected_before_comparison_order_creation():
    """El comparativo no combina cotizaciones con términos distintos."""
    first = SimpleNamespace(
        incoterm_code="CIF", incoterm_version="2020", delivery_date=None, delivery_place=None, purchase_terms=None
    )
    second = SimpleNamespace(
        incoterm_code="FOB", incoterm_version="2020", delivery_date=None, delivery_place=None, purchase_terms=None
    )

    with pytest.raises(ValueError, match="incompatibles"):
        ensure_compatible_logistics([first, second], terms_field="purchase_terms")


@pytest.mark.parametrize(
    "payload",
    [
        '{"concept": "Flete"}',
        '[{"amount": 10}]',
        '[{"concept": "Seguro", "amount": -1}]',
    ],
)
def test_landed_cost_snapshot_rejects_invalid_estimates(payload):
    """Los cargos sin concepto o negativos no pueden persistirse."""
    with pytest.raises(ValueError):
        _landed_cost_snapshot(form={"landed_cost_estimates_json": payload})
