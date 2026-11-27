# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 William José Moreno Reyes

"""#2306: el posting de pagos toma el lock de conciliación automática."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import date
from threading import Event
from time import sleep
from uuid import uuid4

import pytest

from test_purchase_receipt_return_cancel_postgresql import _drop, _isolated_url, _seed

from cacao_accounting import create_app
from cacao_accounting.approval_engine import approved_execution
from cacao_accounting.config import configuracion
from cacao_accounting.contabilidad.posting_service import post_payment_entry
from cacao_accounting.database import Bank, BankAccount, PaymentEntry, User, database
from cacao_accounting.default_scope import lock_default_scopes
from cacao_accounting.internal_control_service import audit_actor

pytestmark = pytest.mark.database


def test_posting_de_pago_espera_el_lock_de_conciliacion():
    """Un pago no puede crear candidatos mientras la conciliación automática decide."""
    url, name = _isolated_url()
    try:
        app = create_app(
            {
                **configuracion,
                "SQLALCHEMY_DATABASE_URI": url.render_as_string(hide_password=False),
                "TESTING": True,
                "SECRET_KEY": "test-2306-payment",
                "WTF_CSRF_ENABLED": False,
                "MODO_ESCRITORIO": False,
            }
        )
        _seed(app)
        suffix = uuid4().hex[:6].upper()
        with app.app_context():
            admin = database.session.execute(database.select(User).filter_by(user="admin")).scalar_one()
            bank = Bank(name=f"Banco {suffix}", is_active=True)
            database.session.add(bank)
            database.session.flush()
            account = BankAccount(
                bank_id=bank.id,
                company="cacao",
                account_name=f"Cuenta {suffix}",
                account_no=f"ACC-{suffix}",
                currency="NIO",
            )
            database.session.add(account)
            database.session.flush()
            payment = PaymentEntry(
                company="cacao",
                payment_type="internal_transfer",
                bank_account_id=account.id,
                target_bank_account_id=account.id,
                posting_date=date(2026, 5, 12),
                paid_amount=10,
                received_amount=10,
                docstatus=1,
            )
            database.session.add(payment)
            database.session.commit()
            account_id = account.id
            payment_id = payment.id
            admin_id = str(admin.id)
            database.session.remove()

        finished = Event()
        result: dict[str, object] = {}

        def post() -> None:
            with app.app_context():
                try:
                    payment = database.session.get(PaymentEntry, payment_id)
                    with audit_actor(admin_id, "Admin"), approved_execution(payment, admin_id):
                        post_payment_entry(payment, ledger_code="FISCAL")
                    database.session.commit()
                except Exception as exc:
                    database.session.rollback()
                    result["error"] = type(exc).__name__
                finally:
                    finished.set()
                    database.session.remove()

        with app.app_context():
            lock_default_scopes("bank_auto_reconcile", [("cacao", None), ("cacao", account_id)])
            with ThreadPoolExecutor(max_workers=1) as workers:
                future = workers.submit(post)
                sleep(0.5)
                assert not finished.is_set(), "el pago no esperó el lock de conciliación"
                database.session.commit()
            future.result(timeout=20)
            assert finished.is_set()
            database.session.remove()
    finally:
        _drop(url, name)
