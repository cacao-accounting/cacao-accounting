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

from flask import Blueprint, redirect, render_template, request
from flask_login import login_required
from cacao_accounting.consultas import paginar_consulta
from cacao_accounting.metadata import APPNAME
from cacao_accounting.modulos import validar_modulo_activo

contabilidad = Blueprint("contabilidad", __name__, template_folder="templates")


# <------------------------------------------------------------------------------------------------------------------------> #
# Monedas
@contabilidad.route("/currencies")
@login_required
def monedas():
    from cacao_accounting.database import Moneda

    PAGE = request.args.get("page", default=1, type=int)
    RESULTADO = paginar_consulta(tabla=Moneda)
    PAGINA = RESULTADO.page(PAGE)
    TITULO = "Monedas" + " - " + APPNAME
    return render_template("contabilidad/moneda_lista.html", resultado=RESULTADO, pagina=PAGINA, titulo=TITULO)


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

    PAGE = request.args.get("page", default=1, type=int)
    RESULTADO = paginar_consulta(tabla=Entidad)
    PAGINA = RESULTADO.page(PAGE)
    return render_template("contabilidad/entidad_lista.html", resultado=RESULTADO, pagina=PAGINA, statusweb=Entidad.status_web)


@contabilidad.route("/accounts/entity/<id_entidad>")
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

    PAGE = request.args.get("page", default=1, type=int)
    RESULTADO = paginar_consulta(tabla=Unidad)
    PAGINA = RESULTADO.page(PAGE)
    return render_template("contabilidad/unidad_lista.html", resultado=RESULTADO, pagina=PAGINA)


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
    from cacao_accounting.database import CentroCosto

    PAGE = request.args.get("page", default=1, type=int)
    RESULTADO = paginar_consulta(tabla=CentroCosto)
    PAGINA = RESULTADO.page(PAGE)
    return render_template("contabilidad/centro-costo_lista.html", resultado=RESULTADO, pagina=PAGINA)


# <------------------------------------------------------------------------------------------------------------------------> #
# Proyectos
@contabilidad.route("/accounts/projects")
@login_required
def proyectos():
    from cacao_accounting.database import CentroCosto

    PAGE = request.args.get("page", default=1, type=int)
    RESULTADO = paginar_consulta(tabla=CentroCosto)
    PAGINA = RESULTADO.page(PAGE)
    return render_template("contabilidad/proyecto_lista.html", resultado=RESULTADO, pagina=PAGINA)


# <------------------------------------------------------------------------------------------------------------------------> #
# Tipos de Cambio
@contabilidad.route("/accounts/exchange")
@login_required
def tasa_cambio():
    from cacao_accounting.database import TasaDeCambio

    PAGE = request.args.get("page", default=1, type=int)
    RESULTADO = paginar_consulta(tabla=TasaDeCambio)
    PAGINA = RESULTADO.page(PAGE)
    return render_template("contabilidad/tc_lista.html", resultado=RESULTADO, pagina=PAGINA)
