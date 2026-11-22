# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1973: la macro compartida no declara parámetros sin efecto."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[1] / "cacao_accounting"
MACROS = RAIZ / "templates" / "transaction_form_macros.html"
RETIRADOS = ("items_disponibles", "uoms_disponibles", "source_label", "warehouses_disponibles")
PATRON_FIRMA = re.compile(r"{%\s*macro\s+transaction_grid\((?P<args>[^)]*)\)\s*%}")
PATRON_LLAMADA = re.compile(r"transaction_grid\((?P<args>[^)]*)\)", re.DOTALL)


def _firma() -> str:
    """Devuelve la lista de argumentos declarada por la macro."""
    coincidencia = PATRON_FIRMA.search(MACROS.read_text(encoding="utf-8"))
    assert coincidencia is not None
    return coincidencia.group("args")


def _argumentos_de_llamada(texto: str) -> list[str]:
    """Extrae los argumentos de todas las invocaciones de la macro."""
    return [coincidencia.group("args") for coincidencia in PATRON_LLAMADA.finditer(texto)]


def _consumidores() -> list[Path]:
    """Devuelve las plantillas que invocan la macro compartida."""
    consumidores: list[Path] = []
    for plantilla in RAIZ.rglob("*.html"):
        if plantilla == MACROS:
            continue
        if "transaction_grid(" in plantilla.read_text(encoding="utf-8", errors="ignore"):
            consumidores.append(plantilla)
    return consumidores


def test_la_firma_conserva_solo_los_parametros_consumidos():
    """`source_api_url` y `title` se usan; los cuatro argumentos inertes no vuelven."""
    firma = _firma()
    assert "source_api_url" in firma
    assert "title" in firma
    for retirado in RETIRADOS:
        assert retirado not in firma


def test_ningun_consumidor_envia_los_parametros_retirados():
    """Todas las invocaciones de Ventas, Compras e Inventario usan el contrato vigente."""
    for plantilla in _consumidores():
        texto = plantilla.read_text(encoding="utf-8", errors="ignore")
        invocaciones = _argumentos_de_llamada(texto)
        assert invocaciones, f"{plantilla} no declara invocaciones reconocibles"
        for argumentos in invocaciones:
            for retirado in RETIRADOS:
                assert f"{retirado}=" not in argumentos, f"{plantilla} conserva {retirado}"


def test_todos_los_consumidores_compilan_en_jinja(app):
    """Cada plantilla que invoca la macro es válida para el entorno Jinja."""
    with app.app_context():
        for plantilla in _consumidores():
            partes = plantilla.parts
            nombre = "/".join(partes[partes.index("templates") + 1 :])
            app.jinja_env.get_template(nombre)


def test_la_macro_compila_en_jinja(app):
    """La firma simplificada es válida para el entorno Jinja de la aplicación."""
    with app.app_context():
        app.jinja_env.get_template("transaction_form_macros.html")


@pytest.mark.parametrize(
    "ruta",
    [
        "/sales/sales-request/new",
        "/buying/purchase-order/new",
        "/inventory/stock-entry/material-receipt/new",
    ],
)
def test_formularios_representativos_renderizan(app, entorno_contable, authenticated_client, ruta):
    """Los tres módulos que comparten la macro siguen respondiendo 200."""
    response = authenticated_client().get(ruta)
    assert response.status_code == 200
    assert b"Internal Server Error" not in response.data
