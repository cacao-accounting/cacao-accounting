# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Referencias y compañía de las reglas fiscales.

Escenario de negocio: una regla fiscal solo puede asociarse a una compañía,
moneda y cuenta contable existentes, y la cuenta debe pertenecer a la compañía
de la regla. Un POST de configuración no debe dejar reglas que luego el motor
fiscal rechace.
"""

from __future__ import annotations

from datetime import date

import pytest
from sqlalchemy import text

from cacao_accounting import create_app
from cacao_accounting.accounting_engine.document_builders import PaymentBuildSpec, _payment_tax_rules
from cacao_accounting.auth import proteger_passwd
from cacao_accounting.config import configuracion
from cacao_accounting.database import (
    Accounts,
    CompanyParty,
    Currency,
    Entity,
    Modules,
    Party,
    PaymentEntry,
    TaxRule,
    User,
    database,
)
from cacao_accounting.tax_rule_service import TaxRuleServiceError, create_tax_rule

BASE = {
    "name": "IVA general",
    "concept": "iva",
    "applies_to": "both",
    "rate": "15",
    "company": "cacao",
    "currency": "NIO",
}
CONTRASENA = "tax-rule-2026"


@pytest.fixture
def reglas_fiscales():
    """Dos compañías, moneda local y cuentas separadas."""
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
        database.session.add_all(
            [
                Currency(code="NIO", name="Córdoba", decimals=2, active=True, default=True),
                Modules(module="admin", default=False, enabled=True),
                User(
                    id="admin",
                    user="admin",
                    name="Administrador",
                    password=proteger_passwd(CONTRASENA),
                    active=True,
                    classification="admin",
                ),
                Entity(
                    code="cacao",
                    name="Cacao",
                    company_name="Cacao SA",
                    tax_id="J0001",
                    currency="NIO",
                    enabled=True,
                    status="default",
                ),
                Entity(
                    code="alpha",
                    name="Alpha",
                    company_name="Alpha SA",
                    tax_id="J0002",
                    currency="NIO",
                    enabled=True,
                    status="activo",
                ),
            ]
        )
        database.session.flush()
        cuenta_cacao = Accounts(
            code="2.01.02.001",
            name="IVA por pagar Cacao",
            entity="cacao",
            group=False,
            active=True,
            enabled=True,
            account_type="liability",
        )
        cuenta_alpha = Accounts(
            code="2.01.02.002",
            name="IVA por pagar Alpha",
            entity="alpha",
            group=False,
            active=True,
            enabled=True,
            account_type="liability",
        )
        database.session.add_all([cuenta_cacao, cuenta_alpha])
        database.session.commit()
        ids = {"cuenta_cacao": cuenta_cacao.id, "cuenta_alpha": cuenta_alpha.id}
    yield application, ids
    with application.app_context():
        database.session.remove()
        database.engine.dispose()


def test_regla_rechaza_compania_inexistente(reglas_fiscales):
    """Una compañía inexistente se rechaza antes de persistir."""
    application, _ = reglas_fiscales
    with application.app_context():
        with pytest.raises(TaxRuleServiceError, match="compañía"):
            create_tax_rule({**BASE, "company": "missing"})
        assert database.session.execute(database.select(TaxRule)).scalars().all() == []


def test_regla_rechaza_cuenta_de_otra_compania(reglas_fiscales):
    """La cuenta debe pertenecer a la compañía de la regla."""
    application, ids = reglas_fiscales
    with application.app_context():
        with pytest.raises(TaxRuleServiceError, match="compañía"):
            create_tax_rule({**BASE, "account_id": ids["cuenta_alpha"]})
        assert database.session.execute(database.select(TaxRule)).scalars().all() == []


def test_regla_rechaza_moneda_inexistente(reglas_fiscales):
    """Una moneda inexistente se rechaza antes de persistir."""
    application, _ = reglas_fiscales
    with application.app_context():
        with pytest.raises(TaxRuleServiceError, match="moneda"):
            create_tax_rule({**BASE, "currency": "ZZZ"})
        assert database.session.execute(database.select(TaxRule)).scalars().all() == []


def test_regla_valida_se_persiste(reglas_fiscales):
    """Control positivo: compañía, moneda y cuenta propias son válidas."""
    application, ids = reglas_fiscales
    with application.app_context():
        regla = create_tax_rule({**BASE, "account_id": ids["cuenta_cacao"]})
        database.session.commit()
        assert regla.company == "cacao"
        assert regla.currency == "NIO"
        assert regla.account_id == ids["cuenta_cacao"]


def test_pago_no_usa_regla_predeterminada_de_otra_compania(reglas_fiscales):
    """La regla configurada en el tercero debe ser de la compañía del pago."""
    application, _ = reglas_fiscales
    with application.app_context():
        regla_ajena = TaxRule(
            company="alpha",
            name="Retención Alpha",
            concept="retention",
            applies_to="both",
            tax_type="withholding",
            recognition_event="payment_confirmed",
            currency="NIO",
            is_active=True,
            sequence=10,
        )
        proveedor = Party(code="PROV-1", name="Proveedor", is_supplier=True)
        database.session.add_all([regla_ajena, proveedor])
        database.session.flush()
        pago = PaymentEntry(
            company="cacao",
            payment_type="pay",
            posting_date=date(2026, 10, 20),
            party_type="supplier",
            party_id=proveedor.id,
            docstatus=0,
        )
        database.session.add(pago)
        database.session.add(
            CompanyParty(
                company="cacao",
                party_id=proveedor.id,
                is_active=True,
                default_tax_rule_id=regla_ajena.id,
            )
        )
        database.session.commit()

        spec = PaymentBuildSpec(
            payment_type="pay",
            direction="purchase",
            event_type="payment_confirmed",
            amount_field="paid_amount",
            base_amount_field="base_paid_amount",
            party_type="supplier",
        )
        reglas = _payment_tax_rules(
            document=pago,
            spec=spec,
            company="cacao",
            transaction_currency="NIO",
        )

        assert all(regla.rule_id != regla_ajena.id for regla in reglas)


def test_no_elimina_una_regla_en_uso(reglas_fiscales):
    """El borrado controla la referencia restringida sin perder la regla."""
    application, ids = reglas_fiscales
    with application.app_context():
        database.session.execute(text("PRAGMA foreign_keys=ON"))
        regla = create_tax_rule({**BASE, "account_id": ids["cuenta_cacao"]})
        proveedor = Party(code="PROV-2", name="Proveedor Dos", is_supplier=True)
        database.session.add(proveedor)
        database.session.flush()
        database.session.add(
            CompanyParty(
                company="cacao",
                party_id=proveedor.id,
                is_active=True,
                default_tax_rule_id=regla.id,
            )
        )
        database.session.commit()
        regla_id = regla.id

    client = application.test_client()
    response = client.post("/login", data={"usuario": "admin", "acceso": CONTRASENA}, follow_redirects=True)
    assert response.status_code == 200

    response = client.post(f"/settings/tax-rules/{regla_id}/delete")

    assert response.status_code == 302
    with application.app_context():
        assert database.session.get(TaxRule, regla_id) is not None
