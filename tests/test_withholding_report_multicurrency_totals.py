# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1636: el reporte de retenciones no suma monedas distintas."""

from __future__ import annotations

import json
from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy.pool import StaticPool

from cacao_accounting import create_app
from cacao_accounting.config import configuracion
from cacao_accounting.database import (
    Currency,
    Entity,
    Party,
    PaymentEntry,
    WithholdingCertificate,
    database,
)
from cacao_accounting.reportes.helpers import _format_cell
from cacao_accounting.reportes.services import get_monthly_withholding_report


@pytest.fixture
def withholding_scene():
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
        database.session.flush()
        proveedor = Party(code=f"PROV-{sufijo}", name="Proveedor", is_supplier=True, is_active=True)
        database.session.add(proveedor)
        database.session.flush()
        for indice, moneda, importe in ((1, "USD", "10.00"), (2, "NIO", "100.00")):
            pago = PaymentEntry(
                company="cacao",
                posting_date=date(2026, 11, 10),
                payment_type="pay",
                currency=moneda,
                docstatus=1,
                party_type="supplier",
                party_id=proveedor.id,
                party_name=proveedor.name,
            )
            database.session.add(pago)
            database.session.flush()
            database.session.add(
                WithholdingCertificate(
                    company="cacao",
                    payment_id=pago.id,
                    supplier_id=proveedor.id,
                    supplier_name=proveedor.name,
                    certificate_no=f"CERT-{sufijo}-{indice}",
                    currency=moneda,
                    gross_amount=Decimal(importe),
                    withheld_amount=Decimal(importe),
                    cash_amount=Decimal("0"),
                    lines_json=json.dumps(
                        [
                            {
                                "concept": "Retención",
                                "base_amount": importe,
                                "rate": "10",
                                "amount": importe,
                            }
                        ]
                    ),
                    status="issued",
                    docstatus=1,
                    posting_date=date(2026, 11, 10),
                )
            )
        database.session.commit()
    yield application
    with application.app_context():
        database.session.remove()
        database.engine.dispose()


def test_totales_se_agrupan_por_moneda(withholding_scene):
    """USD y NIO se presentan separados en el total del reporte."""
    with withholding_scene.app_context():
        reporte = get_monthly_withholding_report("cacao", 2026, 11)
        totales = reporte.totals["withheld_amount"]

        assert len(reporte.rows) == 2
        assert totales == {"USD": Decimal("10.0000"), "NIO": Decimal("100.0000")}
        assert "110" not in _format_cell("withheld_amount", totales, None)
        assert "USD 10.00" in _format_cell("withheld_amount", totales, None)
        assert "NIO 100.00" in _format_cell("withheld_amount", totales, None)
