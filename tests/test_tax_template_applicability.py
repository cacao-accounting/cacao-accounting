# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""La aplicabilidad del impuesto se valida al guardar y al calcular."""

from __future__ import annotations

from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import pytest

from cacao_accounting.database import Modules, Tax, TaxTemplate, TaxTemplateItem, database
from cacao_accounting.tax_pricing_service import TaxPricingError, calculate_taxes


@pytest.fixture
def configuracion_fiscal(app):
    """Crea registros fiscales aislados para las pruebas de aplicabilidad."""
    registros: dict[str, str] = {}

    def crear(template_type: str, applies_to: str) -> tuple[str, str]:
        sufijo = uuid4().hex[:10]
        with app.app_context():
            module = database.session.execute(database.select(Modules).filter_by(module="admin")).scalar_one_or_none()
            if module is None:
                database.session.add(Modules(module="admin", default=False, enabled=True))
            else:
                module.enabled = True
            tax = Tax(name=f"Tax applicability {sufijo}", tax_type="percentage", applies_to=applies_to, rate=15)
            template = TaxTemplate(name=f"Template applicability {sufijo}", company="cacao", template_type=template_type)
            database.session.add_all([tax, template])
            database.session.commit()
            registros[template.id] = tax.id
            return template.id, tax.id

    yield crear

    with app.app_context():
        for template_id, tax_id in registros.items():
            database.session.execute(database.delete(TaxTemplateItem).where(TaxTemplateItem.tax_template_id == template_id))
            template = database.session.get(TaxTemplate, template_id)
            tax = database.session.get(Tax, tax_id)
            if template:
                database.session.delete(template)
            if tax:
                database.session.delete(tax)
        database.session.commit()


@pytest.mark.parametrize(
    ("template_type", "applies_to", "valid"),
    [
        ("buying", "purchase", True),
        ("buying", "sales", False),
        ("selling", "sales", True),
        ("selling", "purchase", False),
        ("buying", "both", True),
        ("selling", "both", True),
        ("unknown", "both", False),
    ],
)
def test_admin_restringe_impuestos_a_la_aplicabilidad_de_plantilla(
    app, authenticated_client, configuracion_fiscal, template_type, applies_to, valid
):
    """El formulario acepta solo impuestos compatibles y no persiste cruces inválidos."""
    template_id, tax_id = configuracion_fiscal(template_type, applies_to)
    client = authenticated_client("admin")

    response = client.post(
        f"/settings/tax-templates/{template_id}/items",
        data={"tax_id": tax_id, "sequence": "10", "calculation_base": "net_document", "behavior": "additive"},
    )

    assert response.status_code == 302
    with app.app_context():
        lines = (
            database.session.execute(database.select(TaxTemplateItem).filter_by(tax_template_id=template_id)).scalars().all()
        )
        assert len(lines) == int(valid)


@pytest.mark.parametrize(
    ("template_type", "applies_to", "valid"),
    [
        ("buying", "purchase", True),
        ("buying", "sales", False),
        ("selling", "sales", True),
        ("selling", "purchase", False),
        ("buying", "both", True),
        ("selling", "both", True),
        ("unknown", "both", False),
    ],
)
def test_calculo_revalida_aplicabilidad_de_lineas_existentes(app, configuracion_fiscal, template_type, applies_to, valid):
    """La configuración heredada incompatible falla antes de producir importes."""
    template_id, tax_id = configuracion_fiscal(template_type, applies_to)
    with app.app_context():
        database.session.add(TaxTemplateItem(tax_template_id=template_id, tax_id=tax_id, sequence=10))
        database.session.commit()
        documento = SimpleNamespace(company="cacao", _tax_items=[SimpleNamespace(amount=Decimal("100"))])

        if valid:
            result = calculate_taxes(documento, template_id)
            assert result.lines[0].amount == Decimal("15.0000")
        else:
            with pytest.raises(TaxPricingError, match="no es aplicable"):
                calculate_taxes(documento, template_id)


def test_selector_admin_solo_muestra_impuestos_compatibles(app, authenticated_client, configuracion_fiscal):
    """El selector no ofrece impuestos activos de la operación contraria."""
    template_id, _tax_id = configuracion_fiscal("buying", "purchase")
    _incompatible_template_id, incompatible_tax_id = configuracion_fiscal("buying", "sales")
    client = authenticated_client("admin")

    response = client.get(f"/settings/tax-templates/{template_id}/items")

    assert response.status_code == 200
    assert incompatible_tax_id.encode() not in response.data
