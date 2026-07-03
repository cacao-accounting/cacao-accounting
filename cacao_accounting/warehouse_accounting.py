# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William Jose Moreno Reyes
"""Helpers para resolver configuracion contable por almacen y compania."""

from __future__ import annotations

from typing import Any

from sqlalchemy import select

from cacao_accounting.database import WarehouseCompanyAccount, database


def warehouse_inventory_account_id(warehouse_code: str | None, company: str) -> str | None:
    """Obtiene la cuenta de inventario configurada para un almacen en una compania."""
    if not warehouse_code:
        return None
    settings = (
        database.session.execute(
            select(WarehouseCompanyAccount).filter_by(
                warehouse_code=warehouse_code,
                company=company,
                is_active=True,
            )
        )
        .scalars()
        .first()
    )
    if settings and settings.inventory_account_id:
        return str(settings.inventory_account_id)
    return None


def inventory_account_id_for_document_line(document: Any, line: Any, company: str) -> str | None:
    """Resuelve la cuenta de inventario de una linea usando la bodega efectiva."""
    warehouse_code = (
        getattr(line, "warehouse", None)
        or getattr(line, "target_warehouse", None)
        or getattr(line, "source_warehouse", None)
        or getattr(document, "to_warehouse", None)
        or getattr(document, "from_warehouse", None)
    )
    return warehouse_inventory_account_id(str(warehouse_code or "").strip() or None, company)
