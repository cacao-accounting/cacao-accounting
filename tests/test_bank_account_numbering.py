# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Pruebas para preferencias de numeracion en cuentas bancarias."""

from __future__ import annotations

from datetime import date
from inspect import unwrap

import pytest

from cacao_accounting import create_app
from cacao_accounting.config import configuracion


@pytest.fixture()
def app_ctx():
    """Aplicacion aislada con datos minimos para bancos y series."""
    app = create_app(
        {
            **configuracion,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
            "WTF_CSRF_ENABLED": False,
            "TESTING": True,
        }
    )
    with app.app_context():
        from cacao_accounting.database import Currency, Entity, database

        database.create_all()
        database.session.add_all(
            [
                Currency(code="NIO", name="Cordobas", decimals=2, active=True, default=True),
                Currency(code="USD", name="Dolares", decimals=2, active=True),
                Entity(code="cacao", name="Cacao", company_name="Cacao", tax_id="J0001", currency="NIO"),
                Entity(code="other", name="Other", company_name="Other", tax_id="J0002", currency="USD"),
            ]
        )
        database.session.commit()
        yield app
        database.session.remove()
        database.drop_all()


def _make_payment_series(company: str = "cacao", entity_type: str = "payment_entry"):
    from cacao_accounting.database import NamingSeries, Sequence, SeriesSequenceMap, database

    sequence = Sequence(name=f"{company}-{entity_type}-seq", current_value=0, increment=1, padding=5)
    series = NamingSeries(
        name=f"{company}-{entity_type}",
        entity_type=entity_type,
        company=company,
        prefix_template=f"{company}-PAY-*YYYY*-*MM*-",
        is_active=True,
        is_default=True,
    )
    database.session.add_all([sequence, series])
    database.session.flush()
    database.session.add(SeriesSequenceMap(naming_series_id=series.id, sequence_id=sequence.id, priority=0))
    database.session.flush()
    return series


def _make_checkbook(company: str = "cacao", counter_type: str = "checkbook"):
    from cacao_accounting.database import ExternalCounter, database

    counter = ExternalCounter(
        company=company,
        name=f"Chequera {company} {counter_type}",
        counter_type=counter_type,
        prefix=f"{company.upper()}-CHK-",
        last_used=0,
        padding=5,
        is_active=True,
    )
    database.session.add(counter)
    database.session.flush()
    return counter


def _make_bank_account(series, counter, currency: str = "NIO"):
    from cacao_accounting.database import Bank, BankAccount, database

    bank = Bank(name=f"Banco {currency}", is_active=True)
    database.session.add(bank)
    database.session.flush()
    account = BankAccount(
        bank_id=bank.id,
        company="cacao",
        account_name=f"Cuenta {currency}",
        account_no=f"CTA-{currency}",
        currency=currency,
        default_naming_series_id=series.id,
        default_external_counter_id=counter.id,
        is_active=True,
    )
    database.session.add(account)
    database.session.flush()
    return account


def test_bank_account_new_saves_payment_series_and_checkbook(app_ctx):
    from cacao_accounting.bancos import bancos_cuenta_bancaria_nuevo
    from cacao_accounting.database import Bank, BankAccount, SeriesExternalCounterMap, database

    series = _make_payment_series()
    counter = _make_checkbook()
    bank = Bank(name="Banco Form", is_active=True)
    database.session.add(bank)
    database.session.commit()

    data = {
        "bank_id": bank.id,
        "company": "cacao",
        "account_name": "Cuenta Form",
        "account_no": "FORM-001",
        "currency": "NIO",
        "default_naming_series_id": series.id,
        "default_external_counter_id": counter.id,
    }
    with app_ctx.test_request_context("/cash_management/bank-account/new", method="POST", data=data):
        response = unwrap(bancos_cuenta_bancaria_nuevo)()

    account = database.session.execute(database.select(BankAccount).filter_by(account_no="FORM-001")).scalar_one()
    mapping = database.session.execute(
        database.select(SeriesExternalCounterMap).filter_by(
            naming_series_id=series.id,
            external_counter_id=counter.id,
        )
    ).scalar_one()

    assert response.status_code == 302
    assert account.default_naming_series_id == series.id
    assert account.default_external_counter_id == counter.id
    assert account.id in (mapping.condition_json or "")


def test_bank_account_new_rejects_non_payment_series(app_ctx):
    from cacao_accounting.bancos import bancos_cuenta_bancaria_nuevo
    from cacao_accounting.database import Bank, BankAccount, database

    series = _make_payment_series(entity_type="sales_invoice")
    counter = _make_checkbook()
    bank = Bank(name="Banco Serie Mala", is_active=True)
    database.session.add(bank)
    database.session.commit()

    data = {
        "bank_id": bank.id,
        "company": "cacao",
        "account_name": "Cuenta Serie Mala",
        "account_no": "BAD-SERIES",
        "default_naming_series_id": series.id,
        "default_external_counter_id": counter.id,
    }
    with app_ctx.test_request_context("/cash_management/bank-account/new", method="POST", data=data):
        unwrap(bancos_cuenta_bancaria_nuevo)()

    account = database.session.execute(database.select(BankAccount).filter_by(account_no="BAD-SERIES")).scalar_one_or_none()
    assert account is None


def test_bank_account_new_rejects_cross_company_or_non_checkbook_counter(app_ctx):
    from cacao_accounting.bancos import bancos_cuenta_bancaria_nuevo
    from cacao_accounting.database import Bank, BankAccount, database

    series = _make_payment_series()
    bank = Bank(name="Banco Chequera Mala", is_active=True)
    database.session.add(bank)
    database.session.flush()

    for account_no, counter in (
        ("BAD-COMPANY", _make_checkbook(company="other")),
        ("BAD-TYPE", _make_checkbook(counter_type="fiscal")),
    ):
        data = {
            "bank_id": bank.id,
            "company": "cacao",
            "account_name": account_no,
            "account_no": account_no,
            "default_naming_series_id": series.id,
            "default_external_counter_id": counter.id,
        }
        with app_ctx.test_request_context("/cash_management/bank-account/new", method="POST", data=data):
            unwrap(bancos_cuenta_bancaria_nuevo)()

        account = database.session.execute(database.select(BankAccount).filter_by(account_no=account_no)).scalar_one_or_none()
        assert account is None


def test_payment_creation_uses_bank_account_numbering_defaults(app_ctx):
    from cacao_accounting.bancos import bancos_pago_nuevo
    from cacao_accounting.database import ExternalNumberUsage, PaymentEntry, database

    series = _make_payment_series()
    counter_nio = _make_checkbook()
    counter_usd = _make_checkbook()
    account_nio = _make_bank_account(series, counter_nio, "NIO")
    account_usd = _make_bank_account(series, counter_usd, "USD")
    database.session.commit()

    for account, counter in ((account_nio, counter_nio), (account_usd, counter_usd)):
        data = {
            "payment_type": "pay",
            "company": "cacao",
            "posting_date": date(2026, 5, 13).isoformat(),
            "bank_account_id": account.id,
            "paid_amount": "10.00",
        }
        with app_ctx.test_request_context("/cash_management/payment/new", method="POST", data=data):
            response = unwrap(bancos_pago_nuevo)()

        payment = (
            database.session.execute(
                database.select(PaymentEntry).filter_by(bank_account_id=account.id).order_by(PaymentEntry.created.desc())
            )
            .scalars()
            .first()
        )

        assert response.status_code == 302
        assert payment is not None
        assert payment.naming_series_id == series.id
        assert payment.external_counter_id == counter.id
        assert payment.external_number == f"{counter.prefix}00001"
        usage = database.session.execute(
            database.select(ExternalNumberUsage).filter_by(
                external_counter_id=counter.id,
                entity_id=payment.id,
            )
        ).scalar_one()
        assert usage.external_number == payment.external_number


def test_payment_creation_explicit_values_override_bank_account_defaults(app_ctx):
    from cacao_accounting.bancos import bancos_pago_nuevo
    from cacao_accounting.database import PaymentEntry, database

    default_series = _make_payment_series()
    explicit_series = _make_payment_series()
    default_counter = _make_checkbook()
    explicit_counter = _make_checkbook()
    account = _make_bank_account(default_series, default_counter, "NIO")
    database.session.commit()

    data = {
        "payment_type": "pay",
        "company": "cacao",
        "posting_date": date(2026, 5, 13).isoformat(),
        "bank_account_id": account.id,
        "paid_amount": "10.00",
        "naming_series": explicit_series.id,
        "external_counter_id": explicit_counter.id,
    }
    with app_ctx.test_request_context("/cash_management/payment/new", method="POST", data=data):
        response = unwrap(bancos_pago_nuevo)()

    payment = database.session.execute(database.select(PaymentEntry).filter_by(bank_account_id=account.id)).scalar_one()
    assert response.status_code == 302
    assert payment.naming_series_id == explicit_series.id
    assert payment.external_counter_id == explicit_counter.id
