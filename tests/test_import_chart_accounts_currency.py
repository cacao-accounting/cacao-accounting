# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1676: la moneda vacía del catálogo importado se normaliza a None."""

from __future__ import annotations

from uuid import uuid4

import pytest

from cacao_accounting.database import Accounts, database
from cacao_accounting.imports.adapters.chart_of_accounts import ChartOfAccountsAdapter


@pytest.mark.parametrize("moneda", ["", "   ", None])
def test_moneda_ausente_o_en_blanco_produce_none(moneda):
    """La celda opcional vacía no se persiste como cadena vacía."""
    documento = ChartOfAccountsAdapter().build_document(
        [{"codigo": "1101", "nombre": "Caja", "moneda": moneda, "clasificacion": "Activo"}],
        {"company_id": "cacao"},
    )

    assert documento.currency is None


def test_moneda_valida_se_conserva_sin_espacios():
    """Un código real conserva su valor, sin espacios accidentales."""
    documento = ChartOfAccountsAdapter().build_document(
        [{"codigo": "1101", "nombre": "Caja", "moneda": " NIO ", "clasificacion": "Activo"}],
        {"company_id": "cacao"},
    )

    assert documento.currency == "NIO"


def test_importacion_persiste_cuenta_sin_moneda(app, entorno_contable):
    """El flujo real de persistencia deja NULL, no una moneda vacía inválida."""
    del entorno_contable
    sufijo = uuid4().hex[:6]
    codigo = f"9{sufijo}"
    adapter = ChartOfAccountsAdapter()
    with app.app_context():
        cuenta = adapter.build_document(
            [
                {
                    "codigo": codigo,
                    "nombre": f"Cuenta importada {sufijo}",
                    "moneda": "",
                    "clasificacion": "Activo",
                }
            ],
            {"company_id": "cacao"},
        )
        adapter.persist_document(cuenta)
        database.session.commit()
        account_id = cuenta.id

    try:
        with app.app_context():
            assert database.session.get(Accounts, account_id).currency is None
    finally:
        with app.app_context():
            database.session.execute(database.delete(Accounts).where(Accounts.id == account_id))
            database.session.commit()
