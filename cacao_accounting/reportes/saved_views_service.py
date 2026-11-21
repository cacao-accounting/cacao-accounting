# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Servicio reutilizable de vistas guardadas para reportes financieros (#1938)."""

from __future__ import annotations

from dataclasses import replace
import json
from types import SimpleNamespace
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from cacao_accounting.auth.permisos import Permisos
from cacao_accounting.database import SavedReportView, database
from cacao_accounting.database.helpers import obtener_id_modulo_por_nombre
from cacao_accounting.i18n import _

FILTER_FIELDS = (
    "ledger",
    "accounting_period",
    "period_from",
    "period_to",
    "voucher_number",
    "account_code",
    "account_from",
    "account_to",
    "cost_center_code",
    "unit_code",
    "project_code",
    "party_type",
    "party_id",
    "voucher_type",
    "status",
    "page_size",
    "sort_by",
    "sort_dir",
)
BOOLEAN_FILTER_FIELDS = ("include_cancellations", "include_running_balance", "include_closing", "include_descendants")
DISPLAY_FIELDS = ("visible_columns", "group_by", "page_size", "sort_by", "sort_dir", "show_users", "advanced")


class SavedReportViewError(Exception):
    """Error de negocio o autorización en vistas guardadas."""

    _safe_for_display = True


def _is_saved_view_name_conflict(error: IntegrityError) -> bool:
    """Reconoce la restricción única del nombre entre los motores Tier 1."""
    original = error.orig
    constraint_name = getattr(getattr(original, "diag", None), "constraint_name", None)
    if constraint_name == "uq_saved_report_view_name":
        return True
    return (
        "UNIQUE constraint failed: saved_report_view.company, saved_report_view.user_id, "
        "saved_report_view.report_code, saved_report_view.name" in str(original)
    )


def _require_access(company: str, user_id: str | None) -> None:
    """Valida permiso de reportes y acceso vigente a la compañía."""
    if not company or not user_id:
        raise SavedReportViewError(_("La vista guardada requiere usuario y compañía."))
    permisos = Permisos(modulo=obtener_id_modulo_por_nombre("accounting"), usuario=user_id)
    if not permisos.reportes or not permisos.tiene_acceso_compania(company):
        raise SavedReportViewError(_("No tiene permisos para administrar vistas de esta compañía."))


def _normalize_name(name: str) -> str:
    """Normaliza y valida el nombre visible de la vista."""
    value = str(name or "").strip()
    if not value:
        raise SavedReportViewError(_("El nombre de la vista es obligatorio."))
    if len(value) > 100:
        raise SavedReportViewError(_("El nombre de la vista no puede exceder 100 caracteres."))
    return value


def _clean_filters(filters: Any) -> dict[str, Any]:
    """Extrae únicamente los filtros persistibles del reporte."""
    payload: dict[str, Any] = {}
    for field in FILTER_FIELDS:
        value = getattr(filters, field, None)
        if value not in (None, ""):
            payload[field] = value
    for field in BOOLEAN_FILTER_FIELDS:
        value = getattr(filters, field, False)
        if value:
            payload[field] = True
    return payload


def _clean_display(display: dict[str, Any] | None) -> dict[str, Any]:
    """Valida la lista blanca de preferencias de visualización."""
    payload: dict[str, Any] = {}
    for field, value in (display or {}).items():
        if field not in DISPLAY_FIELDS or value in (None, "", []):
            continue
        if field == "visible_columns":
            if not isinstance(value, (list, tuple)):
                raise SavedReportViewError(_("La selección de columnas no tiene un formato válido."))
            payload[field] = [str(column) for column in value if str(column)]
        elif field in {"show_users", "advanced"}:
            payload[field] = bool(value)
        elif field == "page_size":
            try:
                payload[field] = max(int(value), 1)
            except (TypeError, ValueError) as exc:
                raise SavedReportViewError(_("El tamaño de página no es válido.")) from exc
        else:
            payload[field] = str(value)
    return payload


def _parse_payload(view: SavedReportView) -> tuple[dict[str, Any], dict[str, Any]]:
    """Lee y valida el JSON persistido de una vista."""
    try:
        filters = json.loads(view.filters_json or "{}")
        display = json.loads(view.display_json or "{}")
    except (TypeError, json.JSONDecodeError) as exc:
        raise SavedReportViewError(_("La vista guardada contiene preferencias inválidas.")) from exc
    if not isinstance(filters, dict) or not isinstance(display, dict):
        raise SavedReportViewError(_("La vista guardada contiene preferencias inválidas."))
    return _clean_filters(SimpleNamespace(**filters)), _clean_display(display)


def list_saved_views(report_code: str, company: str, user_id: str | None) -> list[SavedReportView]:
    """Devuelve las vistas del usuario para un reporte y compañía."""
    _require_access(company, user_id)
    return list(
        database.session.execute(
            select(SavedReportView)
            .filter_by(report_code=report_code, company=company, user_id=user_id)
            .order_by(SavedReportView.name.asc())
        ).scalars()
    )


def get_saved_view(view_id: str, report_code: str, company: str, user_id: str | None) -> SavedReportView:
    """Carga una vista propia; una vista ajena se reporta como inexistente."""
    _require_access(company, user_id)
    view = database.session.get(SavedReportView, view_id)
    if view is None or view.report_code != report_code or view.company != company or view.user_id != user_id:
        raise SavedReportViewError(_("La vista guardada no existe."))
    return view


def create_saved_view(
    report_code: str,
    company: str,
    user_id: str | None,
    name: str,
    filters: Any,
    display: dict[str, Any] | None = None,
) -> SavedReportView:
    """Guarda filtros y preferencias de visualización del usuario."""
    _require_access(company, user_id)
    normalized_name = _normalize_name(name)
    duplicate = database.session.execute(
        select(SavedReportView).filter_by(
            report_code=report_code,
            company=company,
            user_id=user_id,
            name=normalized_name,
        )
    ).scalar_one_or_none()
    if duplicate is not None:
        raise SavedReportViewError(_("Ya existe una vista guardada con ese nombre."))
    view = SavedReportView(
        report_code=report_code,
        company=company,
        user_id=user_id,
        name=normalized_name,
        filters_json=json.dumps(_clean_filters(filters), sort_keys=True),
        display_json=json.dumps(_clean_display(display), sort_keys=True),
        created_by=user_id,
        modified_by=user_id,
    )
    database.session.add(view)
    try:
        database.session.commit()
    except IntegrityError as exc:
        database.session.rollback()
        if _is_saved_view_name_conflict(exc):
            raise SavedReportViewError(_("Ya existe una vista guardada con ese nombre.")) from exc
        raise
    return view


def delete_saved_view(view_id: str, report_code: str, company: str, user_id: str | None) -> None:
    """Elimina una vista propia validando reporte, compañía y usuario."""
    view = get_saved_view(view_id, report_code, company, user_id)
    database.session.delete(view)
    database.session.commit()


def restore_filters(filters: Any, view: SavedReportView) -> Any:
    """Aplica filtros persistidos sobre los filtros actuales."""
    stored, _display = _parse_payload(view)
    updates = {field: value for field, value in stored.items() if hasattr(filters, field)}
    updates["company"] = filters.company
    return replace(filters, **updates)


def view_display(view: SavedReportView) -> dict[str, Any]:
    """Devuelve las preferencias de visualización persistidas."""
    _filters, display = _parse_payload(view)
    return display
