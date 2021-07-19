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
from cacao_accounting.contabilidad.auxiliares import (
    obtener_catalogo_base,
    obtener_catalogo_centros_costo_base,
    obtener_catalogo,
    obtener_catalogo_centros_costos,
    obtener_entidad,
    obtener_entidades,
    obtener_lista_monedas,
    obtener_lista_entidades_por_id_razonsocial,
)
from cacao_accounting.database import STATUS_WEB
from cacao_accounting.database.helpers import paginar_consulta, obtener_registro_desde_uuid
from cacao_accounting.decorators import modulo_activo
from cacao_accounting.metadata import APPNAME
from cacao_accounting.modulos import validar_modulo_activo

contabilidad = Blueprint("contabilidad", __name__, template_folder="templates")


# <------------------------------------------------------------------------------------------------------------------------> #
# Monedas
@contabilidad.route("/currency/list")
@modulo_activo("accounting")
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
@modulo_activo("accounting")
@login_required
def conta():
    TITULO = "Módulo Contabilidad - " + APPNAME
    if validar_modulo_activo("accounting"):
        return render_template("contabilidad.html", titulo=TITULO)
    else:
        return redirect("/app")


# <------------------------------------------------------------------------------------------------------------------------> #
# Entidades
@contabilidad.route("/accounts/entity/list")
@modulo_activo("accounting")
@login_required
def entidades():
    from cacao_accounting.database import Entidad

    PAGE = request.args.get("page", default=1, type=int)
    RESULTADO = paginar_consulta(tabla=Entidad)
    PAGINA = RESULTADO.page(PAGE)
    TITULO = "Listado de Entidades - " + APPNAME
    return render_template(
        "contabilidad/entidad_lista.html", titulo=TITULO, resultado=RESULTADO, pagina=PAGINA, statusweb=STATUS_WEB
    )


@contabilidad.route("/accounts/entity/<entidad>")
@modulo_activo("accounting")
@login_required
def entidad(entidad):
    from cacao_accounting.database import Entidad

    registro = Entidad.query.filter_by(entidad=entidad).first()
    return render_template("contabilidad/entidad.html", registro=registro)


@contabilidad.route("/accounts/entity/new", methods=["GET", "POST"])
@modulo_activo("accounting")
@login_required
def nueva_entidad():
    from cacao_accounting.contabilidad.forms import FormularioEntidad

    formulario = FormularioEntidad()
    formulario.moneda.choices = obtener_lista_monedas()

    TITULO = "Crear Nueva Entidad - " + APPNAME
    if formulario.validate_on_submit():
        from cacao_accounting.contabilidad.registros.entidad import RegistroEntidad

        e = RegistroEntidad()
        DATA = {
            "entidad": formulario.id.data,
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
        e.crear_registro_maestro(datos=DATA)
        return redirect("/accounts/entities")

    return render_template("contabilidad/entidad_crear.html", form=formulario, titulo=TITULO)


@contabilidad.route("/accounts/entity/edit/<id_entidad>")
@modulo_activo("accounting")
@login_required
def editar_entidad(id_entidad):
    from cacao_accounting.contabilidad.forms import FormularioEntidad
    from cacao_accounting.database import Entidad

    e = Entidad.query.filter_by(id=id_entidad).first()
    formulario = FormularioEntidad()
    return render_template("contabilidad/entidad_editar.html", form=formulario, entidad=e)


@contabilidad.route("/accounts/entity/delete/<id_entidad>")
@modulo_activo("accounting")
@login_required
def eliminar_entidad(id_entidad):
    # TODO
    return redirect("/app")


@contabilidad.route("/accounts/entity/set_inactive/<id_entidad>")
@modulo_activo("accounting")
@login_required
def inactivar_entidad(id_entidad):
    from cacao_accounting.contabilidad.registros.entidad import RegistroEntidad
    from cacao_accounting.database import Entidad

    REGISTRO = RegistroEntidad()
    TRANSACCION = obtener_registro_desde_uuid(tabla=Entidad, uuid=id_entidad)
    TRANSACCION.accion = "actualizar"
    TRANSACCION.tipo = "principal"
    TRANSACCION.nuevo_estatus = "inactivo"
    REGISTRO.ejecutar_transaccion_a_la_db(TRANSACCION)
    return redirect("/accounts/entity/list")


@contabilidad.route("/accounts/entity/set_default/<id_entidad>")
@modulo_activo("accounting")
@login_required
def predeterminar_entidad(id_entidad):
    from cacao_accounting.contabilidad.registros.entidad import RegistroEntidad
    from cacao_accounting.database import Entidad

    REGISTRO = RegistroEntidad()
    TRANSACCION = obtener_registro_desde_uuid(tabla=Entidad, uuid=id_entidad)
    TRANSACCION.accion = "actualizar"
    TRANSACCION.tipo = "principal"
    TRANSACCION.nuevo_estatus = "predeterminado"
    REGISTRO.ejecutar_transaccion_a_la_db(TRANSACCION)
    return redirect("/accounts/entity/list")


# <------------------------------------------------------------------------------------------------------------------------> #
# Unidades de Negocio
@contabilidad.route("/accounts/unit/list")
@modulo_activo("accounting")
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


@contabilidad.route("/accounts/unit/<unidad>")
@modulo_activo("accounting")
@login_required
def unidad(unidad):
    from cacao_accounting.database import Unidad

    registro = Unidad.query.filter_by(unidad=unidad).first()
    return render_template("contabilidad/unidad.html", registro=registro)


@contabilidad.route("/accounts/unit/delete/<id_unidad>")
@modulo_activo("accounting")
@login_required
def eliminar_unidad(id_unidad):
    # TODO
    return redirect("/app")


@contabilidad.route("/accounts/unit/new", methods=["GET", "POST"])
@modulo_activo("accounting")
@login_required
def nueva_unidad():
    from cacao_accounting.contabilidad.forms import FormularioUnidad

    formulario = FormularioUnidad()
    formulario.entidad.choices = obtener_lista_entidades_por_id_razonsocial()
    TITULO = "Crear Nueva Unidad de Negocios - " + APPNAME
    if formulario.validate_on_submit():
        from cacao_accounting.contabilidad.registros.unidad import RegistroUnidad

        e = RegistroUnidad()
        DATA = {
            "unidad": formulario.id.data,
            "nombre": formulario.nombre.data,
            "entidad": formulario.entidad.data,
            "correo_electronico": formulario.correo_electronico.data,
            "web": formulario.web.data,
            "telefono1": formulario.telefono1.data,
            "telefono2": formulario.telefono2.data,
            "fax": formulario.fax.data,
            "status": "activa",
        }
        e.crear_registro_maestro(datos=DATA)
        return redirect("/accounts/units")
    return render_template("contabilidad/unidad_crear.html", titulo=TITULO, form=formulario)


# <------------------------------------------------------------------------------------------------------------------------> #
# Cuentas Contables


@contabilidad.route("/accounts/accounts", methods=["GET", "POST"])
@modulo_activo("accounting")
@login_required
def cuentas():

    TITULO = "Catalogo de Cuentas Contables - " + APPNAME

    if "entidad" in request.args:
        return render_template(
            "contabilidad/cuenta_lista.html",
            base_cuentas=obtener_catalogo_base(entidad_=request.args.get("entidad")),
            cuentas=obtener_catalogo(entidad_=request.args.get("entidad")),
            entidades=obtener_entidades(),
            entidad=obtener_entidad(ent=request.args.get("entidad")),
            titulo=TITULO,
        )

    else:
        return render_template(
            "contabilidad/cuenta_lista.html",
            base_cuentas=obtener_catalogo_base(),
            cuentas=obtener_catalogo(),
            entidades=obtener_entidades(),
            entidad=obtener_entidad(),
            titulo=TITULO,
        )


@contabilidad.route("/accounts/accounts/<id_cta>")
@modulo_activo("accounting")
@login_required
def cuenta(id_cta):
    from cacao_accounting.database import Cuentas

    registro = Cuentas.query.filter_by(codigo=id_cta).first()
    return render_template("contabilidad/cuenta.html", registro=registro, statusweb=Cuentas.status_web)


# <------------------------------------------------------------------------------------------------------------------------> #
# Centros de Costos
@contabilidad.route("/accounts/costs_center", methods=["GET", "POST"])
@modulo_activo("accounting")
@login_required
def ccostos():
    TITULO = "Catalogo de Centros de Costos - " + APPNAME

    if "entidad" in request.args:
        return render_template(
            "contabilidad/centro-costo_lista.html",
            base_centrocostos=obtener_catalogo_centros_costo_base(entidad_=request.args.get("entidad")),
            centros_costo=obtener_catalogo_centros_costos(entidad_=request.args.get("entidad")),
            entidades=obtener_entidades(),
            entidad=obtener_entidad(ent=request.args.get("entidad")),
            titulo=TITULO,
        )

    else:
        return render_template(
            "contabilidad/centro-costo_lista.html",
            base_centrocostos=obtener_catalogo_centros_costo_base(),
            centros_costo=obtener_catalogo_centros_costos(),
            entidades=obtener_entidades(),
            entidad=obtener_entidad(),
            titulo=TITULO,
        )


@contabilidad.route("/accounts/costs_center/<id_cc>")
@modulo_activo("accounting")
@login_required
def centro_costo(id_cc):
    from cacao_accounting.database import CentroCosto

    registro = CentroCosto.query.filter_by(codigo=id_cc).first()
    return render_template("contabilidad/centro-costo.html", registro=registro, statusweb=CentroCosto.status_web)


# <------------------------------------------------------------------------------------------------------------------------> #
# Proyectos
@contabilidad.route("/accounts/project/list")
@modulo_activo("accounting")
@login_required
def proyectos():
    from cacao_accounting.database import Proyecto

    PAGE = request.args.get("page", default=1, type=int)
    RESULTADO = paginar_consulta(tabla=Proyecto)
    PAGINA = RESULTADO.page(PAGE)
    TITULO = "Listados de Proyectos - " + APPNAME
    return render_template(
        "contabilidad/proyecto_lista.html", titulo=TITULO, resultado=RESULTADO, pagina=PAGINA, statusweb=Proyecto.status_web
    )


# <------------------------------------------------------------------------------------------------------------------------> #
# Tipos de Cambio
@contabilidad.route("/accounts/exchange")
@modulo_activo("accounting")
@login_required
def tasa_cambio():
    from cacao_accounting.database import TasaDeCambio

    PAGE = request.args.get("page", default=1, type=int)
    RESULTADO = paginar_consulta(tabla=TasaDeCambio)
    PAGINA = RESULTADO.page(PAGE)
    TITULO = "Listado de Tasas de Cambio - " + APPNAME
    return render_template("contabilidad/tc_lista.html", titulo=TITULO, resultado=RESULTADO, pagina=PAGINA)


# <------------------------------------------------------------------------------------------------------------------------> #
# Períodos Contables
@contabilidad.route("/accounts/accounting_period")
@modulo_activo("accounting")
@login_required
def periodo_contable():
    from cacao_accounting.database import PeriodoContable

    PAGE = request.args.get("page", default=1, type=int)
    RESULTADO = paginar_consulta(tabla=PeriodoContable)
    PAGINA = RESULTADO.page(PAGE)
    TITULO = "Listado de Períodos Contables - " + APPNAME
    return render_template(
        "contabilidad/periodo_lista.html",
        titulo=TITULO,
        resultado=RESULTADO,
        pagina=PAGINA,
        statusweb=PeriodoContable.status_web,
    )
