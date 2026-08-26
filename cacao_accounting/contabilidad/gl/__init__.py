# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Comprobante Contable."""

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
from cacao_accounting.decorators import modulo_activo, verifica_acceso

gl = Blueprint("gl", __name__, static_folder="static", template_folder="templates")


@login_required
@modulo_activo("accounting")
@verifica_acceso("accounting")
@gl.route("/list")
def gl_list():
    """Lista de Comprobantes Contables."""
    return render_template("gl_lista.html")


@login_required
@modulo_activo("accounting")
@verifica_acceso("accounting")
@gl.route("/new")
def gl_new():
    """Lista de Comprobantes Contables."""
    from cacao_accounting.contabilidad.auxiliares import obtener_lista_entidades_por_id_razonsocial

    INICIO_PERIODO = None  # yyyy-mm-dd

    return render_template(
        "gl_new.html",
        entidades=obtener_lista_entidades_por_id_razonsocial(),
        inicio_periodo=INICIO_PERIODO,
    )
