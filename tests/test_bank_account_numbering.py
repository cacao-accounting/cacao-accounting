# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Pruebas para preferencias de numeracion en cuentas bancarias."""

from __future__ import annotations

from datetime import date
from inspect import unwrap
import json

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


_series_counter = 0


def _make_payment_series(company: str = "cacao", entity_type: str = "payment_entry"):
    global _series_counter
    _series_counter += 1
    from cacao_accounting.database import NamingSeries, Sequence, SeriesSequenceMap, database

    seq_name = f"{company}-{entity_type}-seq-{_series_counter}"
    series_name = f"{company}-{entity_type}-{_series_counter}"
    sequence = Sequence(name=seq_name, current_value=0, increment=1, padding=5)
    series = NamingSeries(
        name=series_name,
        entity_type=entity_type,
        company=company,
        prefix_template=f"{company}-PAY-*YYYY*-*MM*-{_series_counter}-",
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


def test_validate_bank_account_numbering_defaults_returns_same_ids(app_ctx):
    from cacao_accounting.bancos import _validate_bank_account_numbering_defaults

    series = _make_payment_series()
    counter = _make_checkbook()

    naming_series_id, external_counter_id = _validate_bank_account_numbering_defaults(
        company="cacao",
        naming_series_id=series.id,
        external_counter_id=counter.id,
    )

    assert naming_series_id == series.id
    assert external_counter_id == counter.id


def test_validate_bank_account_numbering_defaults_allows_global_payment_series(app_ctx):
    from cacao_accounting.bancos import _validate_bank_account_numbering_defaults

    series = _make_payment_series(company=None)
    counter = _make_checkbook()

    naming_series_id, external_counter_id = _validate_bank_account_numbering_defaults(
        company="cacao",
        naming_series_id=series.id,
        external_counter_id=counter.id,
    )

    assert naming_series_id == series.id
    assert external_counter_id == counter.id


def test_validate_bank_account_numbering_defaults_rejects_missing_or_inactive_payment_series(app_ctx):
    from cacao_accounting.bancos import _validate_bank_account_numbering_defaults
    from cacao_accounting.database import database
    from cacao_accounting.document_identifiers import IdentifierConfigurationError

    inactive_series = _make_payment_series()
    inactive_series.is_active = False
    database.session.commit()

    missing_id = "missing-series"
    for series_id in (missing_id, inactive_series.id):
        with pytest.raises(IdentifierConfigurationError, match="serie interna seleccionada no existe o está inactiva"):
            _validate_bank_account_numbering_defaults(
                company="cacao",
                naming_series_id=series_id,
                external_counter_id=None,
            )


def test_validate_bank_account_numbering_defaults_rejects_wrong_payment_series_type(app_ctx):
    from cacao_accounting.bancos import _validate_bank_account_numbering_defaults
    from cacao_accounting.document_identifiers import IdentifierConfigurationError

    series = _make_payment_series(entity_type="sales_invoice")

    with pytest.raises(IdentifierConfigurationError, match="serie interna debe ser para pagos"):
        _validate_bank_account_numbering_defaults(
            company="cacao",
            naming_series_id=series.id,
            external_counter_id=None,
        )


def test_validate_bank_account_numbering_defaults_rejects_cross_company_payment_series(app_ctx):
    from cacao_accounting.bancos import _validate_bank_account_numbering_defaults
    from cacao_accounting.document_identifiers import IdentifierConfigurationError

    series = _make_payment_series(company="other")

    with pytest.raises(IdentifierConfigurationError, match="serie interna no pertenece a la compañía indicada"):
        _validate_bank_account_numbering_defaults(
            company="cacao",
            naming_series_id=series.id,
            external_counter_id=None,
        )


def test_validate_bank_account_numbering_defaults_rejects_missing_or_inactive_checkbook(app_ctx):
    from cacao_accounting.bancos import _validate_bank_account_numbering_defaults
    from cacao_accounting.database import database
    from cacao_accounting.document_identifiers import IdentifierConfigurationError

    inactive_counter = _make_checkbook()
    inactive_counter.is_active = False
    database.session.commit()

    for counter_id in ("missing-counter", inactive_counter.id):
        with pytest.raises(IdentifierConfigurationError, match="chequera seleccionada no existe o está inactiva"):
            _validate_bank_account_numbering_defaults(
                company="cacao",
                naming_series_id=None,
                external_counter_id=counter_id,
            )


def test_validate_bank_account_numbering_defaults_rejects_wrong_checkbook_type(app_ctx):
    from cacao_accounting.bancos import _validate_bank_account_numbering_defaults
    from cacao_accounting.document_identifiers import IdentifierConfigurationError

    counter = _make_checkbook(counter_type="fiscal")

    with pytest.raises(IdentifierConfigurationError, match="debe ser una chequera"):
        _validate_bank_account_numbering_defaults(
            company="cacao",
            naming_series_id=None,
            external_counter_id=counter.id,
        )


def test_validate_bank_account_numbering_defaults_rejects_cross_company_checkbook(app_ctx):
    from cacao_accounting.bancos import _validate_bank_account_numbering_defaults
    from cacao_accounting.document_identifiers import IdentifierConfigurationError

    counter = _make_checkbook(company="other")

    with pytest.raises(IdentifierConfigurationError, match="chequera no pertenece a la compañía indicada"):
        _validate_bank_account_numbering_defaults(
            company="cacao",
            naming_series_id=None,
            external_counter_id=counter.id,
        )


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

    series = _make_payment_series(entity_type="bank_payment")
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
            "party_type": "supplier",
            "party_id": "SUPP-BANK-NUM",
            "mode_of_payment": "check",
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

    default_series = _make_payment_series(entity_type="bank_payment")
    explicit_series = _make_payment_series(entity_type="bank_payment")
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
        "party_type": "supplier",
        "party_id": "SUPP-BANK-NUM-EXPL",
        "mode_of_payment": "check",
        "naming_series": explicit_series.id,
        "external_counter_id": explicit_counter.id,
    }
    with app_ctx.test_request_context("/cash_management/payment/new", method="POST", data=data):
        response = unwrap(bancos_pago_nuevo)()

    payment = database.session.execute(database.select(PaymentEntry).filter_by(bank_account_id=account.id)).scalar_one()
    assert response.status_code == 302
    assert payment.naming_series_id == explicit_series.id
    assert payment.external_counter_id == explicit_counter.id


def test_payment_creation_rolls_back_when_fiscal_payload_is_invalid(app_ctx):
    from cacao_accounting.bancos import bancos_pago_nuevo
    from cacao_accounting.database import PaymentEntry, database

    series = _make_payment_series(entity_type="bank_payment")
    counter = _make_checkbook()
    account = _make_bank_account(series, counter, "NIO")
    database.session.commit()

    payload = {
        "payment_type": "pay",
        "company": "cacao",
        "posting_date": date(2026, 5, 13).isoformat(),
        "bank_account_id": account.id,
        "party_type": "supplier",
        "party_id": "SUPP-ERR",
        "paid_amount": "10.00",
        "tax_lines": "{invalid_json}",
        "tax_summary": {"document_tax_total": "1.00"},
    }
    with app_ctx.test_request_context(
        "/cash_management/payment/new",
        method="POST",
        data={"payment_payload": json.dumps(payload)},
    ):
        response = unwrap(bancos_pago_nuevo)()

    created_payment = database.session.execute(
        database.select(PaymentEntry).filter_by(bank_account_id=account.id, party_id="SUPP-ERR")
    ).scalar_one_or_none()
    assert isinstance(response, str)
    assert created_payment is None
