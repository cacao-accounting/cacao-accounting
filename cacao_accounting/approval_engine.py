# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Approval Engine (Motor de Aprobaciones) configurable por compañía."""

from __future__ import annotations

import hashlib
import json
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
from cacao_accounting.document_flow.registry import normalize_doctype

PENDING_APPROVAL_STATUS = "Pending Approval"
PENDING_CANCELLATION_STATUS = "Pending Cancellation"


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

    @classmethod
    def handle_submission(cls, document: Any, user: Any, label: str = "Documento") -> bool:
        """Maneja el flujo completo de aprobación al enviar un documento.

        Retorna True si el motor procesó la solicitud (el caller debe redirigir).
        Retorna False si el motor no está activo o no cubre el monto (el caller
        debe proceder con el submit normal).
        """
        from flask import flash as flask_flash

        company_id = getattr(document, "company", None) or getattr(document, "company_id", None)
        if not company_id or not cls.is_enabled(company_id):
            return False

        req = cls.request_approval(document)
        if not req:
            flask_flash(
                "No existe una regla de aprobación que cubra este monto. El documento permanece en borrador.",
                "warning",
            )
            database.session.commit()
            return True

        if cls.can_approve(document, user):
            cls.approve(document, user, "Aprobado por el remitente")
            flask_flash(f"{label} aprobada.", "success")
        else:
            database.session.commit()
            flask_flash(
                f"{label} enviada para aprobación (Pendiente de Aprobación).",
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
        serialized = json.dumps(payload, default=str, ensure_ascii=False, sort_keys=True)
        return payload, hashlib.sha256(serialized.encode("utf-8")).hexdigest()

    @staticmethod
    def _get_user_rules(user_id: str, company_id: str, document_type: str) -> list[ApprovalMatrix]:
        """Obtiene las reglas de matriz aplicables al usuario con su prioridad."""
        # 1. Reglas específicas por usuario
        rules = list(
            database.session.execute(
                select(ApprovalMatrix).filter_by(
                    company_id=company_id,
                    document_type=document_type,
                    user_id=user_id,
                    enabled=True,
                )
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
                select(ApprovalMatrix).filter(
                    ApprovalMatrix.company_id == company_id,
                    ApprovalMatrix.document_type == document_type,
                    ApprovalMatrix.role_id.in_(role_ids),
                    ApprovalMatrix.user_id.is_(None),
                    ApprovalMatrix.enabled,
                )
            )
            .scalars()
            .all()
        )
        return rules

    @classmethod
    def can_approve(cls, document: Any, user: Any) -> bool:
        """Verifica si el usuario tiene autorización para aprobar el documento."""
        company_id = getattr(document, "company", None) or getattr(document, "company_id", None)
        if not company_id:
            return True
        if not cls.is_enabled(company_id):
            return True

        if getattr(user, "classification", None) == "admin":
            return True

        amount = cls.get_document_amount(document)
        document_type = cls._resolve_doctype(document)

        rules = cls._get_user_rules(user.id, company_id, document_type)
        for rule in rules:
            max_amt = rule.max_amount
            if rule.min_amount <= amount and (max_amt is None or max_amt >= amount):
                return True
        return False

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
                _, actual_hash = ApprovalEngine._approval_snapshot(document)
                if actual_hash != expected_hash:
                    raise ValueError("El documento cambió después de solicitar aprobación; debe enviarse nuevamente.")
                return
        requested_at = getattr(req, "created_at", None)
        modified_at = getattr(document, "modified", None)
        if requested_at and modified_at and modified_at > requested_at:
            raise ValueError("El documento cambió después de solicitar aprobación; debe enviarse nuevamente.")

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
            raise ValueError("El documento tiene una solicitud de aprobación pendiente y no puede editarse.")

    @staticmethod
    def _validate_final_cancellation(doctype: str, document: Any) -> None:
        """Recheck downstream dependencies at the moment cancellation executes."""
        if doctype in {"sales_order", "delivery_note", "sales_invoice", "purchase_order", "purchase_receipt"}:
            from cacao_accounting.document_flow.repository import has_active_source_relations

            if has_active_source_relations(doctype, document.id):
                raise ValueError("El documento adquirió relaciones activas mientras esperaba aprobación.")
        if doctype == "purchase_invoice":
            from cacao_accounting.database import DocumentRelation, PaymentEntry, PaymentReference

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
                raise ValueError("La factura adquirió una aplicación de pago activa mientras esperaba aprobación.")

    @staticmethod
    def _validate_final_submission(doctype: str, document: Any) -> None:
        """Repeat common document prerequisites immediately before submit."""
        from cacao_accounting.document_flow.validation import validate_submit_prerequisites
        from cacao_accounting.database import (
            DeliveryNoteItem,
            PurchaseInvoiceItem,
            PurchaseReceiptItem,
            SalesInvoiceItem,
            SalesOrderItem,
            StockEntryItem,
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
            "sales_order": (SalesOrderItem, "sales_order_id"),
            "delivery_note": (DeliveryNoteItem, "delivery_note_id"),
            "sales_invoice": (SalesInvoiceItem, "sales_invoice_id"),
            "purchase_receipt": (PurchaseReceiptItem, "purchase_receipt_id"),
            "purchase_invoice": (PurchaseInvoiceItem, "purchase_invoice_id"),
            "stock_entry": (StockEntryItem, "stock_entry_id"),
        }
        if doctype not in item_models:
            return
        item_model, foreign_key = item_models[doctype]
        items = db.session.execute(db.select(item_model).filter_by(**{foreign_key: document.id})).scalars().all()
        validate_submit_prerequisites(
            document,
            items=items,
            require_party=doctype not in {"stock_entry", "delivery_note"},
            require_rate_positive=doctype not in {"delivery_note", "stock_entry"},
            require_amount_nonzero=doctype in {"sales_invoice", "purchase_invoice"},
            require_warehouse=doctype in {"delivery_note", "sales_invoice", "purchase_receipt", "stock_entry"},
        )
        if doctype == "sales_order" and not getattr(document, "is_return", False):
            from cacao_accounting.ventas import _validate_credit_limit_and_overdue

            _validate_credit_limit_and_overdue(document.company, document.customer_id, document.grand_total or Decimal("0"))
        elif doctype == "sales_invoice":
            from cacao_accounting.ventas import (
                _validate_credit_limit_and_overdue,
                _validate_invoice_prices_against_source,
                _validate_sales_invoice_quantities,
            )

            if not getattr(document, "is_return", False):
                _validate_credit_limit_and_overdue(
                    document.company, document.customer_id, document.grand_total or Decimal("0")
                )
            _validate_sales_invoice_quantities(document.id)
            _validate_invoice_prices_against_source(document)
        elif doctype == "purchase_invoice":
            from cacao_accounting.compras import (
                _validate_duplicate_supplier_invoice,
                _validate_invoice_requires_supplier_link,
                _validate_invoice_quantities_against_receipt,
                _validate_supplier_invoice_flags,
            )

            _validate_invoice_quantities_against_receipt(document.id)
            _validate_invoice_requires_supplier_link(document.id)
            _validate_supplier_invoice_flags(
                document.supplier_id,
                document.company,
                document.purchase_order_id,
                document.purchase_receipt_id,
            )
            _validate_duplicate_supplier_invoice(
                document.supplier_id,
                document.supplier_invoice_no,
                exclude_id=document.id,
            )

    @classmethod
    def request_approval(cls, document: Any) -> ApprovalRequest | None:
        """Crea una solicitud de aprobación para el documento si no existe."""
        company_id = getattr(document, "company", None) or getattr(document, "company_id", None)
        if not company_id or not cls.is_enabled(company_id):
            return None

        doctype = cls._resolve_doctype(document)
        amount = cls.get_document_amount(document)

        req = database.session.execute(
            select(ApprovalRequest).filter_by(document_type=doctype, document_id=document.id)
        ).scalar_one_or_none()
        if req:
            return req

        req_level = cls._get_required_level(company_id, doctype, amount)
        if req_level == 0:
            return None
        user_id = getattr(current_user, "id", None) or getattr(document, "user_id", None) or "system"

        req = ApprovalRequest(
            document_type=doctype,
            document_id=document.id,
            company_id=company_id,
            requested_by=user_id,
            current_level=1,
            required_level=req_level,
            status=PENDING_APPROVAL_STATUS,
        )
        database.session.add(req)
        database.session.flush()
        from cacao_accounting.audit_trail_service import log_approval_requested

        snapshot, snapshot_hash = cls._approval_snapshot(document)
        log_approval_requested(document, snapshot, snapshot_hash)
        return req

    @classmethod
    def request_cancellation(cls, document: Any) -> ApprovalRequest | None:
        """Crea una solicitud de cancelación para el documento si no existe."""
        company_id = getattr(document, "company", None) or getattr(document, "company_id", None)
        if not company_id or not cls.is_enabled(company_id):
            return None

        base_doctype = cls._resolve_doctype(document)
        doctype = f"cancel_{base_doctype}"
        amount = cls.get_document_amount(document)

        req = database.session.execute(
            select(ApprovalRequest).filter_by(document_type=doctype, document_id=document.id)
        ).scalar_one_or_none()
        if req:
            return req

        req_level = cls._get_required_level(company_id, base_doctype, amount)
        if req_level == 0:
            return None
        user_id = getattr(current_user, "id", None) or getattr(document, "user_id", None) or "system"

        req = ApprovalRequest(
            document_type=doctype,
            document_id=document.id,
            company_id=company_id,
            requested_by=user_id,
            current_level=1,
            required_level=req_level,
            status=PENDING_CANCELLATION_STATUS,
        )
        database.session.add(req)
        database.session.flush()
        from cacao_accounting.audit_trail_service import log_approval_requested

        snapshot, snapshot_hash = cls._approval_snapshot(document)
        log_approval_requested(document, snapshot, snapshot_hash, cancellation=True)
        return req

    @staticmethod
    def _find_applicable_rule(
        rules: list[ApprovalMatrix],
        amount: Decimal,
        user: Any,
        req_level: int,
    ) -> ApprovalMatrix | None:
        """Find the first rule covering the given amount, or fallback for admin users."""
        for r in rules:
            if r.min_amount <= amount and (r.max_amount is None or r.max_amount >= amount):
                return r

        if getattr(user, "classification", None) == "admin":
            return ApprovalMatrix(
                approval_level=req_level,
                max_amount=amount,
                enabled=True,
            )
        return None

    @classmethod
    def _finalize_approval(cls, req: ApprovalRequest, document: Any, user: Any) -> bool:
        """Mark request as approved and execute submit or cancel. Returns True if fully approved."""
        if req.document_type.startswith("cancel_"):
            actual_doc_type = req.document_type[7:]
            actual_doc = database.session.get(get_model_class(actual_doc_type), req.document_id)
            cls._validate_final_cancellation(actual_doc_type, actual_doc)
            cls._execute_cancel(actual_doc_type, actual_doc, user)
        else:
            cls._execute_submit(req.document_type, document, user)
        database.session.flush()
        return True

    @classmethod
    def approve(cls, document: Any, user: Any, comments: str | None = None) -> bool:
        """Aprueba el documento para el nivel actual."""
        company_id = getattr(document, "company", None) or getattr(document, "company_id", None)
        if not company_id or not cls.is_enabled(company_id):
            return True

        doctype = cls._resolve_doctype(document)
        amount = cls.get_document_amount(document)

        req = database.session.execute(
            select(ApprovalRequest).filter(
                ApprovalRequest.document_id == document.id,
                ApprovalRequest.document_type.in_({doctype, f"cancel_{doctype}"}),
                ApprovalRequest.status.in_({PENDING_APPROVAL_STATUS, PENDING_CANCELLATION_STATUS}),
            )
        ).scalar_one_or_none()
        if not req:
            req = cls.request_approval(document)
            if not req:
                return True

        if req.status == "Approved":
            return True
        if req.status not in {PENDING_APPROVAL_STATUS, PENDING_CANCELLATION_STATUS}:
            raise ValueError("La solicitud de aprobación no está en estado pendiente.")

        cls._assert_approval_snapshot(req, document)

        rules = cls._get_user_rules(user.id, company_id, doctype)
        applicable_rule = cls._find_applicable_rule(rules, amount, user, req.required_level)
        if not applicable_rule:
            raise ValueError("El usuario no tiene límites autorizados suficientes para aprobar este documento.")

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
            req.status = "Approved"
            return cls._finalize_approval(req, document, user)

        req.current_level = applicable_rule.approval_level + 1
        database.session.flush()
        return False

    @classmethod
    def _execute_submit(cls, doctype: str, document: Any, user: Any) -> None:
        """Ejecuta de manera segura la submision de un documento con todos sus hooks."""
        from cacao_accounting.contabilidad.posting import submit_document
        from cacao_accounting.audit_trail_service import log_submit

        cls._validate_final_submission(doctype, document)

        if doctype == "journal_entry":
            from cacao_accounting.contabilidad.journal_service import submit_journal

            submit_journal(document.id)
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

            submit_document(document)
            _release_reservation_for_delivery_note(document)
            log_submit(document)
            return

        if doctype == "sales_invoice":
            from cacao_accounting.ventas import _create_delivery_note_from_invoice

            submit_document(document)
            if document.update_inventory and not document.delivery_note_id:
                _create_delivery_note_from_invoice(document)
            log_submit(document)
            return

        if doctype in {"purchase_receipt", "purchase_invoice", "payment_entry", "stock_entry"}:
            submit_document(document)
            log_submit(document)

    @classmethod
    def _execute_cancel(cls, doctype: str, document: Any, user: Any) -> None:
        """Ejecuta de manera segura la cancelacion de un documento con todos sus hooks."""
        from cacao_accounting.contabilidad.posting import cancel_document
        from cacao_accounting.audit_trail_service import log_cancel
        from cacao_accounting.document_flow import revert_relations_for_target, refresh_source_caches_for_target

        if doctype == "journal_entry":
            from cacao_accounting.contabilidad.journal_service import cancel_submitted_journal

            cancel_submitted_journal(document.id, user_id=user.id)
            return

        if doctype in {
            "purchase_request",
            "purchase_quotation",
            "supplier_quotation",
            "purchase_order",
            "sales_request",
            "sales_quotation",
            "sales_order",
        }:
            if doctype == "sales_order":
                from cacao_accounting.ventas import _release_reservation_for_sales_order

                _release_reservation_for_sales_order(document)
            document.docstatus = 2
            log_cancel(document)
            revert_relations_for_target(doctype, document.id)
            refresh_source_caches_for_target(doctype, document.id)
            return

        if doctype in {"purchase_receipt", "purchase_invoice", "delivery_note", "sales_invoice"}:
            if doctype == "delivery_note":
                from cacao_accounting.ventas import _restore_reservation_for_delivery_note

                _restore_reservation_for_delivery_note(document)
            elif doctype == "sales_invoice":
                from cacao_accounting.ventas import _cancel_linked_delivery_note

                _cancel_linked_delivery_note(document)
            cancel_document(document)
            log_cancel(document)
            revert_relations_for_target(doctype, document.id)
            refresh_source_caches_for_target(doctype, document.id)
            return

        if doctype in {"payment_entry", "stock_entry"}:
            cancel_document(document)
            if doctype == "payment_entry":
                from cacao_accounting.bancos import _apply_payment_cancellation_hooks

                _apply_payment_cancellation_hooks(document)
            log_cancel(document)

    @classmethod
    def reject(cls, document: Any, user: Any, comments: str | None = None) -> None:
        """Rechaza la solicitud de aprobación del documento."""
        company_id = getattr(document, "company", None) or getattr(document, "company_id", None)
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
            raise ValueError("No existe ninguna solicitud de aprobación para este documento.")

        if req.status not in {PENDING_APPROVAL_STATUS, PENDING_CANCELLATION_STATUS}:
            raise ValueError("La solicitud de aprobación no está pendiente.")

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
        req.status = "Rejected"
        database.session.flush()

    @staticmethod
    def _collect_approvers_from_rules(
        rules: list[ApprovalMatrix],
        amount: Decimal,
    ) -> tuple[list[str], list[str]]:
        """Collect unique role names and user names from matching approval rules."""
        roles: list[str] = []
        users: list[str] = []
        for r in rules:
            if not r.min_amount <= amount or (r.max_amount is not None and r.max_amount < amount):
                continue
            if r.user_id:
                user = database.session.get(User, r.user_id)
                if user and user.name:
                    users.append(user.name)
                continue
            if r.role_id:
                from cacao_accounting.database import Roles

                role = database.session.get(Roles, r.role_id)
                if role:
                    roles.append(role.note or role.name)
        return list(set(roles)), list(set(users))

    @classmethod
    def next_approver(cls, document: Any) -> dict[str, list[str]]:
        """Devuelve nombres de roles y usuarios que pueden realizar la siguiente aprobación."""
        company_id = getattr(document, "company", None) or getattr(document, "company_id", None)
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
