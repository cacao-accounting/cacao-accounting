# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 William José Moreno Reyes

"""Semantic status badges for module cards."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from cacao_accounting.auth.permisos import Permisos
from cacao_accounting.database.helpers import obtener_id_modulo_por_nombre


@dataclass(frozen=True)
class ModuleBadge:
    """Presentation data for a semantic module status badge."""

    status: str
    css_class: str
    label: str
    title: str


_BADGE_META = {
    "ok": ("ca-status-ok", "Todo ok", "Acceso operativo disponible"),
    "no_access": ("ca-status-no-access", "Sin acceso", "No tiene acceso a esta opción"),
    "pending_approval": (
        "ca-status-pending-approval",
        "Pendiente de aprobar",
        "Hay registros pendientes de aprobación",
    ),
    "view_only": ("ca-status-view-only", "Solo visualizar", "Acceso solo de visualización"),
    "attention": ("ca-status-attention", "Requiere atención", "Hay una situación que requiere atención"),
}


def _has_permission(access: Any, permission_name: str | None) -> bool:
    """Return whether a permissions object grants a named permission."""
    if not access or not permission_name:
        return False
    return bool(getattr(access, permission_name, False))


def _resolve_access(module: str | None, user_id: str | None, access: Any | None) -> Any | None:
    """Return a permissions object from explicit access or module/user identifiers."""
    if access is not None:
        return access
    if not module or not user_id:
        return None
    return Permisos(modulo=obtener_id_modulo_por_nombre(module), usuario=user_id)


def module_badge(
    module: str | None = None,
    user_id: str | None = None,
    *,
    access: Any | None = None,
    required: str = "consultar",
    view_permission: str = "consultar",
    pending_count: int = 0,
    requires_attention: bool = False,
    label: str | None = None,
) -> ModuleBadge:
    """Calculate the semantic badge state for a module card link."""
    resolved_access = _resolve_access(module=module, user_id=user_id, access=access)

    has_required_access = _has_permission(resolved_access, required)
    has_view_access = _has_permission(resolved_access, view_permission)

    if requires_attention:
        status = "attention"
    elif not has_required_access and not has_view_access:
        status = "no_access"
    elif pending_count > 0 and has_required_access:
        status = "pending_approval"
    elif not has_required_access and has_view_access:
        status = "view_only"
    else:
        status = "ok"

    css_class, default_label, default_title = _BADGE_META[status]
    resolved_label = label or default_label
    title = resolved_label if label else default_title
    if status == "pending_approval" and pending_count > 0:
        title = f"{pending_count} registro(s) pendiente(s) de aprobación"

    return ModuleBadge(status=status, css_class=css_class, label=resolved_label, title=title)
