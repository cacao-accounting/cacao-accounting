# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1725: editar el rol proveedor conserva la lista de ventas del cliente.

`CompanyParty` es compartida por ambos roles. El formulario de proveedor no
edita la lista de precios de venta, por lo que guardar proveedor en un tercero
dual no debe borrar la lista que Ventas sí consume. El flujo se reproduce con
los mismos `MultiDict` que entregan las rutas a
`upsert_party_company_settings_rows()`.
"""

from __future__ import annotations

import pytest
from sqlalchemy.pool import StaticPool
from werkzeug.datastructures import MultiDict

from cacao_accounting import create_app
from cacao_accounting.config import configuracion
from cacao_accounting.database import (
    Accounts,
    CompanyParty,
    Currency,
    Entity,
    Party,
    PartyAccount,
    PriceList,
    database,
)
from cacao_accounting.party_settings import (
    build_party_company_settings,
    upsert_party_company_settings_rows,
)


@pytest.fixture
def party_scene():
    """Tercero dual, cuentas AR/AP y listas de compra/venta en la misma compañía."""
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
                    tax_id="TAX-1725",
                    currency="NIO",
                    enabled=True,
                    status="default",
                ),
            ]
        )
        database.session.flush()
        database.session.add_all(
            [
                Accounts(
                    entity="cacao",
                    code="110201",
                    name="Por cobrar",
                    account_type="receivable",
                    active=True,
                    enabled=True,
                    group=False,
                ),
                Accounts(
                    entity="cacao",
                    code="210101",
                    name="Por pagar",
                    account_type="payable",
                    active=True,
                    enabled=True,
                    group=False,
                ),
            ]
        )
        database.session.flush()
        database.session.add(Party(code="TER-1725", name="Tercero dual", is_customer=True, is_supplier=True))
        database.session.add_all(
            [
                PriceList(name="Venta 1725", company="cacao", currency="NIO", is_selling=True, is_active=True),
                PriceList(
                    name="Compra 1725", company="cacao", currency="NIO", is_buying=True, is_selling=False, is_active=True
                ),
            ]
        )
        database.session.commit()
        ids = {
            "party": database.session.execute(database.select(Party.id).filter_by(code="TER-1725")).scalar_one(),
            "receivable": database.session.execute(database.select(Accounts.id).filter_by(code="110201")).scalar_one(),
            "payable": database.session.execute(database.select(Accounts.id).filter_by(code="210101")).scalar_one(),
            "selling": database.session.execute(database.select(PriceList.id).filter_by(name="Venta 1725")).scalar_one(),
            "buying": database.session.execute(database.select(PriceList.id).filter_by(name="Compra 1725")).scalar_one(),
        }
    yield application, ids
    with application.app_context():
        database.session.remove()
        database.engine.dispose()


def _customer_form(ids: dict[str, str]) -> MultiDict:
    return MultiDict(
        [
            ("company", "cacao"),
            ("company_is_active", "on"),
            ("receivable_account_id", ids["receivable"]),
            ("default_price_list_id", ids["selling"]),
        ]
    )


def _supplier_form(ids: dict[str, str]) -> MultiDict:
    """Formulario de proveedor: sin lista de precios, con flags de compra."""
    return MultiDict(
        [
            ("company", "cacao"),
            ("company_is_active", "on"),
            ("payable_account_id", ids["payable"]),
            ("allow_purchase_invoice_without_order", "on"),
            ("allow_purchase_invoice_without_receipt", "on"),
        ]
    )


def _company_party(application, party_id: str) -> CompanyParty:
    with application.app_context():
        return database.session.execute(database.select(CompanyParty).filter_by(party_id=party_id)).scalar_one()


def _party_account(application, party_id: str) -> PartyAccount:
    with application.app_context():
        return database.session.execute(database.select(PartyAccount).filter_by(party_id=party_id)).scalar_one()


def test_editar_proveedor_conserva_lista_de_venta_y_cuenta_por_cobrar(party_scene):
    """La lista de venta y el AR del cliente sobreviven a un guardado de proveedor."""
    application, ids = party_scene
    with application.app_context():
        upsert_party_company_settings_rows(ids["party"], "customer", _customer_form(ids))
        database.session.commit()

        upsert_party_company_settings_rows(ids["party"], "supplier", _supplier_form(ids))
        database.session.commit()

    link = _company_party(application, ids["party"])
    assert link.default_price_list_id == ids["selling"]
    assert link.allow_purchase_invoice_without_order is True
    assert link.allow_purchase_invoice_without_receipt is True
    account = _party_account(application, ids["party"])
    assert account.receivable_account_id == ids["receivable"]
    assert account.payable_account_id == ids["payable"]

    with application.app_context():
        settings = build_party_company_settings(ids["party"], "cacao", role="customer")
    assert settings.default_price_list_id == ids["selling"]
    assert settings.default_price_list_label == "Venta 1725"


def test_editar_cliente_conserva_flags_de_compra(party_scene):
    """Guardar cliente no reinicia las preferencias de factura del proveedor."""
    application, ids = party_scene
    with application.app_context():
        upsert_party_company_settings_rows(ids["party"], "supplier", _supplier_form(ids))
        database.session.commit()

        upsert_party_company_settings_rows(ids["party"], "customer", _customer_form(ids))
        database.session.commit()

    link = _company_party(application, ids["party"])
    assert link.allow_purchase_invoice_without_order is True
    assert link.allow_purchase_invoice_without_receipt is True
    assert link.default_price_list_id == ids["selling"]
    account = _party_account(application, ids["party"])
    assert account.receivable_account_id == ids["receivable"]
    assert account.payable_account_id == ids["payable"]


def test_lista_invalida_no_borra_la_lista_de_venta(party_scene):
    """Una validación fallida no altera la preferencia ya persistida."""
    application, ids = party_scene
    with application.app_context():
        upsert_party_company_settings_rows(ids["party"], "customer", _customer_form(ids))
        database.session.commit()

        invalido = MultiDict(
            [
                ("company", "cacao"),
                ("company_is_active", "on"),
                ("default_price_list_id", ids["buying"]),
            ]
        )
        with pytest.raises(ValueError):
            upsert_party_company_settings_rows(ids["party"], "customer", invalido)
        database.session.rollback()

    assert _company_party(application, ids["party"]).default_price_list_id == ids["selling"]
