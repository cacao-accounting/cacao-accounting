# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#2149: la fachada de contabilidad conserva imports históricos y wildcard."""

from __future__ import annotations

import importlib

from cacao_accounting.audit_trail_service import log_submit

contabilidad = importlib.import_module("cacao_accounting.contabilidad")


def test_log_submit_se_importa_desde_la_fachada():
    """El símbolo histórico sigue disponible por import nombrado."""
    assert contabilidad.log_submit is log_submit
    assert "log_submit" in contabilidad.__all__


def test_wildcard_expone_los_simbolos_publicos_historicos():
    """`from ... import *` incluye los símbolos de servicios y rutas."""
    namespace: dict[str, object] = {}
    exec("from cacao_accounting.contabilidad import *", namespace)

    assert namespace["log_submit"] is log_submit
    assert "contabilidad" in namespace
    assert "nuevo_comprobante" in namespace
    assert not any(name.startswith("_") for name in namespace if name != "__builtins__")
