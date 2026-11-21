# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#2113: la cancelación toma el lock documental antes de revisar hijas."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest

from cacao_accounting import create_app
from cacao_accounting.config import configuracion
from cacao_accounting.database import (
    Currency,
    DocumentRelation,
    Entity,
    Item,
    Modules,
    Party,
    SalesOrder,
    SalesOrderItem,
    SalesQuotation,
    SalesQuotationItem,
    SalesRequest,
    UOM,
    User,
    database,
)
from cacao_accounting.document_flow.service import DocumentFlowError, create_document_relation, lock_document_flow_document
from cacao_accounting.ventas import routes as ventas_routes


def _build_isolated_app(database_uri: str):
    """Crea una aplicación aislada sobre una base SQLite en archivo."""
    return create_app(
        {
            **configuracion,
            "SQLALCHEMY_DATABASE_URI": database_uri,
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
            "WTF_CSRF_ENABLED": False,
            "TESTING": True,
            "MODO_ESCRITORIO": False,
        }
    )


def _seed_relation_documents(app) -> dict[str, str]:
    """Siembra una cotificación aprobada con una orden de venta destino."""
    suffix = uuid4().hex[:6]
    with app.app_context():
        database.create_all()
        database.session.add_all(
            [
                Currency(code="NIO", name="Córdoba", decimals=2, active=True, default=True),
                Modules(module="sales", default=True, enabled=True),
                Entity(
                    code="alpha",
                    name="Alpha",
                    company_name=f"Alpha {suffix}",
                    tax_id=f"TAX-{suffix}",
                    currency="NIO",
                    enabled=True,
                    status="default",
                ),
                UOM(code="EA", name="Each", is_active=True),
            ]
        )
        database.session.flush()
        item_code = f"ITEM-{suffix}"
        database.session.add(Item(code=item_code, name="Artículo", item_type="goods", is_stock_item=True, default_uom="EA"))
        database.session.flush()
        customer = Party(code=f"CUST-{suffix}", name="Cliente", is_customer=True, is_active=True)
        database.session.add(customer)
        database.session.flush()
        quotation = SalesQuotation(
            company="alpha",
            document_no=f"SQ-{suffix}",
            customer_id=customer.id,
            customer_name=customer.name,
            posting_date=date(2026, 5, 10),
            docstatus=1,
        )
        order = SalesOrder(
            company="alpha",
            document_no=f"SO-{suffix}",
            customer_id=customer.id,
            customer_name=customer.name,
            posting_date=date(2026, 5, 11),
            docstatus=1,
        )
        database.session.add_all([quotation, order])
        database.session.flush()
        quotation_item = SalesQuotationItem(
            sales_quotation_id=quotation.id,
            item_code=item_code,
            item_name="Artículo",
            qty=Decimal("5"),
            qty_in_base_uom=Decimal("5"),
            uom="EA",
            rate=Decimal("10"),
            amount=Decimal("50"),
        )
        order_item = SalesOrderItem(
            sales_order_id=order.id,
            item_code=item_code,
            item_name="Artículo",
            qty=Decimal("3"),
            qty_in_base_uom=Decimal("3"),
            uom="EA",
            rate=Decimal("10"),
            amount=Decimal("30"),
        )
        database.session.add_all([quotation_item, order_item])
        database.session.commit()
        ids = {
            "source_id": quotation.id,
            "source_item_id": quotation_item.id,
            "target_id": order.id,
            "target_item_id": order_item.id,
        }
        database.session.remove()
    return ids


def test_relacion_no_confirma_tras_cancelacion_commitida(tmp_path):
    """La relectura posterior al lock observa la cancelación confirmada por otra transacción."""
    app = _build_isolated_app(f"sqlite:///{tmp_path / 'relation-status.sqlite'}")
    ids = _seed_relation_documents(app)

    fabrica = database.session.session_factory
    expiracion_original = fabrica.kw.get("expire_on_commit")
    fabrica.kw["expire_on_commit"] = False
    try:
        with app.app_context():
            creador = database.session
            origen_en_caché = creador.get(SalesQuotation, ids["source_id"])
            destino_en_caché = creador.get(SalesOrder, ids["target_id"])
            assert origen_en_caché.docstatus == destino_en_caché.docstatus == 1
            creador.commit()

            with app.app_context():
                cancelador = database.session
                lock_document_flow_document("sales_quotation", ids["source_id"])
                cancelador.get(SalesQuotation, ids["source_id"]).docstatus = 2
                cancelador.commit()
                cancelador.remove()

            # El identity map del creador conserva la foto tomada antes de la
            # cancelación; sin relectura el lock no sirve para validar estados.
            assert origen_en_caché.docstatus == 1

            with pytest.raises(DocumentFlowError, match="origen debe estar aprobado"):
                create_document_relation(
                    source_type="sales_quotation",
                    source_id=ids["source_id"],
                    source_item_id=ids["source_item_id"],
                    target_type="sales_order",
                    target_id=ids["target_id"],
                    target_item_id=ids["target_item_id"],
                    qty=Decimal("3"),
                )
            creador.rollback()

        with app.app_context():
            assert database.session.execute(database.select(DocumentRelation.id)).scalar_one_or_none() is None
    finally:
        if expiracion_original is None:
            fabrica.kw.pop("expire_on_commit", None)
        else:
            fabrica.kw["expire_on_commit"] = expiracion_original
        with app.app_context():
            database.session.remove()
            database.engine.dispose()


def test_cancelacion_bloquea_el_documento_antes_de_revisar_relaciones(
    app, entorno_contable, authenticated_client, monkeypatch
):
    """El lock compartido serializa la cancelación con nuevas relaciones."""
    suffix = uuid4().hex[:8]
    with app.app_context():
        pedido = SalesRequest(
            company="cacao",
            posting_date=date(2026, 5, 15),
            docstatus=1,
            document_no=f"SR-LOCK-{suffix}",
            transaction_currency="NIO",
            base_currency="NIO",
            exchange_rate=Decimal("1"),
        )
        database.session.add(pedido)
        database.session.commit()
        request_id = pedido.id

    llamadas: list[tuple[str, str]] = []
    original = ventas_routes.lock_document_flow_document

    def tracking(document_type: str, document_id: str) -> None:
        llamadas.append((document_type, document_id))
        original(document_type, document_id)

    monkeypatch.setattr(ventas_routes, "lock_document_flow_document", tracking)
    respuesta = authenticated_client().post(f"/sales/sales-request/{request_id}/cancel")

    assert respuesta.status_code == 302
    assert ("sales_request", request_id) in llamadas


def test_aprobacion_de_cancelacion_bloquea_antes_de_validar(app, entorno_contable, monkeypatch):
    """La vía de aprobación adquiere el lock antes de revisar hijas."""
    from types import SimpleNamespace

    from cacao_accounting.approval_engine import ApprovalEngine
    from cacao_accounting.database import SalesOrder

    suffix = uuid4().hex[:8]
    with app.app_context():
        orden = SalesOrder(
            company="cacao",
            posting_date=date(2026, 5, 15),
            docstatus=1,
            document_no=f"SO-APR-{suffix}",
            transaction_currency="NIO",
            base_currency="NIO",
            exchange_rate=Decimal("1"),
        )
        database.session.add(orden)
        database.session.commit()
        orden_id = orden.id
        usuario_id = database.session.execute(database.select(User.id).filter_by(user="admin")).scalar_one()
        usuario = SimpleNamespace(id=str(usuario_id), name="Admin")

    orden_llamadas: list[str] = []
    monkeypatch.setattr(
        "cacao_accounting.document_flow.lock_document_flow_document",
        lambda *_args, **_kwargs: orden_llamadas.append("lock"),
    )
    monkeypatch.setattr(
        ApprovalEngine,
        "_validate_final_cancellation",
        staticmethod(lambda *_args, **_kwargs: orden_llamadas.append("validate")),
    )
    monkeypatch.setattr(
        ApprovalEngine,
        "_execute_cancel",
        staticmethod(lambda *_args, **_kwargs: orden_llamadas.append("execute")),
    )

    solicitud = SimpleNamespace(
        document_type="cancel_sales_order",
        document_id=orden_id,
        cancellation_reason="Prueba",
        cancellation_date=date(2026, 5, 15),
        created_at=None,
    )
    with app.app_context(), app.test_request_context("/"):
        orden_actual = database.session.get(SalesOrder, orden_id)
        ApprovalEngine._finalize_approval(solicitud, orden_actual, usuario)

    assert orden_llamadas == ["lock", "validate", "execute"]
