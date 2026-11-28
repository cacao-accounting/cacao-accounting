# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1790: editar una nota de crédito conserva el tipo del borrador."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest

from cacao_accounting.database import CompanyParty, Party, PurchaseInvoice, database


@pytest.fixture
def nota_credito(app, entorno_contable):
    """Crea una nota de crédito borrador del tipo solicitado."""
    sufijo = uuid4().hex[:8]

    def _crear(credit_note_type: str) -> str:
        with app.app_context():
            proveedor = Party(code=f"PRV-NC-{sufijo}", name=f"Proveedor NC {sufijo}", is_supplier=True)
            database.session.add(proveedor)
            database.session.flush()
            database.session.add(CompanyParty(company="cacao", party_id=proveedor.id, is_active=True))
            factura = PurchaseInvoice(
                company="cacao",
                posting_date=date(2026, 5, 15),
                docstatus=0,
                document_no=f"NC-{sufijo}-{credit_note_type[:4]}",
                supplier_id=proveedor.id,
                supplier_name=proveedor.name,
                document_type="purchase_credit_note",
                credit_note_type=credit_note_type,
                is_return=True,
                transaction_currency="NIO",
                base_currency="NIO",
                exchange_rate=Decimal("1"),
            )
            database.session.add(factura)
            database.session.commit()
            return str(factura.id)

    return _crear


@pytest.mark.parametrize(
    ("tipo", "seleccionado", "no_seleccionado"),
    [
        ("physical_return", "physical_return", "commercial_adjustment"),
        ("commercial_adjustment", "commercial_adjustment", "physical_return"),
    ],
)
def test_editar_nota_credito_preselecciona_su_tipo(authenticated_client, nota_credito, tipo, seleccionado, no_seleccionado):
    """La plantilla marca el tipo persistido, no la primera opción."""
    factura_id = nota_credito(tipo)
    cliente = authenticated_client("admin")

    respuesta = cliente.get(f"/buying/purchase-invoice/{factura_id}/edit")

    assert respuesta.status_code == 200
    cuerpo = respuesta.get_data(as_text=True)
    assert f'value="{seleccionado}" selected' in cuerpo
    assert f'value="{no_seleccionado}" selected' not in cuerpo
