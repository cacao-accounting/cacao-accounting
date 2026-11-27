# SPDX-License-Identifier: Apache-2.0
"""#1680: DocBase optimistic locking detects stale concurrent edits."""

from __future__ import annotations

from datetime import date

import pytest
from sqlalchemy.orm import Session
from sqlalchemy.orm.exc import StaleDataError

from cacao_accounting.database import Entity, PurchaseOrder, database


def _seed(app):
    with app.app_context():
        code = "L1680"
        if database.session.execute(database.select(Entity).filter_by(code=code)).scalar_one_or_none() is None:
            database.session.add(
                Entity(code=code, name="Lock", company_name="Lock", tax_id="J0310000001680", currency="NIO", enabled=True)
            )
            database.session.commit()
        po = PurchaseOrder(
            company=code,
            posting_date=date(2026, 1, 1),
            transaction_currency="NIO",
            base_currency="NIO",
            exchange_rate=1,
            docstatus=0,
        )
        database.session.add(po)
        database.session.commit()
        return po.id


def test_docbase_version_increments_on_update(app):
    po_id = _seed(app)
    with app.app_context():
        po = database.session.get(PurchaseOrder, po_id)
        assert po.version == 1
        po.remarks = "first"
        database.session.commit()
        refreshed = database.session.get(PurchaseOrder, po_id)
        assert refreshed.version == 2


def test_docbase_stale_update_raises(app):
    po_id = _seed(app)
    with app.app_context():
        s1 = Session(bind=database.engine)
        s2 = Session(bind=database.engine)
        try:
            po1 = s1.get(PurchaseOrder, po_id)
            po2 = s2.get(PurchaseOrder, po_id)
            po1.remarks = "first writer"
            s1.commit()
            po2.remarks = "second writer"
            with pytest.raises(StaleDataError):
                s2.commit()
            s2.rollback()
        finally:
            s1.close()
            s2.close()
        final = database.session.get(PurchaseOrder, po_id)
        database.session.refresh(final)
        assert final.remarks == "first writer"
        assert final.version == 2


def test_purchase_order_edit_rejects_stale_form_version(app):
    po_id = _seed(app)
    with app.app_context():
        po = database.session.get(PurchaseOrder, po_id)
        po.remarks = "concurrent"
        database.session.commit()
        database.session.refresh(po)
        assert po.version == 2

        stale_po = database.session.get(PurchaseOrder, po_id)
        # simulate a form submitted with stale version=1 while current is 2
        with app.test_request_context("/compras/orden-compra/%s/editar" % po_id, method="POST", data={"version": "1"}):
            from cacao_accounting.compras.services import _check_optimistic_version

            result = _check_optimistic_version(stale_po)
        assert result == "stale"

        with app.test_request_context("/compras/orden-compra/%s/editar" % po_id, method="POST", data={"version": "2"}):
            from cacao_accounting.compras.services import _check_optimistic_version

            result_ok = _check_optimistic_version(stale_po)
        assert result_ok is None
