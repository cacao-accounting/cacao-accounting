# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Referencias y compañía de las reglas fiscales.

Escenario de negocio: una regla fiscal solo puede asociarse a una compañía,
moneda y cuenta contable existentes, y la cuenta debe pertenecer a la compañía
de la regla. Un POST de configuración no debe dejar reglas que luego el motor
fiscal rechace.
"""

from __future__ import annotations

import pytest

from cacao_accounting import create_app
from cacao_accounting.config import configuracion
from cacao_accounting.database import Accounts, Currency, Entity, TaxRule, database
from cacao_accounting.tax_rule_service import TaxRuleServiceError, create_tax_rule

BASE = {
    "name": "IVA general",
    "concept": "iva",
    "applies_to": "both",
    "rate": "15",
    "company": "cacao",
    "currency": "NIO",
}


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
