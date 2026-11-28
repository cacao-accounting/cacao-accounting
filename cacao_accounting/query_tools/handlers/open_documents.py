# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Paginación de documentos cuyo saldo vigente es positivo.

``status`` es un campo mutable que puede quedar desincronizado del saldo
canónico; las herramientas de documentos abiertos paginan sobre el saldo
calculado y no sobre el estado almacenado (#1127).
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from cacao_accounting.database import database
from cacao_accounting.document_flow.service import compute_outstanding_amount


def paginate_positive_outstanding(
    *,
    model: Any,
    query: Any,
    page: int,
    page_size: int,
) -> tuple[int, list[tuple[Any, Decimal]]]:
    """Devuelve el total y la página de documentos con saldo abierto.

    Recorre el universo ya filtrado (compañía, tercero y estado) calculando el
    saldo canónico de cada documento. Solo cuenta y pagina los saldos mayores
    que cero, de modo que una factura liquidada no aparece como abierta ni
    infla ``total_items``.
    """
    start = (page - 1) * page_size
    total = 0
    page_rows: list[tuple[Any, Decimal]] = []
    ordered = query.order_by(model.posting_date.desc(), model.id)
    result = database.session.execute(ordered.execution_options(yield_per=200)).scalars()
    for document in result:
        outstanding = compute_outstanding_amount(document)
        if outstanding <= 0:
            continue
        if start <= total < start + page_size:
            page_rows.append((document, outstanding))
        total += 1
    return total, page_rows
