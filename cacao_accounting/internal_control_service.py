# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes
"""Transactional Cloud audit and application guards for financial evidence."""

from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
import json
import re
from typing import Any, Iterator, cast

from flask import current_app, has_app_context
from sqlalchemy import event, inspect, select, or_
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session
from sqlalchemy.sql.dml import Delete, Update

from cacao_accounting.audit_trail_service import _current_actor, _json_default
from cacao_accounting.database import AuditTrail, DocBase, database, obtiene_texto_unico
from cacao_accounting.i18n import _
from cacao_accounting.runtime_mode import is_cloud_mode, is_desktop_mode

_ACTOR: ContextVar[tuple[str | None, str] | None] = ContextVar("icfr_actor", default=None)
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
        key = str(target.key or "")
        return key.startswith(("approval_", "four_eyes_", "fiscal_", "accounting_"))
    return type(target).__name__ in SENSITIVE_MODELS


def _snapshot(target: Any, *, previous: bool = False) -> dict[str, Any]:
    """Capture mapped scalar values including old values for changed attributes."""
    state = inspect(target)
    result = {}
    for column in state.mapper.columns:
        if type(target).__name__ == "User" and column.key not in {"id", "user", "classification", "active", "company"}:
            continue
        history = state.attrs[column.key].history
        result[column.key] = history.deleted[0] if previous and history.deleted else getattr(target, column.key)
    return result


def _audited_document(target: Any) -> bool:
    """Include operational documents and the legacy manual journal header."""
    return isinstance(target, DocBase) or target.__table__.name == "comprobante_contable"


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


def _write_event(mapper: Any, connection: Any, target: Any, action: str) -> None:
    """Write through the flush connection so evidence shares the business commit."""
    del mapper
    if not _enabled() or not (_sensitive(target) or _audited_document(target)):
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
        for prefix in ("approval_engine_enabled_", "approval_require_different_approver_"):
            if target.key.startswith(prefix):
                company = target.key.removeprefix(prefix)
                break
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
    connection.execute(AuditTrail.__table__.insert().values(**values))


def _audit_insert(mapper: Any, connection: Any, target: Any) -> None:
    """Record a newly persisted sensitive object."""
    _write_event(mapper, connection, target, "created")


def _audit_update(mapper: Any, connection: Any, target: Any) -> None:
    """Record an updated sensitive object."""
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
        if table == "approval_request" and (
            target in session.deleted
            or changed.intersection(
                {
                    "policy_snapshot",
                    "review_payload",
                    "requested_by",
                    "company_id",
                    "document_id",
                    "document_type",
                    "required_level",
                    "created_at",
                }
            )
        ):
            raise ValueError(_("La evidencia de auditoría es inmutable."))
        _guard_lifecycle(target)
        if _posted(target) and (target in session.deleted or changed.difference(MUTABLE_STATE)):
            raise ValueError(_("Los datos financieros posteados son inmutables; use una reversión o ajuste."))
        _guard_line(session, target, changed)


def _guard_new_lines(session: Session) -> None:
    """Reject additional documentary lines after their header has ledger evidence."""
    from cacao_accounting.database import GLEntry, StockLedgerEntry

    for target in session.new:
        if _audited_document(target) or not type(target).__name__.endswith(("Item", "Detalle")):
            continue
        for parent_class, parent_id in _line_parents(target):
            parent = session.get(parent_class, parent_id)
            if parent is None:
                continue
            if not _posted(parent):
                _stamp_line_editor(parent)
                continue
            for ledger in (GLEntry, StockLedgerEntry):
                query = select(ledger.id).where(ledger.voucher_id == parent_id).limit(1)
                if session.connection().execute(query).first() is not None:
                    raise ValueError(_("Los datos financieros posteados son inmutables; use una reversión o ajuste."))


def _guard_line(session: Session, target: Any, changed: set[str]) -> None:
    """Protect existing financial lines through their mapped parent foreign key."""
    if _audited_document(target) or not type(target).__name__.endswith(("Item", "Reference", "Detalle")):
        return
    if changed.issubset(MUTABLE_STATE) and target not in session.deleted:
        return
    for parent_class, parent_id in _line_parents(target):
        parent = session.get(parent_class, parent_id)
        if parent is not None and _posted(parent):
            raise ValueError(_("Los datos financieros posteados son inmutables; use una reversión o ajuste."))
        if parent is not None:
            _stamp_line_editor(parent)


def _stamp_line_editor(parent: Any) -> None:
    """Treat draft financial line changes as edits by the current maker."""
    actor_id, _actor_name = current_audit_actor()
    if actor_id is not None:
        parent.modified_by = actor_id


def _line_parents(target: Any) -> Iterator[tuple[Any, str]]:
    """Resolve financial headers, including the legacy journal detail link."""
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
        parent_id = getattr(target, foreign_key.parent.key)
        if parent_id is not None:
            yield parent_cls, parent_id


def _guard_raw_sql(connection: Any, cursor: Any, statement: str, parameters: Any, context: Any, executemany: Any) -> None:
    """Reject textual writes that cannot participate in mapped evidence controls."""
    del connection, cursor, parameters, executemany
    if not _enabled() or (context.compiled is not None and isinstance(context.compiled.statement, (Update, Delete))):
        return
    targets = re.findall(
        r'\b(?:UPDATE|DELETE\s+FROM|TRUNCATE(?:\s+TABLE)?)\s+(?:["`]?\w+["`]?\.)?["`]?([\w]+)', statement, flags=re.IGNORECASE
    )
    if not targets:
        return
    protected = EVIDENCE_TABLES.union(LEDGER_TABLES, {"approval_request", "cacao_config"})
    protected = protected.union(
        mapper.local_table.name
        for mapper in cast(Any, database.Model).registry.mappers
        if mapper.class_.__name__ in SENSITIVE_MODELS or issubclass(mapper.class_, DocBase)
    )
    if any(table.lower() in protected for table in targets):
        raise ValueError(_("Los cambios sensibles deben realizarse mediante el servicio auditado."))


def _guard_bulk(connection: Any, clause: Any, multiparams: Any, params: Any, execution_options: Any) -> None:
    """Reject evidence SQL mutations, including Core and ORM bulk statements."""
    del execution_options
    if not _enabled() or not isinstance(clause, (Update, Delete)):
        return
    table_name = getattr(clause.table, "name", None)
    if table_name in LEDGER_TABLES:
        _guard_ledger_statement(clause, multiparams, params)
    if table_name in EVIDENCE_TABLES:
        raise ValueError(_("La evidencia de auditoría es inmutable."))
    if table_name == "approval_request":
        _guard_approval_request_statement(clause, multiparams, params)


def _statement_changed_values(clause: Any, multiparams: Any, params: Any, table: Any) -> dict[str, Any]:
    """Map the mutated column keys of an Update to their bound values."""
    values = getattr(clause, "_values", None)
    if values is not None:
        return {getattr(key, "key", key): getattr(value, "value", value) for key, value in values.items()}
    parameters = list(multiparams or ()) + ([params] if params else [])
    changed: dict[str, Any] = {}
    for group in parameters:
        if group:
            changed.update({key: value for key, value in group.items() if key in table.c})
    return changed


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
    }
)


def _guard_approval_request_statement(clause: Any, multiparams: Any, params: Any) -> None:
    """Reject Core rewrites of approval provenance while allowing lifecycle moves."""
    if isinstance(clause, Delete):
        raise ValueError(_("La evidencia de auditoría es inmutable."))
    changed = _statement_changed_values(clause, multiparams, params, clause.table)
    if changed and changed.keys() & PROTECTED_REQUEST_FIELDS:
        raise ValueError(_("La evidencia de auditoría es inmutable."))


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
    if table.name == "comprobante_contable_detalle":
        parent = parents["comprobante_contable"]
        return table.c.transaction_id.in_(select(parent.c.id).where(_posting_predicate(parent)))
    for key in table.foreign_keys:
        if key.column.table.name in parents:
            return key.parent.in_(select(key.column).where(_posting_predicate(key.column.table)))
    return None


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


def register_internal_controls() -> None:
    """Install idempotent shared listeners once, independent of app instances."""
    if event.contains(Session, "before_flush", _guard_flush):
        return
    event.listen(Session, "before_flush", _guard_flush)
    event.listen(Session, "before_flush", _chain_audit_flush)
    event.listen(Session, "do_orm_execute", _guard_sensitive_bulk)
    event.listen(Engine, "before_execute", _guard_bulk)
    event.listen(Engine, "before_cursor_execute", _guard_raw_sql)
    event.listen(AuditTrail, "before_insert", _stamp_audit_chain)
    for mapper in cast(Any, database.Model).registry.mappers:
        model = mapper.class_
        event.listen(model, "before_insert", _stamp_preparer)
        event.listen(model, "before_update", _stamp_preparer)
        event.listen(model, "after_insert", _audit_insert)
        event.listen(model, "after_update", _audit_update)
        event.listen(model, "after_delete", _audit_delete)
