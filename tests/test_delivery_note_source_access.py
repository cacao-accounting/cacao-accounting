# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#2104: el GET de remisión autoriza el documento origen antes de exponerlo."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest
from flask_login import login_user
from werkzeug.exceptions import Forbidden

from cacao_accounting.database import SalesOrder, User, database
from cacao_accounting.ventas.routes import _load_delivery_note_sources

FECHA = date(2026, 5, 15)


def _orden(app) -> str:
    suffix = uuid4().hex[:8]
    with app.app_context():
        order = SalesOrder(
            company="cacao",
            posting_date=FECHA,
            docstatus=1,
            document_no=f"SO-ACL-{suffix}",
            transaction_currency="NIO",
            base_currency="NIO",
            exchange_rate=Decimal("1"),
        )
        database.session.add(order)
        database.session.commit()
        return str(order.id)


def test_origen_exige_acceso_al_modulo_ventas(app, entorno_contable, reference_users):
    """Un usuario sin acceso a ventas no puede leer la orden de origen."""
    order_id = _orden(app)
    with app.app_context():
        user = database.session.get(User, reference_users["no_access"].id)
        with app.test_request_context("/sales/delivery-note/new"):
            login_user(user)
            with pytest.raises(Forbidden):
                _load_delivery_note_sources(order_id, None)


def test_origen_autorizado_se_devuelve(app, entorno_contable):
    """El administrador conserva el control positivo del origen."""
    order_id = _orden(app)
    with app.app_context():
        admin = database.session.execute(database.select(User).filter_by(user="admin")).scalar_one()
        with app.test_request_context("/sales/delivery-note/new"):
            login_user(admin)
            order, note = _load_delivery_note_sources(order_id, None)
            assert order is not None
            assert note is None
