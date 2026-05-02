# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Modulo de Ventas."""

from flask import Blueprint, render_template
from flask_login import login_required

from cacao_accounting.decorators import modulo_activo

ventas = Blueprint("ventas", __name__, template_folder="templates")


@ventas.route("/ventas")
@ventas.route("/sales")
@modulo_activo("sales")
@login_required
def ventas_():
    """Modulo de ventas."""
    return render_template("ventas.html")
