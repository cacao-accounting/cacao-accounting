# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1635: el payload fiscal solo puede usar reglas aplicables y completas."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import pytest
from sqlalchemy.pool import StaticPool

from cacao_accounting import create_app
from cacao_accounting.config import configuracion
from cacao_accounting.database import Currency, Entity, TaxRule, database
from cacao_accounting.fiscal_persistence_service import calculate_document_total_with_taxes


@pytest.fixture
def tax_rule_scene():
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
                Currency(code="USD", name="Dólar", decimals=2, active=True, default=False),
                Entity(
                    code="cacao",
                    name="Cacao",
                    company_name="Cacao SA",
                    tax_id=f"J-{sufijo}",
                    currency="NIO",
                    enabled=True,
                    status="default",
                ),
            ]
        )
        database.session.commit()
    yield application
    with application.app_context():
        database.session.remove()
        database.engine.dispose()


def _regla(**overrides) -> TaxRule:
    valores = {
        "company": "cacao",
        "name": "IVA venta",
        "applies_to": "sales",
        "concept": "IVA",
        "tax_type": "tax",
        "calculation_method": "percentage",
        "rate": Decimal("15"),
        "recognition_event": "sales_invoice_confirmed",
        "currency": "NIO",
        "is_active": True,
    }
    valores.update(overrides)
    regla = TaxRule(**valores)
    database.session.add(regla)
    database.session.commit()
    return regla


def _documento() -> SimpleNamespace:
    return SimpleNamespace(
        company="cacao",
        document_type="sales_invoice",
        posting_date=date(2026, 5, 15),
        transaction_currency="NIO",
    )


def _payload(rule_id: str) -> list[dict[str, str]]:
    return [{"source_rule_id": rule_id}]


@pytest.mark.parametrize(
    "overrides",
    [
        {"applies_to": "purchase", "recognition_event": "purchase_invoice_confirmed"},
        {"recognition_event": "purchase_invoice_confirmed"},
        {"currency": "USD"},
        {"valid_to": date(2026, 4, 30)},
    ],
)
def test_rechaza_regla_no_aplicable_al_documento(tax_rule_scene, overrides):
    """Tipo, evento, moneda o vigencia incompatible no alteran el total."""
    with tax_rule_scene.app_context():
        regla = _regla(**overrides)
        with pytest.raises(ValueError, match="no corresponde a este documento"):
            calculate_document_total_with_taxes(_documento(), Decimal("100"), [], tax_lines_payload=_payload(regla.id))


def test_rechaza_payload_que_omite_reglas_aplicables(tax_rule_scene):
    """Una línea manual no puede suprimir el impuesto resuelto por el servidor."""
    with tax_rule_scene.app_context():
        _regla()
        manual = [{"manual": True, "concept": "Ajuste", "amount": "0"}]

        with pytest.raises(ValueError, match="Faltan reglas fiscales aplicables"):
            calculate_document_total_with_taxes(_documento(), Decimal("100"), [], tax_lines_payload=manual)


def test_aplica_la_regla_de_venta_correcta(tax_rule_scene):
    """La regla vigente de venta sigue calculando el total esperado."""
    with tax_rule_scene.app_context():
        regla = _regla()
        total = calculate_document_total_with_taxes(_documento(), Decimal("100"), [], tax_lines_payload=_payload(regla.id))

        assert total == Decimal("115.00")
