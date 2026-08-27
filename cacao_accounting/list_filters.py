# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Reusable helpers for simple list filters."""

from __future__ import annotations

from typing import Any

from flask import abort, request
from sqlalchemy import Select, or_
from sqlalchemy.orm.attributes import InstrumentedAttribute

DOCSTATUS_FILTERS: dict[str, int] = {
    "draft": 0,
    "submitted": 1,
    "cancelled": 2,
}


def apply_list_filters(
    query: Select[Any],
    model: type[Any],
    search_fields: tuple[InstrumentedAttribute[Any], ...],
    *,
    include_status: bool = True,
) -> Select[Any]:
    """Apply common search and document status filters to a query."""
    search = (request.args.get("search") or "").strip()
    if search and search_fields:
        pattern = f"%{search}%"
        query = query.filter(or_(*(field.ilike(pattern) for field in search_fields)))

    status = (request.args.get("status") or "").strip()
    if include_status and status in DOCSTATUS_FILTERS:
        if hasattr(model, "docstatus"):
            query = query.filter(model.docstatus == DOCSTATUS_FILTERS[status])
        elif hasattr(model, "status"):
            query = query.filter(model.status == status)

    return query


def apply_period_filter(
    query: Select[Any],
    model: type[Any],
    period_company: str,
    period_from: str | None,
    period_to: str | None,
) -> Select[Any]:
    """Acota una consulta de documento a un rango de períodos contables completos.

    Usa ``AccountingPeriod`` como única fuente de verdad para las fechas. El
    período debe pertenecer a ``period_company``; de lo contrario la resolución
    dispara un error 400. Solo tiene sentido para modelos que exponen ``company``
    y ``posting_date`` (documentos transaccionales).
    """
    from cacao_accounting.reportes.periods import reject_manual_date_overrides, resolve_period_range

    period_range = resolve_period_range(period_company, period_from, period_to)
    if period_range is None:
        return query
    reject_manual_date_overrides(request.args, period_range)
    query = query.where(model.company == period_company)
    query = query.where(model.posting_date >= period_range.period_start)
    query = query.where(model.posting_date <= period_range.period_end)
    return query


def period_company_from_request(
    access_modules: tuple[str, ...],
    *,
    current_user: Any,
    default_company: str | None = None,
) -> str | None:
    """Resuelve la compañía sobre la que aplicar un filtro por período.

    Prioriza el parámetro explícito ``company``; si no hay un único origen
    de datos no ambiguo (una sola compañía autorizada) devuelve ``None`` para
    que el llamador decida cómo comunicar la restricción.
    """
    period_from = request.args.get("accounting_period_from") or request.args.get("period_from")
    period_to = request.args.get("accounting_period_to") or request.args.get("period_to")
    if not (period_from or period_to):
        return None
    company = request.args.get("company")
    if company:
        return company
    if getattr(current_user, "classification", None) != "admin":
        from cacao_accounting.auth.permisos import Permisos
        from cacao_accounting.database.helpers import obtener_id_modulo_por_nombre

        companies = set()
        for module in access_modules:
            permissions = Permisos(modulo=obtener_id_modulo_por_nombre(module), usuario=current_user.id)
            if permissions.consultar:
                companies.update(permissions.obtener_companias_autorizadas())
        if len(companies) == 1:
            return next(iter(companies))
        return None
    return default_company


def require_period_company(access_modules: tuple[str, ...], *, current_user: Any) -> str:
    """Resuelve la compañía para el período o dispara 400 si es ambigua."""
    company = period_company_from_request(access_modules, current_user=current_user)
    if company is None:
        from flask_babel import gettext as _babel_gettext

        abort(400, description=_babel_gettext("Seleccione una compañía para aplicar el filtro por período."))
    return company


def period_picker_context(company: str, period_from: str | None, period_to: str | None) -> dict[str, Any]:
    """Construye el contexto del selector de rango de períodos para un listado."""
    from cacao_accounting.reportes.periods import list_periods_for_company, resolve_period_range

    periods = [
        {"id": str(item.id), "name": item.name, "is_closed": bool(item.is_closed)}
        for item in list_periods_for_company(company)
    ]
    active_from, active_to = period_from, period_to
    if period_from or period_to:
        resolved = resolve_period_range(company, period_from, period_to)
        if resolved is not None:
            active_from, active_to = resolved.from_id, resolved.to_id
    elif not (active_from or active_to):
        resolved = resolve_period_range(company, None, None)
        active_from = active_to = resolved.from_id if resolved is not None else ""
    return {"periods": periods, "period_from": active_from, "period_to": active_to or active_from}


def company_choices_for_module(module: str, *, current_user: Any) -> list[tuple[str, str]]:
    """Devuelve las opciones (código, nombre) de compañía para un módulo."""
    from flask_babel import gettext as _babel_gettext

    from cacao_accounting.auth.permisos import Permisos
    from cacao_accounting.database import Entity, database
    from cacao_accounting.database.helpers import obtener_id_modulo_por_nombre

    permissions = Permisos(modulo=obtener_id_modulo_por_nombre(module), usuario=current_user.id)
    if permissions.administrador:
        codes = [row[0] for row in database.session.execute(database.select(Entity.code)).all()]
    elif permissions.consultar:
        codes = list(permissions.obtener_companias_autorizadas())
    else:
        codes = []
    if not codes:
        return [("", "")]
    names = {
        row.code: row.name for row in database.session.execute(database.select(Entity).where(Entity.code.in_(codes))).scalars()
    }
    return [("", _babel_gettext("Todas"))] + [(code, names.get(code, code)) for code in codes]


def pick_company_period(company: str | None, companies: list[str]) -> str | None:
    """Elige la compañía para el período: la seleccionada o la única disponible."""
    return company or (companies[0] if len(companies) == 1 else None)


def attach_period_picker(paginated: Any, model: type[Any], module: str, *, current_user: Any) -> None:
    """Adjunta al objeto de paginación el contexto del selector de período.

    Solo se aplica a modelos con ``posting_date`` (documentos transaccionales).
    Expone ``company_choices``, ``selected_company``, ``periods``,
    ``period_from``, ``period_to`` y ``period_extra_params`` para que las
    plantillas de listado rendericen el selector sin duplicar lógica por ruta.
    """
    if not hasattr(model, "posting_date"):
        paginated.period_extra_params = {}
        return
    choices = company_choices_for_module(module, current_user=current_user)
    selected = request.args.get("company") or (choices[1][0] if len(choices) > 1 else None)
    period_from = request.args.get("accounting_period_from") or request.args.get("period_from")
    period_to = request.args.get("accounting_period_to") or request.args.get("period_to")
    picker = period_picker_context(selected or "", period_from, period_to)
    params: dict[str, str] = {}
    if request.args.get("company"):
        params["company"] = str(request.args.get("company"))
    if period_from:
        params["accounting_period_from"] = period_from
    if period_to:
        params["accounting_period_to"] = period_to
    paginated.company_choices = choices
    paginated.selected_company = selected or ""
    paginated.periods = picker["periods"]
    paginated.period_from = picker["period_from"]
    paginated.period_to = picker["period_to"]
    paginated.period_extra_params = params
