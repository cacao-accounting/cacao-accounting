# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Validación y persistencia de la configuración de terceros por compañía.

Escenario de negocio (issue #2130): la configuración aceptaba reglas y
plantillas que el motor nunca aplicaría, borraba campos extendidos al guardar
el formulario básico y autorizaba vínculos de compañía desactivados.
"""

from __future__ import annotations

import pytest
from sqlalchemy.pool import StaticPool

from cacao_accounting import create_app
from cacao_accounting.config import configuracion
from cacao_accounting.database import (
    Accounts,
    CompanyParty,
    Currency,
    Entity,
    Party,
    PartyAccount,
    TaxRule,
    TaxTemplate,
    database,
)
from cacao_accounting.party_management import filtrar_parties_por_companias, tercero_tiene_vinculo_autorizado
from cacao_accounting.party_settings import PartyCompanySettingsParams, upsert_party_company_settings


def _params(**overrides) -> PartyCompanySettingsParams:
    valores = {
        "is_active": True,
        "receivable_account_id": None,
        "payable_account_id": None,
        "tax_template_id": None,
        "default_tax_rule_id": None,
        "default_price_list_id": None,
        "allow_purchase_invoice_without_order": False,
        "allow_purchase_invoice_without_receipt": False,
    }
    valores.update(overrides)
    return PartyCompanySettingsParams(**valores)


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
                Currency(code="NIO", name="Córdoba", decimals=2, active=True, default=True),
                Currency(code="USD", name="Dólar", decimals=2, active=True, default=False),
            ]
        )
        database.session.flush()
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
        party = Party(code="CLI-1", name="Cliente", is_customer=True, is_supplier=True)
        database.session.add(party)
        database.session.flush()
        ids = {
            "party": party.id,
            "receivable": database.session.execute(database.select(Accounts).filter_by(code="110201")).scalar_one().id,
            "payable": database.session.execute(database.select(Accounts).filter_by(code="210101")).scalar_one().id,
        }
        database.session.commit()
    return application, ids


def _tax_template(company: str, template_type: str, active: bool = True) -> str:
    template = TaxTemplate(
        name=f"Plantilla {template_type}",
        company=company,
        template_type=template_type,
        is_active=active,
    )
    database.session.add(template)
    database.session.flush()
    return template.id


def _tax_rule(company: str, **overrides) -> str:
    valores = {
        "company": company,
        "name": "Regla",
        "concept": "iva",
        "applies_to": "purchase",
        "tax_type": "withholding",
        "recognition_event": "payment_confirmed",
        "is_active": True,
    }
    valores.update(overrides)
    rule = TaxRule(**valores)
    database.session.add(rule)
    database.session.flush()
    return rule.id


def test_plantilla_debe_estar_activa_y_corresponder_al_rol():
    """#2130: rechaza plantillas inactivas o del tipo opuesto al rol."""
    application, ids = _crear_app()
    try:
        with application.app_context():
            compra = _tax_template("cacao", "buying", active=False)
            with pytest.raises(ValueError, match="no esta activa"):
                upsert_party_company_settings(ids["party"], "supplier", "cacao", _params(tax_template_id=compra))

            venta = _tax_template("cacao", "selling")
            with pytest.raises(ValueError, match="no corresponde al tipo de tercero"):
                upsert_party_company_settings(ids["party"], "supplier", "cacao", _params(tax_template_id=venta))

            compra_activa = _tax_template("cacao", "buying")
            upsert_party_company_settings(ids["party"], "supplier", "cacao", _params(tax_template_id=compra_activa))
            database.session.commit()
            config = database.session.execute(database.select(CompanyParty)).scalar_one()
            assert config.tax_template_id == compra_activa
    finally:
        with application.app_context():
            database.session.remove()
            database.engine.dispose()


def test_regla_de_proveedor_debe_ser_retencion_al_pagar():
    """#2130: el consumidor solo aplica withholding con evento de pago."""
    application, ids = _crear_app()
    try:
        with application.app_context():
            no_retencion = _tax_rule("cacao", tax_type="tax")
            with pytest.raises(ValueError, match="debe ser una retención"):
                upsert_party_company_settings(ids["party"], "supplier", "cacao", _params(default_tax_rule_id=no_retencion))

            evento_incorrecto = _tax_rule("cacao", recognition_event="invoice")
            with pytest.raises(ValueError, match="debe reconocerse al pagar"):
                upsert_party_company_settings(
                    ids["party"], "supplier", "cacao", _params(default_tax_rule_id=evento_incorrecto)
                )

            valida = _tax_rule("cacao")
            upsert_party_company_settings(ids["party"], "supplier", "cacao", _params(default_tax_rule_id=valida))
            database.session.commit()
            config = database.session.execute(database.select(CompanyParty)).scalar_one()
            assert config.default_tax_rule_id == valida
    finally:
        with application.app_context():
            database.session.remove()
            database.engine.dispose()


def test_cliente_conserva_su_regla_venta():
    """#2130: la validación de retención aplica solo al rol proveedor."""
    application, ids = _crear_app()
    try:
        with application.app_context():
            regla_venta = _tax_rule("cacao", applies_to="sales", tax_type="tax", recognition_event="invoice")
            upsert_party_company_settings(ids["party"], "customer", "cacao", _params(default_tax_rule_id=regla_venta))
            database.session.commit()
            config = database.session.execute(database.select(CompanyParty)).scalar_one()
            assert config.default_tax_rule_id == regla_venta
    finally:
        with application.app_context():
            database.session.remove()
            database.engine.dispose()


def test_conserva_los_campos_extendidos_al_guardar_el_formulario():
    """#2130: el guardado básico no reinicia moneda, centro de costo ni banco."""
    application, ids = _crear_app()
    try:
        with application.app_context():
            upsert_party_company_settings(ids["party"], "customer", "cacao", _params())
            config = database.session.execute(database.select(CompanyParty)).scalar_one()
            config.default_currency = "USD"
            config.default_cost_center = "CC-1"
            config.default_business_unit = "UND-1"
            config.default_bank_name = "Banco"
            config.default_bank_account_no = "123"
            config.default_bank_iban = "NI00"
            config.block_overdue = True
            database.session.commit()

            upsert_party_company_settings(ids["party"], "customer", "cacao", _params())
            database.session.commit()

            config = database.session.execute(database.select(CompanyParty)).scalar_one()
            assert config.default_currency == "USD"
            assert config.default_cost_center == "CC-1"
            assert config.default_business_unit == "UND-1"
            assert config.default_bank_name == "Banco"
            assert config.default_bank_account_no == "123"
            assert config.default_bank_iban == "NI00"
            assert config.block_overdue is True
    finally:
        with application.app_context():
            database.session.remove()
            database.engine.dispose()


def test_update_extended_explicito_permite_limpiar_campos():
    """#2130: un llamador que edita los campos extendidos sí puede cambiarlos."""
    application, ids = _crear_app()
    try:
        with application.app_context():
            upsert_party_company_settings(ids["party"], "customer", "cacao", _params())
            config = database.session.execute(database.select(CompanyParty)).scalar_one()
            config.default_currency = "USD"
            config.block_overdue = True
            database.session.commit()

            upsert_party_company_settings(
                ids["party"],
                "customer",
                "cacao",
                _params(),
                update_extended=True,
            )
            database.session.commit()

            config = database.session.execute(database.select(CompanyParty)).scalar_one()
            assert config.default_currency is None
            assert config.block_overdue is False
    finally:
        with application.app_context():
            database.session.remove()
            database.engine.dispose()


def test_conserva_las_cuentas_del_rol_opuesto():
    """#2130: guardar proveedor no borra la cuenta por cobrar (y viceversa)."""
    application, ids = _crear_app()
    try:
        with application.app_context():
            database.session.add(
                PartyAccount(
                    party_id=ids["party"],
                    company="cacao",
                    receivable_account_id=ids["receivable"],
                    payable_account_id=ids["payable"],
                )
            )
            database.session.commit()

            upsert_party_company_settings(ids["party"], "supplier", "cacao", _params(payable_account_id=ids["payable"]))
            database.session.commit()
            cuenta = database.session.execute(database.select(PartyAccount)).scalar_one()
            assert cuenta.receivable_account_id == ids["receivable"]
            assert cuenta.payable_account_id == ids["payable"]

            upsert_party_company_settings(ids["party"], "customer", "cacao", _params(receivable_account_id=ids["receivable"]))
            database.session.commit()
            cuenta = database.session.execute(database.select(PartyAccount)).scalar_one()
            assert cuenta.receivable_account_id == ids["receivable"]
            assert cuenta.payable_account_id == ids["payable"]
    finally:
        with application.app_context():
            database.session.remove()
            database.engine.dispose()


@pytest.mark.parametrize(("activo", "autorizado"), [(False, False), (True, True)])
def test_solo_el_vinculo_activo_autoriza(activo, autorizado):
    """#2130: un CompanyParty desactivado no autoriza ni aparece en consultas."""
    application, ids = _crear_app()
    try:
        with application.app_context():
            database.session.add(CompanyParty(company="cacao", party_id=ids["party"], is_active=activo))
            database.session.commit()

            assert tercero_tiene_vinculo_autorizado(ids["party"], ["cacao"]) is autorizado
            visibles = (
                database.session.execute(filtrar_parties_por_companias(database.select(Party), ["cacao"])).scalars().all()
            )
            assert (ids["party"] in {party.id for party in visibles}) is autorizado
    finally:
        with application.app_context():
            database.session.remove()
            database.engine.dispose()
