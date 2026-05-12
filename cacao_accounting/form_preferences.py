# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Preferencias persistentes de formularios por usuario."""

from __future__ import annotations

import json
from typing import Any

from cacao_accounting.database import UserFormPreference, database

JOURNAL_FORM_KEY = "accounting.journal_entry"
DEFAULT_VIEW_KEY = "draft"
DEFAULT_SCHEMA_VERSION = 1
JOURNAL_DEFAULT_COLUMNS: list[dict[str, Any]] = [
    {"field": "account", "label": "Cuenta", "width": 3, "visible": True, "required": True},
    {"field": "cost_center", "label": "Centro de costos", "width": 2, "visible": True, "required": False},
    {"field": "party_type", "label": "Tipo de tercero", "width": 1, "visible": True, "required": False},
    {"field": "party", "label": "Tercero", "width": 2, "visible": True, "required": False},
    {"field": "debit", "label": "Debe", "width": 2, "visible": True, "required": True},
    {"field": "credit", "label": "Haber", "width": 2, "visible": True, "required": True},
]


def default_form_preference(form_key: str, view_key: str = DEFAULT_VIEW_KEY) -> dict[str, Any]:
    """Devuelve la configuración default versionada para un formulario."""
    if form_key == JOURNAL_FORM_KEY and view_key == DEFAULT_VIEW_KEY:
        return {
            "form_key": form_key,
            "view_key": view_key,
            "schema_version": DEFAULT_SCHEMA_VERSION,
            "columns": JOURNAL_DEFAULT_COLUMNS,
        }
    return {
        "form_key": form_key,
        "view_key": view_key,
        "schema_version": DEFAULT_SCHEMA_VERSION,
        "columns": [],
    }


def get_form_preference(user_id: str, form_key: str, view_key: str) -> dict[str, Any]:
    """Obtiene preferencia de formulario para un usuario o su default."""
    preference = (
        database.session.execute(
            database.select(UserFormPreference).filter_by(user_id=user_id, form_key=form_key, view_key=view_key)
        )
        .scalars()
        .first()
    )
    if preference is None:
        return default_form_preference(form_key, view_key)
    try:
        config = json.loads(preference.config_json)
    except json.JSONDecodeError:
        config = default_form_preference(form_key, view_key)
    config["form_key"] = form_key
    config["view_key"] = view_key
    config["schema_version"] = preference.schema_version
    return config


def save_form_preference(
    *,
    user_id: str,
    form_key: str,
    view_key: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    """Guarda o reemplaza una preferencia de formulario por usuario."""
    normalized = _normalize_preference_payload(form_key=form_key, view_key=view_key, payload=payload)
    preference = (
        database.session.execute(
            database.select(UserFormPreference).filter_by(user_id=user_id, form_key=form_key, view_key=view_key)
        )
        .scalars()
        .first()
    )
    if preference is None:
        preference = UserFormPreference(
            user_id=user_id,
            form_key=form_key,
            view_key=view_key,
            schema_version=int(normalized["schema_version"]),
            config_json=json.dumps(normalized, ensure_ascii=True),
        )
    else:
        preference.schema_version = int(normalized["schema_version"])
        preference.config_json = json.dumps(normalized, ensure_ascii=True)
    database.session.add(preference)
    database.session.commit()
    return normalized


def reset_form_preference(user_id: str, form_key: str, view_key: str) -> dict[str, Any]:
    """Elimina la preferencia del usuario y devuelve el default."""
    preference = (
        database.session.execute(
            database.select(UserFormPreference).filter_by(user_id=user_id, form_key=form_key, view_key=view_key)
        )
        .scalars()
        .first()
    )
    if preference is not None:
        database.session.delete(preference)
        database.session.commit()
    return default_form_preference(form_key, view_key)


def _normalize_preference_payload(form_key: str, view_key: str, payload: dict[str, Any]) -> dict[str, Any]:
    columns = payload.get("columns")
    if not isinstance(columns, list):
        columns = default_form_preference(form_key, view_key)["columns"]
    normalized_columns = []
    for column in columns:
        if not isinstance(column, dict):
            continue
        field = str(column.get("field") or "").strip()
        if not field:
            continue
        normalized_columns.append(
            {
                "field": field,
                "label": str(column.get("label") or field).strip(),
                "width": _normalize_width(column.get("width")),
                "visible": bool(column.get("visible", True)),
                "required": bool(column.get("required", False)),
            }
        )
    return {
        "form_key": form_key,
        "view_key": view_key,
        "schema_version": int(payload.get("schema_version") or DEFAULT_SCHEMA_VERSION),
        "columns": normalized_columns,
    }


def _normalize_width(value: Any) -> int:
    try:
        width = int(value)
    except (TypeError, ValueError):
        width = 1
    return min(max(width, 1), 4)
