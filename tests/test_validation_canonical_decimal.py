# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""La huella pública es estable ante la escala Decimal.

Escenario de negocio (issue #2019): SQLite devuelve 125.50 como 125.5000
después de persistir y releer. El payload y el SHA256 cambiaban, y la ruta
pública marcaba «Datos inconsistentes» para un documento intacto.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from cacao_accounting.database import SalesInvoice, database
from cacao_accounting.printing.validation import (
    ValidationService,
    calculate_validation_hash,
    get_canonical_payload,
)

FECHA = date(2026, 10, 15)


def _hash(grand_total: Decimal) -> str:
    payload = get_canonical_payload(
        {
            "company_code": "cacao",
            "document_type": "sales_invoice",
            "document_id": "INV-1",
            "document_number": "INV-1",
            "document_date": FECHA,
            "currency": "NIO",
            "grand_total": grand_total,
            "status": "posted",
            "line_count": 1,
        }
    )
    return calculate_validation_hash(payload)


def test_la_misma_escala_monetaria_produce_la_misma_huella():
    """Los ceros finales no cambian el hash."""
    assert _hash(Decimal("125.50")) == _hash(Decimal("125.5000"))
    assert _hash(Decimal("125.5")) == _hash(Decimal("125.50"))
    assert get_canonical_payload({"grand_total": Decimal("125.5000")}) == '{"grand_total":"125.5"}'


def test_los_importes_distintos_conservan_hashes_distintos():
    """La canonicalización no oculta diferencias monetarias reales."""
    assert _hash(Decimal("125.50")) != _hash(Decimal("125.51"))
    assert _hash(Decimal("-10.00")) != _hash(Decimal("10.00"))
    assert get_canonical_payload({"grand_total": Decimal("-0.0000")}) == '{"grand_total":"0"}'


def test_persistir_y_releer_conserva_la_huella(app):
    """La recarga de SQLite no cambia el hash del mismo documento."""
    with app.app_context():
        factura = SalesInvoice(
            company="cacao",
            posting_date=FECHA,
            docstatus=1,
            document_no="INV-125",
            transaction_currency="NIO",
            grand_total=Decimal("125.50"),
        )
        database.session.add(factura)
        database.session.commit()
        factura_id = factura.id

        servicio = ValidationService()
        antes = calculate_validation_hash(get_canonical_payload(servicio.extract_document_data(factura)))

        database.session.expire_all()
        recargada = database.session.get(SalesInvoice, factura_id)
        assert recargada is not None
        despues = calculate_validation_hash(get_canonical_payload(servicio.extract_document_data(recargada)))

        assert despues == antes
