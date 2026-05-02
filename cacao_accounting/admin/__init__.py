# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Modulo administrativo."""

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

admin = Blueprint("admin", __name__, template_folder="templates")


@admin.route("/admin")
@admin.route("/ajustes")
@admin.route("/administracion")
@admin.route("/configuracion")
@admin.route("/settings")
@login_required
@modulo_activo("admin")
def admin_():
    """Definición del modulo administrativo."""
    return render_template("admin.html")


@admin.route("/settings/modules")
@login_required
@modulo_activo("admin")
def lista_modulos():
    """Define vista para listar modulos del sistema."""
    return render_template("admin/modulos.html")
