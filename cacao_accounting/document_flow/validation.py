# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William Jose Moreno Reyes

"""Validaciones pre-submit para documentos transaccionales."""


def validate_submit_prerequisites(
    registro,
    items=None,
    *,
    require_party=True,
    require_lines=True,
    require_qty_positive=True,
    require_rate_positive=True,
    require_amount_nonzero=True,
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
    if not registro.company:
        raise ValueError("El documento debe tener una compania.")
    if not registro.posting_date:
        raise ValueError("El documento debe tener una fecha de contabilizacion.")
    if require_party:
        party_id = getattr(registro, "supplier_id", None) or getattr(registro, "customer_id", None)
        if not party_id:
            raise ValueError("El documento debe tener un cliente o proveedor.")
    if require_lines:
        if items is None or len(items) == 0:
            raise ValueError("El documento debe tener al menos una linea de detalle.")
        if require_qty_positive:
            for item in items:
                if getattr(item, "qty", 0) <= 0:
                    raise ValueError("Todas las cantidades deben ser mayores a cero.")
        if require_rate_positive:
            for item in items:
                if getattr(item, "rate", 0) <= 0:
                    raise ValueError("Todas las tarifas deben ser mayores a cero.")
        if require_amount_nonzero:
            for item in items:
                if getattr(item, "amount", 0) == 0:
                    raise ValueError("Los montos no pueden ser cero.")
    if require_warehouse and items:
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
