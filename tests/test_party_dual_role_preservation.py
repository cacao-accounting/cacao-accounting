# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Configuración compartida de un tercero cliente y proveedor.

Escenario de negocio: un tercero puede ser cliente y proveedor a la vez. La
edición del rol cliente no debe borrar el vínculo ``CompanyParty``, las
preferencias de factura de compra ni la cuenta por pagar del proveedor; la
edición del rol proveedor tampoco debe borrar la cuenta por cobrar del cliente.
"""

from __future__ import annotations

import pytest
from werkzeug.datastructures import MultiDict

from cacao_accounting import create_app
from cacao_accounting.config import configuracion
from cacao_accounting.database import (
    Accounts,
    CompanyParty,
    Entity,
    Party,
    PartyAccount,
    database,
)
from cacao_accounting.party_settings import upsert_party_company_settings_rows


@pytest.fixture
def tercero_dual():
    """Tercero dual con vínculo, cuentas AR/AP y preferencias de compra."""
    application = create_app(
        {
            **configuracion,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
            "WTF_CSRF_ENABLED": False,
            "TESTING": True,
            "MODO_ESCRITORIO": True,
        }
    )
    with application.app_context():
        database.create_all()
        database.session.add(
            Entity(
                code="cacao",
                name="Cacao",
                company_name="Cacao SA",
                tax_id="J0001",
                currency="NIO",
                enabled=True,
                status="default",
            )
        )
        database.session.flush()
        por_cobrar = Accounts(
            code="1.01.03.001",
            name="Cuentas por cobrar",
            entity="cacao",
            group=False,
            active=True,
            enabled=True,
            account_type="receivable",
        )
        por_pagar = Accounts(
            code="2.01.01.001",
            name="Cuentas por pagar",
            entity="cacao",
            group=False,
            active=True,
            enabled=True,
            account_type="payable",
        )
        tercero = Party(code="DUAL-1", name="Tercero Dual", is_customer=True, is_supplier=True)
        solo_cliente = Party(code="CLI-1", name="Solo Cliente", is_customer=True, is_supplier=False)
        database.session.add_all([por_cobrar, por_pagar, tercero, solo_cliente])
        database.session.flush()
        database.session.add(
            CompanyParty(
                company="cacao",
                party_id=tercero.id,
                is_active=True,
                allow_purchase_invoice_without_order=True,
                allow_purchase_invoice_without_receipt=True,
            )
        )
        database.session.add(
            PartyAccount(
                party_id=tercero.id,
                company="cacao",
                receivable_account_id=por_cobrar.id,
                payable_account_id=por_pagar.id,
            )
        )
        database.session.add(CompanyParty(company="cacao", party_id=solo_cliente.id, is_active=True))
        database.session.add(PartyAccount(party_id=solo_cliente.id, company="cacao", receivable_account_id=por_cobrar.id))
        database.session.commit()
        ids = {
            "tercero": tercero.id,
            "cobrar": por_cobrar.id,
            "pagar": por_pagar.id,
            "solo_cliente": solo_cliente.id,
        }
    yield application, ids
    with application.app_context():
        database.session.remove()
        database.engine.dispose()


def _estado(application, party_id: str):
    with application.app_context():
        vinculo = database.session.execute(database.select(CompanyParty).filter_by(party_id=party_id)).scalar_one_or_none()
        cuentas = database.session.execute(database.select(PartyAccount).filter_by(party_id=party_id)).scalar_one_or_none()
        return vinculo, cuentas


def test_editar_cliente_conserva_preferencias_y_cuenta_pagar(tercero_dual):
    """Guardar el rol cliente no reinicia los flags ni borra la cuenta AP."""
    application, ids = tercero_dual
    formulario = MultiDict(
        [
            ("company", "cacao"),
            ("company_is_active", "on"),
            ("receivable_account_id", ids["cobrar"]),
        ]
    )

    with application.app_context():
        upsert_party_company_settings_rows(ids["tercero"], "customer", formulario)
        database.session.commit()

    vinculo, cuentas = _estado(application, ids["tercero"])
    assert vinculo is not None
    assert vinculo.allow_purchase_invoice_without_order is True
    assert vinculo.allow_purchase_invoice_without_receipt is True
    assert cuentas.receivable_account_id == ids["cobrar"]
    assert cuentas.payable_account_id == ids["pagar"]


def test_editar_cliente_sin_filas_no_borra_el_vinculo_compartido(tercero_dual):
    """Omitir compañías en el formulario de cliente no elimina el vínculo."""
    application, ids = tercero_dual

    with application.app_context():
        upsert_party_company_settings_rows(ids["tercero"], "customer", MultiDict([]))
        database.session.commit()

    vinculo, cuentas = _estado(application, ids["tercero"])
    assert vinculo is not None
    assert vinculo.is_active is True
    assert cuentas is not None
    assert cuentas.payable_account_id == ids["pagar"]


def test_cliente_sin_rol_proveedor_si_elimina_su_vinculo(tercero_dual):
    """Control de alcance: un tercero solo cliente conserva el borrado normal."""
    application, ids = tercero_dual

    with application.app_context():
        upsert_party_company_settings_rows(ids["solo_cliente"], "customer", MultiDict([]))
        database.session.commit()

    vinculo, cuentas = _estado(application, ids["solo_cliente"])
    assert vinculo is None
    assert cuentas is None


def test_editar_proveedor_conserva_la_cuenta_por_cobrar(tercero_dual):
    """Guardar el rol proveedor no borra la cuenta AR del cliente."""
    application, ids = tercero_dual
    formulario = MultiDict(
        [
            ("company", "cacao"),
            ("company_is_active", "on"),
            ("payable_account_id", ids["pagar"]),
            ("allow_purchase_invoice_without_order", "on"),
            ("allow_purchase_invoice_without_receipt", "on"),
        ]
    )

    with application.app_context():
        upsert_party_company_settings_rows(ids["tercero"], "supplier", formulario)
        database.session.commit()

    _, cuentas = _estado(application, ids["tercero"])
    assert cuentas.receivable_account_id == ids["cobrar"]
    assert cuentas.payable_account_id == ids["pagar"]
