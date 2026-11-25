# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#2098: la aprobación de recepción bloquea la orden de compra."""

from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from decimal import Decimal
from threading import Barrier, Event, current_thread
from typing import Any
from uuid import uuid4

import pytest
from sqlalchemy import event, text

from cacao_accounting import create_app
from cacao_accounting.compras import services as compras_services
from cacao_accounting.config import configuracion
from cacao_accounting.database import (
    Currency,
    DocumentRelation,
    Entity,
    Item,
    PurchaseOrder,
    PurchaseOrderItem,
    PurchaseReceipt,
    PurchaseReceiptItem,
    UOM,
    database,
)

FECHA = date(2026, 5, 15)


def test_submit_bloquea_la_orden_antes_de_validar_cantidades(app, entorno_contable, authenticated_client, monkeypatch):
    """Dos recepciones contra la misma OC se serializan por el lock documental."""
    suffix = uuid4().hex[:8]
    with app.app_context():
        orden = PurchaseOrder(
            company="cacao",
            posting_date=FECHA,
            docstatus=1,
            document_no=f"PO-LOCK-{suffix}",
            transaction_currency="NIO",
            base_currency="NIO",
            exchange_rate=Decimal("1"),
        )
        database.session.add(orden)
        database.session.flush()
        recepcion = PurchaseReceipt(
            company="cacao",
            posting_date=FECHA,
            docstatus=0,
            document_no=f"PR-LOCK-{suffix}",
            purchase_order_id=orden.id,
            transaction_currency="NIO",
            base_currency="NIO",
            exchange_rate=Decimal("1"),
        )
        database.session.add(recepcion)
        database.session.commit()
        orden_id = orden.id
        recepcion_id = recepcion.id

    llamadas: list[tuple[str, str]] = []
    original = compras_services.lock_document_flow_document

    def tracking(document_type: str, document_id: str) -> None:
        llamadas.append((document_type, document_id))
        original(document_type, document_id)

    monkeypatch.setattr(compras_services, "lock_document_flow_document", tracking)
    respuesta = authenticated_client().post(f"/buying/purchase-receipt/{recepcion_id}/submit")

    assert respuesta.status_code == 302
    assert ("purchase_order", orden_id) in llamadas


def test_validacion_final_de_aprobacion_bloquea_la_orden(app, monkeypatch):
    """El camino de aprobación también serializa contra la orden de compra."""
    from types import SimpleNamespace

    from cacao_accounting.approval_engine import ApprovalEngine

    llamadas: list[tuple[str, str]] = []
    monkeypatch.setattr(
        compras_services,
        "lock_document_flow_document",
        lambda document_type, document_id: llamadas.append((document_type, document_id)),
    )
    monkeypatch.setattr(compras_services, "_validate_receipt_quantities_against_po", lambda _id: None)
    monkeypatch.setattr("cacao_accounting.document_flow.validation.validate_submit_prerequisites", lambda *_a, **_k: None)
    monkeypatch.setattr("cacao_accounting.document_flow.validate_currency_contract", lambda *_a, **_k: None)
    import importlib

    inventario_service = importlib.import_module("cacao_accounting.inventario.service")
    monkeypatch.setattr(inventario_service, "validate_batch_serial_draft", lambda *_a, **_k: None)
    documento = SimpleNamespace(id="REC-APROBACION", purchase_order_id="PO-APROBACION", is_return=False)

    with app.app_context():
        ApprovalEngine._validate_final_submission("purchase_receipt", documento)

    assert ("purchase_order", "PO-APROBACION") in llamadas


@pytest.mark.database
def test_dos_aprobaciones_concurrentes_no_exceden_la_orden():
    """Dos recepciones de 6 contra una OC de 10 no pueden aprobar 12 en PostgreSQL."""
    app = create_app({**configuracion, "TESTING": True})
    with app.app_context():
        if database.engine.dialect.name != "postgresql":
            pytest.skip("La carrera de aprobación requiere PostgreSQL.")
        sufijo = uuid4().hex[:6].upper()
        company = f"RC{sufijo}"
        if database.session.execute(database.select(UOM).filter_by(code="UND")).scalar_one_or_none() is None:
            database.session.add(UOM(code="UND", name="Unidad"))
        database.session.add(
            Entity(
                code=company,
                name=f"Empresa {company}",
                company_name=f"Empresa {company}",
                tax_id=f"R{sufijo}",
                currency="NIO",
                enabled=True,
                status="activo",
            )
        )
        database.session.flush()
        item = Item(
            code=f"ITM-{sufijo}",
            name="Artículo recepción",
            item_type="goods",
            is_stock_item=False,
            default_uom="UND",
        )
        database.session.add(item)
        database.session.flush()
        orden = PurchaseOrder(
            company=company,
            posting_date=FECHA,
            docstatus=1,
            document_no=f"PO-RACE-{sufijo}",
            transaction_currency="NIO",
            base_currency="NIO",
            exchange_rate=Decimal("1"),
        )
        database.session.add(orden)
        database.session.flush()
        orden_item = PurchaseOrderItem(
            purchase_order_id=orden.id,
            item_code=item.code,
            qty=Decimal("10"),
            qty_in_base_uom=Decimal("10"),
            uom="UND",
            rate=Decimal("1"),
            amount=Decimal("10"),
        )
        database.session.add(orden_item)
        database.session.flush()
        receipts: list[str] = []
        relations: list[str] = []
        for indice in range(2):
            receipt = PurchaseReceipt(
                company=company,
                posting_date=FECHA,
                docstatus=0,
                document_no=f"PR-RACE-{sufijo}-{indice}",
                purchase_order_id=orden.id,
                transaction_currency="NIO",
                base_currency="NIO",
                exchange_rate=Decimal("1"),
            )
            database.session.add(receipt)
            database.session.flush()
            receipt_item = PurchaseReceiptItem(
                purchase_receipt_id=receipt.id,
                item_code=item.code,
                qty=Decimal("6"),
                qty_in_base_uom=Decimal("6"),
                uom="UND",
                rate=Decimal("1"),
                amount=Decimal("6"),
            )
            database.session.add(receipt_item)
            database.session.flush()
            relation = DocumentRelation(
                company=company,
                source_type="purchase_order",
                source_id=orden.id,
                source_item_id=orden_item.id,
                target_type="purchase_receipt",
                target_id=receipt.id,
                target_item_id=receipt_item.id,
                qty=Decimal("6"),
                qty_in_base_uom=Decimal("6"),
                uom="UND",
                relation_type="consume",
                status="active",
            )
            database.session.add(relation)
            database.session.flush()
            receipts.append(receipt.id)
            relations.append(relation.id)
        database.session.commit()
        orden_id = orden.id
        orden_item_id = orden_item.id
        item_code = item.code

    barrera = Barrier(2)

    def aprobar(receipt_id: str) -> str:
        with app.app_context():
            try:
                barrera.wait(timeout=10)
                compras_services._validate_receipt_quantities_against_po(receipt_id)
                receipt = database.session.get(PurchaseReceipt, receipt_id)
                receipt.docstatus = 1
                database.session.commit()
                return "approved"
            except ValueError:
                database.session.rollback()
                return "rejected"
            finally:
                database.session.remove()

    try:
        with ThreadPoolExecutor(max_workers=2) as workers:
            outcomes = list(workers.map(aprobar, receipts))

        assert sorted(outcomes) == ["approved", "rejected"], outcomes
        with app.app_context():
            aprobadas = (
                database.session.execute(database.select(DocumentRelation).filter(DocumentRelation.id.in_(relations)))
                .scalars()
                .all()
            )
            total = sum(
                relation.qty_in_base_uom or Decimal("0")
                for relation in aprobadas
                if database.session.get(PurchaseReceipt, relation.target_id).docstatus == 1
            )
            assert total <= Decimal("10")
    finally:
        with app.app_context():
            database.session.rollback()
            database.session.execute(database.delete(DocumentRelation).where(DocumentRelation.id.in_(relations)))
            database.session.execute(
                database.delete(PurchaseReceiptItem).where(PurchaseReceiptItem.purchase_receipt_id.in_(receipts))
            )
            database.session.execute(database.delete(PurchaseReceipt).where(PurchaseReceipt.id.in_(receipts)))
            database.session.execute(database.delete(PurchaseOrderItem).where(PurchaseOrderItem.id == orden_item_id))
            database.session.execute(database.delete(PurchaseOrder).where(PurchaseOrder.id == orden_id))
            database.session.execute(database.delete(Item).where(Item.code == item_code))
            database.session.execute(database.delete(Entity).where(Entity.code == company))
            database.session.commit()


def _sembrar_carrera_mysql(application, sufijo: str) -> dict[str, Any]:
    """Crea una OC de 10 y dos recepciones de 6 vinculadas a la misma línea."""
    company = f"RC{sufijo}"
    currency_code = f"RC{sufijo}"
    uom_code = f"UND{sufijo}"
    item_code = f"ITM-{sufijo}"
    with application.app_context():
        database.create_all()
        database.session.add(Currency(code=currency_code, name=f"Moneda {sufijo}", decimals=2, active=True, default=False))
        database.session.add(UOM(code=uom_code, name=f"Unidad {sufijo}"))
        database.session.add(
            Entity(
                code=company,
                name=f"Empresa {company}",
                company_name=f"Empresa {company}",
                tax_id=f"R{sufijo}",
                currency=currency_code,
                enabled=True,
                status="activo",
            )
        )
        database.session.flush()
        database.session.add(
            Item(code=item_code, name="Artículo recepción", item_type="goods", is_stock_item=False, default_uom=uom_code)
        )
        database.session.flush()
        orden = PurchaseOrder(
            company=company,
            posting_date=FECHA,
            docstatus=1,
            document_no=f"PO-MYSQL-{sufijo}",
            transaction_currency=currency_code,
            base_currency=currency_code,
            exchange_rate=Decimal("1"),
        )
        database.session.add(orden)
        database.session.flush()
        orden_item = PurchaseOrderItem(
            purchase_order_id=orden.id,
            item_code=item_code,
            qty=Decimal("10"),
            qty_in_base_uom=Decimal("10"),
            uom=uom_code,
            rate=Decimal("1"),
            amount=Decimal("10"),
        )
        database.session.add(orden_item)
        database.session.flush()
        receipts: list[str] = []
        relations: list[str] = []
        for indice in range(2):
            receipt = PurchaseReceipt(
                company=company,
                posting_date=FECHA,
                docstatus=0,
                document_no=f"PR-MYSQL-{sufijo}-{indice}",
                purchase_order_id=orden.id,
                transaction_currency=currency_code,
                base_currency=currency_code,
                exchange_rate=Decimal("1"),
            )
            database.session.add(receipt)
            database.session.flush()
            receipt_item = PurchaseReceiptItem(
                purchase_receipt_id=receipt.id,
                item_code=item_code,
                qty=Decimal("6"),
                qty_in_base_uom=Decimal("6"),
                uom=uom_code,
                rate=Decimal("1"),
                amount=Decimal("6"),
            )
            database.session.add(receipt_item)
            database.session.flush()
            relation = DocumentRelation(
                company=company,
                source_type="purchase_order",
                source_id=orden.id,
                source_item_id=orden_item.id,
                target_type="purchase_receipt",
                target_id=receipt.id,
                target_item_id=receipt_item.id,
                qty=Decimal("6"),
                qty_in_base_uom=Decimal("6"),
                uom=uom_code,
                relation_type="consume",
                status="active",
            )
            database.session.add(relation)
            database.session.flush()
            receipts.append(receipt.id)
            relations.append(relation.id)
        database.session.commit()
        return {
            "company": company,
            "currency": currency_code,
            "uom": uom_code,
            "item": item_code,
            "order": orden.id,
            "receipts": receipts,
            "relations": relations,
        }


def _limpiar_carrera_mysql(application, ids: dict[str, Any]) -> None:
    """Retira los datos aislados de la carrera MySQL."""
    with application.app_context():
        database.session.rollback()
        database.session.execute(database.delete(DocumentRelation).where(DocumentRelation.id.in_(ids["relations"])))
        database.session.execute(
            database.delete(PurchaseReceiptItem).where(PurchaseReceiptItem.purchase_receipt_id.in_(ids["receipts"]))
        )
        database.session.execute(database.delete(PurchaseReceipt).where(PurchaseReceipt.id.in_(ids["receipts"])))
        database.session.execute(database.delete(PurchaseOrder).where(PurchaseOrder.id == ids["order"]))
        database.session.execute(database.delete(Item).where(Item.code == ids["item"]))
        database.session.execute(database.delete(Entity).where(Entity.code == ids["company"]))
        database.session.execute(database.delete(Currency).where(Currency.code == ids["currency"]))
        database.session.execute(database.delete(UOM).where(UOM.code == ids["uom"]))
        database.session.commit()
        database.session.remove()


@pytest.mark.database
def test_mysql_recepcion_ve_consumo_confirmado_tras_snapshot():
    """En MySQL REPEATABLE READ la perdedora no reutiliza el snapshot previo al commit."""
    configured_uri = str(configuracion["SQLALCHEMY_DATABASE_URI"])
    if not configured_uri.startswith("mysql"):
        pytest.skip("La regresión de snapshot requiere MySQL.")
    if os.environ.get("CHECK_DATABASE", "").strip().lower() not in {"1", "true", "yes", "on"}:
        pytest.skip("Los motores externos requieren CHECK_DATABASE=true.")

    application = create_app(
        {
            **configuracion,
            "SQLALCHEMY_DATABASE_URI": configured_uri,
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
            "TESTING": True,
            "MODO_ESCRITORIO": False,
        }
    )
    with application.app_context():
        if database.session.get_bind().dialect.name != "mysql":
            pytest.skip("La regresión de snapshot requiere MySQL.")
        isolation = database.session.execute(text("SELECT @@transaction_isolation")).scalar_one()
        if str(isolation).replace("_", "-").upper() != "REPEATABLE-READ":
            pytest.skip("La regresión requiere el aislamiento MySQL REPEATABLE READ.")
        database.session.remove()

    ids = _sembrar_carrera_mysql(application, uuid4().hex[:6].upper())
    hilo_perdedor: list[Any] = []
    lock_alcanzado = Event()
    ganador_confirmo = Event()

    def detener_al_perdedor_antes_del_lock(_conn, _cursor, statement, _params, _context, _executemany) -> None:
        if current_thread() is not hilo_perdedor[0] or "document_flow_lock" not in statement.lower():
            return
        lock_alcanzado.set()
        if not ganador_confirmo.wait(timeout=30):
            raise RuntimeError("La transacción ganadora no confirmó a tiempo.")

    def perdedor() -> str:
        hilo_perdedor.append(current_thread())
        with application.app_context():
            try:
                # Lectura ordinaria previa al lock: fija el snapshot de MySQL.
                database.session.execute(database.select(DocumentRelation).filter_by(target_id=ids["receipts"][1])).all()
                compras_services._lock_receipt_purchase_orders(ids["receipts"][1], ids["order"])
                compras_services._validate_receipt_quantities_against_po(ids["receipts"][1])
                receipt = database.session.get(PurchaseReceipt, ids["receipts"][1])
                assert receipt is not None
                receipt.docstatus = 1
                database.session.commit()
                return "approved"
            except ValueError:
                database.session.rollback()
                return "rejected"
            finally:
                database.session.remove()

    event.listen(database.engine, "before_cursor_execute", detener_al_perdedor_antes_del_lock)
    try:
        with ThreadPoolExecutor(max_workers=1) as workers:
            futuro = workers.submit(perdedor)
            assert lock_alcanzado.wait(timeout=15)
            with application.app_context():
                compras_services._validate_receipt_quantities_against_po(ids["receipts"][0])
                ganador = database.session.get(PurchaseReceipt, ids["receipts"][0])
                assert ganador is not None
                ganador.docstatus = 1
                database.session.commit()
                database.session.remove()
            ganador_confirmo.set()
            resultado = futuro.result(timeout=30)

        assert resultado == "rejected"
        with application.app_context():
            aprobadas = database.session.scalars(
                database.select(PurchaseReceipt).where(PurchaseReceipt.id.in_(ids["receipts"]), PurchaseReceipt.docstatus == 1)
            ).all()
            assert len(aprobadas) == 1
            assert aprobadas[0].id == ids["receipts"][0]
    finally:
        ganador_confirmo.set()
        event.remove(database.engine, "before_cursor_execute", detener_al_perdedor_antes_del_lock)
        _limpiar_carrera_mysql(application, ids)
        with application.app_context():
            database.engine.dispose()
