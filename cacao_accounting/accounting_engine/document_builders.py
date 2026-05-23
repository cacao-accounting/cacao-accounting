# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Builders that convert operational documents into calculation contexts."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from decimal import Decimal, InvalidOperation
from typing import Any, Iterable, cast

from sqlalchemy import select

from cacao_accounting.accounting_engine.common.context import (
    AccountingReferences,
    CalculationContext,
    ItemContext,
    TaxRuleContext,
)
from cacao_accounting.database import (
    Accounts,
    BankAccount,
    CompanyDefaultAccount,
    CompanyParty,
    Entity,
    ItemAccount,
    PartyAccount,
    PaymentEntry,
    PaymentReference,
    PaymentTerms,
    PurchaseInvoice,
    PurchaseInvoiceItem,
    PurchaseReceipt,
    PurchaseReceiptItem,
    SalesInvoice,
    SalesInvoiceItem,
    Tax,
    TaxTemplateItem,
    database,
)
from cacao_accounting.document_flow.service import compute_payment_unallocated_amount
from cacao_accounting.tax_pricing_service import TaxCalculationResult, calculate_taxes
from cacao_accounting.fiscal_persistence_service import build_tax_rule_contexts_from_snapshot
from cacao_accounting.tax_rule_service import build_tax_rule_contexts

try:  # pragma: no cover - fallback defensivo para contextos sin Flask-Babel.
    from flask_babel import gettext as _babel_gettext
except ImportError:  # pragma: no cover

    def _(value: str) -> str:
        """Fallback identity translation."""
        return value

else:

    def _(value: str) -> str:
        """Translate user-facing text when Babel is available."""
        try:
            return _babel_gettext(value)
        except (KeyError, RuntimeError):  # pragma: no cover
            return value


class CalculationContextBuilderError(ValueError):
    """Controlled error raised while building a calculation context."""


@dataclass(frozen=True)
class AccountLineSpec:
    """Resolved account line used by the accounting mapper."""

    account_id: str
    amount: Decimal
    side: str
    description: str
    party_id: str | None = None


def build_calculation_context(document: Any) -> CalculationContext | None:
    """Build a calculation context for a supported transactional document."""
    if isinstance(document, PurchaseReceipt):
        return _build_purchase_receipt_context(document)
    if isinstance(document, PurchaseInvoice):
        return _build_purchase_invoice_context(document)
    if isinstance(document, SalesInvoice):
        return _build_sales_invoice_context(document)
    if isinstance(document, PaymentEntry):
        return _build_payment_context(document)
    return None


def _build_purchase_receipt_context(document: PurchaseReceipt) -> CalculationContext:
    """Build the context for a submitted purchase receipt."""
    company = _require_company(document.company)
    defaults = _company_defaults(company)
    items = list(
        database.session.execute(select(PurchaseReceiptItem).filter_by(purchase_receipt_id=document.id)).scalars().all()
    )
    if not items:
        raise CalculationContextBuilderError("La recepción de compra no contiene líneas para cálculo.")
    event_type = "purchase_receipt_confirmed"
    bridge_account_id = _require_account_id(
        getattr(defaults, "bridge_account_id", None),
        "Falta la cuenta puente configurada para la compañía.",
    )
    account_lines: list[AccountLineSpec] = []
    item_contexts: list[ItemContext] = []
    for item in items:
        amount = _line_amount(item)
        inventory_account_id = _require_account_id(
            _item_account_id(item.item_code, company, "inventory"),
            "Falta la cuenta de inventario para una línea de recepción de compra.",
        )
        description = getattr(item, "item_name", None) or item.item_code
        account_lines.append(
            AccountLineSpec(
                account_id=inventory_account_id,
                amount=amount,
                side="debit",
                description=f"{description} - {_event_label('purchase_receipt_confirmed')}",
            )
        )
        account_lines.append(
            AccountLineSpec(
                account_id=bridge_account_id,
                amount=amount,
                side="credit",
                description=f"{description} - {_('Cuenta puente compras')}",
                party_id=document.supplier_id,
            )
        )
        item_contexts.append(_item_context_from_purchase_receipt_item(item))
    tax_rules = _document_tax_rules(document, items, company=company, applies_to="purchase", event_type=event_type)
    return CalculationContext(
        company_id=company,
        document_type="purchase_receipt",
        event_type=event_type,
        transaction_direction="purchase",
        transaction_date=document.posting_date,
        posting_date=document.posting_date,
        party_type="supplier",
        party_id=str(document.supplier_id or ""),
        currency=_document_currency(document, company),
        company_currency=_company_currency(document, company),
        exchange_rate=_document_exchange_rate(document),
        items=item_contexts,
        tax_rules=tax_rules,
        references=_build_references(
            company=company,
            party_id=document.supplier_id,
            direction="purchase",
            account_lines=account_lines,
        ),
    )


def _build_purchase_invoice_context(document: PurchaseInvoice) -> CalculationContext:
    """Build the context for a submitted purchase invoice or credit note."""
    company = _require_company(document.company)
    items = list(
        database.session.execute(select(PurchaseInvoiceItem).filter_by(purchase_invoice_id=document.id)).scalars().all()
    )
    if not items:
        raise CalculationContextBuilderError("La factura de compra no contiene líneas para cálculo.")
    event_type = "purchase_credit_note_confirmed" if _is_purchase_credit_note(document) else "purchase_invoice_confirmed"
    account_lines = _purchase_invoice_account_lines(document, items, company)
    item_contexts = [_item_context_from_purchase_invoice_item(item) for item in items]
    tax_rules = _document_tax_rules(document, items, company=company, applies_to="purchase", event_type=event_type)
    return CalculationContext(
        company_id=company,
        document_type=document.document_type or "purchase_invoice",
        event_type=event_type,
        transaction_direction="purchase",
        transaction_date=document.posting_date,
        posting_date=document.posting_date,
        party_type="supplier",
        party_id=str(document.supplier_id or ""),
        currency=_document_currency(document, company),
        company_currency=_company_currency(document, company),
        exchange_rate=_document_exchange_rate(document),
        items=item_contexts,
        tax_rules=tax_rules,
        references=_build_references(
            company=company,
            party_id=document.supplier_id,
            direction="purchase",
            account_lines=account_lines,
        ),
    )


def _build_sales_invoice_context(document: SalesInvoice) -> CalculationContext:
    """Build the context for a submitted sales invoice or credit note."""
    company = _require_company(document.company)
    items = list(database.session.execute(select(SalesInvoiceItem).filter_by(sales_invoice_id=document.id)).scalars().all())
    if not items:
        raise CalculationContextBuilderError("La factura de venta no contiene líneas para cálculo.")
    event_type = "sales_credit_note_confirmed" if _is_sales_credit_note(document) else "sales_invoice_confirmed"
    side = "debit" if _is_sales_credit_note(document) else "credit"
    account_lines = [
        AccountLineSpec(
            account_id=_require_account_id(
                _item_account_for_line(item, company, "income"),
                "Falta la cuenta de ingresos para una línea de factura de venta.",
            ),
            amount=_line_amount(item),
            side=side,
            description=getattr(item, "item_name", None) or item.item_code,
        )
        for item in items
    ]
    item_contexts = [_item_context_from_sales_invoice_item(item) for item in items]
    tax_rules = _document_tax_rules(document, items, company=company, applies_to="sales", event_type=event_type)
    return CalculationContext(
        company_id=company,
        document_type=document.document_type or "sales_invoice",
        event_type=event_type,
        transaction_direction="sales",
        transaction_date=document.posting_date,
        posting_date=document.posting_date,
        party_type="customer",
        party_id=str(document.customer_id or ""),
        currency=_document_currency(document, company),
        company_currency=_company_currency(document, company),
        exchange_rate=_document_exchange_rate(document),
        items=item_contexts,
        tax_rules=tax_rules,
        references=_build_references(
            company=company,
            party_id=document.customer_id,
            direction="sales",
            account_lines=account_lines,
        ),
    )


def _build_payment_context(document: PaymentEntry) -> CalculationContext | None:
    """Build the context for a payment or collection document."""
    payment_type = (document.payment_type or "").lower()
    if payment_type not in {"pay", "receive"}:
        return None
    company = _require_company(document.company)
    direction = "purchase" if payment_type == "pay" else "sales"
    event_type = "payment_confirmed" if payment_type == "pay" else "collection_confirmed"
    amount_field = "paid_amount" if payment_type == "pay" else "received_amount"
    base_amount_field = "base_paid_amount" if payment_type == "pay" else "base_received_amount"
    actual_cash_amount = _decimal_value(getattr(document, amount_field, None))
    if actual_cash_amount <= 0:
        raise CalculationContextBuilderError("El monto del pago debe ser mayor que cero.")
    references = list(database.session.execute(select(PaymentReference).filter_by(payment_id=document.id)).scalars().all())
    settlement_references = [reference for reference in references if not _is_order_payment_reference(reference)]
    allocated_total = sum((_decimal_value(reference.allocated_amount) for reference in settlement_references), Decimal("0"))
    outstanding_total = sum(
        (
            _decimal_value(reference.outstanding_amount or reference.total_amount or reference.allocated_amount)
            for reference in settlement_references
        ),
        Decimal("0"),
    )
    settlement_amount = allocated_total if allocated_total > 0 else actual_cash_amount
    document_total = outstanding_total if outstanding_total > 0 else settlement_amount
    company_currency = _company_currency(document, company)
    transaction_currency = _document_currency(document, company)
    company_open_balance = Decimal("0")
    if settlement_references:
        company_open_balance = _estimated_company_open_balance(settlement_references, settlement_amount, document_total)
    if company_open_balance <= 0:
        company_open_balance = _decimal_value(getattr(document, base_amount_field, None))
    open_payment_amount = compute_payment_unallocated_amount(document)
    document_exchange_rate = (
        (company_open_balance / document_total).quantize(Decimal("0.000000001"))
        if references and document_total > 0 and company_open_balance > 0
        else _document_exchange_rate(document)
    )
    settlement_exchange_rate = _settlement_exchange_rate(
        document=document,
        company_amount=_decimal_value(getattr(document, base_amount_field, None)),
        transaction_amount=actual_cash_amount,
    )
    manual_discount_total = sum((_decimal_value(ref.discount_amount) for ref in settlement_references), Decimal("0"))
    if manual_discount_total > 0:
        eligible_discount_amount = manual_discount_total
    else:
        eligible_discount_amount = _eligible_discount_amount(
            company=company,
            party_id=document.party_id,
            payment_date=document.posting_date,
            references=settlement_references,
        )
    tax_rules = build_tax_rule_contexts_from_snapshot(
        document_type="payment_entry",
        document_id=document.id,
        recognition_event=event_type,
    )
    if not tax_rules:
        tax_rules = build_tax_rule_contexts(
            company=company,
            applies_to=direction,
            currency=transaction_currency,
            at_date=document.posting_date,
            recognition_event=event_type,
        )
    return CalculationContext(
        company_id=company,
        document_type="payment_entry",
        event_type=event_type,
        transaction_direction=direction,
        transaction_date=document.posting_date,
        posting_date=document.posting_date,
        party_type="supplier" if direction == "purchase" else "customer",
        party_id=str(document.party_id or ""),
        currency=transaction_currency,
        company_currency=company_currency,
        exchange_rate=document_exchange_rate,
        items=[
            ItemContext(
                line_id="PAYMENT-REF",
                item_id="PAYMENT-REF",
                description=f"Settlement {document.document_no or document.id}",
                quantity=Decimal("1"),
                unit_price=document_total,
                gross_amount=document_total,
                net_amount=document_total,
                item_type="service",
            )
        ],
        tax_rules=tax_rules,
        references=_build_references(
            company=company,
            party_id=document.party_id,
            direction=direction,
            account_lines=[],
            cash_account=_payment_cash_account(document),
            open_balance=company_open_balance,
            custom_references={
                "settlement_exchange_rate": settlement_exchange_rate,
                "actual_cash_amount": actual_cash_amount,
                "eligible_discount_amount": eligible_discount_amount,
                "use_advance_as_party_balance": not settlement_references,
                "open_payment_amount": open_payment_amount,
            },
        ),
        settlement_amount=settlement_amount,
    )


def _document_tax_rules(
    document: PurchaseInvoice | PurchaseReceipt | SalesInvoice,
    items: Iterable[Any],
    *,
    company: str,
    applies_to: str,
    event_type: str,
) -> list[TaxRuleContext]:
    """Load persisted tax rules and fall back to the current tax template if necessary."""
    fallback_document_type = (
        "purchase_receipt"
        if isinstance(document, PurchaseReceipt)
        else ("purchase_invoice" if applies_to == "purchase" else "sales_invoice")
    )
    persisted_rules = build_tax_rule_contexts_from_snapshot(
        document_type=getattr(document, "document_type", None) or fallback_document_type,
        document_id=document.id,
        recognition_event=event_type,
    )
    if persisted_rules:
        return persisted_rules
    tax_rules = build_tax_rule_contexts(
        company=company,
        applies_to=applies_to,
        currency=_document_currency(document, company),
        at_date=document.posting_date,
        recognition_event=event_type,
    )
    if tax_rules:
        return tax_rules
    template_id = getattr(document, "tax_template_id", None)
    if not template_id:
        return []
    setattr(document, "_tax_items", list(items))
    tax_result = calculate_taxes(document, template_id)
    return _tax_rules_from_template(document, tax_result, event_type)


def _tax_rules_from_template(
    document: PurchaseInvoice | SalesInvoice,
    tax_result: TaxCalculationResult,
    event_type: str,
) -> list[TaxRuleContext]:
    """Convert the legacy tax template result into rules consumable by the new engine."""
    rules: list[TaxRuleContext] = []
    template_items = (
        database.session.execute(
            select(TaxTemplateItem).filter_by(tax_template_id=document.tax_template_id).order_by(TaxTemplateItem.sequence)
        )
        .scalars()
        .all()
    )
    for index, tax_line in enumerate(tax_result.lines, start=1):
        template_item = template_items[index - 1] if index - 1 < len(template_items) else None
        tax = database.session.get(Tax, tax_line.tax_id)
        if not tax:
            continue
        rule_type = "charge" if tax_line.is_charge else ("withholding" if tax_line.behavior == "deductive" else "tax")
        accounting_treatment = "capitalizable_inventory_cost" if tax_line.is_capitalizable else "separate_tax_account"
        base_mode = "accumulated" if template_item and template_item.calculation_base == "previous_total" else "goods"
        rules.append(
            TaxRuleContext(
                rule_id=str(tax_line.tax_id),
                name=tax_line.name,
                concept=tax_line.name.lower().replace(" ", "_"),
                tax_type=rule_type,
                calculation_method=tax.tax_type if tax.tax_type in {"percentage", "fixed"} else "percentage",
                rate=_decimal_value(tax.rate),
                amount=tax_line.amount if tax.tax_type == "fixed" else Decimal("0"),
                base_mode=base_mode,
                include_concepts=["goods"] if base_mode == "accumulated" else [],
                order=index,
                accounting_treatment=accounting_treatment,
                recognition_event=event_type,
                affects_inventory=bool(tax_line.is_capitalizable),
                affects_document_total=not tax_line.is_inclusive,
                included_in_price=bool(tax_line.is_inclusive),
                account_id=tax_line.account_id,
            )
        )
    return rules


def _build_references(
    *,
    company: str,
    party_id: str | None,
    direction: str,
    account_lines: list[AccountLineSpec],
    cash_account: str | None = None,
    open_balance: Decimal = Decimal("0"),
    custom_references: dict[str, Any] | None = None,
) -> AccountingReferences:
    """Build the accounting reference bag used by the mapper."""
    defaults = _company_defaults(company)
    party_account = _party_account_id(party_id, company, receivable=direction == "sales")
    default_tax_accounts = _default_tax_accounts(defaults)
    custom = dict(custom_references or {})
    custom["account_lines"] = [line.__dict__ for line in account_lines]
    custom["default_purchase_tax_account_id"] = getattr(defaults, "default_purchase_tax_account_id", None)
    custom["default_sales_tax_account_id"] = getattr(defaults, "default_sales_tax_account_id", None)
    custom["default_inventory_account_id"] = getattr(defaults, "default_inventory", None)
    custom["default_income_account_id"] = getattr(defaults, "default_income", None)
    custom["default_bank_account_id"] = getattr(defaults, "default_bank", None)
    custom["default_rounding_account_id"] = getattr(defaults, "default_rounding_account_id", None)
    custom["exchange_gain_account_id"] = getattr(defaults, "exchange_gain_account_id", None)
    custom["exchange_loss_account_id"] = getattr(defaults, "exchange_loss_account_id", None)
    custom["unrealized_exchange_gain_account_id"] = getattr(defaults, "unrealized_exchange_gain_account_id", None)
    custom["unrealized_exchange_loss_account_id"] = getattr(defaults, "unrealized_exchange_loss_account_id", None)
    custom["payment_discount_account_id"] = getattr(defaults, "payment_discount_account_id", None)
    custom["advance_account_id"] = (
        getattr(defaults, "supplier_advance_account_id", None)
        if direction == "purchase"
        else getattr(defaults, "customer_advance_account_id", None)
    )
    return AccountingReferences(
        party_account=party_account,
        cash_account=cash_account or getattr(defaults, "default_bank", None) or getattr(defaults, "default_cash", None),
        open_balance=open_balance,
        default_tax_accounts=default_tax_accounts,
        custom_references=custom,
    )


def _default_tax_accounts(defaults: CompanyDefaultAccount | None) -> dict[str, str]:
    """Build default tax account aliases from company defaults."""
    if defaults is None:
        return {}
    aliases: dict[str, str] = {}
    if defaults.default_purchase_tax_account_id:
        aliases["purchase_tax"] = defaults.default_purchase_tax_account_id
    if defaults.default_sales_tax_account_id:
        aliases["sales_tax"] = defaults.default_sales_tax_account_id
    return aliases


def _purchase_invoice_account_lines(
    document: PurchaseInvoice,
    items: list[PurchaseInvoiceItem],
    company: str,
) -> list[AccountLineSpec]:
    """Resolve the non-tax lines for purchase invoices and credit notes."""
    use_bridge_account = bool(getattr(document, "purchase_receipt_id", None))
    side = "credit" if _is_purchase_credit_note(document) else "debit"
    account_type = "bridge" if use_bridge_account else "expense"
    specs: list[AccountLineSpec] = []
    for item in items:
        account_id = _require_account_id(
            _item_account_for_line(item, company, account_type),
            "Falta la cuenta de gasto o cuenta puente para una línea de factura de compra.",
        )
        specs.append(
            AccountLineSpec(
                account_id=account_id,
                amount=_line_amount(item),
                side=side,
                description=getattr(item, "item_name", None) or item.item_code,
            )
        )
    return specs


def _eligible_discount_amount(
    *,
    company: str,
    party_id: str | None,
    payment_date: Any,
    references: list[PaymentReference],
) -> Decimal:
    """Compute the maximum early payment discount allowed for the payment references."""
    if not party_id or not references:
        return Decimal("0")
    company_party = (
        database.session.execute(select(CompanyParty).filter_by(company=company, party_id=party_id, is_active=True))
        .scalars()
        .first()
    )
    if not company_party or not company_party.payment_terms_id:
        return Decimal("0")
    payment_terms = database.session.get(PaymentTerms, company_party.payment_terms_id)
    if not payment_terms or payment_terms.discount_days is None or payment_terms.discount_percent is None:
        return Decimal("0")
    discount_rate = _decimal_value(payment_terms.discount_percent) / Decimal("100")
    total_discount = Decimal("0")
    for reference in references:
        invoice = _payment_reference_document(reference)
        if invoice is None or not getattr(invoice, "posting_date", None):
            continue
        due_for_discount = invoice.posting_date + timedelta(days=int(payment_terms.discount_days))
        if payment_date <= due_for_discount:
            total_discount += _decimal_value(reference.allocated_amount) * discount_rate
    return total_discount.quantize(Decimal("0.0001"))


def _payment_reference_document(reference: PaymentReference) -> PurchaseInvoice | SalesInvoice | None:
    """Resolve the invoice linked to a payment reference."""
    if _is_order_payment_reference(reference):
        return None
    model = PurchaseInvoice if reference.reference_type == "purchase_invoice" else SalesInvoice
    return cast(PurchaseInvoice | SalesInvoice | None, database.session.get(model, reference.reference_id))


def _is_order_payment_reference(reference: PaymentReference) -> bool:
    """Return True when the reference only traces an advance source order."""
    reference_type = str(reference.reference_type or "")
    flow_source_type = str(getattr(reference, "flow_source_type", "") or "")
    return reference_type in {"purchase_order", "sales_order"} or flow_source_type in {"purchase_order", "sales_order"}


def _estimated_company_open_balance(
    references: list[PaymentReference],
    settlement_amount: Decimal,
    document_total: Decimal,
) -> Decimal:
    """Estimate the carrying balance in company currency for settlement calculations."""
    invoices = [invoice for reference in references if (invoice := _payment_reference_document(reference)) is not None]
    if not invoices:
        return settlement_amount
    total = Decimal("0")
    for invoice in invoices:
        base_outstanding = _decimal_value(getattr(invoice, "base_outstanding_amount", None))
        if base_outstanding > 0:
            total += base_outstanding
            continue
        outstanding = _decimal_value(getattr(invoice, "outstanding_amount", None) or getattr(invoice, "grand_total", None))
        total += outstanding * _document_exchange_rate(invoice)
    return total if total > 0 else document_total


def _settlement_exchange_rate(
    *,
    document: PaymentEntry,
    company_amount: Decimal,
    transaction_amount: Decimal,
) -> Decimal:
    """Resolve the effective settlement rate used by the cash movement."""
    if transaction_amount > 0 and company_amount > 0:
        return (company_amount / transaction_amount).quantize(Decimal("0.000000001"))
    return _document_exchange_rate(document)


def _payment_cash_account(document: PaymentEntry) -> str | None:
    """Resolve the cash or bank GL account referenced by the payment."""
    explicit_account = document.paid_from_account_id or document.paid_to_account_id
    if explicit_account:
        return str(explicit_account)
    if document.bank_account_id:
        bank_account = database.session.get(BankAccount, document.bank_account_id)
        if bank_account and bank_account.gl_account_id:
            return str(bank_account.gl_account_id)
    return None


def _item_context_from_purchase_receipt_item(item: PurchaseReceiptItem) -> ItemContext:
    """Convert a purchase receipt line into an item context."""
    return ItemContext(
        line_id=item.id,
        item_id=item.item_code,
        description=getattr(item, "item_name", None) or item.item_code,
        quantity=_decimal_value(item.qty),
        unit_price=_decimal_value(item.rate),
        gross_amount=_line_amount(item),
        net_amount=_line_amount(item),
        uom=item.uom or "unit",
        warehouse_id=item.warehouse,
    )


def _item_context_from_purchase_invoice_item(item: PurchaseInvoiceItem) -> ItemContext:
    """Convert a purchase invoice line into an item context."""
    return ItemContext(
        line_id=item.id,
        item_id=item.item_code,
        description=getattr(item, "item_name", None) or item.item_code,
        quantity=_decimal_value(item.qty),
        unit_price=_decimal_value(item.rate),
        gross_amount=_line_amount(item),
        net_amount=_line_amount(item),
        uom=item.uom or "unit",
        warehouse_id=item.warehouse,
    )


def _item_context_from_sales_invoice_item(item: SalesInvoiceItem) -> ItemContext:
    """Convert a sales invoice line into an item context."""
    return ItemContext(
        line_id=item.id,
        item_id=item.item_code,
        description=getattr(item, "item_name", None) or item.item_code,
        quantity=_decimal_value(item.qty),
        unit_price=_decimal_value(item.rate),
        gross_amount=_line_amount(item),
        discount_amount=_decimal_value(getattr(item, "discount_amount", None)),
        net_amount=_line_amount(item),
        uom=item.uom or "unit",
        warehouse_id=item.warehouse,
    )


def _item_account_id(item_code: str | None, company: str, account_type: str) -> str | None:
    """Resolve an item account using item mappings and company defaults."""
    if item_code:
        mapping = (
            database.session.execute(select(ItemAccount).filter_by(item_code=item_code, company=company)).scalars().first()
        )
        if mapping is not None:
            value = {
                "income": mapping.income_account_id,
                "expense": mapping.expense_account_id,
                "inventory": mapping.inventory_account_id,
                "bridge": getattr(_company_defaults(company), "bridge_account_id", None),
            }.get(account_type)
            if value:
                return value
    defaults = _company_defaults(company)
    if defaults is None:
        return None
    return {
        "income": defaults.default_income,
        "expense": defaults.default_expense,
        "inventory": defaults.default_inventory,
        "bridge": defaults.bridge_account_id,
    }.get(account_type)


def _item_account_for_line(line: Any, company: str, account_type: str) -> str | None:
    """Resolve an account using the explicit line field first and mappings second."""
    explicit_value = getattr(line, f"{account_type}_account_id", None)
    if explicit_value:
        return str(explicit_value)
    return _item_account_id(getattr(line, "item_code", None), company, account_type)


def _party_account_id(party_id: str | None, company: str, *, receivable: bool) -> str | None:
    """Resolve a third-party control account."""
    if party_id:
        mapping = (
            database.session.execute(select(PartyAccount).filter_by(party_id=party_id, company=company)).scalars().first()
        )
        if mapping is not None:
            account_id = mapping.receivable_account_id if receivable else mapping.payable_account_id
            if account_id:
                return account_id
    defaults = _company_defaults(company)
    if defaults is None:
        return None
    return defaults.default_receivable if receivable else defaults.default_payable


def _company_defaults(company: str) -> CompanyDefaultAccount | None:
    """Return the company default account configuration."""
    return database.session.execute(select(CompanyDefaultAccount).filter_by(company=company)).scalars().first()


def _document_currency(document: Any, company: str) -> str:
    """Resolve the transaction currency for the document."""
    entity = database.session.get(Entity, company)
    return str(
        getattr(document, "transaction_currency", None)
        or getattr(document, "currency", None)
        or getattr(entity, "currency", None)
        or "NIO"
    )


def _company_currency(document: Any, company: str) -> str:
    """Resolve the functional currency for the company/document."""
    entity = database.session.get(Entity, company)
    return str(
        getattr(document, "base_currency", None) or getattr(entity, "currency", None) or _document_currency(document, company)
    )


def _document_exchange_rate(document: Any) -> Decimal:
    """Resolve the document exchange rate."""
    return _decimal_value(getattr(document, "exchange_rate", None) or Decimal("1"))


def _line_amount(line: Any) -> Decimal:
    """Resolve a transactional line amount."""
    amount = _decimal_value(getattr(line, "amount", None))
    if amount > 0:
        return amount
    return _decimal_value(getattr(line, "qty", None)) * _decimal_value(getattr(line, "rate", None))


def _require_company(company: str | None) -> str:
    """Require a company code in the document."""
    if not company:
        raise CalculationContextBuilderError("El documento no tiene compañía configurada.")
    return str(company)


def _require_account_id(account_id: str | None, message: str) -> str:
    """Require an account identifier and validate it exists."""
    if not account_id:
        raise CalculationContextBuilderError(message)
    if database.session.get(Accounts, account_id) is None:
        raise CalculationContextBuilderError("La cuenta contable configurada no existe.")
    return str(account_id)


def _is_purchase_credit_note(document: PurchaseInvoice) -> bool:
    """Return whether the purchase invoice behaves as a credit note."""
    return bool(getattr(document, "is_return", False) or getattr(document, "document_type", "") == "purchase_credit_note")


def _is_sales_credit_note(document: SalesInvoice) -> bool:
    """Return whether the sales invoice behaves as a credit note."""
    return bool(getattr(document, "is_return", False) or getattr(document, "document_type", "") == "sales_credit_note")


def _decimal_value(value: Any) -> Decimal:
    """Convert any numeric-like value into Decimal."""
    if value is None:
        return Decimal("0")
    if isinstance(value, Decimal):
        return value
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError) as exc:
        raise CalculationContextBuilderError("Valor numérico inválido en el documento.") from exc


def _event_label(event_type: str) -> str:
    """Return a human readable label for account line descriptions."""
    labels = {
        "purchase_receipt_confirmed": _("Recepción de compra"),
    }
    return labels.get(event_type, event_type)
