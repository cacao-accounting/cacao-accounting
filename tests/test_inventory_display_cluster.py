# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Presentación de categoría y lote en inventario.

Escenario de negocio:
- #1944: la lista de artículos mostraba siempre «-» en Categoría.
- #1960: el detalle usaba batch_id interno en lugar de Batch.batch_no.
"""

from __future__ import annotations

from decimal import Decimal
from types import SimpleNamespace

from flask import render_template_string
from sqlalchemy.pool import StaticPool

from cacao_accounting import create_app
from cacao_accounting.config import configuracion
from cacao_accounting.database import (
    Batch,
    Currency,
    Entity,
    Item,
    ItemCategory,
    Modules,
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
        database.session.add_all(
            [
                Modules(module="inventory", default=False, enabled=True),
                Currency(code="NIO", name="Córdoba", decimals=2, active=True, default=True),
                Entity(
                    code="cacao",
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
                UOM(code="UND", name="Unidad", is_active=True),
            ]
        )
        database.session.flush()
        categoria = ItemCategory(name="Materia Prima", is_active=True)
        database.session.add(categoria)
        database.session.flush()
        item = Item(
            code="ART-1",
            name="Artículo",
            item_type="goods",
            is_stock_item=True,
            default_uom="UND",
            item_category_id=categoria.id,
            is_active=True,
        )
        database.session.add(item)
        batch = Batch(item_code="ART-1", batch_no="LOTE-PUBLICO", is_active=True)
        database.session.add(batch)
        database.session.commit()
        ids = {"batch": batch.id, "batch_no": batch.batch_no, "category": categoria.name}
    return application, ids


def _cliente(application):
    client = application.test_client()
    with client.session_transaction() as session:
        session["_user_id"] = "admin"
        session["_fresh"] = True
    return client


def test_lista_de_articulos_muestra_la_categoria():
    """#1944: la columna Categoría resuelve el nombre de ItemCategory."""
    application, ids = _crear_app()
    try:
        client = _cliente(application)
        respuesta = client.get("/inventory/item/list")

        assert respuesta.status_code == 200
        html = respuesta.get_data(as_text=True)
        assert ids["category"] in html
        assert "<td>-</td>" not in html
    finally:
        with application.app_context():
            database.session.remove()
            database.engine.dispose()


def test_detalle_muestra_el_numero_de_lote_no_el_id_interno():
    """#1960: la macro resuelve Batch.batch_no y no expone el ULID del FK."""
    application, ids = _crear_app()
    try:
        with application.app_context():
            item = SimpleNamespace(
                item_code="ART-1",
                item_name="Artículo",
                uom="UND",
                qty=Decimal("1"),
                batch_id=ids["batch"],
                serial_no="SERIE-1",
            )
            html = render_template_string(
                '{% import "detail_view_macros.html" as m %}' "{{ m.detail_lines_table([(item,)], show_pricing=False) }}",
                item=item,
            )

            assert f'data-batch-no="{ids["batch_no"]}"' in html
            assert ids["batch"] not in html
    finally:
        with application.app_context():
            database.session.remove()
            database.engine.dispose()
