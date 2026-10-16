# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 William José Moreno Reyes

"""Servicio auditado de configuración de matching de compras y ventas.

La única vía de actualización de ``PurchaseMatchingConfig`` y
``SalesMatchingConfig`` es este servicio: la ruta administrativa entrega los
valores del formulario y aquí se decide si el cambio debilita controles.

Clasificación de cambios que debilitan controles (política acordada en
el issue #924, documentada en ``docs/cloud/internal-controls.md``):

- pasar de 3-way a 2-way,
- desactivar el requisito de orden de venta/compra, la cuenta puente o la
  conciliación automática,
- permitir diferencias de precio,
- cambiar cualquier tolerancia de precio o cantidad.

En modo Cloud, con revisión independiente activa, esos cambios requieren
la aprobación previa de otro revisor autorizado mediante el flujo de
revisión independiente (``config_change``). Los cambios que no debilitan
controles se aplican de inmediato y quedan auditados por el rastro
transversal de configuraciones sensibles.
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
# Desactivar estos toggles (True -> False) debilita el control activo.
WEAKENING_TOGGLES = {
    "purchase": ("require_purchase_order", "bridge_account_required", "auto_reconcile"),
    "sales": ("require_sales_order",),
}
# Activar estos toggles (False -> True) debilita el control activo.
WEAKENING_FEATURES = {
    "purchase": ("allow_price_difference",),
    "sales": ("allow_price_difference",),
}
WEAKENING_TOLERANCES = {
    "purchase": ("price_tolerance", "qty_tolerance"),
    "sales": ("price_tolerance",),
}
_DECIMAL_FIELDS = frozenset({"price_tolerance_value", "qty_tolerance_value"})


def weakened_fields(model: str, before: dict[str, Any], after: dict[str, Any]) -> list[str]:
    """Devuelve los campos cuyo cambio relaja un control de matching activo."""
    if model not in CONFIG_FIELDS:
        raise ValueError(_("La configuración solicitada no existe."))
    debilitados: set[str] = set()
    if before.get("matching_type") == "3-way" and after.get("matching_type") != "3-way":
        debilitados.add("matching_type")
    debilitados.update(
        field for field in WEAKENING_TOGGLES[model] if before.get(field) is True and after.get(field) is not True
    )
    debilitados.update(
        field for field in WEAKENING_FEATURES[model] if before.get(field) is not True and after.get(field) is True
    )
    for prefijo in WEAKENING_TOLERANCES[model]:
        actual = (before.get(f"{prefijo}_type"), before.get(f"{prefijo}_value"))
        nuevo = (after.get(f"{prefijo}_type"), after.get(f"{prefijo}_value"))
        if actual != nuevo:
            debilitados.add(prefijo)
    return sorted(debilitados)


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

    Devuelve la fila de ``ApprovalRequest`` cuando el cambio debilita
    controles y espera revisión (Cloud), o el objeto de configuración
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
    debilitados = weakened_fields(model, typed_before, typed_after)
    payload = {
        "model": model,
        "before": {field: _plain(value) for field, value in typed_before.items()},
        "after": {field: _plain(value) for field, value in typed_after.items()},
        "weakened_fields": debilitados,
    }
    pending = None
    if debilitados:
        identifier = f"{model}:{company}"
        pending = require_review("config_change", identifier, company, actor_id, payload)
    if pending is None:
        for field, value in typed_after.items():
            setattr(config, field, value)
        database.session.flush()
        return config
    return pending
