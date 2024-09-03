# Copyright 2020 William José Moreno Reyes
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

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
    from cacao_accounting.database import Entidad, database

    ENTIDADES = database.session.execute(database.select(Entidad).order_by(Entidad.predeterminada)).all()
    INICIO_PERIODO = None  # yyyy-mm-dd

    return render_template("gl_new.html", entidades=ENTIDADES, inicio_periodo=INICIO_PERIODO)
