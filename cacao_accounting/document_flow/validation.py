# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William Jose Moreno Reyes

"""Validaciones pre-submit para documentos transaccionales.

Refs: #758

El contrato de moneda exige que cada documento aprobable tenga moneda
transaccional y snapshot de moneda base persistidos. Este modulo concentra
la validacion previa al submit; los servicios de cada dominio la invocan
antes de cambiar el ``docstatus``.
"""

from typing import Any, Iterable

from cacao_accounting.database import DocumentRelation, database
from cacao_accounting.document_flow import DocumentFlowError


def _collect_currency_sources(registro: Any) -> list[Any]:
    """Devuelve los documentos origen asociados a un documento via relaciones activas."""
    target_type = getattr(registro, "voucher_type", None) or type(registro).__tablename__
    target_id = str(getattr(registro, "id", "") or "")
    if not target_id:
        return []
    rows = (
        database.session.execute(
            database.select(DocumentRelation).filter_by(
                target_type=target_type,
                target_id=target_id,
                status="active",
            )
        )
        .scalars()
        .all()
    )
    sources: list[Any] = []
    for row in rows:
        source = getattr(row, "source", None)
        if source is not None:
            sources.append(source)
    return sources


def validate_currency_contract(registro: Any, *, context: str = "documento") -> None:
    """Valida el contrato de moneda explicita previo al submit.

    Reglas:

    - ``transaction_currency`` no vacia en el documento persistido.
    - ``base_currency`` snapshot presente y consistente con la compania.
    - Si hay origenes de Document Flow, todos comparten la misma moneda
      transaccional; en caso contrario se rechaza antes de crear GL/SLE.
    """
    from cacao_accounting.document_flow.currency_resolver import (
        assert_base_currency_snapshot,
        assert_currency_explicit,
        validate_flow_currency_homogeneity,
    )

    assert_currency_explicit(registro, context=context)
    assert_base_currency_snapshot(registro, company=getattr(registro, "company", None), context=context)
    sources = _collect_currency_sources(registro)
    if sources:
        inherited = validate_flow_currency_homogeneity(sources)
        document_currency = str(getattr(registro, "transaction_currency", "") or "")
        if inherited and inherited != document_currency:
            raise DocumentFlowError(
                f"La moneda del {context} ({document_currency!r}) no coincide con la moneda "
                f"heredada de Document Flow ({inherited!r}).",
                400,
            )


def assert_currency_contract_or_raise(
    registro: Any,
    *,
    context: str = "documento",
    sources: Iterable[Any] | None = None,
) -> None:
    """Variante con fuentes externas; util cuando el documento aun no fue persistido.

    Permite a las pruebas y a las rutas que derivan documentos validar el
    contrato de moneda antes de que la relacion DocumentRelation haya sido
    persistida. Si ``sources`` es ``None`` se calcula desde las relaciones
    activas del registro.
    """
    from cacao_accounting.document_flow.currency_resolver import (
        assert_base_currency_snapshot,
        assert_currency_explicit,
        validate_flow_currency_homogeneity,
    )

    assert_currency_explicit(registro, context=context)
    assert_base_currency_snapshot(registro, company=getattr(registro, "company", None), context=context)
    resolved_sources = list(sources) if sources is not None else _collect_currency_sources(registro)
    if resolved_sources:
        inherited = validate_flow_currency_homogeneity(resolved_sources)
        document_currency = str(getattr(registro, "transaction_currency", "") or "")
        if inherited and inherited != document_currency:
            raise DocumentFlowError(
                f"La moneda del {context} ({document_currency!r}) no coincide con la moneda "
                f"heredada de Document Flow ({inherited!r}).",
                400,
            )


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


def require_line_relations(*, target_type: str, target_id: str, source_type: str, source_id: str, items: list[Any]) -> None:
    """Exige una relación activa por cada línea cuando existe un documento origen."""
    relations = (
        database.session.execute(
            database.select(DocumentRelation).filter_by(
                target_type=target_type,
                target_id=target_id,
                source_type=source_type,
                source_id=source_id,
                status="active",
            )
        )
        .scalars()
        .all()
    )
    expected_item_ids = {str(item.id) for item in items}
    relation_item_ids = {str(relation.target_item_id) for relation in relations if relation.target_item_id}
    if len(relations) != len(items) or relation_item_ids != expected_item_ids:
        raise ValueError(
            "Cada línea debe conservar una relación activa con el documento origen " f"({source_type}:{source_id})."
        )


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
