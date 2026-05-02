# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Interfaz de linea de comandos."""

# ---------------------------------------------------------------------------------------
# Libreria estandar
# --------------------------------------------------------------------------------------
import sys

# ---------------------------------------------------------------------------------------
# Librerias de terceros
# ---------------------------------------------------------------------------------------
from flask.cli import FlaskGroup

# ---------------------------------------------------------------------------------------
# Recursos locales
# ---------------------------------------------------------------------------------------


# <---------------------------------------------------------------------------------------------> #
# Definición de interfaz de linea de comandos.
LINEA_COMANDOS = FlaskGroup(help="""\
Interfaz de linea de comandos para la administración de Cacao Accounting.
""")


def linea_comandos(as_module=False):
    """Linea de comandos para administración de la aplicacion."""
    LINEA_COMANDOS.main(args=sys.argv[1:], prog_name="python -m flask" if as_module else None)
