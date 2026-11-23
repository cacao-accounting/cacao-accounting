# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1943: el preview fiscal con errores no se presenta como éxito."""

from __future__ import annotations

from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]


def test_el_endpoint_no_oculta_los_errores_del_motor():
    """La API responde 422 cuando el resultado trae errors."""
    fuente = (RAIZ / "cacao_accounting" / "api" / "__init__.py").read_text(encoding="utf-8")

    assert 'if result.get("errors"):' in fuente
    assert "return jsonify(result), 422" in fuente


def test_el_formulario_muestra_los_errores_del_preview():
    """El JS no descarta el arreglo errors de la respuesta."""
    js = (RAIZ / "cacao_accounting" / "static" / "js" / "transaction-form.js").read_text(encoding="utf-8")

    assert "data?.errors" in js or "data.errors" in js
