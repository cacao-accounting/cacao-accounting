# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Las casillas de venta y vigencia se respetan al crear listas.

Escenario de negocio (issue #2009): un checkbox desmarcado no se envía; la
ruta aplicaba True por defecto, así que no se podía crear una lista solo de
compras ni una lista inactiva desde la interfaz.
"""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy.pool import StaticPool

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
    database,
)


def _crear_app():
    application = create_app(
        {
            **configuracion,
            "SQLALCHEMY_DATABASE_URI": "sqlite://",
            "SQLALCHEMY_ENGINE_OPTIONS": {
                "poolclass": StaticPool,
                "connect_args": {"check_same_thread": False},
            },
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
            "WTF_CSRF_ENABLED": False,
            "TESTING": True,
            "MODO_ESCRITORIO": False,
        }
    )
    with application.app_context():
        database.create_all()
        database.session.add(UOM(code="Unidad", name="Unidad"))
        database.session.flush()
        database.session.add_all(
            [
                Currency(code="NIO", name="Córdoba", decimals=2, active=True, default=True),
                Modules(module="admin", default=False, enabled=True),
                Modules(module="sales", default=False, enabled=True),
                Entity(
                    code="CACAO",
                    name="Cacao",
                    company_name="Cacao SA",
                    tax_id="J0001",
                    currency="NIO",
                    enabled=True,
                    status="default",
                ),
                User(
                    id="admin",
                    user="admin",
                    name="Administrador",
                    password=b"x",
                    active=True,
                    classification="admin",
                ),
                Item(
                    code="ART-1",
                    name="Artículo",
                    item_type="goods",
                    is_stock_item=False,
                    is_sale_item=True,
                    is_active=True,
                    default_uom="Unidad",
                    standard_rate=Decimal("10"),
                ),
            ]
        )
        database.session.flush()
        database.session.add(
            PriceList(
                name="Venta vigente",
                company="CACAO",
                currency="NIO",
                is_selling=True,
                is_default=True,
                is_active=True,
            )
        )
        database.session.commit()
    return application


def _cliente(application):
    client = application.test_client()
    with client.session_transaction() as session:
        session["_user_id"] = "admin"
        session["_fresh"] = True
    return client


def test_crea_lista_solo_compras_e_inactiva_sin_tocar_la_default():
    """Omitir venta/vigencia persiste False y no altera la lista predeterminada."""
    application = _crear_app()
    try:
        client = _cliente(application)
        respuesta = client.post(
            "/settings/price-lists",
            data={
                "name": "Compras",
                "company": "CACAO",
                "currency": "NIO",
                "is_buying": "on",
            },
        )

        assert respuesta.status_code == 302
        with application.app_context():
            nueva = database.session.execute(database.select(PriceList).filter_by(name="Compras")).scalar_one()
            assert nueva.is_buying is True
            assert nueva.is_selling is False
            assert nueva.is_active is False
            predeterminada = database.session.execute(database.select(PriceList).filter_by(name="Venta vigente")).scalar_one()
            assert predeterminada.is_default is True
            assert database.session.execute(database.select(ItemPrice)).scalars().all() == []
    finally:
        with application.app_context():
            database.session.remove()
            database.engine.dispose()


def test_las_casillas_marcadas_persisten_true():
    """El control positivo conserva venta y vigencia marcadas."""
    application = _crear_app()
    try:
        client = _cliente(application)
        respuesta = client.post(
            "/settings/price-lists",
            data={
                "name": "Venta nueva",
                "company": "CACAO",
                "currency": "NIO",
                "is_selling": "on",
                "is_active": "on",
            },
        )

        assert respuesta.status_code == 302
        with application.app_context():
            nueva = database.session.execute(database.select(PriceList).filter_by(name="Venta nueva")).scalar_one()
            assert nueva.is_selling is True
            assert nueva.is_active is True
    finally:
        with application.app_context():
            database.session.remove()
            database.engine.dispose()
