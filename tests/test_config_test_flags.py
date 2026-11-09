# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Claves de configuración activas en el entorno de pruebas.

Escenario de negocio (issue #2102): el bloque de ``CACAO_TEST`` escribía la
clave ``DEGUG`` (typo) y dejaba ``TEMPLATES_AUTO_RELOAD`` como cadena. Flask
ignoraba ambas, de modo que el modo debug declarado nunca se aplicaba.
"""

from __future__ import annotations

import os
import subprocess
import sys

SCRIPT = (
    "from cacao_accounting.config import configuracion;"
    "print(repr(configuracion.get('DEBUG')));"
    "print(repr(configuracion.get('TEMPLATES_AUTO_RELOAD')));"
    "print('DEGUG' in configuracion)"
)


def test_cacao_test_configura_claves_validas_y_booleanas():
    """El proceso de importación usa DEBUG como booleano y sin la clave errónea."""
    entorno = {**os.environ, "CACAO_TEST": "True"}
    resultado = subprocess.run(
        [sys.executable, "-c", SCRIPT],
        capture_output=True,
        text=True,
        env=entorno,
        timeout=120,
    )

    assert resultado.returncode == 0, resultado.stderr
    debug, auto_reload, typo = resultado.stdout.split()
    assert debug == "True"
    assert auto_reload == "True"
    assert typo == "False"
