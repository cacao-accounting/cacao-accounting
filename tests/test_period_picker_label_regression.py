# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Regresión: los selectores de período deben mostrar el nombre legible, no el ULID.

Cuando un listado se renderiza con un período contable pre-seleccionado, el
campo de selección asistida (smart-select) debe mostrar el nombre del
período (e.g. ``01-2026``) en el input de búsqueda, no el identificador ULID
del registro. El identificador sigue enviándose como valor del input oculto
para que el backend lo pueda resolver, pero la etiqueta visible debe ser
comprensible para el usuario.
"""

from __future__ import annotations

from datetime import date

import pytest

from cacao_accounting import create_app
from cacao_accounting.config import configuracion


@pytest.fixture()
def period_picker_app():
    app = create_app(
        {
            **configuracion,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
            "WTF_CSRF_ENABLED": False,
            "TESTING": True,
            "SECRET_KEY": "testing",
        }
    )
    with app.app_context():
        from cacao_accounting.database import (
            AccountingPeriod,
            Entity,
            Modules,
            User,
            database,
        )

        database.create_all()
        user = User(
            user="picker-user",
            name="Picker User",
            classification="admin",
            active=True,
        )
        user.password = b"x"
        database.session.add_all(
            [
                Entity(
                    code="cacao",
                    name="Cacao Accounting",
                    company_name="Cacao Accounting SA",
                    tax_id="J0001",
                    currency="NIO",
                    enabled=True,
                    status="default",
                ),
                Modules(module="sales", default=True, enabled=True),
                Modules(module="purchases", default=True, enabled=True),
                Modules(module="inventory", default=True, enabled=True),
                Modules(module="cash", default=True, enabled=True),
                Modules(module="banking", default=True, enabled=True),
                user,
                AccountingPeriod(
                    entity="cacao",
                    name="01-2026",
                    enabled=True,
                    is_closed=False,
                    start=date(2026, 1, 1),
                    end=date(2026, 1, 31),
                ),
            ]
        )
        database.session.commit()
        yield app


def _login(client, user_id: str) -> None:
    with client.session_transaction() as session:
        session["_user_id"] = user_id
        session["_fresh"] = True


def _period_id(app) -> str:
    from cacao_accounting.database import AccountingPeriod, database

    period = database.session.execute(
        database.select(AccountingPeriod).where(AccountingPeriod.name == "01-2026")
    ).scalar_one()
    return str(period.id)


def test_period_picker_context_exposes_legible_label(period_picker_app) -> None:
    """`period_picker_context` debe retornar el `name` del período activo."""
    from cacao_accounting.list_filters import period_picker_context

    with period_picker_app.app_context():
        period_id = _period_id(period_picker_app)
        payload = period_picker_context("cacao", period_id, period_id)
        assert payload["period_from"] == period_id
        assert payload["period_to"] == period_id
        assert payload["period_from_label"] == "01-2026"
        assert payload["period_to_label"] == "01-2026"


def test_period_picker_payload_exposes_legible_label(period_picker_app) -> None:
    """`_period_picker_payload` debe retornar el `name` del período activo."""
    from cacao_accounting.reportes.helpers import _period_picker_payload

    with period_picker_app.app_context():
        period_id = _period_id(period_picker_app)
        with period_picker_app.test_request_context(
            f"/reports/kardex?company=cacao&accounting_period_from={period_id}&accounting_period_to={period_id}"
        ):
            payload = _period_picker_payload("cacao", period_id, period_id)
            assert payload["period_from"] == period_id
            assert payload["period_to"] == period_id
            assert payload["period_from_label"] == "01-2026"
            assert payload["period_to_label"] == "01-2026"


def test_delivery_note_list_renders_legible_period_label(period_picker_app) -> None:
    """El listado de Remisiones de Mercadería Vendida muestra el nombre del período."""
    from cacao_accounting.database import User

    user = User.query.filter_by(user="picker-user").first()
    client = period_picker_app.test_client()
    _login(client, user.id)
    pid = _period_id(period_picker_app)
    url = (
        f"/sales/delivery-note/list?company=cacao"
        f"&accounting_period_from={pid}&accounting_period_to={pid}"
    )
    response = client.get(url)
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert "Listado de Remisiones de Mercadería Vendida" in html
    assert 'initialLabel: "01-2026"' in html
    assert 'initialValue: "01-2026"' not in html
    assert "01M15SSYCF0VT8JC48GNWG15EX" not in html


def test_sales_invoice_list_renders_legible_period_label(period_picker_app) -> None:
    """El listado de Facturas de Venta muestra el nombre del período."""
    from cacao_accounting.database import User

    user = User.query.filter_by(user="picker-user").first()
    client = period_picker_app.test_client()
    _login(client, user.id)
    pid = _period_id(period_picker_app)
    url = (
        f"/sales/sales-invoice/list?company=cacao"
        f"&accounting_period_from={pid}&accounting_period_to={pid}"
    )
    response = client.get(url)
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert "Listado de Facturas de Venta" in html
    assert 'initialLabel: "01-2026"' in html
    assert "01M15SSYCF0VT8JC48GNWG15EX" not in html


def test_purchase_invoice_list_renders_legible_period_label(period_picker_app) -> None:
    """El listado de Facturas de Compra muestra el nombre del período."""
    from cacao_accounting.database import User

    user = User.query.filter_by(user="picker-user").first()
    client = period_picker_app.test_client()
    _login(client, user.id)
    pid = _period_id(period_picker_app)
    url = (
        f"/buying/purchase-invoice/list?company=cacao"
        f"&accounting_period_from={pid}&accounting_period_to={pid}"
    )
    response = client.get(url)
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert "Listado de Facturas de Compra" in html
    assert 'initialLabel: "01-2026"' in html
    assert "01M15SSYCF0VT8JC48GNWG15EX" not in html


def test_kardex_report_renders_legible_period_label(period_picker_app) -> None:
    """El reporte de Kardex muestra el nombre del período en el selector."""
    from cacao_accounting.database import User

    user = User.query.filter_by(user="picker-user").first()
    client = period_picker_app.test_client()
    _login(client, user.id)
    pid = _period_id(period_picker_app)
    url = (
        f"/reports/kardex?company=cacao"
        f"&accounting_period_from={pid}&accounting_period_to={pid}"
    )
    response = client.get(url)
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert 'initialLabel: "01-2026"' in html
    assert "01M15SSYCF0VT8JC48GNWG15EX" not in html
