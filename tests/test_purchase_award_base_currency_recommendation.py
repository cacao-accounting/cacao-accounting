# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1594: la adjudicación compara tarifas en la moneda base del servidor."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy.pool import StaticPool

from cacao_accounting import create_app
from cacao_accounting.compras.purchase_sourcing_service import (
    PurchaseSourcingError,
    create_purchase_quotation_award,
)
from cacao_accounting.config import configuracion
from cacao_accounting.database import (
    Currency,
    Entity,
    Item,
    Modules,
    PurchaseQuotation,
    PurchaseQuotationAwardItem,
    PurchaseQuotationItem,
    SupplierQuotation,
    SupplierQuotationItem,
    UOM,
    User,
    database,
)


def _crear_escenario(tmp_path):
    """Crea una RFQ con una oferta USD más barata nominalmente pero más cara en NIO."""
    application = create_app(
        {
            **configuracion,
            "SQLALCHEMY_DATABASE_URI": f"sqlite:///{tmp_path / f'sourcing-{uuid4().hex[:6]}.db'}",
            "SQLALCHEMY_ENGINE_OPTIONS": {"poolclass": StaticPool},
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
            "TESTING": True,
            "MODO_ESCRITORIO": True,
            "WTF_CSRF_ENABLED": False,
        }
    )
    with application.app_context():
        database.create_all()
        database.session.add_all(
            [
                Modules(module="purchases", default=True, enabled=True),
                Currency(code="NIO", name="Córdoba", decimals=2, active=True, default=True),
                Currency(code="USD", name="Dólar", decimals=2, active=True, default=False),
                Entity(
                    code="cacao",
                    name="Cacao",
                    company_name="Cacao SA",
                    tax_id=f"J-{uuid4().hex[:6]}",
                    currency="NIO",
                    enabled=True,
                    status="default",
                ),
                User(id="admin", user="admin", name="Administrador", password=b"x", active=True, classification="admin"),
                UOM(code="UND", name="Unidad"),
            ]
        )
        database.session.flush()
        database.session.add(Item(code="ART-1", name="Artículo", item_type="goods", is_stock_item=True, default_uom="UND"))
        database.session.flush()
        rfq = PurchaseQuotation(
            company="cacao",
            posting_date=date(2026, 11, 19),
            docstatus=1,
            document_no="RFQ-1594",
            transaction_currency="NIO",
        )
        database.session.add(rfq)
        database.session.flush()
        rfq_item = PurchaseQuotationItem(
            purchase_quotation_id=rfq.id,
            item_code="ART-1",
            qty=Decimal("5"),
            uom="UND",
            qty_in_base_uom=Decimal("5"),
        )
        database.session.add(rfq_item)
        database.session.flush()
        ofertas = {}
        for codigo, rate, currency, exchange_rate in (
            ("USD-OFFER", "10", "USD", "36.5"),
            ("NIO-OFFER", "300", "NIO", "1"),
        ):
            oferta = SupplierQuotation(
                company="cacao",
                posting_date=date(2026, 11, 19),
                docstatus=1,
                document_no=codigo,
                purchase_quotation_id=rfq.id,
                transaction_currency=currency,
                exchange_rate=Decimal(exchange_rate),
            )
            database.session.add(oferta)
            database.session.flush()
            database.session.add(
                SupplierQuotationItem(
                    supplier_quotation_id=oferta.id,
                    item_code="ART-1",
                    qty=Decimal("5"),
                    uom="UND",
                    qty_in_base_uom=Decimal("5"),
                    rate=Decimal(rate),
                )
            )
            ofertas[codigo] = oferta.id
        database.session.commit()
        return application, {"rfq": rfq.id, "rfq_item": rfq_item.id, **ofertas}


@pytest.fixture
def escenario_tarifas(tmp_path):
    application, ids = _crear_escenario(tmp_path)
    yield application, ids
    with application.app_context():
        database.session.remove()
        database.engine.dispose()


def test_oferta_usd_mas_cara_en_moneda_base_exige_justificacion(escenario_tarifas):
    """USD 10 con tasa 36.5 equivale a 365 NIO y supera la oferta de 300 NIO."""
    application, ids = escenario_tarifas
    with application.app_context():
        rfq = database.session.get(PurchaseQuotation, ids["rfq"])
        with pytest.raises(PurchaseSourcingError, match="no recomendada"):
            create_purchase_quotation_award(rfq, {ids["rfq_item"]: ids["USD-OFFER"]}, "admin")

        award = create_purchase_quotation_award(
            rfq,
            {ids["rfq_item"]: ids["USD-OFFER"]},
            "admin",
            "Compra urgente con proveedor internacional",
        )
        database.session.commit()
        linea = database.session.execute(database.select(PurchaseQuotationAwardItem).filter_by(award_id=award.id)).scalar_one()
        assert linea.manual_override is True
        assert linea.override_reason == "Compra urgente con proveedor internacional"


def test_oferta_nio_recomendada_no_exige_justificacion(escenario_tarifas):
    """La oferta de 300 NIO es la menor en moneda base y no requiere motivo."""
    application, ids = escenario_tarifas
    with application.app_context():
        rfq = database.session.get(PurchaseQuotation, ids["rfq"])
        award = create_purchase_quotation_award(rfq, {ids["rfq_item"]: ids["NIO-OFFER"]}, "admin")
        database.session.commit()
        linea = database.session.execute(database.select(PurchaseQuotationAwardItem).filter_by(award_id=award.id)).scalar_one()
        assert linea.manual_override is False
        assert linea.override_reason is None
