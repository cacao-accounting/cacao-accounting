# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1668: el catálogo importado valida clasificación y tipo de cuenta."""

from __future__ import annotations

from cacao_accounting.imports.adapters.chart_of_accounts import ChartOfAccountsAdapter


def _fila(**overrides):
    row = {
        "codigo": "1101",
        "nombre": "Caja",
        "clasificacion": "activo",
        "tipo": "cash",
    }
    row.update(overrides)
    return row


def test_rechaza_clasificacion_y_tipo_fuera_del_dominio():
    """Valores arbitrarios no llegan a persistirse en Accounts."""
    errores = ChartOfAccountsAdapter().validate_document(
        [_fila(clasificacion="not-a-class", tipo="made_up")], {"company_id": "cacao"}
    )

    assert errores == [
        "Clasificación no permitida para cuentas contables.",
        "Tipo de cuenta no permitido para cuentas contables.",
    ]


def test_acepta_clasificacion_y_tipo_reconocidos():
    """El dominio del formulario manual sigue disponible en la importación."""
    assert ChartOfAccountsAdapter().validate_document([_fila()], {"company_id": "cacao"}) == []


def test_campos_opcionales_vacios_no_fallan():
    """Clasificación y tipo admiten ausencia como en el alta manual."""
    assert ChartOfAccountsAdapter().validate_document([_fila(clasificacion="", tipo="  ")], {"company_id": "cacao"}) == []


def test_build_document_normaliza_el_tipo():
    """El tipo se guarda en minúsculas canónicas y el vacío queda en None."""
    adapter = ChartOfAccountsAdapter()
    normalizado = adapter.build_document([_fila(tipo=" ASSET ")], {"company_id": "cacao"})
    vacio = adapter.build_document([_fila(tipo="")], {"company_id": "cacao"})

    assert normalizado.account_type == "asset"
    assert vacio.account_type is None
