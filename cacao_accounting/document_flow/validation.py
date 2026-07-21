# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William Jose Moreno Reyes

"""Validaciones pre-submit para documentos transaccionales."""


def _validate_basic_document_fields(registro):
    """Valida campos basicos del documento (compania y fecha)."""
    if not registro.company:
        raise ValueError("El documento debe tener una compania.")
    if not registro.posting_date:
        raise ValueError("El documento debe tener una fecha de contabilizacion.")


def _validate_party(registro):
    """Valida que el documento tenga un cliente o proveedor."""
    party_id = getattr(registro, "supplier_id", None) or getattr(registro, "customer_id", None)
    if not party_id:
        raise ValueError("El documento debe tener un cliente o proveedor.")


def _validate_item_quantities(items):
    """Valida que todas las cantidades sean mayores a cero."""
    for item in items:
        if getattr(item, "qty", 0) <= 0:
            raise ValueError("Todas las cantidades deben ser mayores a cero.")


def _validate_item_rates(items):
    """Valida que todas las tarifas sean mayores a cero."""
    for item in items:
        if getattr(item, "rate", 0) <= 0:
            raise ValueError("Todas las tarifas deben ser mayores a cero.")


def _validate_item_amounts(items):
    """Valida que los montos no sean cero."""
    for item in items:
        if getattr(item, "amount", 0) == 0:
            raise ValueError("Los montos no pueden ser cero.")


def _validate_warehouse_assignments(items, warehouse_for_stock_items_only):
    """Valida que las lineas tengan almacen asignado."""
    for item in items:
        is_stock_item = getattr(item, "is_stock_item", True)
        if warehouse_for_stock_items_only and not is_stock_item:
            continue
        wh = (
            getattr(item, "warehouse", None)
            or getattr(item, "source_warehouse", None)
            or getattr(item, "target_warehouse", None)
        )
        if not wh:
            item_code = getattr(item, "item_code", "desconocido")
            raise ValueError(f"La linea del articulo {item_code} requiere un almacen asignado.")


def validate_submit_prerequisites(
    registro,
    items=None,
    *,
    require_party=True,
    require_lines=True,
    require_qty_positive=True,
    require_rate_positive=True,
    require_amount_nonzero=False,
    require_warehouse=False,
    warehouse_for_stock_items_only=True,
):
    """Valida requisitos comunes antes de aprobar un documento.

    Args:
        registro: El documento a validar (instancia de DocBase).
        items: Lista de items/lineas del documento (opcional).
        require_party: Si se requiere proveedor o cliente.
        require_lines: Si se requiere al menos una linea.
        require_qty_positive: Si las cantidades deben ser > 0.
        require_rate_positive: Si las tarifas (rate) deben ser > 0.
        require_amount_nonzero: Si los montos (amount) no deben ser cero.
        require_warehouse: Si se requiere que las lineas tengan almacen asignado.
        warehouse_for_stock_items_only: Si el almacen solo se exige a articulos
            de inventario (is_stock_item=True). Los servicios lo omiten.

    Raises:
        ValueError: Si alguna validacion falla.
    """
    _validate_basic_document_fields(registro)
    if require_party:
        _validate_party(registro)
    if require_lines:
        if items is None or len(items) == 0:
            raise ValueError("El documento debe tener al menos una linea de detalle.")
        if require_qty_positive:
            _validate_item_quantities(items)
        if require_rate_positive:
            _validate_item_rates(items)
        if require_amount_nonzero:
            _validate_item_amounts(items)
    if require_warehouse and items:
        _validate_warehouse_assignments(items, warehouse_for_stock_items_only)
