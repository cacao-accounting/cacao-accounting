# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Servicio de conciliacion de recepciones de compra con facturas de proveedor.

Framework desacoplado de conciliacion de compras (process-first, event-driven).
Soporta matching 2-way (OC vs Factura) y 3-way (OC vs Recepcion vs Factura).
Los parametros son configurables por compania mediante PurchaseMatchingConfig.

Nota de diseño: la terminologia GR/IR (Goods Receipt / Invoice Receipt) es
propia de SAP y queda prohibida en este proyecto.  Se utiliza el termino
generico "Conciliacion de Compras" o "Purchase Reconciliation".
"""

from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from enum import Enum
from typing import Any

from sqlalchemy import func, select

from cacao_accounting.database import (
    PurchaseEconomicEvent,
    PurchaseInvoice,
    PurchaseInvoiceItem,
    PurchaseMatchingConfig,
    PurchaseReceipt,
    PurchaseReceiptItem,
    PurchaseReconciliation,
    PurchaseReconciliationItem,
    database,
)

# ---------------------------------------------------------------------------
# Enums publicos para estados y tipos
# ---------------------------------------------------------------------------


class MatchingType(str, Enum):
    """Tipo de matching de compras soportado."""

    TWO_WAY = "2-way"
    THREE_WAY = "3-way"


class MatchingResult(str, Enum):
    """Resultado de la evaluacion del motor de matching."""

    MATCH_OK = "MATCH_OK"
    MATCH_PARTIAL = "MATCH_PARTIAL"
    MATCH_FAILED = "MATCH_FAILED"


class ToleranceType(str, Enum):
    """Tipo de tolerancia: porcentaje o valor absoluto."""

    PERCENTAGE = "percentage"
    ABSOLUTE = "absolute"


class EventType(str, Enum):
    """Tipos de eventos economicos inmutables generados por el flujo de compras."""

    GOODS_RECEIVED = "GOODS_RECEIVED"
    INVOICE_RECEIVED = "INVOICE_RECEIVED"
    MATCH_COMPLETED = "MATCH_COMPLETED"
    MATCH_FAILED = "MATCH_FAILED"
    MATCH_CANCELLED = "MATCH_CANCELLED"
    GOODS_RECEIVED_CANCELLED = "GOODS_RECEIVED_CANCELLED"


# ---------------------------------------------------------------------------
# Excepciones
# ---------------------------------------------------------------------------


class PurchaseReconciliationError(ValueError):
    """Error controlado del motor de conciliacion de compras."""


# Alias de compatibilidad — no usar en codigo nuevo
GRIRServiceError = PurchaseReconciliationError


# ---------------------------------------------------------------------------
# Dataclasses de resultado
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PurchaseReconciliationResult:
    """Resultado resumido de una conciliacion de compras."""

    reconciliation_id: str
    matched_qty: Decimal
    matched_amount: Decimal
    price_difference: Decimal
    status: str
    matching_result: str


@dataclass(frozen=True)
class PurchasePendingRow:
    """Fila pendiente de conciliacion de compras."""

    purchase_receipt_id: str
    purchase_receipt_item_id: str
    item_code: str
    warehouse: str | None
    uom: str | None
    pending_qty: Decimal
    pending_amount: Decimal
    status: str


@dataclass
class _AggregatedLines:
    key: tuple[str, str | None]
    lines: list[Any] = field(default_factory=list)
    qty: Decimal = Decimal("0")
    amount: Decimal = Decimal("0")

    @property
    def rate(self) -> Decimal:
        if self.qty == 0:
            return Decimal("0")
        return self.amount / self.qty


@dataclass
class PurchaseReconciliationPanelGroup:
    """Grupo de conciliaciones para el panel colapsable por orden de compra."""

    purchase_order_id: str | None
    purchase_order_name: str
    reconciliations: list[PurchaseReconciliation] = field(default_factory=list)
    receipt_count: int = 0
    invoice_count: int = 0
    worst_status: str = "reconciled"


@dataclass(frozen=True)
class MatchingConfig:
    """Configuracion del motor de matching extraida de PurchaseMatchingConfig."""

    matching_type: str
    price_tolerance_type: str
    price_tolerance_value: Decimal
    qty_tolerance_type: str
    qty_tolerance_value: Decimal
    require_purchase_order: bool
    bridge_account_required: bool
    auto_reconcile: bool
    allow_price_difference: bool


# ---------------------------------------------------------------------------
# Helpers internos
# ---------------------------------------------------------------------------


def _decimal_value(value: Any) -> Decimal:
    if value is None:
        return Decimal("0")
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def _line_qty(line: Any) -> Decimal:
    return _decimal_value(getattr(line, "qty_in_base_uom", None) or getattr(line, "qty", None))


def _line_amount(line: Any) -> Decimal:
    amount = _decimal_value(getattr(line, "amount", None))
    if amount:
        return amount
    return _line_qty(line) * _decimal_value(getattr(line, "rate", None) or getattr(line, "valuation_rate", None))


def _line_rate(line: Any) -> Decimal:
    qty = _line_qty(line)
    if qty <= 0:
        raise PurchaseReconciliationError("La linea de conciliacion requiere cantidad positiva.")
    return _line_amount(line) / qty


def _matched_qty_for_receipt_item(receipt_item_id: str) -> Decimal:
    matched = database.session.execute(
        select(func.coalesce(func.sum(PurchaseReconciliationItem.matched_qty), 0))
        .filter_by(
            purchase_receipt_item_id=receipt_item_id,
        )
        .where(PurchaseReconciliationItem.status != "cancelled")
    ).scalar_one()
    return _decimal_value(matched)


def _matched_amount_for_receipt_item(receipt_item_id: str) -> Decimal:
    matched = database.session.execute(
        select(func.coalesce(func.sum(PurchaseReconciliationItem.matched_amount), 0))
        .filter_by(
            purchase_receipt_item_id=receipt_item_id,
        )
        .where(PurchaseReconciliationItem.status != "cancelled")
    ).scalar_one()
    return _decimal_value(matched)


def _matched_qty_for_order_item(order_item_id: str) -> Decimal:
    matched = database.session.execute(
        select(func.coalesce(func.sum(PurchaseReconciliationItem.matched_qty), 0))
        .filter_by(purchase_order_item_id=order_item_id)
        .where(PurchaseReconciliationItem.status != "cancelled")
    ).scalar_one()
    return _decimal_value(matched)


def _receipt_items(receipt_id: str) -> list[PurchaseReceiptItem]:
    return list(
        database.session.execute(select(PurchaseReceiptItem).filter_by(purchase_receipt_id=receipt_id)).scalars().all()
    )


def _invoice_items(invoice_id: str) -> list[PurchaseInvoiceItem]:
    return list(
        database.session.execute(select(PurchaseInvoiceItem).filter_by(purchase_invoice_id=invoice_id)).scalars().all()
    )


def _line_key(line: Any) -> tuple[str, str | None]:
    return (str(getattr(line, "item_code", "")), getattr(line, "uom", None))


def _group_lines_by_item_and_uom(lines: list[Any]) -> dict[tuple[str, str | None], list[Any]]:
    grouped: dict[tuple[str, str | None], list[Any]] = defaultdict(list)
    for line in lines:
        grouped[_line_key(line)].append(line)
    return grouped


def _aggregate_lines_by_item_and_uom(lines: list[Any]) -> dict[tuple[str, str | None], _AggregatedLines]:
    aggregates: dict[tuple[str, str | None], _AggregatedLines] = {}
    for line in lines:
        key = _line_key(line)
        aggregate = aggregates.setdefault(key, _AggregatedLines(key=key))
        aggregate.lines.append(line)
        aggregate.qty += _line_qty(line)
        aggregate.amount += _line_amount(line)
    return aggregates


def _apply_config_snapshot(reconciliation: PurchaseReconciliation, config: MatchingConfig) -> None:
    reconciliation.price_tolerance_type = config.price_tolerance_type
    reconciliation.price_tolerance_value = config.price_tolerance_value
    reconciliation.qty_tolerance_type = config.qty_tolerance_type
    reconciliation.qty_tolerance_value = config.qty_tolerance_value


def _find_receipt_item_for_invoice_line(
    receipt_items: list[PurchaseReceiptItem],
    invoice_item: PurchaseInvoiceItem,
) -> PurchaseReceiptItem:
    candidates = [
        ri
        for ri in receipt_items
        if ri.item_code == invoice_item.item_code
        and ri.uom == invoice_item.uom
        and (invoice_item.warehouse is None or ri.warehouse == invoice_item.warehouse)
    ]
    if not candidates:
        raise PurchaseReconciliationError("No existe linea de recepcion compatible para la linea de factura.")
    if len(candidates) > 1 and invoice_item.warehouse is None:
        raise PurchaseReconciliationError("La linea de factura requiere almacen para conciliar sin ambiguedad.")
    return candidates[0]


def _find_order_item_for_invoice_line(order_items: list[Any], invoice_item: PurchaseInvoiceItem) -> Any:
    candidates = [
        order_item
        for order_item in order_items
        if order_item.item_code == invoice_item.item_code and order_item.uom == invoice_item.uom
    ]
    if not candidates:
        raise PurchaseReconciliationError(f"No existe linea de OC compatible para el item {invoice_item.item_code}.")
    if len(candidates) > 1:
        raise PurchaseReconciliationError("La linea de factura requiere una OC sin lineas duplicadas ambiguas.")
    return candidates[0]


def _first_available_line(lines: list[Any], *, order_mode: bool) -> Any:
    for line in lines:
        line_qty = _line_qty(line)
        matched_qty = _matched_qty_for_order_item(line.id) if order_mode else _matched_qty_for_receipt_item(line.id)
        if line_qty - matched_qty > 0:
            return line
    return lines[0]


def _within_tolerance(difference: Decimal, reference: Decimal, tolerance_type: str, tolerance_value: Decimal) -> bool:
    """Evalua si una diferencia esta dentro de la tolerancia configurada.

    Nota: con tolerancia porcentual y referencia == 0, solo se acepta
    diferencia == 0 (no se puede calcular porcentaje sobre base cero).
    """
    if tolerance_value <= 0:
        return difference == 0
    match tolerance_type:
        case ToleranceType.PERCENTAGE:
            if reference == 0:
                # No se puede calcular % sobre base cero: solo acepta diferencia exacta
                return difference == 0
            return abs(difference / reference * 100) <= tolerance_value
        case _:
            return abs(difference) <= tolerance_value


# ---------------------------------------------------------------------------
# Servicio de configuracion de matching
# ---------------------------------------------------------------------------


def get_matching_config(company: str) -> MatchingConfig:
    """Devuelve la configuracion de matching para la compania dada.

    Si no existe configuracion, retorna los valores por defecto (modo estricto).
    """
    config = database.session.execute(select(PurchaseMatchingConfig).filter_by(company=company)).scalar_one_or_none()

    if config is None:
        return MatchingConfig(
            matching_type=MatchingType.THREE_WAY,
            price_tolerance_type=ToleranceType.PERCENTAGE,
            price_tolerance_value=Decimal("0"),
            qty_tolerance_type=ToleranceType.PERCENTAGE,
            qty_tolerance_value=Decimal("0"),
            require_purchase_order=True,
            bridge_account_required=True,
            auto_reconcile=True,
            allow_price_difference=False,
        )

    return MatchingConfig(
        matching_type=str(config.matching_type),
        price_tolerance_type=str(config.price_tolerance_type),
        price_tolerance_value=_decimal_value(config.price_tolerance_value),
        qty_tolerance_type=str(config.qty_tolerance_type),
        qty_tolerance_value=_decimal_value(config.qty_tolerance_value),
        require_purchase_order=bool(config.require_purchase_order),
        bridge_account_required=bool(config.bridge_account_required),
        auto_reconcile=bool(config.auto_reconcile),
        allow_price_difference=bool(config.allow_price_difference),
    )


def seed_matching_config_for_company(company: str) -> PurchaseMatchingConfig:
    """Crea la configuracion de matching en modo estricto para una compania nueva.

    El usuario puede relajar las tolerancias desde la pantalla de configuracion.
    """
    existing = database.session.execute(select(PurchaseMatchingConfig).filter_by(company=company)).scalar_one_or_none()
    if existing is not None:
        return existing

    config = PurchaseMatchingConfig(
        company=company,
        matching_type=MatchingType.THREE_WAY,
        price_tolerance_type=ToleranceType.PERCENTAGE,
        price_tolerance_value=Decimal("0"),
        qty_tolerance_type=ToleranceType.PERCENTAGE,
        qty_tolerance_value=Decimal("0"),
        require_purchase_order=True,
        bridge_account_required=True,
        auto_reconcile=True,
        allow_price_difference=False,
    )
    database.session.add(config)
    return config


# ---------------------------------------------------------------------------
# Motor de eventos economicos
# ---------------------------------------------------------------------------


def emit_economic_event(
    event_type: str,
    company: str,
    document_type: str,
    document_id: str,
    payload: dict[str, Any] | None = None,
) -> PurchaseEconomicEvent:
    """Emite un evento economico inmutable al log de eventos."""
    event = PurchaseEconomicEvent(
        event_type=event_type,
        company=company,
        document_type=document_type,
        document_id=document_id,
        payload=json.dumps(payload or {}),
        processing_status="pending",
    )
    database.session.add(event)
    return event


def mark_event_processed(event: PurchaseEconomicEvent) -> None:
    """Compatibilidad legacy: los eventos economicos no se mutan desde el motor de matching."""
    _ = event


# ---------------------------------------------------------------------------
# Motor de matching principal
# ---------------------------------------------------------------------------


def _evaluate_matching_result(
    total_invoiced_qty: Decimal,
    total_reference_qty: Decimal,
    total_price_difference: Decimal,
    total_amount_difference: Decimal,
    total_reference_amount: Decimal,
    config: MatchingConfig,
) -> MatchingResult:
    """Evalua el resultado del matching segun la configuracion de tolerancias."""
    qty_difference = total_invoiced_qty - total_reference_qty
    qty_ok = _within_tolerance(
        qty_difference,
        total_reference_qty,
        config.qty_tolerance_type,
        config.qty_tolerance_value,
    )
    price_ok = _within_tolerance(
        total_price_difference,
        total_reference_amount,
        config.price_tolerance_type,
        config.price_tolerance_value,
    )
    amount_ok = _within_tolerance(
        total_amount_difference,
        total_reference_amount,
        config.price_tolerance_type,
        config.price_tolerance_value,
    )

    # Facturar menos que la referencia es un parcial valido; no debe fallar por monto menor.
    if total_amount_difference <= 0:
        amount_ok = True

    if qty_difference > 0 and not qty_ok:
        return MatchingResult.MATCH_FAILED
    if not price_ok or not amount_ok:
        return MatchingResult.MATCH_FAILED
    if qty_difference != 0:
        return MatchingResult.MATCH_PARTIAL
    if qty_ok and price_ok and amount_ok:
        return MatchingResult.MATCH_OK
    return MatchingResult.MATCH_FAILED


def _derive_reconciliation_status(
    matching_result: MatchingResult,
    total_invoiced_qty: Decimal,
    total_reference_qty: Decimal,
) -> str:
    """Deriva el estado de conciliacion desde el resultado del matching."""
    match matching_result:
        case MatchingResult.MATCH_FAILED:
            return "disputed"
        case MatchingResult.MATCH_PARTIAL:
            return "partial"
        case _ if total_invoiced_qty < total_reference_qty:
            return "partial"
        case _:
            return "reconciled"


def reconcile_purchase_invoice(purchase_invoice_id: str) -> PurchaseReconciliationResult:
    """Concilia una factura de compra segun la configuracion de matching de la compania.

    - **3-way**: OC → Recepcion → Factura (requiere `purchase_receipt_id` en la factura).
    - **2-way**: OC → Factura (requiere `purchase_order_id` en la factura; valida cantidades contra la OC).

    En ambos casos respeta las tolerancias configuradas y emite eventos economicos.
    """
    duplicate = database.session.execute(
        select(PurchaseReconciliation.id)
        .filter_by(purchase_invoice_id=purchase_invoice_id)
        .where(PurchaseReconciliation.status != "cancelled")
        .limit(1)
    ).scalar_one_or_none()
    if duplicate:
        raise PurchaseReconciliationError("La factura de compra ya tiene una conciliacion activa.")

    invoice = database.session.get(PurchaseInvoice, purchase_invoice_id)
    if not invoice:
        raise PurchaseReconciliationError("La factura de compra no existe.")

    config = get_matching_config(str(invoice.company))

    if config.matching_type == MatchingType.TWO_WAY:
        return _reconcile_two_way(invoice, config)
    return _reconcile_three_way(invoice, config)


# ---------------------------------------------------------------------------
# Implementaciones internas de matching
# ---------------------------------------------------------------------------


def _reconcile_three_way(invoice: PurchaseInvoice, config: MatchingConfig) -> PurchaseReconciliationResult:
    """Matching 3-way: compara Recepcion vs Factura validando cantidades recibidas."""
    if not invoice.purchase_receipt_id:
        raise PurchaseReconciliationError("Matching 3-way requiere que la factura referencie una recepcion de compra.")
    receipt = database.session.get(PurchaseReceipt, invoice.purchase_receipt_id)
    if not receipt:
        raise PurchaseReconciliationError("La recepcion de compra referenciada no existe.")
    if receipt.company != invoice.company:
        raise PurchaseReconciliationError("La factura y la recepcion deben pertenecer a la misma compania.")
    if getattr(receipt, "docstatus", 0) != 1:
        raise PurchaseReconciliationError("La recepcion de compra debe estar aprobada.")

    receipt_items = _receipt_items(receipt.id)
    invoice_items = _invoice_items(invoice.id)
    if not receipt_items or not invoice_items:
        raise PurchaseReconciliationError("La conciliacion 3-way requiere lineas de recepcion y factura.")
    receipt_groups = _aggregate_lines_by_item_and_uom(receipt_items)
    invoice_groups = _aggregate_lines_by_item_and_uom(invoice_items)

    reconciliation = PurchaseReconciliation(
        company=invoice.company,
        purchase_order_id=getattr(invoice, "purchase_order_id", None),
        purchase_receipt_id=receipt.id,
        purchase_invoice_id=invoice.id,
        matching_type=MatchingType.THREE_WAY,
        matched_amount=Decimal("0"),
        matched_date=invoice.posting_date,
        status="pending_invoice",
    )
    _apply_config_snapshot(reconciliation, config)
    database.session.add(reconciliation)
    database.session.flush()

    total_qty = sum((aggregate.qty for aggregate in invoice_groups.values()), Decimal("0"))
    total_amount = Decimal("0")
    total_price_difference = Decimal("0")
    total_amount_difference = Decimal("0")
    total_invoiced_qty = Decimal("0")
    total_received_qty = Decimal("0")

    for key, invoice_group in invoice_groups.items():
        receipt_group = receipt_groups.get(key)
        if receipt_group is None:
            raise PurchaseReconciliationError("No existe linea de recepcion compatible para la linea de factura.")
        if invoice_group.qty <= 0:
            raise PurchaseReconciliationError("La cantidad facturada debe ser positiva.")
        pending_qty = sum(
            (_line_qty(line) - _matched_qty_for_receipt_item(line.id) for line in receipt_group.lines),
            Decimal("0"),
        )
        reference_qty = min(receipt_group.qty, pending_qty)
        reference_amount = reference_qty * receipt_group.rate
        matched_amount = min(invoice_group.qty, reference_qty) * receipt_group.rate
        price_difference = invoice_group.rate - receipt_group.rate
        amount_difference = invoice_group.amount - reference_amount

        total_amount += matched_amount
        total_price_difference += price_difference
        total_amount_difference += amount_difference
        total_invoiced_qty += invoice_group.qty
        total_received_qty += reference_qty

    result = _finalize_reconciliation(
        reconciliation,
        invoice,
        config,
        total_qty,
        total_amount,
        total_price_difference,
        total_amount_difference,
        total_invoiced_qty,
        total_received_qty,
        receipt_id=receipt.id,
    )
    if result.matching_result == MatchingResult.MATCH_FAILED.value:
        return result

    for invoice_item in invoice_items:
        receipt_item = _first_available_line(receipt_groups[_line_key(invoice_item)].lines, order_mode=False)
        invoice_qty = _line_qty(invoice_item)
        receipt_qty = _line_qty(receipt_item)
        receipt_rate = _line_rate(receipt_item)
        invoice_rate = _line_rate(invoice_item)
        matched_amount = invoice_qty * receipt_rate
        invoiced_amount = invoice_qty * invoice_rate
        price_difference = invoice_rate - receipt_rate
        database.session.add(
            PurchaseReconciliationItem(
                purchase_reconciliation_id=reconciliation.id,
                purchase_order_item_id=None,
                purchase_receipt_item_id=receipt_item.id,
                purchase_invoice_item_id=invoice_item.id,
                item_code=invoice_item.item_code,
                warehouse=receipt_item.warehouse,
                uom=invoice_item.uom,
                received_qty=receipt_qty,
                invoiced_qty=invoice_qty,
                matched_qty=invoice_qty,
                received_amount=invoice_qty * receipt_rate,
                invoiced_amount=invoiced_amount,
                matched_amount=matched_amount,
                price_difference=price_difference,
                status="reconciled",
            )
        )
    return result


def _reconcile_two_way(invoice: PurchaseInvoice, config: MatchingConfig) -> PurchaseReconciliationResult:
    """Matching 2-way: compara OC vs Factura, sin requerir recepcion previa.

    Valida que las cantidades facturadas no superen las ordenadas en la OC.
    """
    from cacao_accounting.database import PurchaseOrder, PurchaseOrderItem

    purchase_order_id = getattr(invoice, "purchase_order_id", None)
    if not purchase_order_id:
        raise PurchaseReconciliationError("Matching 2-way requiere que la factura referencie una orden de compra.")
    order = database.session.get(PurchaseOrder, purchase_order_id)
    if not order:
        raise PurchaseReconciliationError("La orden de compra referenciada no existe.")
    if getattr(order, "company", None) != invoice.company:
        raise PurchaseReconciliationError("La factura y la orden de compra deben pertenecer a la misma compania.")
    if getattr(order, "docstatus", 0) != 1:
        raise PurchaseReconciliationError("La orden de compra debe estar aprobada para el matching 2-way.")

    order_items = list(
        database.session.execute(select(PurchaseOrderItem).filter_by(purchase_order_id=purchase_order_id)).scalars().all()
    )
    invoice_items = _invoice_items(invoice.id)
    if not order_items or not invoice_items:
        raise PurchaseReconciliationError("La conciliacion 2-way requiere lineas de OC y factura.")
    order_groups = _aggregate_lines_by_item_and_uom(order_items)
    invoice_groups = _aggregate_lines_by_item_and_uom(invoice_items)

    reconciliation = PurchaseReconciliation(
        company=invoice.company,
        purchase_order_id=purchase_order_id,
        purchase_receipt_id=None,
        purchase_invoice_id=invoice.id,
        matching_type=MatchingType.TWO_WAY,
        matched_amount=Decimal("0"),
        matched_date=invoice.posting_date,
        status="pending_invoice",
    )
    _apply_config_snapshot(reconciliation, config)
    database.session.add(reconciliation)
    database.session.flush()

    total_qty = sum((aggregate.qty for aggregate in invoice_groups.values()), Decimal("0"))
    total_amount = Decimal("0")
    total_price_difference = Decimal("0")
    total_amount_difference = Decimal("0")
    total_invoiced_qty = Decimal("0")
    total_ordered_qty = Decimal("0")

    for key, invoice_group in invoice_groups.items():
        order_group = order_groups.get(key)
        if order_group is None:
            item_code, _uom = key
            raise PurchaseReconciliationError(f"No existe linea de OC compatible para el item {item_code}.")
        if invoice_group.qty <= 0:
            raise PurchaseReconciliationError("La cantidad facturada debe ser positiva.")
        pending_qty = sum(
            (_line_qty(line) - _matched_qty_for_order_item(line.id) for line in order_group.lines),
            Decimal("0"),
        )
        reference_qty = min(order_group.qty, pending_qty)
        reference_amount = reference_qty * order_group.rate
        matched_amount = min(invoice_group.qty, reference_qty) * order_group.rate
        price_difference = invoice_group.rate - order_group.rate
        amount_difference = invoice_group.amount - reference_amount

        total_amount += matched_amount
        total_price_difference += price_difference
        total_amount_difference += amount_difference
        total_invoiced_qty += invoice_group.qty
        total_ordered_qty += reference_qty

    result = _finalize_reconciliation(
        reconciliation,
        invoice,
        config,
        total_qty,
        total_amount,
        total_price_difference,
        total_amount_difference,
        total_invoiced_qty,
        total_ordered_qty,
        receipt_id=None,
    )
    if result.matching_result == MatchingResult.MATCH_FAILED.value:
        return result

    for invoice_item in invoice_items:
        order_item = _first_available_line(order_groups[_line_key(invoice_item)].lines, order_mode=True)
        invoice_qty = _line_qty(invoice_item)
        ordered_qty = _line_qty(order_item)
        order_rate = _line_rate(order_item)
        invoice_rate = _line_rate(invoice_item)
        matched_amount = invoice_qty * order_rate
        invoiced_amount = invoice_qty * invoice_rate
        price_difference = invoice_rate - order_rate
        database.session.add(
            PurchaseReconciliationItem(
                purchase_reconciliation_id=reconciliation.id,
                purchase_order_item_id=order_item.id,
                purchase_receipt_item_id=None,
                purchase_invoice_item_id=invoice_item.id,
                item_code=invoice_item.item_code,
                warehouse=None,
                uom=invoice_item.uom,
                received_qty=ordered_qty,  # "received" = ordered in 2-way context
                invoiced_qty=invoice_qty,
                matched_qty=invoice_qty,
                received_amount=invoice_qty * order_rate,
                invoiced_amount=invoiced_amount,
                matched_amount=matched_amount,
                price_difference=price_difference,
                status="reconciled",
            )
        )
    return result


def _finalize_reconciliation(
    reconciliation: PurchaseReconciliation,
    invoice: PurchaseInvoice,
    config: MatchingConfig,
    total_qty: Decimal,
    total_amount: Decimal,
    total_price_difference: Decimal,
    total_amount_difference: Decimal,
    total_invoiced_qty: Decimal,
    total_reference_qty: Decimal,
    receipt_id: str | None,
) -> PurchaseReconciliationResult:
    """Evalua el resultado del matching y emite el evento economico correspondiente."""
    matching_result = _evaluate_matching_result(
        total_invoiced_qty,
        total_reference_qty,
        total_price_difference,
        total_amount_difference,
        total_amount,
        config,
    )

    reconciliation.status = _derive_reconciliation_status(matching_result, total_invoiced_qty, total_reference_qty)
    event_type = EventType.MATCH_FAILED if matching_result == MatchingResult.MATCH_FAILED else EventType.MATCH_COMPLETED
    reconciliation.matched_amount = total_amount

    emit_economic_event(
        event_type=event_type,
        company=str(invoice.company),
        document_type="purchase_reconciliation",
        document_id=reconciliation.id,
        payload={
            "purchase_invoice_id": invoice.id,
            "purchase_receipt_id": receipt_id,
            "purchase_order_id": reconciliation.purchase_order_id,
            "matched_qty": str(total_qty),
            "matched_amount": str(total_amount),
            "price_difference": str(total_price_difference),
            "amount_difference": str(total_amount_difference),
            "matching_result": matching_result.value,
            "matching_type": reconciliation.matching_type,
            "price_tolerance_type": config.price_tolerance_type,
            "price_tolerance_value": str(config.price_tolerance_value),
            "qty_tolerance_type": config.qty_tolerance_type,
            "qty_tolerance_value": str(config.qty_tolerance_value),
        },
    )

    return PurchaseReconciliationResult(
        reconciliation_id=reconciliation.id,
        matched_qty=total_qty,
        matched_amount=total_amount,
        price_difference=total_price_difference,
        status=str(reconciliation.status),
        matching_result=matching_result.value,
    )


def cancel_purchase_reconciliation(purchase_invoice_id: str) -> None:
    """Marca como canceladas las conciliaciones asociadas a una factura."""
    reconciliations = (
        database.session.execute(
            select(PurchaseReconciliation)
            .filter_by(purchase_invoice_id=purchase_invoice_id)
            .where(PurchaseReconciliation.status != "cancelled")
        )
        .scalars()
        .all()
    )
    for reconciliation in reconciliations:
        reconciliation.status = "cancelled"
        for item in (
            database.session.execute(
                select(PurchaseReconciliationItem).filter_by(purchase_reconciliation_id=reconciliation.id)
            )
            .scalars()
            .all()
        ):
            item.status = "cancelled"

        emit_economic_event(
            event_type=EventType.MATCH_CANCELLED,
            company=str(reconciliation.company),
            document_type="purchase_reconciliation",
            document_id=reconciliation.id,
            payload={"purchase_invoice_id": purchase_invoice_id},
        )


def get_purchase_reconciliation_pending(company: str, as_of_date: date | None = None) -> list[PurchasePendingRow]:
    """Devuelve saldos pendientes de conciliacion por linea de recepcion."""
    query = (
        select(PurchaseReceipt, PurchaseReceiptItem)
        .join(
            PurchaseReceiptItem,
            PurchaseReceiptItem.purchase_receipt_id == PurchaseReceipt.id,
        )
        .filter(PurchaseReceipt.company == company)
    )
    if as_of_date is not None:
        query = query.where(PurchaseReceipt.posting_date <= as_of_date)

    rows: list[PurchasePendingRow] = []
    for receipt, item in database.session.execute(query).all():
        item_qty = _line_qty(item)
        item_amount = _line_amount(item)
        pending_qty = item_qty - _matched_qty_for_receipt_item(item.id)
        pending_amount = item_amount - _matched_amount_for_receipt_item(item.id)
        if pending_qty <= 0 and pending_amount <= 0:
            continue
        rows.append(
            PurchasePendingRow(
                purchase_receipt_id=receipt.id,
                purchase_receipt_item_id=item.id,
                item_code=item.item_code,
                warehouse=item.warehouse,
                uom=item.uom,
                pending_qty=pending_qty,
                pending_amount=pending_amount,
                status="partial" if pending_qty < item_qty else "open",
            )
        )
    return rows


def get_purchase_reconciliation_panel_groups(company: str) -> list[PurchaseReconciliationPanelGroup]:
    """Devuelve conciliaciones activas agrupadas por orden de compra para la UI."""
    reconciliations = (
        database.session.execute(
            select(PurchaseReconciliation)
            .filter_by(company=company)
            .where(PurchaseReconciliation.status != "cancelled")
            .order_by(PurchaseReconciliation.matched_date.desc())
        )
        .scalars()
        .all()
    )
    status_rank: dict[str, int] = {
        "disputed": 0,
        "partial": 1,
        "pending_receipt": 2,
        "pending_invoice": 3,
        "reconciled": 4,
    }

    groups: dict[str | None, PurchaseReconciliationPanelGroup] = {}
    receipt_ids_by_group: dict[str | None, set[str]] = defaultdict(set)
    invoice_ids_by_group: dict[str | None, set[str]] = defaultdict(set)

    for reconciliation in reconciliations:
        key = reconciliation.purchase_order_id
        group = groups.get(key)
        if group is None:
            group = PurchaseReconciliationPanelGroup(
                purchase_order_id=key,
                purchase_order_name=str(key) if key else "Sin Orden de Compra",
            )
            groups[key] = group

        group.reconciliations.append(reconciliation)
        if reconciliation.purchase_receipt_id:
            receipt_ids_by_group[key].add(reconciliation.purchase_receipt_id)
        if reconciliation.purchase_invoice_id:
            invoice_ids_by_group[key].add(reconciliation.purchase_invoice_id)
        if status_rank.get(str(reconciliation.status), 99) < status_rank.get(group.worst_status, 99):
            group.worst_status = str(reconciliation.status)

    return [
        PurchaseReconciliationPanelGroup(
            purchase_order_id=group.purchase_order_id,
            purchase_order_name=group.purchase_order_name,
            reconciliations=group.reconciliations,
            receipt_count=len(receipt_ids_by_group[key]),
            invoice_count=len(invoice_ids_by_group[key]),
            worst_status=group.worst_status,
        )
        for key, group in groups.items()
    ]


# ---------------------------------------------------------------------------
# Cancelacion de recepcion — evento inverso
# ---------------------------------------------------------------------------


def emit_goods_received_cancelled(purchase_receipt_id: str, company: str) -> None:
    """Emite un evento GOODS_RECEIVED_CANCELLED cuando se anula una recepcion.

    Debe ser llamado desde la capa de posting al cancelar un PurchaseReceipt.
    Tambien cancela las conciliaciones 3-way que dependian de esa recepcion.
    """
    affected = (
        database.session.execute(
            select(PurchaseReconciliation)
            .filter_by(purchase_receipt_id=purchase_receipt_id)
            .where(PurchaseReconciliation.status != "cancelled")
        )
        .scalars()
        .all()
    )
    for reconciliation in affected:
        reconciliation.status = "cancelled"
        for item in (
            database.session.execute(
                select(PurchaseReconciliationItem).filter_by(purchase_reconciliation_id=reconciliation.id)
            )
            .scalars()
            .all()
        ):
            item.status = "cancelled"
        emit_economic_event(
            event_type=EventType.MATCH_CANCELLED,
            company=company,
            document_type="purchase_reconciliation",
            document_id=reconciliation.id,
            payload={"reason": "purchase_receipt_cancelled", "purchase_receipt_id": purchase_receipt_id},
        )

    emit_economic_event(
        event_type="GOODS_RECEIVED_CANCELLED",
        company=company,
        document_type="purchase_receipt",
        document_id=purchase_receipt_id,
        payload={"purchase_receipt_id": purchase_receipt_id},
    )


# ---------------------------------------------------------------------------
# Reconstruccion de estado desde eventos (criterio de aceptacion #3)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ReconciliationStateSnapshot:
    """Estado de una conciliacion reconstruido desde el log de eventos."""

    document_id: str
    document_type: str
    company: str
    current_status: str
    events: list[dict[str, Any]]


def reconstruct_reconciliation_state(company: str, document_id: str) -> ReconciliationStateSnapshot:
    """Reconstruye el estado de una conciliacion desde el log de eventos inmutable.

    Permite auditar y verificar que el estado actual de PurchaseReconciliation
    es coherente con la secuencia historica de eventos economicos.
    """
    events_raw = (
        database.session.execute(
            select(PurchaseEconomicEvent)
            .filter_by(company=company, document_id=document_id)
            .order_by(PurchaseEconomicEvent.id)  # ULID IDs are time-sortable
        )
        .scalars()
        .all()
    )

    import json as _json

    events_list: list[dict[str, Any]] = [
        {
            "id": ev.id,
            "event_type": ev.event_type,
            "document_type": ev.document_type,
            "document_id": ev.document_id,
            "payload": _json.loads(ev.payload) if ev.payload else {},
            "processing_status": ev.processing_status,
            "created_at": str(getattr(ev, "created_at", "")),
        }
        for ev in events_raw
    ]

    # Derive current status by replaying events in order
    derived_status = "unknown"
    for ev in events_list:
        match ev["event_type"]:
            case EventType.MATCH_COMPLETED:
                payload = ev.get("payload", {})
                derived_status = payload.get("matching_result", "reconciled")
                if derived_status == MatchingResult.MATCH_OK.value:
                    derived_status = "reconciled"
                elif derived_status == MatchingResult.MATCH_PARTIAL.value:
                    derived_status = "partial"
            case EventType.MATCH_FAILED:
                derived_status = "disputed"
            case EventType.MATCH_CANCELLED | "GOODS_RECEIVED_CANCELLED":
                derived_status = "cancelled"

    return ReconciliationStateSnapshot(
        document_id=document_id,
        document_type="purchase_reconciliation",
        company=company,
        current_status=derived_status,
        events=events_list,
    )


def get_events_for_document(company: str, document_id: str) -> list[dict[str, Any]]:
    """Devuelve todos los eventos economicos de un documento ordenados cronologicamente."""
    snapshot = reconstruct_reconciliation_state(company, document_id)
    return snapshot.events
