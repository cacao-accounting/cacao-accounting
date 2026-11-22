# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 William José Moreno Reyes

"""#1298: el proveedor no conserva una lista de precios sin consumidor.

Compras no lee `CompanyParty.default_price_list_id`; solo el flujo de ventas
consume la lista configurada del cliente. Por eso el proveedor no debe
persistir ni exponer una lista de compra inerte.
"""

from __future__ import annotations

import pytest
from sqlalchemy.pool import StaticPool

from cacao_accounting import create_app
from cacao_accounting.config import configuracion
from cacao_accounting.database import CompanyParty, Currency, Entity, Party, PriceList, database
from cacao_accounting.party_settings import (
    PartyCompanySettingsParams,
    build_party_company_settings,
    upsert_party_company_settings,
)


def _params(**overrides) -> PartyCompanySettingsParams:
    values = {
        "is_active": True,
        "receivable_account_id": None,
        "payable_account_id": None,
        "tax_template_id": None,
        "default_tax_rule_id": None,
        "default_price_list_id": None,
        "allow_purchase_invoice_without_order": False,
        "allow_purchase_invoice_without_receipt": False,
    }
    values.update(overrides)
    return PartyCompanySettingsParams(**values)


@pytest.fixture
def party_scene():
    """Create a dual-role party, a purchase list and a sales list."""
    application = create_app(
        {
            **configuracion,
            "SQLALCHEMY_DATABASE_URI": "sqlite://",
            "SQLALCHEMY_ENGINE_OPTIONS": {"poolclass": StaticPool, "connect_args": {"check_same_thread": False}},
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
                Currency(code="NIO", name="Córdoba", decimals=2, active=True, default=True),
                Entity(
                    code="cacao",
                    name="Cacao",
                    company_name="Cacao SA",
                    tax_id="TAX-1298",
                    currency="NIO",
                    enabled=True,
                    status="default",
                ),
                Party(code="TER-1298", name="Tercero", is_customer=True, is_supplier=True, is_active=True),
                PriceList(name="Compra 1298", company="cacao", currency="NIO", is_buying=True, is_active=True),
                PriceList(name="Venta 1298", company="cacao", currency="NIO", is_selling=True, is_active=True),
            ]
        )
        database.session.commit()
        party_id = database.session.execute(database.select(Party.id).filter_by(code="TER-1298")).scalar_one()
        buying_id = database.session.execute(database.select(PriceList.id).filter_by(name="Compra 1298")).scalar_one()
        selling_id = database.session.execute(database.select(PriceList.id).filter_by(name="Venta 1298")).scalar_one()
    yield application, {"party": party_id, "buying": buying_id, "selling": selling_id}
    with application.app_context():
        database.session.remove()
        database.engine.dispose()


def test_supplier_does_not_persist_price_list(party_scene):
    """A purchase list submitted for a supplier is ignored, not stored."""
    application, ids = party_scene
    with application.app_context():
        upsert_party_company_settings(ids["party"], "supplier", "cacao", _params(default_price_list_id=ids["buying"]))
        database.session.commit()
        link = database.session.execute(
            database.select(CompanyParty).filter_by(party_id=ids["party"], company="cacao")
        ).scalar_one()
        assert link.default_price_list_id is None

        settings = build_party_company_settings(ids["party"], "cacao", role="supplier")
        assert settings.default_price_list_id is None
        assert settings.default_price_list_label == ""


def test_customer_still_persists_sales_price_list(party_scene):
    """The customer keeps the sales list that sales pricing actually reads."""
    application, ids = party_scene
    with application.app_context():
        upsert_party_company_settings(ids["party"], "customer", "cacao", _params(default_price_list_id=ids["selling"]))
        database.session.commit()
        link = database.session.execute(
            database.select(CompanyParty).filter_by(party_id=ids["party"], company="cacao")
        ).scalar_one()
        assert link.default_price_list_id == ids["selling"]

        settings = build_party_company_settings(ids["party"], "cacao", role="customer")
        assert settings.default_price_list_id == ids["selling"]
        assert settings.default_price_list_label == "Venta 1298"


def test_supplier_form_drops_price_list_field():
    """The supplier form no longer declares an inert price list field."""
    from cacao_accounting.compras.forms import FormularioProveedor

    assert "default_price_list_id" not in FormularioProveedor()._fields
