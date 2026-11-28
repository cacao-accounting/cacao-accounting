# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 William José Moreno Reyes

"""#2306: las altas GL bancarias toman el lock de conciliación automática."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from threading import Event
from time import sleep
from uuid import uuid4

import pytest

from test_purchase_receipt_return_cancel_postgresql import _drop, _isolated_url, _seed

from cacao_accounting import create_app
from cacao_accounting.config import configuracion
from cacao_accounting.contabilidad.posting_service import _add_entries
from cacao_accounting.database import Accounts, Bank, BankAccount, Book, GLEntry, database
from cacao_accounting.default_scope import lock_default_scopes

pytestmark = pytest.mark.database


def test_alta_gl_bancaria_espera_el_lock_de_conciliacion():
    """Un asiento bancario no puede crear candidatos mientras se concilia."""
    url, name = _isolated_url()
    try:
        app = create_app(
            {
                **configuracion,
                "SQLALCHEMY_DATABASE_URI": url.render_as_string(hide_password=False),
                "TESTING": True,
                "SECRET_KEY": "test-2306-gl",
                "WTF_CSRF_ENABLED": False,
                "MODO_ESCRITORIO": False,
            }
        )
        _seed(app)
        suffix = uuid4().hex[:6].upper()
        with app.app_context():
            bank = Bank(name=f"Banco {suffix}", is_active=True)
            database.session.add(bank)
            database.session.flush()
            bank_gl = database.session.execute(database.select(Accounts).filter_by(entity="cacao", code="1102")).scalar_one()
            income = database.session.execute(database.select(Accounts).filter_by(entity="cacao", code="4101")).scalar_one()
            book = database.session.execute(database.select(Book).filter_by(entity="cacao", is_primary=True)).scalar_one()
            account = BankAccount(
                bank_id=bank.id,
                company="cacao",
                account_name=f"Cuenta {suffix}",
                account_no=f"ACC-{suffix}",
                currency="NIO",
                gl_account_id=bank_gl.id,
            )
            database.session.add(account)
            database.session.commit()
            account_id = account.id
            book_id = book.id
            bank_gl_id, bank_gl_code = bank_gl.id, bank_gl.code
            income_id, income_code = income.id, income.code
            database.session.remove()

        finished = Event()

        def post_gl() -> None:
            with app.app_context():
                try:
                    _add_entries(
                        [
                            GLEntry(
                                company="cacao",
                                ledger_id=book_id,
                                account_id=bank_gl_id,
                                account_code=bank_gl_code,
                                debit=1,
                                credit=0,
                                voucher_type="journal_entry",
                                voucher_id=f"GL-{suffix}",
                            ),
                            GLEntry(
                                company="cacao",
                                ledger_id=book_id,
                                account_id=income_id,
                                account_code=income_code,
                                debit=0,
                                credit=1,
                                voucher_type="journal_entry",
                                voucher_id=f"GL-{suffix}",
                            ),
                        ]
                    )
                    database.session.commit()
                except Exception:
                    database.session.rollback()
                finally:
                    finished.set()
                    database.session.remove()

        with app.app_context():
            lock_default_scopes("bank_auto_reconcile", [("cacao", None), ("cacao", account_id)])
            with ThreadPoolExecutor(max_workers=1) as workers:
                future = workers.submit(post_gl)
                sleep(0.5)
                assert not finished.is_set(), "el asiento GL no esperó el lock de conciliación"
                database.session.commit()
            future.result(timeout=20)
            assert finished.is_set()
            database.session.remove()
    finally:
        _drop(url, name)
