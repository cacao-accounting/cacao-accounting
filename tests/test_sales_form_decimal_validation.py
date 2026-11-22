# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 William José Moreno Reyes

"""Regresión #1544: ventas rechaza tarifas y cantidades no finitas."""

from __future__ import annotations

from decimal import Decimal
from uuid import uuid4

import pytest

from cacao_accounting.database import SalesRequest, database
from cacao_accounting.ventas.services import _form_decimal

DECIMALES_INVALIDOS = [
    ("qty_0", "abc", "válido"),
    ("qty_0", "NaN", "finito"),
    ("qty_0", "Infinity", "finito"),
    ("qty_0", "-Infinity", "finito"),
    ("rate_0", "abc", "válido"),
    ("rate_0", "NaN", "finito"),
    ("rate_0", "Infinity", "finito"),
]


@pytest.mark.parametrize(("campo", "valor", "mensaje"), DECIMALES_INVALIDOS)
def test_decimal_invalido_se_convierte_en_validacion(app, campo, valor, mensaje):
    """Sintaxis inválida o valores no finitos no escapan como InvalidOperation."""
    with app.test_request_context("/", method="POST", data={campo: valor}):
        with pytest.raises(ValueError, match=mensaje):
            _form_decimal(campo)


def test_decimal_valido_se_conserva(app):
    """Un valor finito conserva su precisión."""
    with app.test_request_context("/", method="POST", data={"rate_0": "12.75"}):
        assert _form_decimal("rate_0") == Decimal("12.75")


def _datos_linea(marcador: str, campo: str, valor: str) -> dict:
    return {
        "company": "cacao",
        "currency": "NIO",
        "posting_date": "2026-05-15",
        "remarks": marcador,
        "item_code_0": "ART01",
        "qty_0": "1",
        "rate_0": "10",
        campo: valor,
    }


@pytest.mark.parametrize(("campo", "valor", "mensaje"), DECIMALES_INVALIDOS)
def test_alta_pedido_venta_rechaza_tarifa_no_finita(app, entorno_contable, authenticated_client, campo, valor, mensaje):
    """El POST real devuelve validación y no persiste el pedido."""
    marcador = f"DEC-SV-{uuid4().hex[:8]}"
    respuesta = authenticated_client().post("/sales/sales-request/new", data=_datos_linea(marcador, campo, valor))

    assert respuesta.status_code == 200
    assert mensaje in respuesta.get_data(as_text=True)
    with app.app_context():
        assert (
            database.session.execute(database.select(SalesRequest.id).filter_by(remarks=marcador)).scalar_one_or_none() is None
        )
