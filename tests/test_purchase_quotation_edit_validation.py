# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Editar una RFQ inválida no responde 500 ni pierde el borrador.

Escenario de negocio (issue #1947): la edición borraba líneas y luego el
servicio lanzaba DocumentFlowError sin capturarlo.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy.pool import StaticPool

from cacao_accounting import create_app
from cacao_accounting.config import configuracion
from cacao_accounting.database import (
    Currency,
    Entity,
    Item,
    Modules,
    PurchaseQuotation,
    PurchaseQuotationItem,
    UOM,
    User,
    database,
)


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
            "MODO_ESCRITORIO": False,
        }
    )
    with application.app_context():
        database.create_all()
        database.session.add_all(
            [
                Modules(module="purchases", default=False, enabled=True),
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
                User(
                    id="admin",
                    user="admin",
                    name="Administrador",
                    password=b"x",
                    active=True,
                    classification="admin",
                ),
            ]
        )
        database.session.flush()
        database.session.add(UOM(code="UND", name="Unidad"))
        database.session.flush()
        database.session.add(
            Item(
                code="ART-1",
                name="Artículo",
                item_type="goods",
                is_stock_item=False,
                is_purchase_item=True,
                default_uom="UND",
                is_active=True,
            )
        )
        database.session.flush()
        quotation = PurchaseQuotation(
            company="cacao",
            posting_date=date(2026, 11, 5),
            docstatus=0,
            document_no="RFQ-1",
            transaction_currency="NIO",
        )
        database.session.add(quotation)
        database.session.flush()
        item = PurchaseQuotationItem(
            purchase_quotation_id=quotation.id,
            item_code="ART-1",
            item_name="Artículo",
            qty=Decimal("1"),
            uom="UND",
            rate=Decimal("0"),
            amount=Decimal("0"),
        )
        database.session.add(item)
        database.session.commit()
        ids = {"quotation": quotation.id, "item": item.id}
    return application, ids


def _cliente(application):
    client = application.test_client()
    with client.session_transaction() as session:
        session["_user_id"] = "admin"
        session["_fresh"] = True
    return client


@pytest.mark.parametrize(
    "lineas",
    [
        {},
        {"item_code_0": "ART-1", "item_name_0": "Artículo", "qty_0": "0", "uom_0": "UND"},
    ],
)
def test_edicion_invalida_conserva_el_borrador(lineas):
    """#1947: sin líneas o con cantidad <= 0 vuelve con redirect y conserva ítems."""
    application, ids = _crear_app()
    try:
        client = _cliente(application)
        datos = {"company": "cacao", "posting_date": "2026-11-05", **lineas}
        respuesta = client.post(f"/buying/request-for-quotation/{ids['quotation']}/edit", data=datos)

        assert respuesta.status_code == 302
        with application.app_context():
            quotation = database.session.get(PurchaseQuotation, ids["quotation"])
            items = (
                database.session.execute(
                    database.select(PurchaseQuotationItem).filter_by(purchase_quotation_id=ids["quotation"])
                )
                .scalars()
                .all()
            )
            assert quotation is not None
            assert len(items) == 1
            assert items[0].item_code == "ART-1"
    finally:
        with application.app_context():
            database.session.remove()
            database.engine.dispose()
