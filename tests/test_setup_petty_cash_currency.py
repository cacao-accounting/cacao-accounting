# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#2081: la caja chica del setup usa la moneda funcional de la compañía."""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy.pool import StaticPool

from cacao_accounting import create_app
from cacao_accounting.bancos.services import create_default_petty_cash
from cacao_accounting.config import configuracion
from cacao_accounting.database import Accounts, Currency, Entity, database


def _app():
    return create_app(
        {
            **configuracion,
            "SQLALCHEMY_DATABASE_URI": "sqlite://",
            "SQLALCHEMY_ENGINE_OPTIONS": {"poolclass": StaticPool, "connect_args": {"check_same_thread": False}},
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
            "WTF_CSRF_ENABLED": False,
            "TESTING": True,
            "MODO_ESCRITORIO": True,
        }
    )


def test_caja_chica_sin_moneda_de_cuenta_usa_la_funcional():
    """La moneda global predeterminada no sustituye la moneda de la compañía."""
    app = _app()
    with app.app_context():
        database.create_all()
        database.session.add_all(
            [
                Currency(code="USD", name="Dólar", decimals=2, active=True, default=True),
                Currency(code="NIO", name="Córdoba", decimals=2, active=True, default=False),
                Entity(
                    code="cacao",
                    name="Cacao",
                    company_name="Cacao SA",
                    tax_id="J0001",
                    currency="NIO",
                    enabled=True,
                    status="default",
                ),
            ]
        )
        database.session.flush()
        cuenta = Accounts(
            code="1.01.01.001",
            name="Caja chica",
            entity="cacao",
            group=False,
            active=True,
            enabled=True,
            account_type="petty_cash",
            currency=None,
        )
        database.session.add(cuenta)
        database.session.commit()

        registro = create_default_petty_cash("cacao")

        assert registro is not None
        assert registro.currency == "NIO"
        assert registro.float_amount == Decimal("0")
        database.session.remove()
        database.engine.dispose()
