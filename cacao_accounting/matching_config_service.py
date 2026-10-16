# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 William José Moreno Reyes

"""Configuración auditada de matching de compras y ventas.

Regla aprobada en #924: cambio de configuración -> aprobación.
Todo cambio efectivo requiere revisión independiente cuando el control
Cloud está activo, sin clasificar si fortalece o debilita controles.
Guardar los mismos valores no genera una solicitud. Desktop conserva
su operación de un solo usuario y la auditoría sigue el modo existente.
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any

from cacao_accounting.database import PurchaseMatchingConfig, SalesMatchingConfig, database
from cacao_accounting.i18n import _

CONFIG_MODELS = {
    "purchase": PurchaseMatchingConfig,
    "sales": SalesMatchingConfig,
}
CONFIG_FIELDS = {
    "purchase": (
        "matching_type",
        "price_tolerance_type",
        "price_tolerance_value",
        "qty_tolerance_type",
        "qty_tolerance_value",
        "require_purchase_order",
        "bridge_account_required",
        "auto_reconcile",
        "allow_price_difference",
    ),
    "sales": (
        "matching_type",
        "price_tolerance_type",
        "price_tolerance_value",
        "require_sales_order",
        "allow_price_difference",
    ),
}
_DECIMAL_FIELDS = frozenset({"price_tolerance_value", "qty_tolerance_value"})


def _plain(value: Any) -> Any:
    """Representaciones JSON estables para el payload de revisión."""
    return str(value) if isinstance(value, Decimal) else value


def _normalize(field: str, value: Any) -> Any:
    """Acepta valores del formulario o del JSON de revisión con igual resultado."""
    if field in _DECIMAL_FIELDS and value is not None and value != "":
        try:
            return Decimal(str(value))
        except (ValueError, InvalidOperation) as exc:
            raise ValueError(_("El valor de tolerancia debe ser numérico.")) from exc
    return value


def update_matching_config(
    model: str,
    company: str,
    values: dict[str, Any],
    actor_id: str | None = None,
    *,
    expected_before: dict[str, Any] | None = None,
) -> Any:
    """Aplica la edición de configuración o la deja pendiente de revisión independiente.

    Devuelve la fila de ``ApprovalRequest`` cuando existe un cambio y
    espera revisión (Cloud), o el objeto de configuración
    actualizado cuando la edición se aplicó de inmediato; la aplicación es
    la misma que ejecuta la revisión aprobada para que la ruta
    administrativa y la aprobación independiente usen un solo validador.
    """
    from cacao_accounting.control_review_service import require_review

    clase = CONFIG_MODELS.get(model)
    if clase is None:
        raise ValueError(_("La configuración solicitada no existe."))
    config = database.session.execute(
        database.select(clase).filter_by(company=company).with_for_update().execution_options(populate_existing=True)
    ).scalar_one_or_none()
    if config is None:
        raise ValueError(_("La configuración de matching no existe para la compañía solicitada."))
    fields = CONFIG_FIELDS[model]
    typed_after = {field: _normalize(field, values.get(field)) for field in fields}
    typed_before = {field: _normalize(field, getattr(config, field)) for field in fields}
    if expected_before is not None and typed_before != {
        field: _normalize(field, expected_before.get(field)) for field in fields
    }:
        raise ValueError(_("La operación cambió después de solicitar la revisión."))
    changed_fields = [field for field in fields if typed_before[field] != typed_after[field]]
    payload = {
        "model": model,
        "before": {field: _plain(value) for field, value in typed_before.items()},
        "after": {field: _plain(value) for field, value in typed_after.items()},
        "changed_fields": changed_fields,
    }
    identifier = f"{model}:{company}"
    pending = require_review("config_change", identifier, company, actor_id, payload, review_required=bool(changed_fields))
    if pending is None:
        for field, value in typed_after.items():
            setattr(config, field, value)
        database.session.flush()
        return config
    return pending
