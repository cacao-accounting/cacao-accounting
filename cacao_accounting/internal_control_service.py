# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes
"""Transactional Cloud audit and application guards for financial evidence."""

from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
import json
from typing import Any, Iterator, cast

from flask import current_app, has_app_context
from sqlalchemy import and_, event, inspect, or_, select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, object_session
from sqlalchemy.sql.dml import Delete, Insert, Update

from cacao_accounting.audit_trail_service import _current_actor, _json_default
from cacao_accounting.database import AuditTrail, DocBase, database, obtiene_texto_unico
from cacao_accounting.internal_control_sql import raw_sql_mutates_protected_table
from cacao_accounting.i18n import _
from cacao_accounting.runtime_mode import is_cloud_mode, is_desktop_mode

_ACTOR: ContextVar[tuple[str | None, str] | None] = ContextVar("icfr_actor", default=None)
_APPROVAL_TRANSITION: ContextVar[frozenset[int]] = ContextVar("icfr_approval_transition", default=frozenset())
_FLOW_TRANSITION: ContextVar[frozenset[int]] = ContextVar("icfr_flow_transition", default=frozenset())
_BANK_RECONCILIATION_TRANSITION: ContextVar[frozenset[int]] = ContextVar(
    "icfr_bank_reconciliation_transition", default=frozenset()
)
_AUDIT_TRAIL_INSERT_ACTIVE: ContextVar[bool] = ContextVar("icfr_audit_trail_insert_active", default=False)
_ORM_FLUSH_ACTIVE: ContextVar[bool] = ContextVar("icfr_orm_flush_active", default=False)
_POSTED_DOCUMENTS_IN_TRANSACTION = "icfr_posted_documents"
EVIDENCE_TABLES = frozenset({"audit_trail", "approval_action", "audit_log"})
LEDGER_TABLES = frozenset(
    {
        "gl_entry",
        "stock_ledger_entry",
        "ar_ap_ledger_entry",
        "ar_ap_ledger_book_entry",
        "purchase_economic_event",
        "document_transition",
        "exchange_revaluation_item",
    }
)
# Inter-voucher flow evidence: the link, consumed quantities and matching
# results that downstream reports reconcile against the financial ledger.
FLOW_EVIDENCE_TABLES = frozenset(
    {
        "document_relation",
        "purchase_reconciliation",
        "purchase_reconciliation_item",
        "purchase_invoice_receipt_allocation",
        "purchase_receipt_return_allocation",
        "purchase_credit_note_allocation",
    }
)
# Workflow transitions allowed on flow evidence rows; anything else is the
# historical figure of the document flow and stays immutable.
FLOW_EVIDENCE_TRANSITIONS = {
    "document_relation": frozenset(
        {"status", "reversed_at", "reversed_by", "reversal_reason", "cancelled_at", "cancelled_by", "metadata_json"}
    ),
    "purchase_reconciliation": frozenset({"status"}),
    "purchase_reconciliation_item": frozenset({"status"}),
    "purchase_invoice_receipt_allocation": frozenset({"status"}),
    "purchase_receipt_return_allocation": frozenset({"status"}),
    "purchase_credit_note_allocation": frozenset({"status"}),
}
FLOW_PROVIDER_STAMPS = frozenset({"modified", "modified_by"})
SENSITIVE_MODELS = (
    "User",
    "Roles",
    "RolesAccess",
    "RolesUser",
    "UserCompanyAccess",
    "Entity",
    "ApprovalMatrix",
    "ExchangeRate",
    "AccountingPeriod",
    "FiscalYear",
    "Tax",
    "TaxTemplate",
    "TaxTemplateItem",
    "TaxRule",
    "LedgerMappingRule",
    "CompanyDefaultAccount",
    "ItemAccount",
    "PartyAccount",
    "Book",
    "Accounts",
    "PurchaseMatchingConfig",
    "SalesMatchingConfig",
)
# These fields are operational state, never a rewrite of financial evidence.
MUTABLE_STATE = frozenset(
    {
        "status",
        "docstatus",
        "modified",
        "modified_by",
        "version",
        "cancelled_at",
        "cancelled_by",
        "cancel_reason",
        "canceled",
        "canceled_by",
        "is_cancelled",
        "outstanding_amount",
        "base_outstanding_amount",
        "unallocated_amount",
        "base_unallocated_amount",
        "is_superseded",
        "supplier_invoice_key",
        "capitalized_by_id",
        "capitalization_origin_id",
    }
)


@contextmanager
def audit_actor(user_id: str | None, name: str) -> Iterator[None]:
    """Identify a service or automated job for all changes in its transaction."""
    if not name.strip():
        raise ValueError("An audit actor name is required")
    token = _ACTOR.set((user_id, name))
    try:
        yield
    finally:
        _ACTOR.reset(token)


def current_audit_actor() -> tuple[str | None, str | None]:
    """Resolve an explicit actor, authenticated user, or named system process."""
    explicit = _ACTOR.get()
    if explicit is not None:
        return explicit
    authenticated = _current_actor()
    return authenticated if authenticated[0] else (None, "system")


@contextmanager
def approval_request_transition(*requests: Any) -> Iterator[None]:
    """Authorize approval state changes for the supplied request rows only."""
    allowed = _APPROVAL_TRANSITION.get().union(id(request) for request in requests)
    token = _APPROVAL_TRANSITION.set(frozenset(allowed))
    try:
        yield
    finally:
        _APPROVAL_TRANSITION.reset(token)


@contextmanager
def flow_evidence_transition(*rows: Any) -> Iterator[None]:
    """Authorize workflow changes for the supplied evidence rows only."""
    allowed = _FLOW_TRANSITION.get().union(id(row) for row in rows)
    token = _FLOW_TRANSITION.set(frozenset(allowed))
    try:
        yield
    finally:
        _FLOW_TRANSITION.reset(token)


@contextmanager
def bank_reconciliation_transition(*rows: Any) -> Iterator[None]:
    """Authorize reconciliation-link state changes for the supplied bank rows."""
    allowed = _BANK_RECONCILIATION_TRANSITION.get().union(id(row) for row in rows)
    token = _BANK_RECONCILIATION_TRANSITION.set(frozenset(allowed))
    try:
        yield
    finally:
        _BANK_RECONCILIATION_TRANSITION.reset(token)


def _enabled() -> bool:
    """Avoid Cloud checks for Desktop, test runs and engine work outside the app.

    The controls are active in production Cloud. Generic test runs operate with
    production services in process and would otherwise be blocked by the write
    guards during fixture setup or cleanup; the dedicated ICFR suite opts in
    explicitly through the ``INTERNAL_CONTROLS_ENFORCE`` configuration.
    """
    if not has_app_context() or is_desktop_mode():
        return False
    override = current_app.config.get("INTERNAL_CONTROLS_ENFORCE")
    if override is not None:
        return bool(override)
    return is_cloud_mode() and not current_app.config.get("TESTING", False)


def _sensitive(target: Any) -> bool:
    """Select administrative/accounting configuration without collecting secrets."""
    if type(target).__name__ == "CacaoConfig":
        state = inspect(target)
        previous_key = _persisted_value(state, "key", target.key) if state.persistent else target.key
        return any(str(key or "").startswith(_SENSITIVE_CONFIG_PREFIXES) for key in (target.key, previous_key))
    return type(target).__name__ in SENSITIVE_MODELS


def _snapshot(target: Any, *, previous: bool = False) -> dict[str, Any]:
    """Capture mapped scalar values including old values for changed attributes."""
    state = inspect(target)
    result = {}
    for column in state.mapper.columns:
        if type(target).__name__ == "User" and column.key not in {"id", "user", "classification", "active", "company"}:
            continue
        history = state.attrs[column.key].history
        current = getattr(target, column.key)
        if previous and history.deleted:
            result[column.key] = history.deleted[0]
        elif previous and state.persistent and history.has_changes():
            result[column.key] = _persisted_value(state, column.key, current)
        else:
            result[column.key] = current
    return result


def _audited_document(target: Any) -> bool:
    """Include operational documents and the legacy manual journal header."""
    return isinstance(target, DocBase) or target.__table__.name == "comprobante_contable"


def _flow_evidence(target: Any) -> bool:
    """Identify documentary flow rows so their transitions are audited."""
    return target.__table__.name in FLOW_EVIDENCE_TRANSITIONS


def _stamp_preparer(mapper: Any, connection: Any, target: Any) -> None:
    """Persist maker identity before insert or a financial draft modification."""
    del mapper, connection
    if not _enabled() or not _audited_document(target):
        return
    actor_id, _actor_name = current_audit_actor()
    if actor_id is None:
        return
    state = inspect(target)
    if not state.persistent:
        if not target.created_by:
            target.created_by = actor_id
        return
    changed = {attr.key for attr in state.attrs if attr.history.has_changes()}
    if changed.difference(MUTABLE_STATE):
        target.modified_by = actor_id


def _config_company(key: str, before: dict[str, Any] | None) -> str | None:
    """Keep the company scope when an approval configuration key is renamed."""
    for candidate in (key, (before or {}).get("key", "")):
        for prefix in ("approval_engine_enabled_", "approval_require_different_approver_"):
            if candidate.startswith(prefix):
                return candidate.removeprefix(prefix)
    return None


def _write_event(mapper: Any, connection: Any, target: Any, action: str) -> None:
    """Write through the flush connection so evidence shares the business commit."""
    del mapper
    if not _enabled() or not (_sensitive(target) or _audited_document(target) or _flow_evidence(target)):
        return
    before = _snapshot(target, previous=True) if action != "created" else None
    after = _snapshot(target) if action != "deleted" else None
    if before == after:
        return
    actor_id, actor_name = current_audit_actor()
    company = getattr(target, "company", None) or getattr(target, "entity", None) or getattr(target, "company_code", None)
    if type(target).__name__ == "Entity":
        company = target.code
    company = company or getattr(target, "company_id", None)
    if type(target).__name__ == "CacaoConfig":
        company = _config_company(target.key, before)
    before_values = before or {}
    changes = {
        key: {"before": before_values.get(key), "after": after.get(key)}
        for key in before_values
        if after is not None and before_values[key] != after.get(key)
    }
    values: dict[str, Any] = {
        "id": obtiene_texto_unico(),
        "timestamp": None,
    }
    values.update(
        document_type=target.__table__.name,
        document_id=str(target.id),
        document_no=getattr(target, "document_no", None),
        company=company,
        action=action,
        actor_user_id=actor_id,
        actor_name=actor_name,
        source_module="internal_control",
        before_json=json.dumps(before, default=_json_default, ensure_ascii=False) if before else None,
        after_json=json.dumps(after, default=_json_default, ensure_ascii=False) if after else None,
        changes_json=json.dumps(changes, default=_json_default, ensure_ascii=False) if changes else None,
    )
    from cacao_accounting.audit_chain import stamp_audit_values

    stamp_audit_values(connection, values)
    token = _AUDIT_TRAIL_INSERT_ACTIVE.set(True)
    try:
        connection.execute(AuditTrail.__table__.insert().values(**values))
    finally:
        _AUDIT_TRAIL_INSERT_ACTIVE.reset(token)


def _audit_insert(mapper: Any, connection: Any, target: Any) -> None:
    """Record a newly persisted sensitive object."""
    _write_event(mapper, connection, target, "created")


def _audit_update(mapper: Any, connection: Any, target: Any) -> None:
    """Record an updated sensitive object.

    Se emite en ``before_update`` para que el snapshot previo provenga del
    valor almacenado en la transacción (el UPDATE todavía no se ejecutó);
    ``after_update`` ya ve la fila nueva y el "antes" sería indistinguible.
    """
    _write_event(mapper, connection, target, "updated")


def _audit_delete(mapper: Any, connection: Any, target: Any) -> None:
    """Record a deleted assignment or configuration object."""
    _write_event(mapper, connection, target, "deleted")


def _persisted_value(state: Any, key: str, current: Any) -> Any:
    """Read the stored value, falling back to the database when history is unknown.

    After a commit the instance is expired and the default (non-active) history
    does not know the previous value. ``before_flush`` runs before the UPDATE is
    emitted, so the connection still holds the persisted value and the guard can
    tell a real change from an unknown baseline.
    """
    history = state.attrs[key].history
    if history.deleted:
        return history.deleted[0]
    session = state.session
    if session is None or not state.identity:
        return current
    table = state.mapper.local_table
    primary_key = state.mapper.primary_key[0]
    row = session.connection().execute(select(table.c[key]).where(primary_key == state.identity[0])).first()
    return row[0] if row is not None else current


def _posted(target: Any) -> bool:
    """Use persisted posting state, allowing initial document posting."""
    state = inspect(target)
    if not state.persistent:
        return False
    if isinstance(target, DocBase):
        return _persisted_value(state, "docstatus", target.docstatus) in (1, 2)
    if target.__table__.name == "comprobante_contable":
        status = _persisted_value(state, "status", target.status)
        applied_at = _persisted_value(state, "applied", target.applied)
        return bool(applied_at) or status in {"submitted", "cancelled"}
    return False


def _guard_lifecycle(target: Any) -> None:
    """Prevent restoring a posted document to draft to evade financial protection."""
    if not _posted(target):
        return
    if isinstance(target, DocBase) and target.docstatus == 0:
        raise ValueError(_("Los datos financieros posteados son inmutables; use una reversión o ajuste."))
    if target.__table__.name == "comprobante_contable" and target.status == "draft":
        raise ValueError(_("Los datos financieros posteados son inmutables; use una reversión o ajuste."))


def _guard_flush(session: Session, flush_context: Any, instances: Any) -> None:
    """Protect existing evidence and posted document financial values."""
    del flush_context, instances
    if not _enabled():
        return
    _guard_new_lines(session)
    for target in set(session.dirty).union(session.deleted):
        table = target.__table__.name
        changed = {attr.key for attr in inspect(target).attrs if attr.history.has_changes()}
        if table in EVIDENCE_TABLES and (target in session.deleted or changed):
            raise ValueError(_("La evidencia de auditoría es inmutable."))
        _guard_sensitive_delete(table, target in session.deleted)
        _guard_flow_evidence(target, table, changed, target in session.deleted)
        _guard_approval_request(target, table, changed, target in session.deleted)
        _guard_authorized_transition(target, table, changed)
        _guard_lifecycle(target)
        if _posted(target) and (target in session.deleted or changed.difference(MUTABLE_STATE)):
            raise ValueError(_("Los datos financieros posteados son inmutables; use una reversión o ajuste."))
        _guard_line(session, target, changed)


def _is_currently_posted(target: Any) -> bool:
    """Return whether a document is currently in its posted state."""
    if isinstance(target, DocBase):
        return target.docstatus == 1
    return target.__table__.name == "comprobante_contable" and (bool(target.applied) or target.status == "submitted")


def _remember_posted_document(target: Any) -> None:
    """Allow child rows only while their parent is posted in this transaction."""
    session = object_session(target)
    if session is None or not _is_currently_posted(target):
        return
    posted = session.info.setdefault(_POSTED_DOCUMENTS_IN_TRANSACTION, set())
    posted.add((target.__table__.name, str(target.id)))


def _remember_inserted_posted_document(mapper: Any, connection: Any, target: Any) -> None:
    """Remember a document created already posted for its initial atomic write."""
    del mapper, connection
    _remember_posted_document(target)


def _remember_document_posting_transition(mapper: Any, connection: Any, target: Any) -> None:
    """Remember a draft-to-posted transition inside the active transaction."""
    del mapper, connection
    if _is_currently_posted(target) and not _posted(target):
        _remember_posted_document(target)


def _clear_transaction_posted_documents(session: Session, transaction: Any) -> None:
    """Clear posting allowances after the outer database transaction ends."""
    if transaction.parent is None:
        session.info.pop(_POSTED_DOCUMENTS_IN_TRANSACTION, None)


def _posted_in_current_transaction(session: Session, target: Any) -> bool:
    """Return whether this header was created or posted in the active transaction."""
    if not _is_currently_posted(target):
        return False
    posted = session.info.get(_POSTED_DOCUMENTS_IN_TRANSACTION, set())
    return (target.__table__.name, str(target.id)) in posted


def _guard_approval_request(target: Any, table: str, changed: set[str], deleted: bool) -> None:
    """Protect immutable approval evidence fields from ORM changes."""
    if table == "approval_request" and (deleted or changed.intersection(PROTECTED_REQUEST_FIELDS)):
        raise ValueError(_("La evidencia de auditoría es inmutable."))


def _guard_sensitive_delete(table: str, deleted: bool) -> None:
    """Reject ORM deletion of sensitive records while auditing normal updates."""
    if deleted and _is_sensitive_table(table):
        raise ValueError(_("Los cambios sensibles deben realizarse mediante el servicio auditado."))


def _guard_authorized_transition(target: Any, table: str, changed: set[str]) -> None:
    """Require service scopes for approval and document-flow transitions."""
    if table == "approval_request" and changed.intersection({"status", "current_level"}):
        if id(target) not in _APPROVAL_TRANSITION.get():
            raise ValueError(_("Las transiciones requieren el servicio autorizado."))
    if table in FLOW_EVIDENCE_TRANSITIONS and changed.intersection(FLOW_EVIDENCE_TRANSITIONS[table]):
        if id(target) not in _FLOW_TRANSITION.get():
            raise ValueError(_("Las transiciones documentales requieren el servicio autorizado."))


def _guard_flow_evidence(target: Any, table: str, changed: set[str], deleted: bool) -> None:
    """Reject Evidence-field rewrites and deletes of document flow links."""
    transitions = FLOW_EVIDENCE_TRANSITIONS.get(table)
    if transitions is None:
        return
    if deleted or (changed and changed - transitions - FLOW_PROVIDER_STAMPS):
        raise ValueError(_("Los vínculos documentales son inmutables; registre una relación nueva."))
    if table == "document_relation" and "status" in changed:
        previous = _persisted_value(inspect(target), "status", target.status)
        if previous != "active" and target.status == "active":
            raise ValueError(_("Una relación revertida no se reactiva; registre una relación nueva."))


def _guard_new_lines(session: Session) -> None:
    """Reject additional documentary lines after their header is posted."""
    for target in session.new:
        if _audited_document(target):
            continue
        for parent_class, parent_id in _line_parents(target):
            parent = session.get(parent_class, parent_id)
            if parent is None:
                continue
            if not _posted(parent):
                _stamp_line_editor(parent)
                continue
            if _is_posted_advance_reference(target, parent):
                continue
            if _posted_in_current_transaction(session, parent) and target.__table__.name != "payment_reference":
                continue
            raise ValueError(_("Los datos financieros posteados son inmutables; use una reversión o ajuste."))


def _is_posted_advance_reference(target: Any, parent: Any) -> bool:
    """Allow the supported later allocation of a posted advance payment."""
    from cacao_accounting.database import PaymentEntry, PaymentReference

    return (
        isinstance(target, PaymentReference)
        and isinstance(parent, PaymentEntry)
        and parent.docstatus == 1
        and parent.is_advance
    )


def _guard_line(session: Session, target: Any, changed: set[str]) -> None:
    """Protect existing financial lines through their mapped parent foreign key."""
    if _audited_document(target):
        return
    if changed.issubset(MUTABLE_STATE) and target not in session.deleted:
        return
    if (
        target.__table__.name == "bank_transaction"
        and changed
        and changed.issubset({"payment_entry_id", "is_reconciled"})
        and id(target) in _BANK_RECONCILIATION_TRANSITION.get()
    ):
        return
    if target.__table__.name == "bank_transaction":
        if changed.intersection({"payment_entry_id", "is_reconciled"}):
            raise ValueError(_("Los vínculos de conciliación bancaria requieren el servicio autorizado."))
        if target in session.deleted or _has_bank_reconciliation_evidence(session, target):
            raise ValueError(_("Los datos financieros conciliados son inmutables."))
    for parent_class, parent_id in _line_parents(target):
        parent = session.get(parent_class, parent_id)
        if parent is not None and _posted(parent):
            raise ValueError(_("Los datos financieros posteados son inmutables; use una reversión o ajuste."))
        if parent is not None:
            _stamp_line_editor(parent)


def _has_bank_reconciliation_evidence(session: Session, target: Any) -> bool:
    """Check whether an imported bank row has ever been reconciled."""
    if _persisted_value(inspect(target), "is_reconciled", target.is_reconciled):
        return True
    from cacao_accounting.database import ReconciliationItem

    return (
        session.execute(
            select(ReconciliationItem.id)
            .where(
                or_(
                    and_(
                        ReconciliationItem.source_type == "bank_transaction",
                        ReconciliationItem.source_id == target.id,
                    ),
                    and_(
                        ReconciliationItem.reference_type == "bank_transaction",
                        ReconciliationItem.reference_id == target.id,
                    ),
                )
            )
            .limit(1)
        ).scalar_one_or_none()
        is not None
    )


def _stamp_line_editor(parent: Any) -> None:
    """Treat draft financial line changes as edits by the current maker."""
    actor_id, _actor_name = current_audit_actor()
    if actor_id is not None:
        parent.modified_by = actor_id


POLYMORPHIC_EVIDENCE_TABLES = frozenset({"document_tax_summary", "document_tax_line", "landed_cost_allocation"})


def _field_values(target: Any, key: str) -> tuple[Any, ...]:
    """Return current and persisted values for a mapped relationship field."""
    current = getattr(target, key, None)
    state = inspect(target)
    if not state.persistent:
        return (current,)
    persisted = _persisted_value(state, key, current)
    return (current,) if current == persisted else (current, persisted)


def _polymorphic_document_parent(document_type: Any, document_id: Any) -> tuple[Any, str] | None:
    """Resolve a registered polymorphic document identity to its header model."""
    if not document_type or not document_id:
        return None
    from cacao_accounting.document_flow.registry import DOCUMENT_TYPES

    document = DOCUMENT_TYPES.get(str(document_type))
    if document is None:
        return None
    return document.header_model, str(document_id)


def _polymorphic_parents(target: Any) -> Iterator[tuple[Any, str]]:
    """Resolve the document referenced by ``document_type``/``document_id`` without a foreign key."""
    table = target.__table__.name
    if table == "document_tax_line":
        from cacao_accounting.database import DocumentTaxSummary

        session = object_session(target)
        if session is None:
            return
        parents: set[tuple[Any, str]] = set()
        for summary_id in _field_values(target, "document_tax_summary_id"):
            summary = session.get(DocumentTaxSummary, summary_id) if summary_id else None
            if summary is not None:
                parents.update(_polymorphic_parents(summary))
        yield from parents
        return
    elif table not in POLYMORPHIC_EVIDENCE_TABLES:
        return
    document_types = _field_values(target, "document_type")
    document_ids = _field_values(target, "document_id")
    pairs = {(document_types[0], document_ids[0])}
    if len(document_types) > 1 or len(document_ids) > 1:
        pairs.add((document_types[-1], document_ids[-1]))
    for document_type, document_id in pairs:
        parent = _polymorphic_document_parent(document_type, document_id)
        if parent is not None:
            yield parent


def _line_parents(target: Any) -> Iterator[tuple[Any, str]]:
    """Resolve financial headers, including the legacy journal detail link."""
    yield from _polymorphic_parents(target)
    if target.__table__.name == "comprobante_contable_detalle" and target.transaction_id:
        from cacao_accounting.database import ComprobanteContable

        yield ComprobanteContable, target.transaction_id
    for foreign_key in target.__table__.foreign_keys:
        parent_table = cast(Any, foreign_key.column.table)
        parent_cls = next(
            (m.class_ for m in cast(Any, database.Model).registry.mappers if m.local_table is parent_table), None
        )
        if parent_cls is None or not (issubclass(parent_cls, DocBase) or parent_table.name == "comprobante_contable"):
            continue
        for parent_id in _field_values(target, foreign_key.parent.key):
            if parent_id is not None:
                yield parent_cls, parent_id


def _document_parent_tables() -> dict[str, Any]:
    """Return mapped document headers and the legacy accounting journal."""
    return {
        mapper.local_table.name: mapper.local_table
        for mapper in cast(Any, database.Model).registry.mappers
        if issubclass(mapper.class_, DocBase) or mapper.local_table.name == "comprobante_contable"
    }


def _financial_child_tables() -> set[str]:
    """Return mapped tables with a foreign key to a document header."""
    parents = _document_parent_tables()
    return {
        mapper.local_table.name
        for mapper in cast(Any, database.Model).registry.mappers
        if any(key.column.table.name in parents for key in mapper.local_table.foreign_keys)
    }


def _raw_sql_protected_tables() -> set[str]:
    """Collect tables that textual SQL cannot mutate directly."""
    protected = set(EVIDENCE_TABLES).union(
        LEDGER_TABLES,
        FLOW_EVIDENCE_TABLES,
        POLYMORPHIC_EVIDENCE_TABLES,
        _financial_child_tables(),
        {"approval_request", "cacao_config"},
    )
    protected.update(
        mapper.local_table.name
        for mapper in cast(Any, database.Model).registry.mappers
        if mapper.class_.__name__ in SENSITIVE_MODELS or issubclass(mapper.class_, DocBase)
    )
    return protected


def _guard_raw_sql(connection: Any, cursor: Any, statement: str, parameters: Any, context: Any, executemany: Any) -> None:
    """Reject textual writes that cannot participate in mapped evidence controls."""
    del cursor, parameters, executemany
    if not _enabled() or (context.compiled is not None and isinstance(context.compiled.statement, (Insert, Update, Delete))):
        return
    if raw_sql_mutates_protected_table(statement, _raw_sql_protected_tables(), connection.dialect.name):
        raise ValueError(_("Los cambios sensibles deben realizarse mediante el servicio auditado."))


def _guard_bulk(connection: Any, clause: Any, multiparams: Any, params: Any, execution_options: Any) -> None:
    """Reject evidence SQL mutations, including Core and ORM bulk statements."""
    if not _enabled():
        return
    table_name = getattr(getattr(clause, "table", None), "name", None)
    if _is_orm_unit_of_work(execution_options, table_name):
        return
    if isinstance(clause, Insert):
        _guard_bulk_insert(connection, clause, multiparams, params, table_name)
        return
    if not isinstance(clause, (Update, Delete)):
        return
    _guard_bulk_update(connection, clause, multiparams, params, table_name)


def _guard_bulk_insert(connection: Any, clause: Insert, multiparams: Any, params: Any, table_name: str | None) -> None:
    """Protect direct Core inserts to audit, ledger and document tables."""
    if table_name == "audit_trail" and _AUDIT_TRAIL_INSERT_ACTIVE.get():
        return
    protected_tables = EVIDENCE_TABLES.union(
        LEDGER_TABLES,
        FLOW_EVIDENCE_TABLES,
        POLYMORPHIC_EVIDENCE_TABLES,
        {"payment_reference", "approval_request", "cacao_config"},
        _document_parent_tables(),
    )
    if table_name in protected_tables or _is_sensitive_table(table_name):
        raise ValueError(_("Los cambios sensibles deben realizarse mediante el servicio auditado."))
    if table_name in _financial_child_tables():
        _guard_core_financial_insert(connection, clause, multiparams, params)
        return
    if table_name in _raw_sql_protected_tables():
        raise ValueError(_("Los cambios sensibles deben realizarse mediante el servicio auditado."))


def _guard_bulk_update(
    connection: Any, clause: Update | Delete, multiparams: Any, params: Any, table_name: str | None
) -> None:
    """Protect direct Core updates and deletes from rewriting evidence."""
    if table_name == "bank_transaction":
        _guard_bank_transaction_statement(connection, clause, multiparams, params)
    if table_name in POLYMORPHIC_EVIDENCE_TABLES:
        raise ValueError(_("Los cambios sensibles deben realizarse mediante el servicio auditado."))
    if table_name in _financial_child_tables() or table_name in _document_parent_tables():
        _guard_core_financial_write(connection, clause, multiparams, params)
    if table_name in LEDGER_TABLES:
        _guard_ledger_statement(clause, multiparams, params)
    if table_name in FLOW_EVIDENCE_TABLES:
        _guard_flow_evidence_statement(clause, multiparams, params)
    if table_name in EVIDENCE_TABLES:
        raise ValueError(_("La evidencia de auditoría es inmutable."))
    if table_name == "approval_request":
        _guard_approval_request_statement(clause, multiparams, params)
    if table_name == "cacao_config":
        _guard_cacao_config_statement(clause, multiparams, params)
    if _is_sensitive_table(table_name):
        raise ValueError(_("Los cambios sensibles deben realizarse mediante el servicio auditado."))


def _guard_bank_transaction_statement(connection: Any, clause: Any, multiparams: Any, params: Any) -> None:
    """Protect reconciled bank evidence from direct Core or ORM bulk writes."""
    from cacao_accounting.database import ReconciliationItem

    table = clause.table
    if isinstance(clause, Update):
        changed = _statement_changed_values(clause, multiparams, params, table)
        if changed.keys() & {"payment_entry_id", "is_reconciled"}:
            raise ValueError(_("Los vínculos de conciliación bancaria requieren el servicio autorizado."))
    reconciliation_history = (
        select(ReconciliationItem.id)
        .where(
            or_(
                and_(
                    ReconciliationItem.source_type == "bank_transaction",
                    ReconciliationItem.source_id == table.c.id,
                ),
                and_(
                    ReconciliationItem.reference_type == "bank_transaction",
                    ReconciliationItem.reference_id == table.c.id,
                ),
            )
        )
        .exists()
    )
    protected = or_(table.c.is_reconciled.is_(True), reconciliation_history)
    query = select(1).select_from(table).where(*clause._where_criteria, protected).limit(1)
    for parameter_set in _parameter_sets(multiparams, params):
        if connection.execute(query, parameter_set).first() is not None:
            raise ValueError(_("Los datos financieros conciliados son inmutables."))


def _guard_flow_evidence_statement(clause: Any, multiparams: Any, params: Any) -> None:
    """Reject Core rewrites of documentary flow evidence fields."""
    if isinstance(clause, Delete):
        raise ValueError(_("La evidencia del flujo documental no se elimina; use una reversión documental."))
    changed = _statement_changed_values(clause, multiparams, params, clause.table)
    if changed:
        raise ValueError(_("Las transiciones documentales deben realizarse mediante el servicio auditado."))


_SENSITIVE_CONFIG_PREFIXES = ("approval_", "four_eyes_", "fiscal_", "accounting_")


def _guard_cacao_config_statement(clause: Any, multiparams: Any, params: Any) -> None:
    """Reject direct Core rewrites of key/value configuration.

    La identidad de la fila sensible vive en el WHERE, no en las columnas
    mutadas, así que el guard rechaza todo UPDATE Core directo: la
    configuración solo se edita por la ruta ORM auditada (el flush del
    unit-of-work queda exento por _is_orm_unit_of_work).
    """
    del clause, multiparams, params
    raise ValueError(_("Los cambios sensibles deben realizarse mediante el servicio auditado."))


def _statement_changed_values(clause: Any, multiparams: Any, params: Any, table: Any) -> dict[str, Any]:
    """Map the mutated column keys of an Update to their bound values."""
    values = getattr(clause, "_values", None)
    ordered_values = getattr(clause, "_ordered_values", None)
    if ordered_values is not None:
        values = dict(ordered_values)
    if values is not None:
        bound_parameters = {key: value for group in _parameter_sets(multiparams, params) for key, value in group.items()}
        return {getattr(key, "key", key): _bound_value(value, bound_parameters) for key, value in values.items()}
    parameter_sets = _parameter_sets(multiparams, params)
    changed: dict[str, Any] = {}
    for group in parameter_sets:
        if group:
            changed.update({key: value for key, value in group.items() if key in table.c})
    return changed


def _bound_value(value: Any, parameters: dict[str, Any]) -> Any:
    """Resolve a SQLAlchemy bind parameter when its execution value is known."""
    bind_key = getattr(value, "key", None)
    if bind_key in parameters:
        return parameters[bind_key]
    return getattr(value, "value", value)


def _statement_values_for_parameters(clause: Any, parameters: dict[str, Any], table: Any) -> dict[str, Any]:
    """Resolve the changed fields for one Core execution parameter set."""
    values = getattr(clause, "_values", None)
    ordered_values = getattr(clause, "_ordered_values", None)
    if ordered_values is not None:
        values = dict(ordered_values)
    if values is not None:
        return {getattr(key, "key", key): _bound_value(value, parameters) for key, value in values.items()}
    return {key: value for key, value in parameters.items() if key in table.c}


def _parameter_sets(multiparams: Any, params: Any) -> list[dict[str, Any]]:
    """Normalize SQLAlchemy Core parameter forms for guard queries."""
    if isinstance(multiparams, dict):
        return [multiparams]
    if multiparams:
        if not all(isinstance(group, dict) for group in multiparams):
            raise ValueError(_("Los cambios financieros requieren parámetros nombrados."))
        return list(multiparams)
    return [params] if isinstance(params, dict) and params else [{}]


def _guard_core_financial_write(connection: Any, clause: Any, multiparams: Any, params: Any) -> None:
    """Apply posted-parent checks to direct Core updates and deletes."""
    table = clause.table
    parents = _document_parent_tables()
    criterion = _bulk_posted_predicate(table, parents)
    if criterion is None:
        return
    query = select(1).select_from(table).where(*clause._where_criteria, criterion).limit(1)
    foreign_keys = {key.parent.key for key in table.foreign_keys if key.column.table.name in parents}
    for row in _parameter_sets(multiparams, params):
        if isinstance(clause, Update):
            changed = _statement_values_for_parameters(clause, row, table)
            if changed.keys() & foreign_keys:
                raise ValueError(_("Los vínculos financieros deben modificarse mediante el servicio auditado."))
            restores_draft = changed.get("docstatus") == 0 or changed.get("status") == "draft"
            if changed and changed.keys() <= MUTABLE_STATE and not restores_draft:
                continue
        if connection.execute(query, row).first() is not None:
            raise ValueError(_("Los datos financieros posteados son inmutables; use una reversión o ajuste."))


def _normalized_values(values: Any, parameters: dict[str, Any] | None = None) -> dict[str, Any]:
    """Convert Core insert keys and bind parameters to plain column values."""
    supplied = parameters or {}
    return {getattr(key, "key", key): _bound_value(value, supplied) for key, value in (values or {}).items()}


def _core_insert_rows(clause: Any, multiparams: Any, params: Any) -> list[dict[str, Any]]:
    """Extract literal INSERT rows needed to check their document parents."""
    inline_values = getattr(clause, "_values", None)
    parameter_sets = _parameter_sets(multiparams, params)
    rows = _multi_value_insert_rows(clause, inline_values, parameter_sets)
    if rows:
        return rows
    return _single_value_insert_rows(clause, inline_values, parameter_sets)


def _multi_value_insert_rows(clause: Any, inline_values: Any, parameter_sets: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Resolve SQLAlchemy INSERT statements with multiple inline rows."""
    rows: list[dict[str, Any]] = []
    for group in getattr(clause, "_multi_values", ()) or ():
        entries = group if isinstance(group, (list, tuple)) else (group,)
        for entry in entries:
            rows.extend(
                _merge_insert_values(inline_values, entry, parameter_set, clause.table) for parameter_set in parameter_sets
            )
    return rows


def _single_value_insert_rows(clause: Any, inline_values: Any, parameter_sets: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Resolve SQLAlchemy INSERT statements with execution-time row values."""
    rows = []
    for parameter_set in parameter_sets:
        values = _merge_insert_values(inline_values, None, parameter_set, clause.table)
        if values:
            rows.append(values)
    return rows


def _merge_insert_values(inline_values: Any, row_values: Any, parameters: dict[str, Any], table: Any) -> dict[str, Any]:
    """Merge inline and execution-time values for one inserted row."""
    values = _normalized_values(inline_values, parameters)
    values.update(_normalized_values(row_values, parameters))
    values.update({key: value for key, value in parameters.items() if key in table.c})
    return values


def _parent_is_posted(connection: Any, table: Any, parent_id: str) -> bool:
    """Check persisted document lifecycle state for a Core INSERT parent."""
    if "docstatus" in table.c:
        row = connection.execute(select(table.c.docstatus).where(table.c.id == parent_id)).first()
        return row is not None and row[0] in (1, 2)
    row = connection.execute(select(table.c.status, table.c.applied).where(table.c.id == parent_id)).first()
    return row is not None and (bool(row.applied) or row.status in {"submitted", "cancelled"})


def _guard_core_financial_insert(connection: Any, clause: Any, multiparams: Any, params: Any) -> None:
    """Reject Core inserts that append children to posted documents."""
    parents = _document_parent_tables()
    rows = _core_insert_rows(clause, multiparams, params)
    if not rows:
        raise ValueError(_("Las líneas financieras deben registrarse mediante el servicio auditado."))
    for row in rows:
        _guard_core_insert_row(connection, clause.table, row, parents)


def _guard_core_insert_row(connection: Any, table: Any, row: dict[str, Any], parents: dict[str, Any]) -> None:
    """Reject a single Core INSERT row linked to posted financial evidence."""
    for foreign_key in table.foreign_keys:
        parent_table = foreign_key.column.table
        if parent_table.name not in parents:
            continue
        parent_id = row.get(foreign_key.parent.key)
        if parent_id is None:
            if not foreign_key.parent.nullable:
                raise ValueError(_("Las líneas financieras deben registrarse mediante el servicio auditado."))
            continue
        if not isinstance(parent_id, str):
            raise ValueError(_("Las líneas financieras deben registrarse mediante el servicio auditado."))
        if not _parent_is_posted(connection, parent_table, parent_id):
            continue
        raise ValueError(_("Los datos financieros posteados son inmutables; use una reversión o ajuste."))


def _guard_ledger_statement(clause: Any, multiparams: Any, params: Any) -> None:
    """Mirror the existing ledger mapper rule for Core and ORM SQL statements."""
    if isinstance(clause, Delete):
        raise ValueError(_("Las líneas del ledger no se pueden eliminar; use una reversa."))
    changed = _statement_changed_values(clause, multiparams, params, clause.table)
    if not changed:
        raise ValueError(_("Las líneas del ledger son inmutables; use una reversa append-only."))
    if {key for key in changed if key != "is_cancelled"}:
        raise ValueError(_("Las líneas del ledger son inmutables; use una reversa append-only."))
    if not changed["is_cancelled"]:
        raise ValueError(_("Una línea del ledger cancelada no se reactiva; registre una nueva línea."))


PROTECTED_REQUEST_FIELDS = frozenset(
    {
        "policy_snapshot",
        "review_payload",
        "requested_by",
        "company_id",
        "document_id",
        "document_type",
        "required_level",
        "created_at",
        "cancellation_date",
        "cancellation_reason",
    }
)


def _guard_approval_request_statement(clause: Any, multiparams: Any, params: Any) -> None:
    """Reject Core rewrites of approval provenance while allowing lifecycle moves."""
    if isinstance(clause, Delete):
        raise ValueError(_("La evidencia de auditoría es inmutable."))
    changed = _statement_changed_values(clause, multiparams, params, clause.table)
    if changed and changed.keys() & PROTECTED_REQUEST_FIELDS:
        raise ValueError(_("La evidencia de auditoría es inmutable."))
    if changed:
        raise ValueError(_("Las transiciones de aprobación deben realizarse mediante el servicio autorizado."))


def _is_sensitive_table(table_name: Any) -> bool:
    """Return whether a table belongs to a sensitive mapped model."""
    if not isinstance(table_name, str):
        return False
    return any(
        mapper.local_table.name == table_name and mapper.class_.__name__ in SENSITIVE_MODELS
        for mapper in cast(Any, database.Model).registry.mappers
    )


def _is_orm_unit_of_work(execution_options: Any, table_name: Any) -> bool:
    """Allow only flush SQL carrying the mapped table's internal statement cache."""
    if not _ORM_FLUSH_ACTIVE.get() or not isinstance(table_name, str):
        return False
    compiled_cache = execution_options.get("compiled_cache")
    if compiled_cache is None:
        return False
    return any(
        mapper.local_table.name == table_name and mapper.base_mapper._compiled_cache is compiled_cache
        for mapper in cast(Any, database.Model).registry.mappers
    )


def _posting_predicate(table: Any) -> Any:
    """Use lifecycle state for modern documents and application for legacy journals."""
    if "docstatus" in table.c:
        return table.c.docstatus.in_([1, 2])
    return or_(table.c.applied.is_not(None), table.c.status.in_(["submitted", "cancelled"]))


def _bulk_posted_predicate(table: Any, parents: dict[str, Any]) -> Any:
    """Build a posted-parent predicate for document headers or linked evidence."""
    parent = parents.get(table.name)
    if parent is not None:
        return _posting_predicate(parent)
    predicates = []
    if table.name == "comprobante_contable_detalle":
        parent = parents.get("comprobante_contable")
        if parent is not None:
            predicates.append(table.c.transaction_id.in_(select(parent.c.id).where(_posting_predicate(parent))))
    for key in table.foreign_keys:
        if key.column.table.name in parents:
            predicates.append(key.parent.in_(select(key.column).where(_posting_predicate(key.column.table))))
    return or_(*predicates) if predicates else None


def _guard_financial_bulk(state: Any) -> None:
    """Check persisted parents before allowing a bulk financial document write."""
    statement = state.statement
    table = getattr(statement, "table", None)
    if table is None:
        return
    values = getattr(statement, "_values", None) or {}
    changed = {getattr(key, "key", key) for key in values}
    payload = {getattr(key, "key", key): getattr(value, "value", None) for key, value in values.items()}
    restores_draft = payload.get("docstatus") == 0 or payload.get("status") == "draft"
    if state.is_update and changed and changed.issubset(MUTABLE_STATE) and not restores_draft:
        return
    parents = {
        mapper.local_table.name: mapper.local_table
        for mapper in cast(Any, database.Model).registry.mappers
        if issubclass(mapper.class_, DocBase) or mapper.local_table.name == "comprobante_contable"
    }
    criterion = _bulk_posted_predicate(table, parents)
    if criterion is None:
        return
    query = select(table).where(*statement._where_criteria, criterion).limit(1)
    if state.session.connection().execute(query, state.parameters or {}).first() is not None:
        raise ValueError(_("Los datos financieros posteados son inmutables; use una reversión o ajuste."))


def _guard_sensitive_bulk(state: Any) -> None:
    """Require ORM objects for configuration changes so snapshots cannot be skipped."""
    if not _enabled() or not (state.is_update or state.is_delete):
        return
    table = getattr(state.statement, "table", None)
    sensitive_tables = {
        mapper.local_table.name
        for mapper in cast(Any, database.Model).registry.mappers
        if mapper.class_.__name__ in SENSITIVE_MODELS
    }
    if table is not None and table.name == "approval_request":
        raise ValueError(_("La evidencia de auditoría es inmutable."))
    if table is not None and table.name in sensitive_tables:
        raise ValueError(_("Los cambios sensibles deben realizarse mediante el servicio auditado."))
    _guard_financial_bulk(state)


def _stamp_audit_chain(mapper: Any, connection: Any, target: Any) -> None:
    """Attach the audit hash chain to ORM rows in both desktop and cloud."""
    del mapper
    from cacao_accounting.audit_chain import stamp_audit_entry

    stamp_audit_entry(connection, target)


def _chain_audit_flush(session: Session, flush_context: Any, instances: Any) -> None:
    """Chain pending audit rows at flush start, in both desktop and cloud."""
    del flush_context, instances
    from cacao_accounting.audit_chain import chain_pending_rows

    chain_pending_rows(session)


def _start_orm_flush(session: Session, flush_context: Any, instances: Any) -> None:
    """Mark ORM unit-of-work SQL so Core guards can distinguish it from direct writes."""
    del session, flush_context, instances
    _ORM_FLUSH_ACTIVE.set(True)


def _end_orm_flush(session: Session, flush_context: Any) -> None:
    """Clear the ORM unit-of-work marker after successful or failed flushes."""
    del session, flush_context
    _ORM_FLUSH_ACTIVE.set(False)


def register_internal_controls() -> None:
    """Install idempotent shared listeners once, independent of app instances."""
    if event.contains(Session, "before_flush", _guard_flush):
        return
    event.listen(Session, "before_flush", _guard_flush)
    event.listen(Session, "before_flush", _chain_audit_flush)
    event.listen(Session, "before_flush", _start_orm_flush)
    event.listen(Session, "after_flush_postexec", _end_orm_flush)
    event.listen(Session, "after_soft_rollback", _end_orm_flush)
    event.listen(Session, "after_transaction_end", _clear_transaction_posted_documents)
    event.listen(Session, "do_orm_execute", _guard_sensitive_bulk)
    event.listen(Engine, "before_execute", _guard_bulk)
    event.listen(Engine, "before_cursor_execute", _guard_raw_sql)
    event.listen(AuditTrail, "before_insert", _stamp_audit_chain)
    for mapper in cast(Any, database.Model).registry.mappers:
        model = mapper.class_
        if issubclass(model, DocBase) or mapper.local_table.name == "comprobante_contable":
            event.listen(model, "after_insert", _remember_inserted_posted_document)
            event.listen(model, "before_update", _remember_document_posting_transition)
        event.listen(model, "before_insert", _stamp_preparer)
        event.listen(model, "before_update", _stamp_preparer)
        event.listen(model, "before_update", _audit_update)
        event.listen(model, "after_insert", _audit_insert)
        event.listen(model, "after_delete", _audit_delete)
