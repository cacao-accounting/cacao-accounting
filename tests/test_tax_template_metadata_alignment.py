# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""La plantilla fiscal conserva la base de cada impuesto activo.

Escenario de negocio (issue #2020): ``calculate_taxes`` omite impuestos
inactivos, pero el adaptador alineaba por índice con la lista completa. Con
una fila inactiva anterior, el impuesto activo heredaba la base equivocada.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from types import SimpleNamespace

from sqlalchemy.pool import StaticPool

from cacao_accounting import create_app
from cacao_accounting.accounting_engine.document_builders import _tax_rules_from_template
from cacao_accounting.config import configuracion
from cacao_accounting.database import (
    Currency,
    Entity,
    Tax,
    TaxTemplate,
    TaxTemplateItem,
    database,
)
from cacao_accounting.tax_pricing_service import calculate_taxes

FECHA = date(2026, 10, 15)


def _crear_app():
    application = create_app(
        {
            **configuracion,
            "SQLALCHEMY_DATABASE_URI": "sqlite://",
            "SQLALCHEMY_ENGINE_OPTIONS": {
                "poolclass": StaticPool,
                "connect_args": {"check_same_thread": False},
            },
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
            "WTF_CSRF_ENABLED": False,
            "TESTING": True,
            "MODO_ESCRITORIO": True,
        }
    )
    with application.app_context():
        database.create_all()
        database.session.add_all(
            [
                Currency(code="NIO", name="Córdoba", decimals=2, active=True, default=True),
                Entity(
                    code="cacao",
                    name="Cacao",
                    company_name="Cacao SA",
                    tax_id="J0001",
                    currency="NIO",
                    enabled=True,
                    status="default",
                ),
                Tax(
                    id="TAX-INACTIVE",
                    name="Impuesto inactivo",
                    rate=10,
                    tax_type="percentage",
                    applies_to="sales",
                    is_active=False,
                ),
                Tax(
                    id="TAX-ACTIVE",
                    name="Impuesto activo",
                    rate=20,
                    tax_type="percentage",
                    applies_to="sales",
                    is_active=True,
                ),
            ]
        )
        database.session.flush()
        plantilla = TaxTemplate(
            name="Plantilla de venta",
            company="cacao",
            template_type="selling",
            currency="NIO",
        )
        database.session.add(plantilla)
        database.session.flush()
        database.session.add_all(
            [
                TaxTemplateItem(
                    tax_template_id=plantilla.id,
                    tax_id="TAX-INACTIVE",
                    sequence=10,
                    calculation_base="net_document",
                    behavior="additive",
                    is_inclusive=False,
                ),
                TaxTemplateItem(
                    tax_template_id=plantilla.id,
                    tax_id="TAX-ACTIVE",
                    sequence=20,
                    calculation_base="previous_total",
                    behavior="deductive",
                    is_inclusive=True,
                ),
            ]
        )
        database.session.commit()
        return application, plantilla.id


def test_el_impuesto_activo_conserva_su_base():
    """Un inactivo previo no desplaza la base del activo."""
    application, template_id = _crear_app()
    try:
        with application.app_context():
            documento = SimpleNamespace(
                company="cacao",
                tax_template_id=template_id,
                _tax_items=[SimpleNamespace(amount=Decimal("100"))],
            )
            resultado = calculate_taxes(documento, template_id)
            assert len(resultado.lines) == 1
            assert resultado.lines[0].tax_id == "TAX-ACTIVE"

            reglas = _tax_rules_from_template(documento, resultado, "sales_invoice")

            assert len(reglas) == 1
            assert reglas[0].rule_id == "TAX-ACTIVE"
            assert reglas[0].base_mode == "accumulated"
            assert reglas[0].calculation_method == "percentage"
            assert reglas[0].included_in_price is True
    finally:
        with application.app_context():
            database.session.remove()
            database.engine.dispose()
