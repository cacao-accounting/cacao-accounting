# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1607: el dashboard separa saldo de cuenta y total en moneda base."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy.pool import StaticPool

from cacao_accounting import create_app
from cacao_accounting.api.dashboard import get_banks_data
from cacao_accounting.config import configuracion
from cacao_accounting.database import Accounts, Bank, BankAccount, Book, Currency, Entity, GLEntry, database


@pytest.fixture
def bank_balance_scene():
    application = create_app(
        {
            **configuracion,
            "SQLALCHEMY_DATABASE_URI": "sqlite://",
            "SQLALCHEMY_ENGINE_OPTIONS": {"poolclass": StaticPool},
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
            "TESTING": True,
            "MODO_ESCRITORIO": True,
        }
    )
    with application.app_context():
        database.create_all()
        database.session.add_all(
            [
                Currency(code="NIO", name="Córdoba", decimals=2, active=True, default=True),
                Currency(code="USD", name="Dólar", decimals=2, active=True, default=False),
                Entity(
                    code="cacao",
                    name="Cacao",
                    company_name="Cacao SA",
                    tax_id="J-1607",
                    currency="NIO",
                    enabled=True,
                    status="default",
                ),
            ]
        )
        database.session.flush()
        libro = Book(
            entity="cacao",
            code="DEFAULT_BOOK",
            name="Libro principal",
            status="activo",
            is_primary=True,
            default=True,
            currency="NIO",
        )
        database.session.add(libro)
        database.session.flush()
        banco = Bank(name="Banco 1607", is_active=True)
        database.session.add(banco)
        database.session.flush()
        cuenta = Accounts(
            entity="cacao",
            code="1102",
            name="Banco USD",
            classification="activo",
            group=False,
        )
        database.session.add(cuenta)
        database.session.flush()
        cuenta_bancaria = BankAccount(
            company="cacao",
            bank_id=banco.id,
            account_name="Cuenta USD",
            account_no="USD-1607",
            currency="USD",
            gl_account_id=cuenta.id,
            is_active=True,
        )
        database.session.add(cuenta_bancaria)
        database.session.flush()
        database.session.add(
            GLEntry(
                posting_date=date(2026, 5, 15),
                company="cacao",
                account_id=cuenta.id,
                ledger_id=libro.id,
                debit=Decimal("3600"),
                credit=Decimal("0"),
                debit_in_account_currency=Decimal("100"),
                credit_in_account_currency=Decimal("0"),
                account_currency="USD",
                company_currency="NIO",
                exchange_rate=Decimal("36"),
                voucher_type="journal_entry",
                voucher_id="JE-1607",
                is_cancelled=False,
            )
        )
        database.session.commit()
    yield application
    with application.app_context():
        database.session.remove()
        database.engine.dispose()


def test_saldo_de_cuenta_usa_su_moneda_y_total_usa_moneda_base(bank_balance_scene):
    """La tabla muestra 100 USD y el KPI 3,600 NIO, no 3,600 USD."""
    with bank_balance_scene.app_context():
        payload = get_banks_data("cacao", "NIO", None, None)

    fila = payload["tables"]["account_balances"][0]
    assert Decimal(str(fila["balance"])) == Decimal("100")
    assert fila["currency"] == "USD"

    kpi = payload["kpis"]["balance"]
    assert Decimal(str(kpi["value"])) == Decimal("3600")
    assert kpi["currency"] == "NIO"
