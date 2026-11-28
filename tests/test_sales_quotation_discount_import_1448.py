# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 William José Moreno Reyes

"""#1448: el esquema y el guardado usan descuento porcentual."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import uuid4

from sqlalchemy import select

from cacao_accounting.api.line_import_registry import LineImportSchemaRegistry
from cacao_accounting.database import Party, SalesQuotation, SalesQuotationItem, User, database
from cacao_accounting.document_identifiers import ensure_default_naming_series_for_company


def test_esquema_declara_descuento_porcentual():
    """La plantilla identifica la clave y la unidad del descuento."""
    schema = LineImportSchemaRegistry.get_schema("sales_quotation")
    assert schema is not None
    column = next(column for column in schema["columns"] if column["key"] == "discount_percentage")
    assert column["label"] == "Descuento %"
    assert "discount" in column["aliases"]
    assert "discount_percentage" in column["aliases"]


def test_cotizacion_guarda_descuento_importado(entorno_contable_aislado):
    """El POST real conserva 10% y calcula 90 sobre un bruto de 100."""
    app = entorno_contable_aislado.app
    marker = f"COT-DISC-{uuid4().hex[:8]}"
    with app.app_context():
        ensure_default_naming_series_for_company("cacao", ["sales_quotation"])
        customer_id = str(database.session.execute(select(Party.id).filter_by(code="CLI001")).scalar_one())
        admin_id = str(database.session.execute(select(User.id).filter_by(user="admin")).scalar_one())

    client = app.test_client()
    with client.session_transaction() as session:
        session["_user_id"] = admin_id
        session["_fresh"] = True
    response = client.post(
        "/sales/quotation/new",
        data={
            "company": "cacao",
            "currency": "NIO",
            "posting_date": date(2026, 5, 15).isoformat(),
            "customer_id": customer_id,
            "remarks": marker,
            "item_code_0": "ART01",
            "item_name_0": "Artículo comercial",
            "qty_0": "2",
            "rate_0": "50",
            "uom_0": "UND",
            "discount_percentage_0": "10",
        },
    )

    assert response.status_code == 302
    with app.app_context():
        quotation = database.session.execute(select(SalesQuotation).filter_by(remarks=marker)).scalar_one()
        line = database.session.execute(select(SalesQuotationItem).filter_by(sales_quotation_id=quotation.id)).scalar_one()
        assert line.discount_percentage == Decimal("10")
        assert line.discount_amount == Decimal("10")
        assert line.amount == Decimal("90")
        assert quotation.grand_total == Decimal("90")
