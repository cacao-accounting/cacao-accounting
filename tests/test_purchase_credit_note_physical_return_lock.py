# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 William José Moreno Reyes

"""#2355: la nota física espera la cancelación de la devolución."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import date
from threading import Barrier
from time import sleep
from types import SimpleNamespace
from uuid import uuid4

import pytest

from test_purchase_receipt_return_cancel_postgresql import _drop, _isolated_url, _seed

from cacao_accounting import create_app
from cacao_accounting.compras.purchase_reconciliation_service import _physical_return_items_by_code
from cacao_accounting.config import configuracion
from cacao_accounting.database import PurchaseReceipt, PurchaseReceiptItem, database

pytestmark = pytest.mark.database


def test_nota_fisica_espera_cancelacion_de_la_devolucion():
    """La lectura bloqueante evita confirmar contra una devolución ya cancelada."""
    url, name = _isolated_url()
    try:
        app = create_app(
            {
                **configuracion,
                "SQLALCHEMY_DATABASE_URI": url.render_as_string(hide_password=False),
                "TESTING": True,
                "SECRET_KEY": "test-2355",
                "WTF_CSRF_ENABLED": False,
                "MODO_ESCRITORIO": False,
            }
        )
        _seed(app)
        suffix = uuid4().hex[:6].upper()
        with app.app_context():
            receipt = PurchaseReceipt(
                company="cacao",
                posting_date=date(2026, 5, 12),
                docstatus=1,
                document_no=f"RET-{suffix}",
                is_return=True,
                transaction_currency="NIO",
                base_currency="NIO",
                exchange_rate=1,
            )
            database.session.add(receipt)
            database.session.flush()
            database.session.add(
                PurchaseReceiptItem(
                    purchase_receipt_id=receipt.id,
                    item_code="ART01",
                    item_name="Artículo",
                    qty=1,
                    qty_in_base_uom=1,
                    uom="UND",
                    warehouse="BOD01",
                )
            )
            database.session.commit()
            receipt_id = receipt.id
            database.session.remove()

        barrier = Barrier(2, timeout=30)

        def cancel_return() -> str:
            with app.app_context():
                try:
                    receipt = database.session.get(PurchaseReceipt, receipt_id, with_for_update=True)
                    barrier.wait(timeout=10)
                    sleep(0.5)
                    receipt.docstatus = 2
                    database.session.commit()
                    return "cancelada"
                finally:
                    database.session.remove()

        def read_items() -> str:
            with app.app_context():
                try:
                    barrier.wait(timeout=10)
                    note = SimpleNamespace(credit_note_type="physical_return", purchase_receipt_id=receipt_id)
                    _physical_return_items_by_code(note)
                    return "leyo"
                except Exception:
                    return "rechazo"
                finally:
                    database.session.remove()

        with ThreadPoolExecutor(max_workers=2) as workers:
            cancel_future = workers.submit(cancel_return)
            read_future = workers.submit(read_items)
            assert cancel_future.result(timeout=20) == "cancelada"
            assert read_future.result(timeout=20) == "rechazo"
    finally:
        _drop(url, name)
