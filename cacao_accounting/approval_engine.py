# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Approval Engine (Motor de Aprobaciones) configurable por compañía."""

from __future__ import annotations

import hashlib
import json
from contextvars import ContextVar
from contextlib import contextmanager
from collections.abc import Iterator
from datetime import date, datetime
from decimal import Decimal
from typing import Any
from flask_login import current_user
from sqlalchemy import select

from cacao_accounting.database import (
    ApprovalMatrix,
    ApprovalRequest,
    ApprovalAction,
    AuditTrail,
    CacaoConfig,
    RolesUser,
    User,
    database,
)
from cacao_accounting.runtime_mode import is_desktop_mode
from cacao_accounting import approval_policy
from cacao_accounting.document_flow.registry import normalize_doctype


from cacao_accounting.i18n import _

_APPROVAL_EXECUTION: ContextVar[tuple[str, str, str, str] | None] = ContextVar("approval_execution", default=None)


PENDING_APPROVAL_STATUS = "Pending Approval"
PENDING_CANCELLATION_STATUS = "Pending Cancellation"
_RELATION_ONLY_CANCEL_DOCTYPES = frozenset(
    {
        "purchase_request",
        "purchase_quotation",
        "supplier_quotation",
        "purchase_order",
        "sales_request",
        "sales_quotation",
        "sales_order",
    }
)
_POSTED_CANCEL_DOCTYPES = frozenset({"purchase_receipt", "purchase_invoice", "delivery_note", "sales_invoice"})


def _submit_document_and_refresh_flow(doctype: str, document: Any) -> None:
    """Post a related document and refresh source quantities after approval.

    Draft targets are intentionally excluded from flow consumption.  The
    refresh must therefore happen only after posting has made the target
    submitted, otherwise the source cache remains at its draft value.
    """
    from cacao_accounting.contabilidad.posting import submit_document
    from cacao_accounting.document_flow import refresh_source_caches_for_target

    submit_document(document)  # type: ignore[misc]
    refresh_source_caches_for_target(doctype, document.id)


def _cancel_relation_only_document(doctype: str, document: Any) -> None:
    """Cancel a draft relation document and refresh its flow caches."""
    from cacao_accounting.audit_trail_service import log_cancel
    from cacao_accounting.document_flow import refresh_source_caches_for_target, revert_relations_for_target

    if doctype == "sales_order":
        from cacao_accounting.ventas import _release_reservation_for_sales_order

        _release_reservation_for_sales_order(document)
    document.docstatus = 2
    log_cancel(document)
    revert_relations_for_target(doctype, document.id)
    refresh_source_caches_for_target(doctype, document.id)


def _cancel_posted_document(
    doctype: str,
    document: Any,
    *,
    reason: str | None,
    cancellation_date: Any = None,
    requested_at: Any = None,
    actor_user_id: str,
) -> None:
    """Cancel a posted document and refresh reversal-dependent caches."""
    from cacao_accounting.audit_trail_service import log_cancel
    from cacao_accounting.contabilidad.posting import cancel_document
    from cacao_accounting.document_flow import refresh_source_caches_for_target, revert_relations_for_target

    if doctype == "delivery_note":
        from cacao_accounting.ventas import _restore_reservation_for_delivery_note

        _restore_reservation_for_delivery_note(document)
    elif doctype == "sales_invoice":
        from cacao_accounting.ventas import _cancel_linked_delivery_note

        _cancel_linked_delivery_note(
            document,
            reason=reason,
            actor_user_id=actor_user_id,
            cancellation_date=cancellation_date,
            requested_at=requested_at,
        )
    cancel_document(
        document,
        reason=reason,
        actor_user_id=actor_user_id,
        cancellation_date=cancellation_date,
        requested_at=requested_at,
    )  # type: ignore[misc]
    log_cancel(document)
    target_type = getattr(document, "document_type", None) or doctype
    revert_relations_for_target(target_type, document.id)
    refresh_source_caches_for_target(target_type, document.id)
    _refresh_reversal_cache(document, target_type)


def _refresh_reversal_cache(document: Any, target_type: str) -> None:
    """Refresh outstanding cache for a source document after its reversal."""
    if not getattr(document, "reversal_of", None):
        return
    from cacao_accounting.document_flow.payment import refresh_outstanding_amount_cache

    source = database.session.get(get_model_class(target_type), document.reversal_of)
    if source:
        refresh_outstanding_amount_cache(source)


def _cancel_payment_or_stock(
    doctype: str,
    document: Any,
    *,
    reason: str | None,
    cancellation_date: Any = None,
    requested_at: Any = None,
    actor_user_id: str,
) -> None:
    """Cancel a payment or stock entry, applying payment-specific hooks."""
    from cacao_accounting.audit_trail_service import log_cancel
    from cacao_accounting.contabilidad.posting import cancel_document

    cancel_document(
        document,
        reason=reason,
        actor_user_id=actor_user_id,
        cancellation_date=cancellation_date,
        requested_at=requested_at,
    )  # type: ignore[misc]
    log_cancel(document)


def _deterministic_default(obj: Any) -> str:
    """Serialize non-primitive types to a stable string representation.

    Unlike the built-in ``default=str`` which may produce non-deterministic
    output for some objects (e.g. ORM instances whose ``__str__`` includes a
    memory address), this helper converts known types to canonical strings
    and falls back to ``repr()`` which is always deterministic for a given
    object type and value.
    """
    if isinstance(obj, Decimal):
        return str(obj)
    if isinstance(obj, (date, datetime)):
        return obj.isoformat()
    return repr(obj)


def _rule_amount_matches(rule: ApprovalMatrix, amount: Decimal) -> bool:
    """Check if an amount falls within a rule's min/max range."""
    if not rule.min_amount <= amount:
        return False
    if rule.max_amount is not None and rule.max_amount < amount:
        return False
    return True


def _rule_selection_key(rule: ApprovalMatrix) -> tuple[Any, ...]:
    """Order overlapping rules deterministically for a reproducible decision.

    When several rules cover the same amount, the one used to record the
    approval must not depend on the database return order. The most senior
    level wins; ties are broken by the most specific range (highest lower
    bound, then narrowest upper bound) and finally by the stable rule id.
    """
    upper = rule.max_amount if rule.max_amount is not None else Decimal("1e30")
    return (rule.approval_level, rule.min_amount, -upper, str(rule.id or ""))


def _add_approver_from_rule(rule: ApprovalMatrix, roles: list[str], users: list[str]) -> None:
    """Add a user or role name from a matching approval rule."""
    if rule.user_id:
        user = database.session.get(User, rule.user_id)
        if user and user.name:
            users.append(user.name)
        return
    if rule.role_id:
        from cacao_accounting.database import Roles

        role = database.session.get(Roles, rule.role_id)
        if role:
            roles.append(role.note or role.name)


class ApprovalEngine:
    """Motor de Aprobaciones configurable por compañía."""

    @staticmethod
    def is_enabled(company_id: str | None) -> bool:
        """Indica si el Approval Engine está habilitado para la compañía."""
        if not company_id:
            return False
        if is_desktop_mode():
            return False
        # Buscamos en CacaoConfig f"approval_engine_enabled_{company_id}"
        cfg = database.session.execute(
            select(CacaoConfig).filter_by(key=f"approval_engine_enabled_{company_id}")
        ).scalar_one_or_none()
        if cfg and cfg.value.lower() in {"1", "true", "yes", "on", "enabled"}:
            return True
        return False

    @staticmethod
    def requires_different_approver(company_id: str | None) -> bool:
        """Devuelve si la compañía exige un aprobador distinto del creador."""
        if not company_id or is_desktop_mode():
            return False
        cfg = database.session.execute(
            select(CacaoConfig).filter_by(key=f"approval_require_different_approver_{company_id}")
        ).scalar_one_or_none()
        if not cfg:
            return False
        return cfg.value.lower() in {"1", "true", "yes", "on", "enabled"}

    @classmethod
    def _pending_request(cls, document: Any, *, lock: bool = False) -> ApprovalRequest | None:
        """Load the active request, locking it before a state transition."""
        doctype = cls._resolve_doctype(document)
        query = select(ApprovalRequest).where(
            ApprovalRequest.document_id == document.id,
            ApprovalRequest.document_type.in_({doctype, f"cancel_{doctype}"}),
            ApprovalRequest.status.in_({PENDING_APPROVAL_STATUS, PENDING_CANCELLATION_STATUS}),
        )
        if lock:
            query = query.with_for_update().execution_options(populate_existing=True)
        return database.session.execute(query).scalar_one_or_none()

    @classmethod
    def _independent_policy(cls, document: Any, req: ApprovalRequest | None = None) -> dict[str, Any] | None:
        """Prefer the persisted policy so configuration cannot weaken pending reviews."""
        if req is not None and req.policy_snapshot is not None:
            return req.policy_snapshot if req.policy_snapshot.get("requires_independent") else None
        company = (
            getattr(document, "company", None) or getattr(document, "company_id", None) or getattr(document, "entity", None)
        )
        if not cls.requires_different_approver(company):
            return None
        requester = req.requested_by if req else getattr(current_user, "id", None)
        try:
            return approval_policy.build_policy(document, str(requester or ""), cls._resolve_doctype(document))
        except ValueError:
            return {"requires_independent": True, "module": "", "preparers": []}

    @classmethod
    def handle_submission(cls, document: Any, user: Any, label: str = "Documento") -> bool:
        """Maneja el flujo completo de aprobación al enviar un documento.

        Retorna True si el motor procesó la solicitud (el caller debe redirigir).
        Retorna False si el motor no está activo o no cubre el monto (el caller
        debe proceder con el submit normal).
        """
        from flask import flash as flask_flash

        company_id = (
            getattr(document, "company", None) or getattr(document, "company_id", None) or getattr(document, "entity", None)
        )
        if not company_id or not cls.is_enabled(company_id):
            return False

        req = cls.request_approval(document, actor=user)
        if not req:
            flask_flash(
                _("No existe una regla de aprobación que cubra este monto. El documento permanece en borrador."),
                "warning",
            )
            database.session.commit()
            return True

        if cls.can_approve(document, user):
            cls.approve(document, user, _("Aprobado por el remitente"))
            database.session.commit()
            flask_flash(_("%(label)s aprobada.") % {"label": label}, "success")
        else:
            database.session.commit()
            flask_flash(
                _("%(label)s enviada para aprobación (Pendiente de Aprobación).") % {"label": label},
                "info",
            )
        return True

    @staticmethod
    def _resolve_doctype(document: Any) -> str:
        doctype = getattr(document, "document_type", None) or getattr(document, "__tablename__", "") or ""
        if doctype == "comprobante_contable":
            return "journal_entry"
        return normalize_doctype(str(doctype))

    @staticmethod
    def get_document_amount(document: Any) -> Decimal:
        """Resuelve el monto total de cualquier documento."""
        for field in ["grand_total", "total_amount", "total", "paid_amount", "received_amount"]:
            val = getattr(document, field, None)
            if val is not None:
                return Decimal(str(val))
        return Decimal("0")

    @classmethod
    def _approval_snapshot(cls, document: Any) -> tuple[dict[str, Any], str]:
        """Build a canonical header/lines payload and its persistent hash."""
        doctype = cls._resolve_doctype(document)
        excluded = {"modified", "modified_by"}
        document_table = getattr(document, "__table__", None)
        header = (
            {
                str(column.name): getattr(document, column.name)
                for column in document_table.columns
                if str(column.name) not in excluded
            }
            if document_table is not None
            else {}
        )
        lines: list[dict[str, Any]] = []
        try:
            from cacao_accounting.document_flow.registry import get_document_type

            spec = get_document_type(doctype)
            parent_field = spec.parent_field
            rows = database.session.execute(select(spec.item_model).filter_by(**{parent_field: document.id})).scalars().all()
            for row in sorted(rows, key=lambda value: str(getattr(value, "id", ""))):
                row_table = getattr(row, "__table__", None)
                if row_table is None:
                    continue
                lines.append(
                    {
                        str(column.name): getattr(row, column.name)
                        for column in row_table.columns
                        if str(column.name) not in {"id", "created", "modified", "created_by", "modified_by"}
                    }
                )
        except (KeyError, AttributeError):
            # Some accounting documents do not participate in document flow.
            lines = []
        payload = {"header": header, "lines": lines}
        serialized = json.dumps(payload, default=_deterministic_default, ensure_ascii=False, sort_keys=True)
        return payload, hashlib.sha256(serialized.encode("utf-8")).hexdigest()

    @staticmethod
    def _get_user_rules(user_id: str, company_id: str, document_type: str) -> list[ApprovalMatrix]:
        """Obtiene las reglas de matriz aplicables al usuario con su prioridad."""
        # 1. Reglas específicas por usuario
        rules = list(
            database.session.execute(
                select(ApprovalMatrix)
                .filter_by(
                    company_id=company_id,
                    document_type=document_type,
                    user_id=user_id,
                    enabled=True,
                )
                .order_by(ApprovalMatrix.approval_level.desc(), ApprovalMatrix.min_amount.desc(), ApprovalMatrix.id)
            )
            .scalars()
            .all()
        )
        if rules:
            return rules

        # 2. Reglas del rol del usuario si no hay específicas
        role_ids = list(
            database.session.execute(select(RolesUser.role_id).filter_by(user_id=user_id, active=True)).scalars().all()
        )
        if not role_ids:
            return []

        rules = list(
            database.session.execute(
                select(ApprovalMatrix)
                .filter(
                    ApprovalMatrix.company_id == company_id,
                    ApprovalMatrix.document_type == document_type,
                    ApprovalMatrix.role_id.in_(role_ids),
                    ApprovalMatrix.user_id.is_(None),
                    ApprovalMatrix.enabled,
                )
                .order_by(ApprovalMatrix.approval_level.desc(), ApprovalMatrix.min_amount.desc(), ApprovalMatrix.id)
            )
            .scalars()
            .all()
        )
        return rules

    @classmethod
    def can_approve(cls, document: Any, user: Any) -> bool:
        """Verifica si el usuario tiene autorización para aprobar el documento."""
        company_id = (
            getattr(document, "company", None) or getattr(document, "company_id", None) or getattr(document, "entity", None)
        )
        if not company_id:
            return True
        req = cls._pending_request(document)
        if not cls.is_enabled(company_id) and req is None:
            return True

        spec_module = approval_policy.document_module(cls._resolve_doctype(document))
        if not approval_policy.authorized(user, company_id, spec_module):
            return False
        policy = cls._independent_policy(document, req)
        if policy and not approval_policy.permits_independent_approval(policy, user, company_id):
            return False
        if approval_policy.is_admin(user):
            return True

        amount = cls.get_document_amount(document)
        document_type = cls._resolve_doctype(document)

        rules = cls._get_user_rules(user.id, company_id, document_type)
        required_level = req.required_level if req is not None else 0
        return cls._find_applicable_rule(rules, amount, user, required_level) is not None

    @classmethod
    def _get_required_level(cls, company_id: str, document_type: str, amount: Decimal) -> int:
        """Determina el nivel requerido para aprobar un monto."""
        rules = list(
            database.session.execute(
                select(ApprovalMatrix).filter_by(
                    company_id=company_id,
                    document_type=document_type,
                    enabled=True,
                )
            )
            .scalars()
            .all()
        )
        covering_rules = []
        for r in rules:
            if r.min_amount <= amount and (r.max_amount is None or r.max_amount >= amount):
                covering_rules.append(r)

        if not covering_rules:
            return 0

        return min(r.approval_level for r in covering_rules)

    @staticmethod
    def _assert_approval_snapshot(req: ApprovalRequest, document: Any) -> None:
        """Reject approval when the persisted document payload changed."""
        from sqlalchemy import desc

        expected_action = "cancellation_requested" if str(req.document_type).startswith("cancel_") else "approval_requested"
        snapshot_entry = (
            database.session.execute(
                select(AuditTrail)
                .where(AuditTrail.document_id == document.id, AuditTrail.action == expected_action)
                .order_by(desc(AuditTrail.timestamp), desc(AuditTrail.id))
            )
            .scalars()
            .first()
        )
        if snapshot_entry and snapshot_entry.comment:
            marker = "snapshot_sha256:"
            expected_hash = next(
                (part[len(marker) :] for part in snapshot_entry.comment.split() if part.startswith(marker)),
                None,
            )
            if expected_hash:
                _snapshot, actual_hash = ApprovalEngine._approval_snapshot(document)
                if actual_hash != expected_hash:
                    raise ValueError(_("El documento cambió después de solicitar aprobación; debe enviarse nuevamente."))
                return
        requested_at = getattr(req, "created_at", None)
        modified_at = getattr(document, "modified", None)
        if requested_at and modified_at and modified_at > requested_at:
            raise ValueError(_("El documento cambió después de solicitar aprobación; debe enviarse nuevamente."))

    @staticmethod
    def ensure_document_editable(document: Any) -> None:
        """Prevent edits while an approval or cancellation request is pending."""
        doctype = ApprovalEngine._resolve_doctype(document)
        pending = database.session.execute(
            select(ApprovalRequest.id).where(
                ApprovalRequest.document_id == document.id,
                ApprovalRequest.document_type.in_({doctype, f"cancel_{doctype}"}),
                ApprovalRequest.status.in_({PENDING_APPROVAL_STATUS, PENDING_CANCELLATION_STATUS}),
            )
        ).scalar_one_or_none()
        if pending:
            raise ValueError(_("El documento tiene una solicitud de aprobación pendiente y no puede editarse."))

    @staticmethod
    def _validate_final_cancellation(doctype: str, document: Any) -> None:
        """Recheck downstream dependencies at the moment cancellation executes."""
        if doctype in {"sales_order", "delivery_note", "sales_invoice", "purchase_order", "purchase_receipt"}:
            from cacao_accounting.document_flow.repository import has_active_source_relations

            if has_active_source_relations(doctype, document.id):
                raise ValueError(_("El documento adquirió relaciones activas mientras esperaba aprobación."))
        if doctype == "purchase_invoice":
            from cacao_accounting.database import DocumentRelation, PaymentEntry, PaymentReference
            from cacao_accounting.compras import _has_active_purchase_reversal_notes

            if _has_active_purchase_reversal_notes(document.id):
                raise ValueError(_("La factura adquirió notas de crédito o débito activas mientras esperaba aprobación."))

            active_payment = (
                database.select(PaymentReference.id)
                .join(
                    DocumentRelation,
                    (DocumentRelation.target_item_id == PaymentReference.id)
                    & (DocumentRelation.target_type == "payment_entry")
                    & (DocumentRelation.status == "active"),
                )
                .join(PaymentEntry, PaymentEntry.id == PaymentReference.payment_id)
                .where(
                    PaymentReference.reference_type == "purchase_invoice",
                    PaymentReference.reference_id == document.id,
                    PaymentEntry.docstatus == 1,
                )
            )
            if database.session.execute(active_payment).scalars().first() is not None:
                raise ValueError(_("La factura adquirió una aplicación de pago activa mientras esperaba aprobación."))

    @staticmethod
    def _validate_sales_submission(doctype: str, document: Any) -> None:
        """Validate sales credit, quantity, price, and credit rules."""
        from cacao_accounting.ventas import _validate_credit_limit_and_overdue

        if doctype == "sales_order" and not getattr(document, "is_return", False):
            _validate_credit_limit_and_overdue(
                document.company,
                document.customer_id,
                document.grand_total or Decimal("0"),
                current_document=document,
            )
            return
        if doctype not in {"sales_invoice", "sales_return"}:
            return
        from cacao_accounting.ventas import (
            _validate_invoice_prices_against_source,
            _validate_reversal_of,
            _validate_sales_invoice_quantities,
        )

        if not getattr(document, "is_return", False):
            _validate_credit_limit_and_overdue(
                document.company,
                document.customer_id,
                document.grand_total or Decimal("0"),
                current_document=document,
            )
        _validate_sales_invoice_quantities(document.id)
        _validate_invoice_prices_against_source(document)
        if getattr(document, "document_type", None) in {"sales_credit_note", "sales_return"}:
            _validate_reversal_of(
                document.reversal_of or "",
                document.customer_id,
                document.company,
                note_amount=Decimal(str(document.grand_total or "0")),
                document_type=document.document_type,
                posting_date=document.posting_date,
                lock_source=True,
            )

    @staticmethod
    def _validate_purchase_submission(document: Any) -> None:
        """Validate purchase invoice receipt, supplier, and duplicate rules."""
        from cacao_accounting.compras import (
            _validate_duplicate_supplier_invoice,
            _validate_invoice_requires_supplier_link,
            _validate_invoice_quantities_against_receipt,
            _validate_purchase_reversal_of,
            _validate_supplier_invoice_flags,
        )

        _validate_invoice_quantities_against_receipt(document.id)
        _validate_invoice_requires_supplier_link(document.id)
        _validate_supplier_invoice_flags(
            document.supplier_id,
            document.company,
            document.purchase_order_id,
            document.purchase_receipt_id,
            document_type=getattr(document, "document_type", None),
        )
        _validate_duplicate_supplier_invoice(
            document.supplier_id,
            document.supplier_invoice_no,
            exclude_id=document.id,
        )
        if getattr(document, "document_type", None) in {"purchase_credit_note", "purchase_debit_note"}:
            _validate_purchase_reversal_of(
                document.reversal_of or "",
                document.supplier_id,
                document.company,
                note_amount=Decimal(str(document.grand_total or "0")),
                document_type=document.document_type,
                posting_date=document.posting_date,
                lock_source=True,
            )

    @staticmethod
    def _validate_final_submission(doctype: str, document: Any) -> None:
        """Repeat common document prerequisites immediately before submit."""
        from cacao_accounting.document_flow.validation import validate_submit_prerequisites
        from cacao_accounting.database import (
            DeliveryNoteItem,
            PurchaseInvoiceItem,
            PurchaseOrderItem,
            PurchaseQuotationItem,
            PurchaseRequestItem,
            PurchaseReceiptItem,
            SalesInvoiceItem,
            SalesQuotationItem,
            SalesRequestItem,
            SalesOrderItem,
            StockEntryItem,
            SupplierQuotationItem,
            database as db,
        )

        if doctype == "payment_entry":
            from cacao_accounting.bancos import _validate_payment_header

            payment_type = str(getattr(document, "payment_type", "") or "")
            amount = Decimal(str(getattr(document, "paid_amount", None) or getattr(document, "received_amount", None) or 0))
            posting_date = getattr(document, "posting_date", None)
            _validate_payment_header(
                payment_type=payment_type,
                company=getattr(document, "company", None),
                bank_account_id=getattr(document, "bank_account_id", None),
                posting_date_raw=posting_date.isoformat() if posting_date else None,
                amount=amount,
                party_type=getattr(document, "party_type", None),
                party_id=getattr(document, "party_id", None),
                target_bank_account_id=getattr(document, "target_bank_account_id", None),
            )
            return

        item_models = {
            "sales_request": (SalesRequestItem, "sales_request_id"),
            "sales_quotation": (SalesQuotationItem, "sales_quotation_id"),
            "sales_order": (SalesOrderItem, "sales_order_id"),
            "delivery_note": (DeliveryNoteItem, "delivery_note_id"),
            "sales_invoice": (SalesInvoiceItem, "sales_invoice_id"),
            "sales_return": (SalesInvoiceItem, "sales_invoice_id"),
            "purchase_request": (PurchaseRequestItem, "purchase_request_id"),
            "purchase_quotation": (PurchaseQuotationItem, "purchase_quotation_id"),
            "supplier_quotation": (SupplierQuotationItem, "supplier_quotation_id"),
            "purchase_order": (PurchaseOrderItem, "purchase_order_id"),
            "purchase_receipt": (PurchaseReceiptItem, "purchase_receipt_id"),
            "purchase_invoice": (PurchaseInvoiceItem, "purchase_invoice_id"),
            "stock_entry": (StockEntryItem, "stock_entry_id"),
        }
        if doctype not in item_models:
            return
        item_model, foreign_key = item_models[doctype]
        item_query = db.select(item_model).filter_by(**{foreign_key: document.id})
        if hasattr(item_model, "is_superseded"):
            item_query = item_query.filter_by(is_superseded=False)
        items = db.session.execute(item_query).scalars().all()
        if doctype in {"delivery_note", "sales_invoice", "purchase_receipt", "stock_entry"}:
            from cacao_accounting.inventario.service import validate_batch_serial_draft

            validate_batch_serial_draft(items)
        from cacao_accounting.document_flow import validate_currency_contract

        validate_currency_contract(document, context=doctype)
        validate_submit_prerequisites(
            document,
            items=items,
            require_party=doctype not in {"stock_entry", "delivery_note", "purchase_request"},
            require_rate_positive=doctype not in {"delivery_note", "stock_entry", "sales_request", "purchase_request"},
            require_amount_nonzero=doctype in {"sales_invoice", "sales_return", "purchase_invoice"},
            require_warehouse=doctype in {"delivery_note", "sales_invoice", "purchase_receipt", "stock_entry"},
        )
        if doctype in {"sales_order", "sales_invoice", "sales_return"}:
            ApprovalEngine._validate_sales_submission(doctype, document)
        elif doctype == "purchase_invoice":
            ApprovalEngine._validate_purchase_submission(document)
        elif doctype == "purchase_receipt":
            from cacao_accounting.compras import _validate_receipt_quantities_against_po

            _validate_receipt_quantities_against_po(document.id)

    @staticmethod
    def _request_actor_id(actor: Any = None) -> str:
        """Require a real active requester instead of inventing a system user id."""
        from cacao_accounting.internal_control_service import current_audit_actor

        actor_id = getattr(actor, "id", None) if actor is not None else current_audit_actor()[0]
        user = database.session.get(User, actor_id) if actor_id else None
        if user is None or user.active is not True:
            raise ValueError(_("La solicitud requiere un usuario activo identificado."))
        return str(user.id)

    @staticmethod
    def _lock_document(document: Any) -> None:
        """Serialize request creation on the existing document in PostgreSQL."""
        model = type(document)
        database.session.execute(select(model).where(model.id == document.id).with_for_update())

    @classmethod
    def request_approval(cls, document: Any, *, actor: Any = None) -> ApprovalRequest | None:
        """Crea una solicitud de aprobación para el documento si no existe."""
        company_id = (
            getattr(document, "company", None) or getattr(document, "company_id", None) or getattr(document, "entity", None)
        )
        if not company_id or not cls.is_enabled(company_id):
            return None

        doctype = cls._resolve_doctype(document)
        amount = cls.get_document_amount(document)

        cls._lock_document(document)
        req = database.session.execute(
            select(ApprovalRequest)
            .filter_by(document_type=doctype, document_id=document.id)
            .where(ApprovalRequest.status.in_({PENDING_APPROVAL_STATUS, PENDING_CANCELLATION_STATUS, "Approved"}))
            .order_by(ApprovalRequest.created_at.desc())
            .limit(1)
        ).scalar_one_or_none()
        if req:
            return req

        req_level = cls._get_required_level(company_id, doctype, amount)
        if req_level == 0:
            return None
        user_id = cls._request_actor_id(actor)
        policy = cls._new_policy(document, user_id, doctype.removeprefix("cancel_"))

        req = ApprovalRequest(
            document_type=doctype,
            document_id=document.id,
            company_id=company_id,
            requested_by=user_id,
            policy_snapshot=policy,
            current_level=1,
            required_level=req_level,
            status=PENDING_APPROVAL_STATUS,
        )
        database.session.add(req)
        database.session.flush()
        from cacao_accounting.audit_trail_service import log_approval_requested

        from cacao_accounting.internal_control_service import audit_actor

        snapshot, snapshot_hash = cls._approval_snapshot(document)
        with audit_actor(user_id, str(getattr(actor, "name", None) or user_id)):
            log_approval_requested(document, snapshot, snapshot_hash)
        return req

    @classmethod
    def request_cancellation(
        cls, document: Any, *, reason: str | None = None, cancellation_date: Any = None, actor: Any = None
    ) -> ApprovalRequest | None:
        """Crea una solicitud de cancelación para el documento si no existe."""
        company_id = (
            getattr(document, "company", None) or getattr(document, "company_id", None) or getattr(document, "entity", None)
        )
        if not company_id or not cls.is_enabled(company_id):
            return None

        base_doctype = cls._resolve_doctype(document)
        doctype = f"cancel_{base_doctype}"
        if base_doctype in _POSTED_CANCEL_DOCTYPES or base_doctype == "journal_entry":
            if not (reason or "").strip():
                raise ValueError(_("Debe indicar el motivo de la anulación."))
        amount = cls.get_document_amount(document)

        cls._lock_document(document)
        req = database.session.execute(
            select(ApprovalRequest)
            .filter_by(document_type=doctype, document_id=document.id)
            .where(ApprovalRequest.status.in_({PENDING_APPROVAL_STATUS, PENDING_CANCELLATION_STATUS, "Approved"}))
            .order_by(ApprovalRequest.created_at.desc())
            .limit(1)
        ).scalar_one_or_none()
        if req:
            return req

        req_level = cls._get_required_level(company_id, base_doctype, amount)
        if req_level == 0:
            return None
        user_id = cls._request_actor_id(actor)
        policy = cls._new_policy(document, user_id, doctype.removeprefix("cancel_"))

        req = ApprovalRequest(
            document_type=doctype,
            document_id=document.id,
            company_id=company_id,
            requested_by=user_id,
            policy_snapshot=policy,
            current_level=1,
            required_level=req_level,
            status=PENDING_CANCELLATION_STATUS,
            cancellation_date=cancellation_date,
            cancellation_reason=(reason or "").strip() or None,
        )
        database.session.add(req)
        database.session.flush()
        from cacao_accounting.audit_trail_service import log_approval_requested

        from cacao_accounting.internal_control_service import audit_actor

        snapshot, snapshot_hash = cls._approval_snapshot(document)
        with audit_actor(user_id, str(getattr(actor, "name", None) or user_id)):
            log_approval_requested(document, snapshot, snapshot_hash, cancellation=True)
        return req

    @classmethod
    def _new_policy(cls, document: Any, user_id: str, doctype: str) -> dict[str, Any]:
        """Validate and freeze independent approval configuration."""
        company = (
            getattr(document, "company", None) or getattr(document, "company_id", None) or getattr(document, "entity", None)
        )
        if not cls.requires_different_approver(company):
            return {"requires_independent": False}
        try:
            return approval_policy.build_policy(document, user_id, doctype)
        except ValueError as exc:
            raise ValueError(_("Debe identificar y clasificar a los preparadores antes de solicitar aprobación.")) from exc

    @staticmethod
    def _find_applicable_rule(
        rules: list[ApprovalMatrix],
        amount: Decimal,
        user: Any,
        req_level: int,
    ) -> ApprovalMatrix | None:
        """Find the deterministic rule covering the amount, or fallback for admin users."""
        if approval_policy.is_admin(user):
            return ApprovalMatrix(
                approval_level=req_level,
                max_amount=amount,
                enabled=True,
            )
        covering = [rule for rule in rules if _rule_amount_matches(rule, amount)]
        return max(covering, key=_rule_selection_key) if covering else None

    @classmethod
    def _finalize_approval(cls, req: ApprovalRequest, document: Any, user: Any) -> bool:
        """Mark request as approved and execute submit or cancel. Returns True if fully approved."""
        from cacao_accounting.internal_control_service import audit_actor

        token = _APPROVAL_EXECUTION.set(_execution_key(document, str(user.id)))
        try:
            with audit_actor(str(user.id), str(getattr(user, "name", None) or user.id)):
                if req.document_type.startswith("cancel_"):
                    actual_doc_type = req.document_type[7:]
                    actual_doc = database.session.get(get_model_class(actual_doc_type), req.document_id)
                    cls._validate_final_cancellation(actual_doc_type, actual_doc)
                    cls._execute_cancel(
                        actual_doc_type,
                        actual_doc,
                        user,
                        reason=req.cancellation_reason,
                        cancellation_date=req.cancellation_date,
                        requested_at=req.created_at,
                    )
                else:
                    cls._execute_submit(req.document_type, document, user)
                from cacao_accounting.audit_trail_service import log_approve

                log_approve(document)
                database.session.flush()
                return True

        finally:
            _APPROVAL_EXECUTION.reset(token)

    @classmethod
    def approve(cls, document: Any, user: Any, comments: str | None = None) -> bool:
        """Aprueba el documento para el nivel actual."""
        company_id = (
            getattr(document, "company", None) or getattr(document, "company_id", None) or getattr(document, "entity", None)
        )
        if not company_id or is_desktop_mode():
            return True
        if not cls.is_enabled(company_id) and cls._pending_request(document) is None:
            return True

        doctype = cls._resolve_doctype(document)
        amount = cls.get_document_amount(document)

        req = cls._pending_request(document, lock=True)
        if not req:
            finished = database.session.execute(
                select(ApprovalRequest.id).where(
                    ApprovalRequest.document_id == document.id,
                    ApprovalRequest.document_type.in_({doctype, f"cancel_{doctype}"}),
                    ApprovalRequest.status == "Approved",
                )
            ).first()
            if finished:
                return True
            req = cls.request_approval(document, actor=user)
            if not req:
                return True

        if req.status == "Approved":
            return True
        if req.status not in {PENDING_APPROVAL_STATUS, PENDING_CANCELLATION_STATUS}:
            raise ValueError(_("La solicitud de aprobación no está en estado pendiente."))

        if not cls.can_approve(document, user):
            raise ValueError(_("El usuario no cumple los permisos, límites o independencia requeridos para aprobar."))

        cls._assert_approval_snapshot(req, document)

        rules = cls._get_user_rules(user.id, company_id, doctype)
        applicable_rule = cls._find_applicable_rule(rules, amount, user, req.required_level)
        if not applicable_rule:
            raise ValueError(_("El usuario no tiene límites autorizados suficientes para aprobar este documento."))

        action = ApprovalAction(
            approval_request_id=req.id,
            approved_by=user.id,
            role_id=applicable_rule.role_id,
            rule_id=applicable_rule.id if applicable_rule.id else None,
            limit_allowed=applicable_rule.max_amount,
            document_amount=amount,
            action="approve",
            comments=comments,
            level=applicable_rule.approval_level,
        )
        database.session.add(action)

        if applicable_rule.approval_level >= req.required_level:
            from cacao_accounting.internal_control_service import approval_request_transition

            with approval_request_transition(req):
                req.status = "Approved"
                return cls._finalize_approval(req, document, user)

        from cacao_accounting.internal_control_service import approval_request_transition

        with approval_request_transition(req):
            req.current_level = applicable_rule.approval_level + 1
            database.session.flush()
        return False

    @classmethod
    def _execute_submit(cls, doctype: str, document: Any, user: Any) -> None:
        """Ejecuta de manera segura la submision de un documento con todos sus hooks."""
        from cacao_accounting.audit_trail_service import log_submit

        cls._validate_final_submission(doctype, document)

        if doctype == "journal_entry":
            from cacao_accounting.contabilidad.journal_service import submit_journal

            submit_journal(document.id, commit=False, user_id=str(user.id))
            return

        if doctype in {
            "purchase_request",
            "purchase_quotation",
            "supplier_quotation",
            "purchase_order",
            "sales_request",
            "sales_quotation",
        }:
            document.docstatus = 1
            log_submit(document)
            return

        if doctype == "sales_order":
            # Reservation is a submit hook, never a pre-approval side effect.
            # This path runs only once the final approval has been granted.
            from cacao_accounting.ventas import _validate_and_reserve_stock_for_sales_order

            _validate_and_reserve_stock_for_sales_order(document)
            document.docstatus = 1
            log_submit(document)
            return

        if doctype == "delivery_note":
            from cacao_accounting.ventas import _release_reservation_for_delivery_note

            _submit_document_and_refresh_flow(doctype, document)
            _release_reservation_for_delivery_note(document)
            log_submit(document)
            return

        if doctype in {"sales_invoice", "sales_return"}:
            from cacao_accounting.ventas import _create_delivery_note_from_invoice, _persist_sales_reversal_relation

            _submit_document_and_refresh_flow(doctype, document)
            _persist_sales_reversal_relation(document)
            if document.update_inventory and not document.delivery_note_id:
                _create_delivery_note_from_invoice(document)
            log_submit(document)
            return

        if doctype == "purchase_invoice":
            from cacao_accounting.compras import _persist_purchase_reversal_relation

            _submit_document_and_refresh_flow(doctype, document)
            _persist_purchase_reversal_relation(document)
            log_submit(document)
            return

        if doctype in {"purchase_receipt", "payment_entry", "stock_entry"}:
            _submit_document_and_refresh_flow(doctype, document)
            log_submit(document)

    @classmethod
    def _execute_cancel(
        cls,
        doctype: str,
        document: Any,
        user: Any,
        *,
        reason: str | None = None,
        cancellation_date: Any = None,
        requested_at: Any = None,
    ) -> None:
        """Ejecuta de manera segura la cancelacion de un documento con todos sus hooks."""
        if doctype == "journal_entry":
            from cacao_accounting.contabilidad.journal_service import cancel_submitted_journal

            cancel_submitted_journal(
                document.id,
                user_id=user.id,
                reason=reason,
                cancellation_date=cancellation_date,
                requested_at=requested_at,
                commit=False,
            )
            return
        if doctype in _RELATION_ONLY_CANCEL_DOCTYPES:
            _cancel_relation_only_document(doctype, document)
            return
        if doctype in _POSTED_CANCEL_DOCTYPES:
            _cancel_posted_document(
                doctype,
                document,
                reason=reason,
                cancellation_date=cancellation_date,
                requested_at=requested_at,
                actor_user_id=str(user.id),
            )
            return
        if doctype in {"payment_entry", "stock_entry"}:
            _cancel_payment_or_stock(
                doctype,
                document,
                reason=reason,
                cancellation_date=cancellation_date,
                requested_at=requested_at,
                actor_user_id=str(user.id),
            )

    @classmethod
    def reject(cls, document: Any, user: Any, comments: str | None = None) -> None:
        """Rechaza la solicitud de aprobación del documento."""
        company_id = (
            getattr(document, "company", None) or getattr(document, "company_id", None) or getattr(document, "entity", None)
        )
        if not company_id or not cls.is_enabled(company_id):
            return

        doctype = cls._resolve_doctype(document)
        req = database.session.execute(
            select(ApprovalRequest).filter(
                ApprovalRequest.document_id == document.id,
                ApprovalRequest.document_type.in_({doctype, f"cancel_{doctype}"}),
                ApprovalRequest.status.in_({PENDING_APPROVAL_STATUS, PENDING_CANCELLATION_STATUS}),
            )
        ).scalar_one_or_none()
        if not req:
            raise ValueError(_("No existe ninguna solicitud de aprobación para este documento."))

        if req.status not in {PENDING_APPROVAL_STATUS, PENDING_CANCELLATION_STATUS}:
            raise ValueError(_("La solicitud de aprobación no está pendiente."))

        if not cls.can_approve(document, user):
            raise ValueError(_("El usuario no cumple los permisos, límites o independencia requeridos para aprobar."))
        rules = cls._get_user_rules(user.id, company_id, doctype)
        rule = rules[0] if rules else None

        action = ApprovalAction(
            approval_request_id=req.id,
            approved_by=user.id,
            role_id=rule.role_id if rule else None,
            rule_id=rule.id if rule else None,
            limit_allowed=rule.max_amount if rule else None,
            document_amount=cls.get_document_amount(document),
            action="reject",
            comments=comments,
            level=rule.approval_level if rule else req.current_level,
        )
        database.session.add(action)
        from cacao_accounting.internal_control_service import approval_request_transition

        with approval_request_transition(req):
            req.status = "Rejected"
            database.session.flush()
        if req.document_type == doctype:
            from cacao_accounting.document_flow import refresh_source_caches_for_target, revert_relations_for_target

            revert_relations_for_target(doctype, document.id, reason="approval_rejected")
            refresh_source_caches_for_target(doctype, document.id)

    @staticmethod
    def _collect_approvers_from_rules(
        rules: list[ApprovalMatrix],
        amount: Decimal,
    ) -> tuple[list[str], list[str]]:
        """Collect unique role names and user names from matching approval rules."""
        roles: list[str] = []
        users: list[str] = []
        for r in rules:
            if _rule_amount_matches(r, amount):
                _add_approver_from_rule(r, roles, users)
        return sorted(set(roles)), sorted(set(users))

    @classmethod
    def next_approver(cls, document: Any) -> dict[str, list[str]]:
        """Devuelve nombres de roles y usuarios que pueden realizar la siguiente aprobación."""
        company_id = (
            getattr(document, "company", None) or getattr(document, "company_id", None) or getattr(document, "entity", None)
        )
        if not company_id or not cls.is_enabled(company_id):
            return {}

        doctype = cls._resolve_doctype(document)
        req = database.session.execute(
            select(ApprovalRequest).filter(
                ApprovalRequest.document_id == document.id,
                ApprovalRequest.document_type.in_({doctype, f"cancel_{doctype}"}),
                ApprovalRequest.status.in_({PENDING_APPROVAL_STATUS, PENDING_CANCELLATION_STATUS}),
            )
        ).scalar_one_or_none()
        if not req or req.status not in {PENDING_APPROVAL_STATUS, PENDING_CANCELLATION_STATUS}:
            return {}

        amount = cls.get_document_amount(document)
        rules = list(
            database.session.execute(
                select(ApprovalMatrix).filter(
                    ApprovalMatrix.company_id == company_id,
                    ApprovalMatrix.document_type == doctype,
                    ApprovalMatrix.approval_level >= req.current_level,
                    ApprovalMatrix.enabled,
                )
            )
            .scalars()
            .all()
        )

        roles, users = cls._collect_approvers_from_rules(rules, amount)
        return {"roles": roles, "users": users}


def get_model_class(doctype: str) -> Any:
    """Devuelve la clase del modelo correspondiente al doctype."""
    from cacao_accounting.document_flow.registry import get_document_type

    actual_doctype = doctype
    if actual_doctype.startswith("cancel_"):
        actual_doctype = actual_doctype[7:]
    actual_doctype = "journal_entry" if actual_doctype == "comprobante_contable" else actual_doctype
    return get_document_type(actual_doctype).header_model


def _document_company(document: Any) -> str | None:
    """Resolve the company directly or through a bank transaction's account."""
    company = getattr(document, "company", None) or getattr(document, "company_id", None) or getattr(document, "entity", None)
    if not company and ApprovalEngine._resolve_doctype(document) == "bank_transaction":
        from cacao_accounting.database import BankAccount

        bank_account = database.session.get(BankAccount, getattr(document, "bank_account_id", None))
        company = bank_account.company if bank_account is not None else None
    return company


def _execution_key(document: Any, actor_id: str) -> tuple[str, str, str, str]:
    """Bind execution to identity, company and document type as well as its id."""
    company = _document_company(document)
    return str(document.id), actor_id, str(company), ApprovalEngine._resolve_doctype(document)


@contextmanager
def approved_child_execution(parent: Any, child: Any, expected_doctype: str) -> Iterator[None]:
    """Authorize a validated generated child only within its approved parent action."""
    actor = execution_actor(parent.id)
    if actor is None:
        yield
        return
    parent_key = _execution_key(parent, actor)
    child_key = _execution_key(child, actor)
    if _APPROVAL_EXECUTION.get() != parent_key or child_key[2] != parent_key[2] or child_key[3] != expected_doctype:
        raise ValueError(_("El documento generado no corresponde a la operación aprobada."))
    with approved_execution(child, actor):
        yield


@contextmanager
def approved_execution(document: Any, actor_id: str) -> Iterator[None]:
    """Scope execution to a document after its independent review was verified.

    Only trusted approval transitions or their validated generated-document hooks
    may establish this scope; it is not a replacement for authority validation.
    """
    token = _APPROVAL_EXECUTION.set(_execution_key(document, str(actor_id)))
    try:
        yield
    finally:
        _APPROVAL_EXECUTION.reset(token)


def execution_actor(document_id: str) -> str | None:
    """Return the actor only for a document currently executing its approved action."""
    execution = _APPROVAL_EXECUTION.get()
    return execution[1] if execution and execution[0] == str(document_id) else None


def assert_execution_authorized(document: Any, actor_id: str | None = None, *, action: str = "approve") -> None:
    """Enforce Cloud authority and prevent direct independent-review bypasses."""
    if is_desktop_mode():
        return
    from cacao_accounting.internal_control_service import current_audit_actor

    company = _document_company(document)
    actor = actor_id or current_audit_actor()[0]
    if _APPROVAL_EXECUTION.get() == _execution_key(document, str(actor)):
        return
    user = database.session.get(User, actor) if actor else None
    try:
        module = approval_policy.document_module(ApprovalEngine._resolve_doctype(document))
    except KeyError as exc:
        raise ValueError(_("La operación requiere un módulo y un usuario autorizados.")) from exc
    if not user or not approval_policy.authorized(user, str(company or ""), module, action):
        raise ValueError(_("La operación requiere un módulo y un usuario autorizados."))
    pending = ApprovalEngine._pending_request(document)
    snapshot = ApprovalEngine._independent_policy(document, pending)
    if pending is not None or (ApprovalEngine.is_enabled(company) and snapshot):
        raise ValueError(_("La operación debe ejecutarse mediante su aprobación autorizada."))
