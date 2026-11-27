# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 William José Moreno Reyes

"""#2329: dos ediciones rápidas con la misma versión no deben perder una actualización."""

from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from threading import Barrier
from uuid import uuid4

import pytest

from cacao_accounting import create_app
from cacao_accounting.config import configuracion
from cacao_accounting.database import (
    Currency,
    Entity,
    Item,
    ItemPrice,
    Modules,
    PriceList,
    UOM,
    User,
    UserCompanyAccess,
    database,
)

pytestmark = pytest.mark.database


def _app(tmp_path):
    uri = str(configuracion["SQLALCHEMY_DATABASE_URI"])
    if uri.startswith("sqlite"):
        uri = f"sqlite:///{tmp_path / 'quick-edit.sqlite'}"
    elif os.environ.get("CHECK_DATABASE", "").strip().lower() not in {"1", "true", "yes", "on"}:
        pytest.skip("Los motores externos requieren CHECK_DATABASE=true.")
    return create_app(
        {
            **configuracion,
            "SQLALCHEMY_DATABASE_URI": uri,
            "SQLALCHEMY_ENGINE_OPTIONS": {
                **configuracion.get("SQLALCHEMY_ENGINE_OPTIONS", {}),
                "pool_size": 4,
                "max_overflow": 0,
            },
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
            "WTF_CSRF_ENABLED": False,
            "TESTING": True,
            "SECRET_KEY": "test-2329",
            "MODO_ESCRITORIO": False,
        }
    )


def _seed(app, suffix: str, user_id: str) -> str:
    with app.app_context():
        database.create_all()
        module = database.session.execute(database.select(Modules).filter_by(module="admin")).scalar_one_or_none()
        if module is None:
            database.session.add(Modules(module="admin", default=False, enabled=True))
        else:
            module.enabled = True
        database.session.add_all(
            [
                Currency(code=f"C{suffix}", name="Moneda", decimals=2, active=True, default=False),
                Entity(
                    code=f"E{suffix}",
                    name=f"Empresa {suffix}",
                    company_name=f"Empresa {suffix} SA",
                    tax_id=f"T{suffix}",
                    currency=f"C{suffix}",
                    enabled=True,
                    status="default",
                ),
                User(
                    id=user_id,
                    user=f"admin_{suffix}",
                    name="Admin",
                    password=b"unused",
                    classification="admin",
                    active=True,
                    company=f"E{suffix}",
                ),
                UserCompanyAccess(user_id=user_id, company_code=f"E{suffix}"),
                UOM(code=f"U{suffix}", name="Unidad", is_active=True),
            ]
        )
        database.session.flush()
        database.session.add(
            Item(
                code=f"ART{suffix}",
                name="Artículo",
                item_type="service",
                is_stock_item=False,
                is_sale_item=True,
                is_purchase_item=False,
                default_uom=f"U{suffix}",
                is_active=True,
            )
        )
        database.session.flush()
        price_list = PriceList(
            name=f"Lista {suffix}",
            company=f"E{suffix}",
            currency=f"C{suffix}",
            is_selling=True,
            is_active=True,
        )
        database.session.add(price_list)
        database.session.flush()
        price = ItemPrice(
            item_code=f"ART{suffix}",
            price_list_id=price_list.id,
            uom=f"U{suffix}",
            price=Decimal("10"),
            min_qty=Decimal("0"),
        )
        database.session.add(price)
        database.session.commit()
        price_id = price.id
        database.session.remove()
        return price_id


def _client(app, user_id: str):
    client = app.test_client()
    with client.session_transaction() as session:
        session["_user_id"] = user_id
        session["_auth_version"] = 0
        session["_fresh"] = True
    return client


def test_dos_ediciones_concurrentes_no_pierden_actualizacion(tmp_path):
    """Solo una versión puede confirmar; la otra recibe rechazo controlado."""
    app = _app(tmp_path)
    suffix = uuid4().hex[:6]
    user_id = f"user-{suffix}"
    price_id = _seed(app, suffix, user_id)
    barrier = Barrier(2, timeout=30)

    def edit(new_price: str) -> tuple[int, str]:
        client = _client(app, user_id)
        barrier.wait(timeout=10)
        response = client.post(
            f"/settings/item-prices/{price_id}",
            data={"price": new_price, "expected_price": "10"},
            follow_redirects=True,
        )
        return response.status_code, response.get_data(as_text=True)

    try:
        with ThreadPoolExecutor(max_workers=2) as workers:
            results = list(workers.map(edit, ("18.75", "19.25")))
        with app.app_context():
            final = database.session.get(ItemPrice, price_id)
            assert final is not None
            assert final.price in {Decimal("18.7500"), Decimal("19.2500")}
        exitos = [html for status, html in results if "actualizado correctamente" in html]
        rechazos = [html for status, html in results if "El precio cambió mientras editaba" in html]
        assert len(exitos) == 1
        assert len(rechazos) == 1
    finally:
        with app.app_context():
            database.session.remove()
            database.engine.dispose()


def test_dos_listas_predeterminadas_concurrentes_dejan_una_sola(tmp_path):
    """La creación concurrente de predeterminadas no deja dos activas (#2009/#2302)."""
    app = _app(tmp_path)
    suffix = uuid4().hex[:6]
    user_id = f"user-{suffix}"
    _seed(app, suffix, user_id)
    barrier = Barrier(2, timeout=30)

    def create(name: str) -> int:
        client = _client(app, user_id)
        barrier.wait(timeout=10)
        response = client.post(
            "/settings/price-lists",
            data={
                "name": name,
                "company": f"E{suffix}",
                "currency": f"C{suffix}",
                "is_selling": "y",
                "is_active": "y",
                "is_default": "y",
            },
        )
        return response.status_code

    try:
        with ThreadPoolExecutor(max_workers=2) as workers:
            statuses = list(workers.map(create, (f"Default A {suffix}", f"Default B {suffix}")))
        assert statuses == [302, 302]
        with app.app_context():
            defaults = (
                database.session.execute(
                    database.select(PriceList).filter_by(
                        company=f"E{suffix}", is_selling=True, is_default=True, is_active=True
                    )
                )
                .scalars()
                .all()
            )
            assert len(defaults) == 1
    finally:
        with app.app_context():
            database.session.remove()
            database.engine.dispose()


def test_guardar_el_mismo_precio_no_reporta_conflicto(tmp_path):
    """MySQL no informa filas encontradas; el mismo precio debe guardarse sin error."""
    app = _app(tmp_path)
    suffix = uuid4().hex[:6]
    user_id = f"user-{suffix}"
    price_id = _seed(app, suffix, user_id)
    client = _client(app, user_id)

    response = client.post(
        f"/settings/item-prices/{price_id}",
        data={"price": "10", "expected_price": "10"},
        follow_redirects=True,
    )

    html = response.get_data(as_text=True)
    assert response.status_code == 200
    assert "actualizado correctamente" in html
    assert "El precio cambió mientras editaba" not in html
    with app.app_context():
        assert database.session.get(ItemPrice, price_id).price == Decimal("10.0000")
        database.session.remove()
        database.engine.dispose()
