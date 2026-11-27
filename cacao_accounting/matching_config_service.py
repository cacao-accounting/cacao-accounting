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

from decimal import Decimal
from typing import Any

from cacao_accounting.database import PurchaseMatchingConfig, SalesMatchingConfig, database
from cacao_accounting.i18n import _
from cacao_accounting.numbers import coerce_decimal

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
_MATCHING_TYPES = frozenset({"2-way", "3-way"})
_TOLERANCE_TYPES = frozenset({"percentage", "absolute"})
_NUMERIC_TOLERANCE_FIELDS = ("price_tolerance_value", "qty_tolerance_value")
_ENUM_FIELDS = {
    "matching_type": _MATCHING_TYPES,
    "price_tolerance_type": _TOLERANCE_TYPES,
    "qty_tolerance_type": _TOLERANCE_TYPES,
}


def _plain(value: Any) -> Any:
    """Representaciones JSON estables para el payload de revisión."""
    return str(value) if isinstance(value, Decimal) else value


def _normalize(field: str, value: Any) -> Any:
    """Acepta valores del formulario o del JSON de revisión con igual resultado."""
    if field in _DECIMAL_FIELDS and value is not None and value != "":
        return coerce_decimal(value, field, max_fractional_digits=4)
    return value


def _validate_enum_values(model: str, values: dict[str, Any]) -> None:
    """Reject unknown matching modes before applying or requesting review."""
    for field, allowed_values in _ENUM_FIELDS.items():
        if field not in CONFIG_FIELDS[model]:
            continue
        value = values.get(field)
        if not isinstance(value, str) or value not in allowed_values:
            raise ValueError(_("El valor de configuración de matching no es válido."))


def _validate_tolerance_values(model: str, values: dict[str, Any]) -> None:
    """Reject negative, non-finite, or unrepresentable tolerance values."""
    for field in _NUMERIC_TOLERANCE_FIELDS:
        if field not in CONFIG_FIELDS[model]:
            continue
        number = coerce_decimal(values.get(field), field, non_negative=True, max_fractional_digits=4)
        if number.adjusted() > 5:
            raise ValueError(_("El campo %(field)s excede la precisión admitida.") % {"field": field})


def _normalize_stored(field: str, value: Any) -> Any:
    """Normaliza valores persistidos tolerando legado inválido para permitir corrección."""
    try:
        return _normalize(field, value)
    except (TypeError, ValueError, ArithmeticError):
        if field in _DECIMAL_FIELDS and value is not None and value != "":
            try:
                return coerce_decimal(value, field, max_fractional_digits=4)
            except (TypeError, ValueError, ArithmeticError):
                return str(value)
        return value


def _prepare_config_change(
    model: str,
    config: Any,
    values: dict[str, Any],
    expected_before: dict[str, Any] | None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Normalize values, verify the review snapshot, and prepare its payload."""
    fields = CONFIG_FIELDS[model]
    _validate_enum_values(model, values)
    _validate_tolerance_values(model, values)
    typed_after = {field: _normalize(field, values.get(field)) for field in fields}
    typed_before = {field: _normalize_stored(field, getattr(config, field)) for field in fields}
    if expected_before is not None:
        expected_typed = {field: _normalize_stored(field, expected_before.get(field)) for field in fields}
        if typed_before != expected_typed:
            raise ValueError(_("La operación cambió después de solicitar la revisión."))
    changed_fields = [field for field in fields if typed_before[field] != typed_after[field]]
    payload = {
        "model": model,
        "before": {field: _plain(value) for field, value in typed_before.items()},
        "after": {field: _plain(value) for field, value in typed_after.items()},
        "changed_fields": changed_fields,
    }
    return typed_after, payload


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
    typed_after, payload = _prepare_config_change(model, config, values, expected_before)
    identifier = f"{model}:{company}"
    pending = require_review(
        "config_change", identifier, company, actor_id, payload, review_required=bool(payload["changed_fields"])
    )
    if pending is None:
        for field, value in typed_after.items():
            setattr(config, field, value)
        database.session.flush()
        return config
    return pending
