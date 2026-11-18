# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1064: la prevalidación rechaza tarifas negativas.

La base impone `rate >= 0`; el importador debe reportar el error antes de
habilitar la ejecución y no dejar documentos parcialmente confirmados.
"""

from __future__ import annotations

from uuid import uuid4

import pytest

from cacao_accounting import create_app
from cacao_accounting.config import configuracion
from cacao_accounting.database import Currency, Entity, database
from cacao_accounting.imports.adapters.purchase_order import PurchaseOrderAdapter
from cacao_accounting.imports.adapters.transaction_documents import (
    TransactionDocumentAdapter,
    TransactionImportConfig,
)


@pytest.fixture
def negative_rate_scenario():
    """Create a company with a functional currency."""
    app = create_app(
        {
            **configuracion,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
            "WTF_CSRF_ENABLED": False,
            "TESTING": True,
            "MODO_ESCRITORIO": False,
        }
    )
    with app.app_context():
        database.create_all()
        database.session.add_all(
            [
                Currency(code="NIO", name="Córdoba", decimals=2, active=True, default=True),
                Entity(
                    code="alpha",
                    name="Alfa",
                    company_name=f"Compañía Alfa {uuid4().hex[:6]}",
                    tax_id=f"TAX-{uuid4().hex[:6]}",
                    currency="NIO",
                    enabled=True,
                    status="default",
                ),
            ]
        )
        database.session.commit()

    yield app

    with app.app_context():
        database.session.remove()
        database.engine.dispose()


def _transaction_adapter() -> TransactionDocumentAdapter:
    """Build the generic transaction adapter."""
    return TransactionDocumentAdapter(
        TransactionImportConfig(
            entity_type="purchase_request",
            header_model=object,
            item_model=object,
            parent_field="purchase_request_id",
        )
    )


@pytest.mark.parametrize("rate", ["-0.01", "-1"])
def test_transaction_row_rejects_negative_unit_price(negative_rate_scenario, rate):
    """The row reports the negative price."""
    app = negative_rate_scenario

    with app.app_context():
        errors = _transaction_adapter().validate_row({"document_ref": "PR-1", "cantidad": "1", "precio_unitario": rate})

    assert any("negativo" in error for error in errors)


def test_purchase_order_validation_rejects_negative_price(negative_rate_scenario):
    """The purchase-order prevalidation reports the same rule."""
    app = negative_rate_scenario
    row = {
        "document_ref": "PO-1",
        "fecha": "2026-05-10",
        "proveedor": "SUP-1",
        "producto": "ITEM-1",
        "cantidad": "1",
        "precio_unitario": "-1",
    }

    with app.app_context():
        errors = PurchaseOrderAdapter().validate_document([row], {"company_id": "alpha"})
        with pytest.raises(ValueError):
            PurchaseOrderAdapter().build_document([row], {"company_id": "alpha"})

    assert any("negativo" in error for error in errors)
