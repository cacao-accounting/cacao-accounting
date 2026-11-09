# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Cada herramienta conserva esquemas independientes.

Escenario de negocio (issue #2179): todas las herramientas sin
``response_schema`` compartían ``_DEFAULT_RESPONSE_SCHEMA``, y el decorador
guardaba por referencia los esquemas recibidos. Modificar el contrato de una
herramienta alteraba el de otras.
"""

from __future__ import annotations

from uuid import uuid4

from cacao_accounting.query_tools.decorators import query_tool
from cacao_accounting.query_tools.registry import registry


def _registrar(nombre: str, **kwargs) -> object:
    @query_tool(nombre, "Herramienta de prueba", **kwargs)
    def handler(context):  # pragma: no cover - no se ejecuta
        return {}

    return handler


def test_el_esquema_por_defecto_no_se_comparte_entre_herramientas():
    """Dos tools sin response_schema tienen diccionarios distintos."""
    sufijo = uuid4().hex
    herramienta_a = _registrar(f"probe.a.{sufijo}")
    herramienta_b = _registrar(f"probe.b.{sufijo}")

    assert herramienta_a.response_schema is not herramienta_b.response_schema
    assert herramienta_a.response_schema["properties"] is not herramienta_b.response_schema["properties"]

    herramienta_a.response_schema["properties"]["injected"] = {"type": "string"}
    assert "injected" not in herramienta_b.response_schema["properties"]


def test_el_decorador_copia_los_esquemas_recibidos():
    """Mutar el diccionario original no cambia el contrato registrado."""
    sufijo = uuid4().hex
    original = {"type": "object", "properties": {"filters": {"type": "array"}}}
    herramienta = _registrar(f"probe.copy.{sufijo}", parameters_schema=original)

    original["properties"]["injected"] = {"type": "string"}

    assert "injected" not in herramienta.parameters_schema["properties"]


def test_el_registro_entrega_copias_del_contrato():
    """Un consumidor no puede alterar el descriptor almacenado."""
    sufijo = uuid4().hex
    nombre = f"probe.registry.{sufijo}"
    _registrar(nombre)

    copia = registry.get(nombre)
    copia.response_schema["properties"]["injected"] = {"type": "string"}

    assert "injected" not in registry.get(nombre).response_schema["properties"]
