# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 William José Moreno Reyes

"""Cloud internal-control evidence queried from existing audit and approvals."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any

from sqlalchemy import case, func, literal, or_, select, union_all

from cacao_accounting.auth.permisos import Permisos
from cacao_accounting.database import AccountingPeriod, ApprovalAction, ApprovalRequest, AuditTrail, User, database
from cacao_accounting.database.helpers import obtener_id_modulo_por_nombre
from cacao_accounting.document_authorship import AUTHOR_COLUMNS, report_authorship
from cacao_accounting.i18n import _, _l
from cacao_accounting.reportes.services import PaginatedReport, ReportRow
from cacao_accounting.runtime_mode import is_cloud_mode

REPORT_HEADERS = {
    "event_id": _l("ID del evento"),
    "company": _l("Compañía"),
    "document_type": _l("Tipo de documento"),
    "document_id": _l("ID del documento"),
    "document_no": _l("Número de documento"),
    "action": _l("Acción"),
    "actor_id": _l("ID del usuario"),
    "actor_name": _l("Usuario"),
    "timestamp": _l("Fecha y hora (UTC)"),
    "before_json": _l("Valores anteriores"),
    "after_json": _l("Valores posteriores"),
    "comment": _l("Comentario"),
    "created_by": _l("Creado por"),
    "created_at": _l("Fecha de creación"),
    "approved_by": _l("Aprobado por"),
    "approved_at": _l("Fecha de aprobación"),
    "modified_by": _l("Modificado por"),
    "modified_at": _l("Fecha de modificación"),
}


@dataclass(frozen=True)
class InternalControlFilters:
    """Filter evidence by event time rather than document posting time."""

    company: str
    date_from: date | None = None
    date_to: date | None = None
    period: str | None = None
    action: str | None = None
    actor_id: str | None = None
    document_type: str | None = None
    document_id: str | None = None
    include_global: bool = False
    page: int = 1
    page_size: int = 100
    export_all: bool = False


def control_report_access(company: str, user_id: str, include_global: bool = False) -> None:
    """Enforce report permission and tenant scope even outside an HTTP route."""
    user = database.session.get(User, user_id)
    if not is_cloud_mode() or user is None or not user.active:
        raise PermissionError(_("No tiene permiso para consultar la evidencia de control interno."))
    permissions = Permisos(modulo=obtener_id_modulo_por_nombre("accounting"), usuario=user_id)
    if not permissions.reportes or not permissions.tiene_acceso_compania(company):
        raise PermissionError(_("No tiene permiso para consultar la evidencia de control interno."))
    if include_global and not permissions.administrador:
        raise PermissionError(_("Solo Admin puede consultar cambios de configuración global."))


def _date_bounds(filters: InternalControlFilters) -> tuple[date | None, date | None]:
    """Resolve a company-owned period and reject contradictory date filters."""
    start, end = filters.date_from, filters.date_to
    if filters.period:
        period = database.session.scalar(
            select(AccountingPeriod).where(
                AccountingPeriod.entity == filters.company,
                or_(AccountingPeriod.id == filters.period, AccountingPeriod.name == filters.period),
            )
        )
        if period is None:
            raise ValueError(_("El período no pertenece a la compañía seleccionada."))
        if (start and start != period.start) or (end and end != period.end):
            raise ValueError(_("Seleccione un período o un rango de fechas compatible."))
        start, end = period.start, period.end
    if start and end and start > end:
        raise ValueError(_("La fecha inicial no puede ser posterior a la fecha final."))
    return start, end


def _evidence_query(filters: InternalControlFilters) -> Any:
    """Combine append-only audit and approval evidence before SQL pagination."""
    scope = AuditTrail.company == filters.company
    if filters.include_global:
        scope = or_(scope, AuditTrail.company.is_(None))
    trail = select(
        (literal("audit:") + AuditTrail.id).label("event_id"),
        AuditTrail.company.label("company"),
        AuditTrail.document_type.label("document_type"),
        AuditTrail.document_id.label("document_id"),
        AuditTrail.document_no.label("document_no"),
        AuditTrail.action.label("action"),
        AuditTrail.actor_user_id.label("actor_id"),
        AuditTrail.actor_name.label("actor_name"),
        AuditTrail.timestamp.label("timestamp"),
        AuditTrail.before_json.label("before_json"),
        AuditTrail.after_json.label("after_json"),
        AuditTrail.comment.label("comment"),
    ).where(scope)
    approvals = (
        select(
            (literal("approval:") + ApprovalAction.id).label("event_id"),
            ApprovalRequest.company_id,
            ApprovalRequest.document_type,
            ApprovalRequest.document_id,
            literal(None),
            case((ApprovalAction.action == "approve", "approved"), else_="rejected"),
            ApprovalAction.approved_by,
            func.coalesce(User.name, User.user),
            ApprovalAction.created_at,
            literal(None),
            literal(None),
            ApprovalAction.comments,
        )
        .join(ApprovalRequest, ApprovalRequest.id == ApprovalAction.approval_request_id)
        .join(User, User.id == ApprovalAction.approved_by, isouter=True)
        .where(ApprovalRequest.company_id == filters.company)
    )
    return union_all(trail, approvals).subquery()


def get_internal_control_report(filters: InternalControlFilters, *, user_id: str) -> PaginatedReport:
    """Return authorized filtered evidence; missing provenance remains explicit."""
    control_report_access(filters.company, user_id, filters.include_global)
    start, end = _date_bounds(filters)
    evidence = _evidence_query(filters)
    query = select(evidence)
    for name in ("action", "actor_id", "document_type", "document_id"):
        if value := getattr(filters, name):
            query = query.where(evidence.c[name] == value)
    if start:
        query = query.where(evidence.c.timestamp >= start)
    if end:
        query = query.where(evidence.c.timestamp < end + timedelta(days=1))
    count = database.session.scalar(select(func.count()).select_from(query.subquery())) or 0
    query = query.order_by(evidence.c.timestamp, evidence.c.event_id)
    size, page = min(max(filters.page_size, 1), 500), max(filters.page, 1)
    if not filters.export_all:
        query = query.offset((page - 1) * size).limit(size)
    rows = [ReportRow(values=dict(row)) for row in database.session.execute(query).mappings()]
    columns = list(evidence.c.keys()) + list(AUTHOR_COLUMNS)
    report = PaginatedReport(rows=rows, totals={}, columns=columns, total_rows=count, page=page, page_size=size)
    return report_authorship(report, filters.company, True)
