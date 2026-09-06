# SPDX-License-Identifier: Apache-2.0
"""Pruebas para el fix de #853: versionado de líneas y eventos idempotentes.

- Las líneas de recepción/factura se marcan como superseded en vez de eliminarse.
- emit_economic_event no duplica eventos documentales.
- reconstruct_reconciliation_state deduplica eventos existentes.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from cacao_accounting import create_app
from cacao_accounting.config import configuracion
from cacao_accounting.database import (
    PurchaseEconomicEvent,
    PurchaseInvoiceItem,
    PurchaseReceiptItem,
    database,
)


@pytest.fixture()
def app_ctx():
    """Aplicación aislada con base SQLite en memoria."""
    app = create_app({**configuracion, "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:"})
    with app.app_context():
        database.create_all()
        yield app


# ---------------------------------------------------------------------------
# Líneas de recepción: is_superseded en vez de delete
# ---------------------------------------------------------------------------


def test_receipt_item_is_superseded_defaults_false(app_ctx) -> None:
    """Una línea nueva no está superseded."""
    item = PurchaseReceiptItem(
        purchase_receipt_id="PR-001",
        item_code="ART-001",
        qty=Decimal("5"),
        rate=Decimal("10"),
        amount=Decimal("50"),
    )
    database.session.add(item)
    database.session.flush()
    assert item.is_superseded is False


def test_receipt_item_superseded_preserves_row(app_ctx) -> None:
    """Marcar una línea como superseded no la elimina de la base de datos."""
    item = PurchaseReceiptItem(
        purchase_receipt_id="PR-001",
        item_code="ART-001",
        qty=Decimal("5"),
        rate=Decimal("10"),
        amount=Decimal("50"),
    )
    database.session.add(item)
    database.session.flush()
    item_id = item.id

    item.is_superseded = True
    database.session.flush()

    persisted = database.session.get(PurchaseReceiptItem, item_id)
    assert persisted is not None
    assert persisted.is_superseded is True


def test_receipt_items_superseded_filter(app_ctx) -> None:
    """El filtro is_superseded=False distingue líneas vigentes de obsoletas."""
    old_item = PurchaseReceiptItem(
        purchase_receipt_id="PR-002",
        item_code="ART-001",
        qty=Decimal("5"),
        rate=Decimal("10"),
        amount=Decimal("50"),
        is_superseded=True,
    )
    new_item = PurchaseReceiptItem(
        purchase_receipt_id="PR-002",
        item_code="ART-001",
        qty=Decimal("3"),
        rate=Decimal("10"),
        amount=Decimal("30"),
        is_superseded=False,
    )
    database.session.add_all([old_item, new_item])
    database.session.flush()

    active = (
        database.session.execute(
            database.select(PurchaseReceiptItem).filter_by(purchase_receipt_id="PR-002", is_superseded=False)
        )
        .scalars()
        .all()
    )
    all_items = (
        database.session.execute(database.select(PurchaseReceiptItem).filter_by(purchase_receipt_id="PR-002")).scalars().all()
    )
    assert len(active) == 1
    assert active[0].id == new_item.id
    assert len(all_items) == 2


# ---------------------------------------------------------------------------
# Líneas de factura: is_superseded en vez de delete
# ---------------------------------------------------------------------------


def test_invoice_item_is_superseded_defaults_false(app_ctx) -> None:
    """Una línea de factura nueva no está superseded."""
    item = PurchaseInvoiceItem(
        purchase_invoice_id="PI-001",
        item_code="ART-001",
        qty=Decimal("5"),
        rate=Decimal("10"),
        amount=Decimal("50"),
    )
    database.session.add(item)
    database.session.flush()
    assert item.is_superseded is False


def test_invoice_item_superseded_preserves_row(app_ctx) -> None:
    """Marcar una línea de factura como superseded no la elimina."""
    item = PurchaseInvoiceItem(
        purchase_invoice_id="PI-001",
        item_code="ART-001",
        qty=Decimal("5"),
        rate=Decimal("10"),
        amount=Decimal("50"),
    )
    database.session.add(item)
    database.session.flush()
    item_id = item.id

    item.is_superseded = True
    database.session.flush()

    persisted = database.session.get(PurchaseInvoiceItem, item_id)
    assert persisted is not None
    assert persisted.is_superseded is True


def test_invoice_items_superseded_filter(app_ctx) -> None:
    """El filtro is_superseded=False distingue líneas vigentes de obsoletas en facturas."""
    old_item = PurchaseInvoiceItem(
        purchase_invoice_id="PI-002",
        item_code="ART-001",
        qty=Decimal("5"),
        rate=Decimal("10"),
        amount=Decimal("50"),
        is_superseded=True,
    )
    new_item = PurchaseInvoiceItem(
        purchase_invoice_id="PI-002",
        item_code="ART-001",
        qty=Decimal("3"),
        rate=Decimal("10"),
        amount=Decimal("30"),
        is_superseded=False,
    )
    database.session.add_all([old_item, new_item])
    database.session.flush()

    active = (
        database.session.execute(
            database.select(PurchaseInvoiceItem).filter_by(purchase_invoice_id="PI-002", is_superseded=False)
        )
        .scalars()
        .all()
    )
    all_items = (
        database.session.execute(database.select(PurchaseInvoiceItem).filter_by(purchase_invoice_id="PI-002")).scalars().all()
    )
    assert len(active) == 1
    assert active[0].id == new_item.id
    assert len(all_items) == 2


# ---------------------------------------------------------------------------
# Idempotencia de eventos documentales
# ---------------------------------------------------------------------------


def test_emit_document_event_is_idempotent(app_ctx) -> None:
    """GOODS_RECEIVED no se duplica para el mismo documento."""
    from cacao_accounting.compras.purchase_reconciliation_service import EventType, emit_economic_event

    first = emit_economic_event(
        event_type=EventType.GOODS_RECEIVED,
        company="cacao",
        document_type="purchase_receipt",
        document_id="PR-IDEM-01",
        payload={"supplier_id": "SUP-1", "posting_date": "2026-09-06"},
    )
    database.session.flush()

    second = emit_economic_event(
        event_type=EventType.GOODS_RECEIVED,
        company="cacao",
        document_type="purchase_receipt",
        document_id="PR-IDEM-01",
        payload={"supplier_id": "SUP-1", "posting_date": "2026-09-06"},
    )
    database.session.flush()

    assert first.id == second.id

    events = (
        database.session.execute(
            database.select(PurchaseEconomicEvent).filter_by(document_id="PR-IDEM-01", event_type="GOODS_RECEIVED")
        )
        .scalars()
        .all()
    )
    assert len(events) == 1


def test_emit_invoice_event_is_idempotent(app_ctx) -> None:
    """INVOICE_RECEIVED no se duplica para el mismo documento."""
    from cacao_accounting.compras.purchase_reconciliation_service import EventType, emit_economic_event

    first = emit_economic_event(
        event_type=EventType.INVOICE_RECEIVED,
        company="cacao",
        document_type="purchase_invoice",
        document_id="PI-IDEM-01",
    )
    database.session.flush()

    second = emit_economic_event(
        event_type=EventType.INVOICE_RECEIVED,
        company="cacao",
        document_type="purchase_invoice",
        document_id="PI-IDEM-01",
    )
    database.session.flush()

    assert first.id == second.id

    events = (
        database.session.execute(
            database.select(PurchaseEconomicEvent).filter_by(document_id="PI-IDEM-01", event_type="INVOICE_RECEIVED")
        )
        .scalars()
        .all()
    )
    assert len(events) == 1


def test_different_documents_emit_separate_events(app_ctx) -> None:
    """Documentos distintos generan eventos independientes."""
    from cacao_accounting.compras.purchase_reconciliation_service import EventType, emit_economic_event

    ev1 = emit_economic_event(
        event_type=EventType.GOODS_RECEIVED,
        company="cacao",
        document_type="purchase_receipt",
        document_id="PR-A",
    )
    ev2 = emit_economic_event(
        event_type=EventType.GOODS_RECEIVED,
        company="cacao",
        document_type="purchase_receipt",
        document_id="PR-B",
    )
    database.session.flush()
    assert ev1.id != ev2.id


def test_match_events_are_not_idempotent(app_ctx) -> None:
    """MATCH_COMPLETED puede emitirse múltiples veces (reconciliaciones sucesivas)."""
    from cacao_accounting.compras.purchase_reconciliation_service import EventType, emit_economic_event

    ev1 = emit_economic_event(
        event_type=EventType.MATCH_COMPLETED,
        company="cacao",
        document_type="purchase_reconciliation",
        document_id="REC-001",
    )
    ev2 = emit_economic_event(
        event_type=EventType.MATCH_COMPLETED,
        company="cacao",
        document_type="purchase_reconciliation",
        document_id="REC-001",
    )
    database.session.flush()
    assert ev1.id != ev2.id


# ---------------------------------------------------------------------------
# Deduplicación en reconstrucción
# ---------------------------------------------------------------------------


def test_reconstruct_deduplicates_document_events(app_ctx) -> None:
    """reconstruct_reconciliation_state deduplica eventos documentales repetidos."""
    from cacao_accounting.compras.purchase_reconciliation_service import (
        EventType,
        PurchaseEconomicEvent,
        reconstruct_reconciliation_state,
    )

    # Insertar eventos duplicados directamente (simula datos legacy)
    ev1 = PurchaseEconomicEvent(
        event_type=EventType.GOODS_RECEIVED,
        company="cacao",
        document_type="purchase_receipt",
        document_id="PR-DEDUP-01",
        payload="{}",
        processing_status="pending",
    )
    ev2 = PurchaseEconomicEvent(
        event_type=EventType.GOODS_RECEIVED,
        company="cacao",
        document_type="purchase_receipt",
        document_id="PR-DEDUP-01",
        payload="{}",
        processing_status="pending",
    )
    database.session.add_all([ev1, ev2])
    database.session.flush()

    snapshot = reconstruct_reconciliation_state("cacao", "PR-DEDUP-01")
    goods_events = [e for e in snapshot.events if e["event_type"] == EventType.GOODS_RECEIVED]
    assert len(goods_events) == 1


def test_reconstruct_preserves_distinct_event_types(app_ctx) -> None:
    """reconstruct_reconciliation_state preserva tipos de evento distintos."""
    from cacao_accounting.compras.purchase_reconciliation_service import (
        EventType,
        PurchaseEconomicEvent,
        reconstruct_reconciliation_state,
    )

    ev_goods = PurchaseEconomicEvent(
        event_type=EventType.GOODS_RECEIVED,
        company="cacao",
        document_type="purchase_receipt",
        document_id="PR-MIX-01",
        payload="{}",
        processing_status="pending",
    )
    ev_match = PurchaseEconomicEvent(
        event_type=EventType.MATCH_COMPLETED,
        company="cacao",
        document_type="purchase_reconciliation",
        document_id="PR-MIX-01",
        payload='{"matching_result": "match_ok"}',
        processing_status="pending",
    )
    database.session.add_all([ev_goods, ev_match])
    database.session.flush()

    snapshot = reconstruct_reconciliation_state("cacao", "PR-MIX-01")
    assert len(snapshot.events) == 2
    types = {e["event_type"] for e in snapshot.events}
    assert EventType.GOODS_RECEIVED in types
    assert EventType.MATCH_COMPLETED in types
