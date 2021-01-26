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
#
# Contributors:
# - William José Moreno Reyes

"""
Modulo de Contabilidad.
"""

from flask import Blueprint, redirect, render_template
from flask_login import login_required
from cacao_accounting.modulos import validar_modulo_activo

contabilidad = Blueprint("contabilidad", __name__, template_folder="templates")


# <------------------------------------------------------------------------------------------------------------------------> #
# Monedas
@contabilidad.route("/currencies")
@login_required
def monedas():
    from cacao_accounting.database import Moneda

    MONEDAS = Moneda.query.order_by(Moneda.id).all()
    return render_template("contabilidad/moneda_lista.html", monedas=MONEDAS)


# <------------------------------------------------------------------------------------------------------------------------> #
# Contabilidad
@contabilidad.route("/contabilidad")
@contabilidad.route("/conta")
@contabilidad.route("/accounts")
@login_required
def conta():
    if validar_modulo_activo("accounting"):
        return render_template("contabilidad.html")
    else:
        redirect("/app")


# <------------------------------------------------------------------------------------------------------------------------> #
# Entidades
@contabilidad.route("/accounts/entities")
@login_required
def entidades():
    from cacao_accounting.database import Entidad

    ENTIDADES = Entidad.query.order_by(Entidad.id).all()
    return render_template("contabilidad/entidad_lista.html", entidades=ENTIDADES)


@contabilidad.route("/accounts/entities/<id_entidad>")
@login_required
def entidad(id_entidad):
    from cacao_accounting.database import Entidad

    registro = Entidad.query.filter_by(id=id_entidad).first()
    return render_template("contabilidad/entidad.html", registro=registro)


@contabilidad.route("/accounts/entities/new", methods=["GET", "POST"])
@login_required
def nueva_entidad():
    from cacao_accounting.contabilidad.forms import FormularioEntidad

    formulario = FormularioEntidad()
    return render_template("contabilidad/entidad_crear.html", form=formulario)


@contabilidad.route("/accounts/entities/edit/<id_entidad>")
@login_required
def editar_entidad(id_entidad):
    from cacao_accounting.contabilidad.forms import FormularioEntidad

    formulario = FormularioEntidad()
    return render_template("contabilidad/entidad_editar.html", form=formulario)


# <------------------------------------------------------------------------------------------------------------------------> #
# Unidades de Negocio
@contabilidad.route("/accounts/units")
@login_required
def unidades():
    from cacao_accounting.database import Unidad

    UNIDADES = Unidad.query.order_by(Unidad.entidad).all()
    return render_template("contabilidad/unidad_lista.html", unidades=UNIDADES)


@contabilidad.route("/accounts/unit/<id_unidad>")
@login_required
def unidad(id_unidad):
    from cacao_accounting.database import Unidad

    registro = Unidad.query.filter_by(id=id_unidad).first()
    return render_template("contabilidad/unidad.html", registro=registro)


@contabilidad.route("/accounts/units/new")
@login_required
def nueva_unidad():
    return render_template("contabilidad/unidad_crear.html")


# <------------------------------------------------------------------------------------------------------------------------> #
# Cuentas Contables
@contabilidad.route("/accounts/accounts")
@login_required
def cuentas():
    from cacao_accounting.database import Cuentas

    catalogo = Cuentas.query.order_by(Cuentas.codigo).all()
    return render_template("contabilidad/cuenta_lista.html", catalogo=catalogo)


@contabilidad.route("/accounts/accounts/<id_cta>")
@login_required
def cuenta(id_cta):
    from cacao_accounting.database import Cuentas

    registro = Cuentas.query.filter_by(codigo=id_cta).first()
    return render_template("contabilidad/cuenta.html", registro=registro)


# <------------------------------------------------------------------------------------------------------------------------> #
# Centros de Costos
@contabilidad.route("/accounts/ccenter")
@login_required
def ccostos():
    return render_template("contabilidad/ccostos.html")


# <------------------------------------------------------------------------------------------------------------------------> #
# Proyectos
@contabilidad.route("/accounts/projects")
@login_required
def proyectos():
    return render_template("contabilidad/proyecto_lista.html")


# <------------------------------------------------------------------------------------------------------------------------> #
# Tipos de Cambio
@contabilidad.route("/accounts/exchange")
@login_required
def tasa_cambio():
    return render_template("contabilidad/tc.html")
