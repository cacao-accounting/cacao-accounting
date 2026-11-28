# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 William José Moreno Reyes

"""#1791: el alta de landed cost rechaza payloads inválidos sin dejar evidencia."""

from __future__ import annotations

from datetime import date
from uuid import uuid4

import pytest
from sqlalchemy import inspect, select

from cacao_accounting.database import (
    Accounts,
    Entity,
    ImportLandedCost,
    ImportLandedCostCharge,
    ImportLandedCostItem,
    Item,
    PurchaseInvoice,
    User,
    database,
)


def _escenario(env, *, items: list[Item] | None = None):
    """Crea una factura aprobada y un cliente autenticado sobre SQLite aislada."""
    suffix = uuid4().hex[:6]
    with env.app.app_context():
        database.session.add_all(items or [])
        invoice = PurchaseInvoice(
            company="cacao",
            document_type="purchase_invoice",
            document_no=f"PI-1791-{suffix}",
            posting_date=date(2026, 5, 15),
            docstatus=1,
        )
        database.session.add(invoice)
        database.session.commit()
        invoice_id = str(inspect(invoice).identity[0])
        admin_id = database.session.execute(select(User).filter_by(user="admin")).scalar_one().id
    client = env.app.test_client()
    with client.session_transaction() as session:
        session["_user_id"] = str(admin_id)
        session["_fresh"] = True
    return client, invoice_id, suffix


def _datos(invoice_id: str, **overrides) -> dict[str, str]:
    """Payload mínimo válido con una línea y un cargo capitalizable."""
    data = {
        "company": "cacao",
        "posting_date": "2026-05-15",
        "from_invoice": invoice_id,
        "allocation_method": "by_value",
        "item_item_code_0": "ART-1791",
        "item_item_name_0": "Artículo",
        "item_qty_0": "1",
        "item_uom_0": "UND",
        "item_rate_0": "100",
        "charge_concept_0": "Flete",
        "charge_type_0": "charge",
        "charge_amount_0": "10",
    }
    data.update(overrides)
    return data


def _articulo(code: str, **overrides) -> Item:
    """Construye un artículo de inventario comprable por defecto."""
    values = {
        "code": code,
        "name": code,
        "item_type": "goods",
        "is_stock_item": True,
        "is_purchase_item": True,
        "default_uom": "UND",
    }
    values.update(overrides)
    return Item(**values)


def _assert_sin_evidencia(env, invoice_id: str):
    """El rechazo no deja cabecera, líneas ni cargos confirmados."""
    with env.app.app_context():
        assert (
            database.session.execute(select(ImportLandedCost).filter_by(purchase_invoice_id=invoice_id)).scalars().all() == []
        )
        assert database.session.execute(select(ImportLandedCostItem)).scalars().all() == []
        assert database.session.execute(select(ImportLandedCostCharge)).scalars().all() == []


def test_cantidad_cero_devuelve_error_controlado(entorno_contable_aislado):
    """La CHECK de cantidad positiva se valida antes del flush."""
    env = entorno_contable_aislado
    client, invoice_id, _suffix = _escenario(env, items=[_articulo("ART-1791")])

    response = client.post("/buying/import-landed-cost/new", data=_datos(invoice_id, item_qty_0="0"))

    assert response.status_code == 200
    assert "La cantidad debe ser mayor que cero." in response.get_data(as_text=True)
    _assert_sin_evidencia(env, invoice_id)


def test_articulo_inexistente_devuelve_error_controlado(entorno_contable_aislado):
    """Un código manipulado no llega a la restricción FK del modelo."""
    env = entorno_contable_aislado
    client, invoice_id, suffix = _escenario(env)
    missing = f"NO-EXISTE-{suffix}"

    response = client.post(
        "/buying/import-landed-cost/new",
        data=_datos(invoice_id, item_item_code_0=missing),
    )

    assert response.status_code == 200
    assert f"El item {missing} no existe." in response.get_data(as_text=True)
    _assert_sin_evidencia(env, invoice_id)


@pytest.mark.parametrize(
    ("overrides", "code"),
    [
        ({"is_purchase_item": False}, "NO-COMPRA-1791"),
        ({"is_stock_item": False}, "NO-STOCK-1791"),
        ({"is_active": False}, "INACTIVO-1791"),
    ],
)
def test_articulo_no_habilitado_devuelve_error_controlado(entorno_contable_aislado, overrides, code):
    """Solo artículos activos, comprables y de inventario capitalizan costos."""
    env = entorno_contable_aislado
    client, invoice_id, _suffix = _escenario(env, items=[_articulo(code, **overrides)])

    response = client.post(
        "/buying/import-landed-cost/new",
        data=_datos(invoice_id, item_item_code_0=code),
    )

    assert response.status_code == 200
    assert f"El item {code} no está habilitado para compra." in response.get_data(as_text=True)
    _assert_sin_evidencia(env, invoice_id)


def test_cargo_cero_devuelve_error_controlado(entorno_contable_aislado):
    """Un cargo sin importe no crea un documento aparentemente válido."""
    env = entorno_contable_aislado
    client, invoice_id, _suffix = _escenario(env, items=[_articulo("ART-1791")])

    response = client.post(
        "/buying/import-landed-cost/new",
        data=_datos(invoice_id, charge_amount_0="0"),
    )

    assert response.status_code == 200
    assert "El monto debe ser mayor que cero." in response.get_data(as_text=True)
    _assert_sin_evidencia(env, invoice_id)


def test_cuenta_de_cargo_inexistente_devuelve_error_controlado(entorno_contable_aislado):
    """La cuenta del cargo se valida antes de persistir la relación FK."""
    env = entorno_contable_aislado
    client, invoice_id, _suffix = _escenario(env, items=[_articulo("ART-1791")])

    response = client.post(
        "/buying/import-landed-cost/new",
        data=_datos(invoice_id, charge_account_id_0="CUENTA-INEXISTENTE"),
    )

    assert response.status_code == 200
    assert "La cuenta contable indicada no existe para la compañía." in response.get_data(as_text=True)
    _assert_sin_evidencia(env, invoice_id)


def test_cuenta_de_cargo_de_otra_compania_devuelve_error_controlado(entorno_contable_aislado):
    """Una cuenta existente fuera de la compañía también se rechaza."""
    env = entorno_contable_aislado
    suffix = uuid4().hex[:6]
    other_company = Entity(
        code=f"O{suffix}",
        name=f"Otra {suffix}",
        company_name=f"Otra {suffix} SA",
        tax_id=f"T-{suffix}",
        currency="NIO",
        enabled=True,
    )
    other_account = Accounts(
        entity=other_company.code,
        code=f"A{suffix}",
        name="Cuenta ajena",
        classification="expense",
        account_type="expense",
    )
    with env.app.app_context():
        database.session.add(other_company)
        database.session.flush()
        database.session.add(other_account)
        database.session.commit()
        other_account_id = other_account.id
    client, invoice_id, _suffix = _escenario(env, items=[_articulo("ART-1791")])

    response = client.post(
        "/buying/import-landed-cost/new",
        data=_datos(invoice_id, charge_account_id_0=other_account_id),
    )

    assert response.status_code == 200
    assert "La cuenta contable indicada no existe para la compañía." in response.get_data(as_text=True)
    _assert_sin_evidencia(env, invoice_id)
