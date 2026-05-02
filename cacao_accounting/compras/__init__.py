# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Modulo de Compras."""

# ---------------------------------------------------------------------------------------
# Libreria estandar
# --------------------------------------------------------------------------------------

# ---------------------------------------------------------------------------------------
# Librerias de terceros
# ---------------------------------------------------------------------------------------
from flask import Blueprint, render_template
from flask_login import login_required

# ---------------------------------------------------------------------------------------
# Recursos locales
# ---------------------------------------------------------------------------------------
from cacao_accounting.decorators import modulo_activo

# < --------------------------------------------------------------------------------------------- >
compras = Blueprint("compras", __name__, template_folder="templates")


@compras.route("/compras")
@compras.route("/buying")
@modulo_activo("buying")
@login_required
def compras_():
    """Pantalla principal del modulo de compras."""
    return render_template("compras.html")
