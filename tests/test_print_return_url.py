# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""La URL de retorno de la vista previa debe ser interna.

Escenario de negocio (issue #1923): ``_safe_return_url`` aceptaba
``/\\evil.example/path``. El navegador normaliza esa ruta a un destino externo
al pulsar «Volver al comprobante».
"""

from __future__ import annotations

import pytest

from cacao_accounting.printing.routes import _safe_return_url


def test_conserva_una_ruta_interna_valida(app):
    """Una ruta interna con query se mantiene."""
    with app.test_request_context("/"):
        assert _safe_return_url("/sales/sales-request/ABC?tab=lines") == "/sales/sales-request/ABC?tab=lines"


@pytest.mark.parametrize(
    "destino",
    [
        "https://evil.example/path",
        "//evil.example/path",
        r"/\evil.example/path",
        "/\\\\evil.example/path",
        "/%5C%5Cevil.example/path",
        "/ruta\x00/evil",
        "",
        None,
    ],
)
def test_rechaza_destinos_externos_o_manipulados(app, destino):
    """Esquemas, host, barras invertidas y controles caen al inicio."""
    with app.test_request_context("/"):
        resultado = _safe_return_url(destino)

        assert resultado != destino or destino in ("", None)
        assert resultado.startswith("/")
        assert not resultado.startswith("//")
        assert "\\" not in resultado
