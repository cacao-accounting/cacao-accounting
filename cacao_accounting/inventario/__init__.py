# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes


"""Modulo de Inventarios."""

from flask import Blueprint, render_template
from flask_login import login_required

from cacao_accounting.decorators import modulo_activo

inventario = Blueprint("inventario", __name__, template_folder="templates")


@inventario.route("/inventario")
@inventario.route("/inventory")
@modulo_activo("inventory")
@login_required
def inventario_():
    """Definición de vista principal de inventarios."""
    return render_template("inventario.html")
