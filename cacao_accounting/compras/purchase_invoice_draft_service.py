"""HTTP-independent, transactional creation of purchase-invoice drafts.

This is the shared domain boundary for the manual form, importers and Cloud
document intake.  It never submits, approves, posts or creates master data.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from typing import Literal

from cacao_accounting.audit_trail_service import log_create
from cacao_accounting.database import (
    AccountingPeriod,
    CompanyParty,
    Currency,
    Entity,
    Item,
    Party,
    PurchaseInvoice,
    PurchaseInvoiceItem,
    PurchaseOrder,
    PurchaseReceipt,
    TaxTemplate,
    UOM,
    User,
    database,
)
from cacao_accounting.document_flow import (
    DocumentFlowError,
    create_document_relation,
    refresh_source_caches_for_target,
)
from cacao_accounting.document_identifiers import assign_document_identifier

MONEY_QUANTUM = Decimal("0.0001")
PURCHASE_INVOICE = "purchase_invoice"


class PurchaseInvoiceDraftError(ValueError):
    """A domain validation failure suitable for a caller-specific exception UI."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(message)


@dataclass(frozen=True)
class PurchaseInvoiceDraftLine:
    """Resolved line values.  Internal IDs originate only from Cacao matching."""

    item_code: str
    quantity: Decimal
    rate: Decimal
    amount: Decimal
    uom: str | None = None
    expense_account_id: str | None = None
    purchase_order_item_id: str | None = None
    purchase_receipt_item_id: str | None = None


@dataclass(frozen=True)
class PurchaseInvoiceDraftCommand:
    """Validated input to create exactly one ``docstatus=0`` purchase invoice."""

    company_id: str
    supplier_id: str
    supplier_invoice_no: str
    posting_date: date
    transaction_currency: str
    lines: tuple[PurchaseInvoiceDraftLine, ...]
    matching_mode: Literal["THREE_WAY_MATCH", "TWO_WAY_MATCH", "NON_PO_INVOICE"]
    purchase_order_id: str | None = None
    purchase_receipt_id: str | None = None
    expected_total: Decimal | None = None
    observed_tax_total: Decimal | None = None
    tax_template_id: str | None = None
    remarks: str | None = None
    idempotency_key: str | None = None
    source_references: dict[int, tuple[str, str, str | None]] = field(
        default_factory=dict
    )


def _decimal(value: Decimal) -> Decimal:
    return Decimal(str(value)).quantize(MONEY_QUANTUM)


def _require_actor_can_create(actor_id: str, company_id: str) -> None:
    """Re-check the initiating actor without relying on a Flask request context."""
    from cacao_accounting.auth.permisos import Permisos
    from cacao_accounting.database.helpers import obtener_id_modulo_por_nombre

    actor = database.session.get(User, actor_id)
    module_id = obtener_id_modulo_por_nombre("purchases")
    permissions = Permisos(modulo=module_id, usuario=actor_id) if module_id else None
    if (
        actor is None
        or not actor.active
        or permissions is None
        or not (permissions.administrador or permissions.crear)
        or not permissions.tiene_acceso_compania(company_id, "can_write")
    ):
        raise PurchaseInvoiceDraftError(
            "AUTHORIZATION_REVOKED",
            "El usuario ya no puede crear facturas en la compañía.",
        )


def _validate_header(
    command: PurchaseInvoiceDraftCommand,
) -> tuple[Entity, Party, CompanyParty]:
    # Purchase documents carry the public Entity.code, not Entity.id.
    company = database.session.execute(
        database.select(Entity).where(Entity.code == command.company_id)
    ).scalar_one_or_none()
    supplier = database.session.get(Party, command.supplier_id)
    if company is None or not company.enabled:
        raise PurchaseInvoiceDraftError(
            "AUTHORIZATION_REVOKED", "La compañía no está activa."
        )
    if supplier is None or not supplier.is_active or not supplier.is_supplier:
        raise PurchaseInvoiceDraftError(
            "SUPPLIER_UNRESOLVED", "El proveedor no está activo."
        )
    settings = database.session.execute(
        database.select(CompanyParty).where(
            CompanyParty.company == command.company_id,
            CompanyParty.party_id == command.supplier_id,
            CompanyParty.is_active.is_(True),
        )
    ).scalar_one_or_none()
    if settings is None:
        raise PurchaseInvoiceDraftError(
            "SUPPLIER_UNRESOLVED", "El proveedor no está habilitado para la compañía."
        )
    currency = database.session.execute(
        database.select(Currency).where(
            Currency.code == command.transaction_currency, Currency.active.is_not(False)
        )
    ).scalar_one_or_none()
    if currency is None:
        raise PurchaseInvoiceDraftError(
            "ORDER_CURRENCY_MISMATCH", "La moneda de la factura no está activa."
        )
    if not command.supplier_invoice_no.strip():
        raise PurchaseInvoiceDraftError(
            "DUPLICATE_INVOICE", "La factura requiere número de proveedor."
        )
    closed = database.session.execute(
        database.select(AccountingPeriod.id).where(
            AccountingPeriod.entity == command.company_id,
            AccountingPeriod.start <= command.posting_date,
            AccountingPeriod.end >= command.posting_date,
            AccountingPeriod.is_closed.is_(True),
        )
    ).scalar_one_or_none()
    if closed:
        raise PurchaseInvoiceDraftError(
            "CLOSED_ACCOUNTING_PERIOD", "El período contable está cerrado."
        )
    return company, supplier, settings


def _validate_duplicate(command: PurchaseInvoiceDraftCommand) -> None:
    duplicate = database.session.execute(
        database.select(PurchaseInvoice.id).where(
            PurchaseInvoice.company == command.company_id,
            PurchaseInvoice.supplier_id == command.supplier_id,
            PurchaseInvoice.supplier_invoice_no == command.supplier_invoice_no.strip(),
            PurchaseInvoice.docstatus != 2,
        )
    ).scalar_one_or_none()
    if duplicate:
        raise PurchaseInvoiceDraftError(
            "DUPLICATE_INVOICE", "La factura del proveedor ya existe."
        )


def _validate_sources(
    command: PurchaseInvoiceDraftCommand, settings: CompanyParty
) -> None:
    order = (
        database.session.get(PurchaseOrder, command.purchase_order_id)
        if command.purchase_order_id
        else None
    )
    receipt = (
        database.session.get(PurchaseReceipt, command.purchase_receipt_id)
        if command.purchase_receipt_id
        else None
    )
    if command.matching_mode == "NON_PO_INVOICE":
        if order or receipt or not settings.allow_purchase_invoice_without_order:
            raise PurchaseInvoiceDraftError(
                "PURCHASE_ORDER_REQUIRED",
                "La política del proveedor exige orden de compra.",
            )
        return
    if order is None or order.docstatus != 1:
        raise PurchaseInvoiceDraftError(
            "PURCHASE_ORDER_NOT_FOUND",
            "La orden de compra no está disponible para facturación.",
        )
    if order.company != command.company_id or order.supplier_id != command.supplier_id:
        raise PurchaseInvoiceDraftError(
            "PURCHASE_ORDER_NOT_FOUND",
            "La orden no corresponde a compañía y proveedor.",
        )
    if (
        order.transaction_currency
        and order.transaction_currency != command.transaction_currency
    ):
        raise PurchaseInvoiceDraftError(
            "ORDER_CURRENCY_MISMATCH", "La moneda no coincide con la orden."
        )
    if command.matching_mode == "THREE_WAY_MATCH":
        if receipt is None or receipt.docstatus != 1:
            raise PurchaseInvoiceDraftError(
                "RECEIPT_MISSING", "La recepción requerida no está disponible."
            )
        if (
            receipt.company != command.company_id
            or receipt.supplier_id != command.supplier_id
            or receipt.purchase_order_id != order.id
        ):
            raise PurchaseInvoiceDraftError(
                "RECEIPT_MISSING", "La recepción no corresponde a la orden y proveedor."
            )


def _exchange_rate(company: Entity, command: PurchaseInvoiceDraftCommand) -> Decimal:
    if company.currency == command.transaction_currency:
        return Decimal("1")
    from cacao_accounting.contabilidad.posting import (
        PostingError,
        _lookup_exchange_rate,
    )

    try:
        return _lookup_exchange_rate(
            command.transaction_currency, company.currency, command.posting_date
        )
    except PostingError as exc:
        raise PurchaseInvoiceDraftError(
            "ORDER_CURRENCY_MISMATCH", "No existe tasa de cambio para la fecha."
        ) from exc


def _validate_line(line: PurchaseInvoiceDraftLine) -> Item:
    item = database.session.execute(
        database.select(Item).where(Item.code == line.item_code)
    ).scalar_one_or_none()
    if item is None or not item.is_purchase_item:
        raise PurchaseInvoiceDraftError(
            "LINE_UNRESOLVED", f"El ítem '{line.item_code}' no es comprable."
        )
    if line.uom:
        uom = database.session.execute(
            database.select(UOM).where(UOM.code == line.uom)
        ).scalar_one_or_none()
        if uom is None or not uom.is_active:
            raise PurchaseInvoiceDraftError(
                "LINE_UNRESOLVED", "La unidad de medida no es válida."
            )
    if line.quantity <= 0 or line.rate < 0 or line.amount < 0:
        raise PurchaseInvoiceDraftError(
            "MATH_MISMATCH", "Cantidad, precio e importe inválidos."
        )
    if abs(_decimal(line.quantity * line.rate) - _decimal(line.amount)) > Decimal(
        "0.02"
    ):
        raise PurchaseInvoiceDraftError(
            "MATH_MISMATCH", "El importe de línea no coincide con cantidad y precio."
        )
    return item


def _resolve_tax_total(
    command: PurchaseInvoiceDraftCommand, line_total: Decimal
) -> Decimal:
    """Calculate tax from Cacao's configured template and compare observation.

    The intake provider may report a tax total, but it never determines a tax
    rule.  A template is selected only from Cacao's company/supplier policy
    and evaluated by the same tax-pricing service used by purchase documents.
    """
    observed = _decimal(command.observed_tax_total or Decimal("0"))
    if not command.tax_template_id:
        if observed != Decimal("0"):
            raise PurchaseInvoiceDraftError(
                "TAX_MISMATCH",
                "Hay impuesto observado sin una plantilla fiscal resuelta.",
            )
        return Decimal("0")

    from cacao_accounting.tax_pricing_service import TaxPricingError, calculate_taxes

    template = database.session.get(TaxTemplate, command.tax_template_id)
    if (
        template is None
        or not template.is_active
        or (template.company and template.company != command.company_id)
        or template.template_type not in {"buying", "purchase"}
        or (template.currency and template.currency != command.transaction_currency)
    ):
        raise PurchaseInvoiceDraftError(
            "TAX_MISMATCH",
            "La plantilla fiscal no es aplicable a esta factura de compra.",
        )
    tax_document = SimpleNamespace(
        company=command.company_id,
        total=line_total,
        _tax_items=[SimpleNamespace(amount=line.amount) for line in command.lines],
    )
    try:
        calculated = _decimal(
            calculate_taxes(tax_document, command.tax_template_id).payable_delta
        )
    except TaxPricingError as exc:
        raise PurchaseInvoiceDraftError(
            "TAX_MISMATCH", "La plantilla fiscal configurada no puede aplicarse."
        ) from exc
    if abs(observed - calculated) > Decimal("0.02"):
        raise PurchaseInvoiceDraftError(
            "TAX_MISMATCH", "El impuesto observado no coincide con la plantilla fiscal."
        )
    return calculated


def create_purchase_invoice_draft(
    command: PurchaseInvoiceDraftCommand,
    actor_id: str,
    *,
    commit: bool = True,
) -> PurchaseInvoice:
    """Create a draft and line relations atomically, with no HTTP form dependency."""
    try:
        _require_actor_can_create(actor_id, command.company_id)
        company, supplier, settings = _validate_header(command)
        if command.idempotency_key:
            existing = database.session.execute(
                database.select(PurchaseInvoice).where(
                    PurchaseInvoice.idempotency_key == command.idempotency_key
                )
            ).scalar_one_or_none()
            if existing is not None:
                return existing
        _validate_duplicate(command)
        _validate_sources(command, settings)
        if not command.lines:
            raise PurchaseInvoiceDraftError(
                "LINE_UNRESOLVED", "La factura requiere al menos una línea."
            )
        validated = [_validate_line(line) for line in command.lines]
        line_total = sum(
            (_decimal(line.amount) for line in command.lines), Decimal("0")
        )
        rate = _exchange_rate(company, command)
        tax_total = _resolve_tax_total(command, line_total)
        grand_total = line_total + tax_total
        if command.expected_total is not None and abs(
            _decimal(command.expected_total) - grand_total
        ) > Decimal("0.02"):
            raise PurchaseInvoiceDraftError(
                "MATH_MISMATCH",
                "El total extraído no coincide con las líneas resueltas.",
            )
        invoice = PurchaseInvoice(
            company=command.company_id,
            supplier_id=command.supplier_id,
            supplier_name=supplier.name,
            supplier_invoice_no=command.supplier_invoice_no.strip(),
            idempotency_key=command.idempotency_key,
            document_type=PURCHASE_INVOICE,
            posting_date=command.posting_date,
            document_date=command.posting_date,
            transaction_currency=command.transaction_currency,
            base_currency=company.currency,
            exchange_rate=rate,
            purchase_order_id=command.purchase_order_id,
            purchase_receipt_id=command.purchase_receipt_id,
            tax_template_id=command.tax_template_id,
            total=line_total,
            base_total=_decimal(line_total * rate),
            tax_total=tax_total,
            grand_total=grand_total,
            base_grand_total=_decimal(grand_total * rate),
            outstanding_amount=grand_total,
            base_outstanding_amount=_decimal(grand_total * rate),
            remarks=command.remarks,
            docstatus=0,
            created_by=actor_id,
        )
        database.session.add(invoice)
        database.session.flush()
        assign_document_identifier(
            document=invoice,
            entity_type=PURCHASE_INVOICE,
            posting_date_raw=command.posting_date,
            naming_series_id=None,
        )
        for index, (line, item) in enumerate(
            zip(command.lines, validated, strict=True)
        ):
            invoice_line = PurchaseInvoiceItem(
                purchase_invoice_id=invoice.id,
                item_code=item.code,
                item_name=item.name,
                qty=line.quantity,
                uom=line.uom or item.purchase_uom or item.default_uom,
                rate=line.rate,
                amount=line.amount,
                base_rate=_decimal(line.rate * rate),
                base_amount=_decimal(line.amount * rate),
                expense_account_id=line.expense_account_id,
            )
            database.session.add(invoice_line)
            database.session.flush()
            if command.matching_mode == "THREE_WAY_MATCH":
                if not line.purchase_receipt_item_id:
                    raise PurchaseInvoiceDraftError(
                        "LINE_UNRESOLVED", "Falta la recepción de una línea 3-way."
                    )
                create_document_relation(
                    source_type="purchase_receipt",
                    source_id=str(command.purchase_receipt_id),
                    source_item_id=line.purchase_receipt_item_id,
                    target_type=PURCHASE_INVOICE,
                    target_id=invoice.id,
                    target_item_id=invoice_line.id,
                    qty=line.quantity,
                    uom=invoice_line.uom,
                    rate=line.rate,
                    amount=line.amount,
                )
            elif command.matching_mode == "TWO_WAY_MATCH":
                if not line.purchase_order_item_id:
                    raise PurchaseInvoiceDraftError(
                        "LINE_UNRESOLVED", "Falta la orden de una línea 2-way."
                    )
                create_document_relation(
                    source_type="purchase_order",
                    source_id=str(command.purchase_order_id),
                    source_item_id=line.purchase_order_item_id,
                    target_type=PURCHASE_INVOICE,
                    target_id=invoice.id,
                    target_item_id=invoice_line.id,
                    qty=line.quantity,
                    uom=invoice_line.uom,
                    rate=line.rate,
                    amount=line.amount,
                )
        refresh_source_caches_for_target(PURCHASE_INVOICE, invoice.id)
        log_create(invoice)
        if commit:
            database.session.commit()
        return invoice
    except PurchaseInvoiceDraftError:
        if commit:
            database.session.rollback()
        raise
    except DocumentFlowError as exc:
        if commit:
            database.session.rollback()
        code = (
            "QUANTITY_EXCEEDS_RECEIPT"
            if command.matching_mode == "THREE_WAY_MATCH"
            else "QUANTITY_EXCEEDS_ORDER"
        )
        raise PurchaseInvoiceDraftError(
            code, "La cantidad facturada excede el saldo disponible."
        ) from exc
    except Exception:
        if commit:
            database.session.rollback()
        raise
