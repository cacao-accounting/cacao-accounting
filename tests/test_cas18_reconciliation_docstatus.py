"""Tests for CAS-18: bank reconciliation must validate payment docstatus."""

from datetime import date
from decimal import Decimal

import pytest
from cacao_accounting import create_app
from cacao_accounting.database import database, Party, PaymentEntry
from cacao_accounting.database.helpers import inicia_base_de_datos
from cacao_accounting.bancos.reconciliation_service import (
    _target_amount,
    _target_company,
    BankReconciliationError,
)


@pytest.fixture()
def app_ctx():
    app = create_app(
        {
            "TESTING": True,
            "SECRET_KEY": "test_secret_key",
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
            "WTF_CSRF_ENABLED": False,
        }
    )
    with app.app_context():
        from cacao_accounting.datos.dev import master_data

        inicia_base_de_datos(app, user="cacao", passwd="cacao", with_examples=False)
        master_data()
        database.session.commit()
        yield app


def test_cas18_draft_payment_rejected_by_target_amount(app_ctx):
    """CAS-18: _target_amount must reject draft payments."""
    supplier = database.session.execute(database.select(Party).filter(Party.is_supplier.is_(True))).scalars().first()
    payment = PaymentEntry(
        company="cacao",
        party_type="supplier",
        party_id=supplier.id,
        payment_type="pay",
        posting_date=date.today(),
        paid_amount=100,
        docstatus=0,
    )
    database.session.add(payment)
    database.session.commit()

    with pytest.raises(BankReconciliationError, match="aprobada"):
        _target_amount("payment_entry", payment.id)


def test_cas18_cancelled_payment_rejected_by_target_amount(app_ctx):
    """CAS-18: _target_amount must reject cancelled payments."""
    supplier = database.session.execute(database.select(Party).filter(Party.is_supplier.is_(True))).scalars().first()
    payment = PaymentEntry(
        company="cacao",
        party_type="supplier",
        party_id=supplier.id,
        payment_type="pay",
        posting_date=date.today(),
        paid_amount=100,
        docstatus=2,
    )
    database.session.add(payment)
    database.session.commit()

    with pytest.raises(BankReconciliationError, match="aprobada"):
        _target_amount("payment_entry", payment.id)


def test_cas18_submitted_payment_accepted(app_ctx):
    """CAS-18: _target_amount must accept submitted payments."""
    supplier = database.session.execute(database.select(Party).filter(Party.is_supplier.is_(True))).scalars().first()
    payment = PaymentEntry(
        company="cacao",
        party_type="supplier",
        party_id=supplier.id,
        payment_type="pay",
        posting_date=date.today(),
        paid_amount=100,
        docstatus=1,
    )
    database.session.add(payment)
    database.session.commit()

    result = _target_amount("payment_entry", payment.id)
    assert result == Decimal("100")


def test_cas18_draft_payment_rejected_by_target_company(app_ctx):
    """CAS-18: _target_company must reject draft payments."""
    supplier = database.session.execute(database.select(Party).filter(Party.is_supplier.is_(True))).scalars().first()
    payment = PaymentEntry(
        company="cacao",
        party_type="supplier",
        party_id=supplier.id,
        payment_type="pay",
        posting_date=date.today(),
        paid_amount=100,
        docstatus=0,
    )
    database.session.add(payment)
    database.session.commit()

    with pytest.raises(BankReconciliationError, match="aprobada"):
        _target_company("payment_entry", payment.id)
