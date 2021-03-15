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
    TITULO = "Listado de Monedas - " + " - " + APPNAME
    return render_template("contabilidad/moneda_lista.html", resultado=RESULTADO, pagina=PAGINA, titulo=TITULO)


# <------------------------------------------------------------------------------------------------------------------------> #
# Contabilidad
@contabilidad.route("/contabilidad")
@contabilidad.route("/conta")
@contabilidad.route("/accounts")
@login_required
def conta():
    TITULO = "Módulo Contabilidad - " + APPNAME
    if validar_modulo_activo("accounting"):
        return render_template("contabilidad.html", titulo=TITULO)
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
    TITULO = "Listado de Entidades - " + APPNAME
    return render_template(
        "contabilidad/entidad_lista.html", titulo=TITULO, resultado=RESULTADO, pagina=PAGINA, statusweb=Entidad.status_web
    )


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
    TITULO = "Crear Nueva Entidad - " + APPNAME
    if formulario.validate_on_submit():
        from cacao_accounting.contabilidad.registros.entidad import RegistroEntidad

        e = RegistroEntidad()
        DATA = {
            "id": formulario.id.data,
            "razon_social": formulario.razon_social.data,
            "nombre_comercial": formulario.nombre_comercial.data,
            "id_fiscal": formulario.id_fiscal.data,
            "moneda": formulario.moneda.data,
            "tipo_entidad": formulario.tipo_entidad.data,
            "correo_electronico": formulario.correo_electronico.data,
            "web": formulario.web.data,
            "telefono1": formulario.telefono1.data,
            "telefono2": formulario.telefono2.data,
            "fax": formulario.fax.data,
            "status": "activa",
        }
        e.crear_entidad(datos=DATA)
        return redirect("/accounts/entities")

    return render_template("contabilidad/entidad_crear.html", form=formulario, titulo=TITULO)


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
    TITULO = "Listado de Unidades de Negocio - " + APPNAME
    return render_template(
        "contabilidad/unidad_lista.html", titulo=TITULO, resultado=RESULTADO, pagina=PAGINA, statusweb=Unidad.status_web
    )


@contabilidad.route("/accounts/unit/<id_unidad>")
@login_required
def unidad(id_unidad):
    from cacao_accounting.database import Unidad

    registro = Unidad.query.filter_by(id=id_unidad).first()
    return render_template("contabilidad/unidad.html", registro=registro)


@contabilidad.route("/accounts/units/new", methods=["GET", "POST"])
@login_required
def nueva_unidad():
    from cacao_accounting.contabilidad.forms import FormularioUnidad

    formulario = FormularioUnidad()
    TITULO = "Crear Nueva Unidad de Negocios - " + APPNAME
    if formulario.validate_on_submit():
        from cacao_accounting.contabilidad.registros.unidad import RegistroUnidad

        e = RegistroUnidad()
        DATA = {
            "id": formulario.id.data,
            "nombre": formulario.nombre.data,
            "entidad": formulario.entidad.data,
            "correo_electronico": formulario.correo_electronico.data,
            "web": formulario.web.data,
            "telefono1": formulario.telefono1.data,
            "telefono2": formulario.telefono2.data,
            "fax": formulario.fax.data,
            "status": "activa",
        }
        e.crear(datos=DATA)
        return redirect("/accounts/units")
    return render_template("contabilidad/unidad_crear.html", titulo=TITULO, form=formulario)


# <------------------------------------------------------------------------------------------------------------------------> #
# Cuentas Contables
@contabilidad.route("/accounts/accounts")
@login_required
def cuentas():
    from cacao_accounting.database import Cuentas

    TITULO = "Catalogo de Cuentas Contables - " + APPNAME
    catalogo = Cuentas.query.order_by(Cuentas.codigo).all()
    return render_template("contabilidad/cuenta_lista.html", catalogo=catalogo, titulo=TITULO)


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
    TITULO = "Catalogo de Centros de Costos - " + APPNAME
    return render_template("contabilidad/centro-costo_lista.html", titulo=TITULO, resultado=RESULTADO, pagina=PAGINA)


# <------------------------------------------------------------------------------------------------------------------------> #
# Proyectos
@contabilidad.route("/accounts/projects")
@login_required
def proyectos():
    from cacao_accounting.database import CentroCosto

    PAGE = request.args.get("page", default=1, type=int)
    RESULTADO = paginar_consulta(tabla=CentroCosto)
    PAGINA = RESULTADO.page(PAGE)
    TITULO = "Listados de Proyectos - " + APPNAME
    return render_template("contabilidad/proyecto_lista.html", titulo=TITULO, resultado=RESULTADO, pagina=PAGINA)


# <------------------------------------------------------------------------------------------------------------------------> #
# Tipos de Cambio
@contabilidad.route("/accounts/exchange")
@login_required
def tasa_cambio():
    from cacao_accounting.database import TasaDeCambio

    PAGE = request.args.get("page", default=1, type=int)
    RESULTADO = paginar_consulta(tabla=TasaDeCambio)
    PAGINA = RESULTADO.page(PAGE)
    TITULO = "Listado de Tasas de Cambio - " + APPNAME
    return render_template("contabilidad/tc_lista.html", titulo=TITULO, resultado=RESULTADO, pagina=PAGINA)
