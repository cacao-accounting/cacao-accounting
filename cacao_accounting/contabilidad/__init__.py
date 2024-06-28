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

"""Modulo de Contabilidad."""


# ---------------------------------------------------------------------------------------
# Libreria estandar
# --------------------------------------------------------------------------------------

# ---------------------------------------------------------------------------------------
# Librerias de terceros
# ---------------------------------------------------------------------------------------
from flask import Blueprint, redirect, render_template, request
from flask.helpers import url_for
from flask_login import login_required

# ---------------------------------------------------------------------------------------
# Recursos locales
# ---------------------------------------------------------------------------------------
from cacao_accounting.contabilidad.auxiliares import (
    obtener_catalogo,
    obtener_catalogo_base,
    obtener_catalogo_centros_costo_base,
    obtener_centros_costos,
    obtener_entidad,
    obtener_entidades,
    obtener_lista_entidades_por_id_razonsocial,
    obtener_lista_monedas,
)
from cacao_accounting.database import STATUS
from cacao_accounting.database.helpers import obtener_registro_desde_uuid
from cacao_accounting.decorators import modulo_activo, verifica_acceso
from cacao_accounting.transaccion import Transaccion

contabilidad = Blueprint("contabilidad", __name__, template_folder="templates")
LISTA_ENTIDADES = redirect("/accounts/entity/list")
APPNAME = "Cacao Accounting"


# <------------------------------------------------------------------------------------------------------------------------> #
# Monedas
@contabilidad.route("/currency/list")
@login_required
@modulo_activo("accounting")
@verifica_acceso("accounting")
def monedas():
    """Listado de monedas registradas en el sistema."""
    from cacao_accounting.database import Moneda, database

    CONSULTA = database.paginate(
        database.select(Moneda),
        page=request.args.get("page", default=1, type=int),
        max_per_page=10,
        count=True,
    )

    TITULO = "Listado de Monedas - " + " - " + APPNAME
    return render_template(
        "contabilidad/moneda_lista.html",
        consulta=CONSULTA,
        titulo=TITULO,
    )


# <------------------------------------------------------------------------------------------------------------------------> #
# Contabilidad
@contabilidad.route("/contabilidad")
@contabilidad.route("/conta")
@contabilidad.route("/accounts")
@login_required
@modulo_activo("accounting")
@verifica_acceso("accounting")
def conta():
    """Pantalla principal del modulo contabilidad."""
    TITULO = "Módulo Contabilidad - " + APPNAME
    return render_template(
        "contabilidad.html",
        titulo=TITULO,
    )


# <------------------------------------------------------------------------------------------------------------------------> #
# Entidades
@contabilidad.route("/accounts/entity/list")
@login_required
@modulo_activo("accounting")
@verifica_acceso("accounting")
def entidades():
    """Listado de entidades."""
    from cacao_accounting.database import Entidad, database

    CONSULTA = database.paginate(
        database.select(Entidad),  # noqa: E712
        page=request.args.get("page", default=1, type=int),
        max_per_page=10,
        count=True,
    )
    TITULO = "Listado de Entidades - " + APPNAME
    return render_template(
        "contabilidad/entidad_lista.html",
        titulo=TITULO,
        consulta=CONSULTA,
        statusweb=STATUS,
    )


@contabilidad.route("/accounts/entity/<entidad_id>")
@login_required
@modulo_activo("accounting")
@verifica_acceso("accounting")
def entidad(entidad_id):
    """Entidad individual."""
    from cacao_accounting.database import Entidad

    registro = Entidad.query.filter_by(entidad=entidad_id).first()
    return render_template(
        "contabilidad/entidad.html",
        registro=registro,
    )


@contabilidad.route("/accounts/entity/new", methods=["GET", "POST"])
@login_required
@modulo_activo("accounting")
@verifica_acceso("accounting")
def nueva_entidad():
    """Formulario para crear una nueva entidad."""
    from cacao_accounting.contabilidad.forms import FormularioEntidad

    formulario = FormularioEntidad()
    formulario.moneda.choices = obtener_lista_monedas()

    TITULO = "Crear Nueva Entidad - " + APPNAME
    if formulario.validate_on_submit() or request.method == "POST":
        from cacao_accounting.contabilidad.registros.entidad import RegistroEntidad
        from cacao_accounting.contabilidad.registros.serie import RegistroSerie

        ENTIDAD = RegistroEntidad()
        DATA = {
            "entidad": request.form.get("id", None),
            "razon_social": request.form.get("razon_social", None),
            "nombre_comercial": request.form.get("nombre_comercial", None),
            "id_fiscal": request.form.get("id_fiscal", None),
            "moneda": request.form.get("moneda", None),
            "tipo_entidad": request.form.get("tipo_entidad", None),
            "correo_electronico": request.form.get("correo_electronico", None),
            "web": request.form.get("web", None),
            "telefono1": request.form.get("telefono1", None),
            "telefono2": request.form.get("telefono2", None),
            "fax": request.form.get("fax", None),
            "status": "activo",
            "habilitada": True,
            "predeterminada": False,
        }
        TRANSACCION_NUEVA_ENTIDAD = Transaccion(
            tipo="principal",
            accion="crear",
            datos=DATA,
            registro="Entidad",
            estatus_actual=None,
            nuevo_estatus=None,
            uuid=None,
            relaciones=None,
            relacion_id=None,
            datos_detalle=None,
        )
        ENTIDAD.ejecutar_transaccion(TRANSACCION_NUEVA_ENTIDAD)

        SERIE = RegistroSerie()
        TRANSACCION_NUEVA_SERIE = Transaccion(
            tipo="principal",
            accion="crear",
            datos={
                "entidad": request.form.get("id", None),
                "documento": "journal",
                "habilitada": True,
                "predeterminada": True,
                "serie": str("CDD-" + request.form.get("id", None)).upper(),
            },
            registro="Serie",
            estatus_actual=None,
            nuevo_estatus=None,
            uuid=None,
            relaciones=None,
            relacion_id=None,
            datos_detalle=None,
        )
        SERIE.ejecutar_transaccion(TRANSACCION_NUEVA_SERIE)

        return LISTA_ENTIDADES

    return render_template(
        "contabilidad/entidad_crear.html",
        form=formulario,
        titulo=TITULO,
    )


@contabilidad.route("/accounts/entity/edit/<id_entidad>", methods=["GET", "POST"])
@login_required
@modulo_activo("accounting")
@verifica_acceso("accounting")
def editar_entidad(id_entidad):
    """Formulario para editar una entidad."""
    from cacao_accounting.contabilidad.forms import FormularioEntidad
    from cacao_accounting.database import Entidad, database

    ENTIDAD = Entidad.query.filter_by(entidad=id_entidad).first()

    if request.method == "POST":

        ENTIDAD.id_fiscal = request.form.get("id_fiscal", None)
        ENTIDAD.nombre_comercial = request.form.get("nombre_comercial", None)
        ENTIDAD.razon_social = request.form.get("razon_social", None)
        ENTIDAD.telefono1 = request.form.get("telefono1", None)
        ENTIDAD.telefono2 = request.form.get("telefono2", None)
        ENTIDAD.correo_electronico = request.form.get("correo_electronico", None)
        ENTIDAD.fax = request.form.get("fax", None)
        ENTIDAD.web = request.form.get("web", None)
        database.session.add(ENTIDAD)  # pylint: disable=no-member
        database.session.commit()  # pylint: disable=no-member
        return redirect(url_for("contabilidad.entidad", entidad_id=ENTIDAD.entidad))
    else:
        DATA = {
            "nombre_comercial": ENTIDAD.nombre_comercial,
            "razon_social": ENTIDAD.razon_social,
            "id_fiscal": ENTIDAD.id_fiscal,
            "correo_electronico": ENTIDAD.correo_electronico,
            "telefono1": ENTIDAD.telefono1,
            "telefono2": ENTIDAD.telefono2,
            "fax": ENTIDAD.fax,
            "web": ENTIDAD.web,
        }

        formulario = FormularioEntidad(data=DATA)
        formulario.moneda.choices = obtener_lista_monedas()
        return render_template("contabilidad/entidad_editar.html", form=formulario)


@contabilidad.route("/accounts/entity/delete/<id_entidad>")
@login_required
@modulo_activo("accounting")
@verifica_acceso("accounting")
def eliminar_entidad(id_entidad):
    """Elimina una entidad de sistema."""
    from cacao_accounting.contabilidad.registros.entidad import RegistroEntidad
    from cacao_accounting.database import Entidad

    REGISTRO = RegistroEntidad()
    TRANSACCION = obtener_registro_desde_uuid(tabla=Entidad, uuid=id_entidad)
    TRANSACCION.accion = "eliminar"
    TRANSACCION.tipo = "principal"
    REGISTRO.ejecutar_transaccion(TRANSACCION)
    return LISTA_ENTIDADES


@contabilidad.route("/accounts/entity/set_inactive/<id_entidad>")
@login_required
@modulo_activo("accounting")
@verifica_acceso("accounting")
def inactivar_entidad(id_entidad):
    """Estable una entidad como inactiva."""
    from cacao_accounting.contabilidad.registros.entidad import RegistroEntidad
    from cacao_accounting.database import Entidad

    REGISTRO = RegistroEntidad()
    TRANSACCION = obtener_registro_desde_uuid(tabla=Entidad, uuid=id_entidad)
    TRANSACCION.accion = "actualizar"
    TRANSACCION.tipo = "principal"
    TRANSACCION.nuevo_estatus = "inactivo"
    REGISTRO.ejecutar_transaccion(TRANSACCION)
    return LISTA_ENTIDADES


@contabilidad.route("/accounts/entity/set_active/<id_entidad>")
@login_required
@modulo_activo("accounting")
@verifica_acceso("accounting")
def activar_entidad(id_entidad):
    """Estable una entidad como inactiva."""
    from cacao_accounting.contabilidad.registros.entidad import RegistroEntidad
    from cacao_accounting.database import Entidad

    REGISTRO = RegistroEntidad()
    TRANSACCION = obtener_registro_desde_uuid(tabla=Entidad, uuid=id_entidad)
    TRANSACCION.accion = "actualizar"
    TRANSACCION.tipo = "principal"
    TRANSACCION.nuevo_estatus = "activo"
    REGISTRO.ejecutar_transaccion(TRANSACCION)
    return LISTA_ENTIDADES


@contabilidad.route("/accounts/entity/set_default/<id_entidad>")
@login_required
@modulo_activo("accounting")
@verifica_acceso("accounting")
def predeterminar_entidad(id_entidad):
    """Establece una entidad como predeterminada."""
    from cacao_accounting.contabilidad.registros.entidad import RegistroEntidad
    from cacao_accounting.database import Entidad

    REGISTRO = RegistroEntidad()
    TRANSACCION = obtener_registro_desde_uuid(tabla=Entidad, uuid=id_entidad)
    TRANSACCION.accion = "actualizar"
    TRANSACCION.tipo = "principal"
    TRANSACCION.nuevo_estatus = "predeterminado"
    REGISTRO.ejecutar_transaccion(TRANSACCION)
    return LISTA_ENTIDADES


# <------------------------------------------------------------------------------------------------------------------------> #
# Unidades de Negocio
@contabilidad.route("/accounts/unit/list")
@login_required
@modulo_activo("accounting")
@verifica_acceso("accounting")
def unidades():
    """Listado de unidades de negocios."""
    from cacao_accounting.database import Unidad, database

    CONSULTA = database.paginate(
        database.select(Unidad),  # noqa: E712
        page=request.args.get("page", default=1, type=int),
        max_per_page=10,
        count=True,
    )

    TITULO = "Listado de Unidades de Negocio - " + APPNAME
    return render_template(
        "contabilidad/unidad_lista.html",
        titulo=TITULO,
        consulta=CONSULTA,
        statusweb=STATUS,
    )


@contabilidad.route("/accounts/unit/<id_unidad>")
@login_required
@modulo_activo("accounting")
@verifica_acceso("accounting")
def unidad(id_unidad):
    """Unidad de negocios."""
    from cacao_accounting.database import Unidad

    registro = Unidad.query.filter_by(unidad=id_unidad).first()
    return render_template("contabilidad/unidad.html", registro=registro)


@contabilidad.route("/accounts/unit/delete/<id_unidad>")
@modulo_activo("accounting")
@login_required
def eliminar_unidad(id_unidad):
    """Elimina una entidad de la base de datos."""
    return redirect("/app")


@contabilidad.route("/accounts/unit/new", methods=["GET", "POST"])
@login_required
@modulo_activo("accounting")
@verifica_acceso("accounting")
def nueva_unidad():
    """Formulario para crear una nueva unidad de negocios."""
    from cacao_accounting.contabilidad.forms import FormularioUnidad

    formulario = FormularioUnidad()
    formulario.entidad.choices = obtener_lista_entidades_por_id_razonsocial()
    TITULO = "Crear Nueva Unidad de Negocios - " + APPNAME
    if formulario.validate_on_submit() or request.method == "POST":
        from cacao_accounting.contabilidad.registros.unidad import RegistroUnidad

        UNIDAD = RegistroUnidad()
        DATA = {
            "unidad": request.form.get("id", None),
            "nombre": request.form.get("nombre", None),
            "entidad": request.form.get("entidad", None),
            "status": "activo",
        }
        TRANSACCION_NUEVA_UNIDAD = Transaccion(
            tipo="principal",
            accion="crear",
            datos=DATA,
            registro="Unidad",
            estatus_actual=None,
            nuevo_estatus=None,
            uuid=None,
            relaciones=None,
            relacion_id=None,
            datos_detalle=None,
        )
        UNIDAD.ejecutar_transaccion(TRANSACCION_NUEVA_UNIDAD)
        return redirect("/accounts/unit/list")
    return render_template(
        "contabilidad/unidad_crear.html",
        titulo=TITULO,
        form=formulario,
    )


# <------------------------------------------------------------------------------------------------------------------------> #
# Cuentas Contables


@contabilidad.route("/accounts/accounts", methods=["GET", "POST"])
@login_required
@modulo_activo("accounting")
@verifica_acceso("accounting")
def cuentas():
    """Catalogo de cuentas contables."""
    TITULO = "Catalogo de Cuentas Contables - " + APPNAME

    return render_template(
        "contabilidad/cuenta_lista.html",
        base_cuentas=obtener_catalogo_base(entidad_=request.args.get("entidad", None)),
        cuentas=obtener_catalogo(entidad_=request.args.get("entidad", None)),
        entidades=obtener_entidades(),
        entidad=obtener_entidad(ent=request.args.get("entidad")),
        titulo=TITULO,
    )


@contabilidad.route("/accounts/account/<id_cta>")
@login_required
@modulo_activo("accounting")
@verifica_acceso("accounting")
def cuenta(id_cta):
    """Cuenta Contable."""
    from cacao_accounting.database import Cuentas

    registro = Cuentas.query.filter_by(codigo=id_cta).first()
    return render_template(
        "contabilidad/cuenta.html",
        registro=registro,
        statusweb=STATUS,
    )


# <------------------------------------------------------------------------------------------------------------------------> #
# Centros de Costos
@contabilidad.route("/accounts/costs_center", methods=["GET", "POST"])
@login_required
@modulo_activo("accounting")
@verifica_acceso("accounting")
def ccostos():
    """Catalogo de centros de costos."""
    TITULO = "Catalogo de Centros de Costos - " + APPNAME

    return render_template(
        "contabilidad/centro-costo_lista.html",
        base_centrocostos=obtener_catalogo_centros_costo_base(entidad_=request.args.get("entidad", None)),
        ccostos=obtener_centros_costos(entidad_=request.args.get("entidad", None)),
        entidades=obtener_entidades(),
        entidad=obtener_entidad(ent=request.args.get("entidad", None)),
        titulo=TITULO,
    )


@contabilidad.route("/accounts/costs_center/<id_cc>")
@login_required
@modulo_activo("accounting")
@verifica_acceso("accounting")
def centro_costo(id_cc):
    """Centro de Costos."""
    from cacao_accounting.database import CentroCosto

    registro = CentroCosto.query.filter_by(codigo=id_cc).first()
    return render_template(
        "contabilidad/centro-costo.html",
        registro=registro,
        statusweb=STATUS,
    )


# <------------------------------------------------------------------------------------------------------------------------> #
# Proyectos
@contabilidad.route("/accounts/project/list")
@login_required
@modulo_activo("accounting")
@verifica_acceso("accounting")
def proyectos():
    """Listado de proyectos."""
    from cacao_accounting.database import Proyecto, database

    CONSULTA = database.paginate(
        database.select(Proyecto),
        page=request.args.get("page", default=1, type=int),
        max_per_page=10,
        count=True,
    )

    TITULO = "Listados de Proyectos - " + APPNAME
    return render_template(
        "contabilidad/proyecto_lista.html",
        titulo=TITULO,
        consulta=CONSULTA,
        statusweb=STATUS,
    )


# <------------------------------------------------------------------------------------------------------------------------> #
# Tipos de Cambio
@contabilidad.route("/accounts/exchange")
@login_required
@modulo_activo("accounting")
@verifica_acceso("accounting")
def tasa_cambio():
    """Listado de tasas de cambio."""
    from cacao_accounting.database import TasaDeCambio, database

    CONSULTA = database.paginate(
        database.select(TasaDeCambio),  # noqa: E712
        page=request.args.get("page", default=1, type=int),
        max_per_page=10,
        count=True,
    )
    TITULO = "Listado de Tasas de Cambio - " + APPNAME
    return render_template(
        "contabilidad/tc_lista.html",
        titulo=TITULO,
        consulta=CONSULTA,
    )


# <------------------------------------------------------------------------------------------------------------------------> #
# Períodos Contables
@contabilidad.route("/accounts/accounting_period")
@login_required
@modulo_activo("accounting")
@verifica_acceso("accounting")
def periodo_contable():
    """Lista de periodos contables."""
    from cacao_accounting.database import PeriodoContable, database

    CONSULTA = database.paginate(
        database.select(PeriodoContable),  # noqa: E712
        page=request.args.get("page", default=1, type=int),
        max_per_page=10,
        count=True,
    )

    TITULO = "Listado de Períodos Contables - " + APPNAME
    return render_template(
        "contabilidad/periodo_lista.html",
        titulo=TITULO,
        consulta=CONSULTA,
        statusweb=STATUS,
    )


# <------------------------------------------------------------------------------------------------------------------------> #
# Comprobante contable
@contabilidad.route("/accounts/journal/new", methods=["GET", "POST"])
@login_required
@modulo_activo("accounting")
@verifica_acceso("accounting")
def nuevo_comprobante():
    """Nuevo comprobante contable."""


@contabilidad.route("/accounts/journal/<identifier>")
@login_required
@modulo_activo("accounting")
@verifica_acceso("accounting")
def ver_comprobante():
    """Nuevo comprobante contable."""


@contabilidad.route("/accounts/journal/edit/<identifier>", methods=["GET", "POST"])
@login_required
@modulo_activo("accounting")
@verifica_acceso("accounting")
def editar_comprobante():
    """Editar comprobante contable."""


# <------------------------------------------------------------------------------------------------------------------------> #
# Series e Identificadores


@contabilidad.route("/accounts/series", methods=["GET", "POST"])
@login_required
@modulo_activo("accounting")
@verifica_acceso("accounting")
def series():
    """Series e Identificadores."""

    from cacao_accounting.database import Serie, database
    from cacao_accounting.modulos import lista_tipos_documentos

    TITULO = "Series e Identificadores - " + APPNAME

    if request.args.get("doc", type=str):
        consulta = consulta = database.paginate(
            database.select(Serie).filter_by(documento=request.args.get("doc", type=str)),
            page=request.args.get("page", default=1, type=int),
            max_per_page=10,
            count=True,
        )
    else:
        consulta = database.paginate(
            database.select(Serie),
            page=request.args.get("page", default=1, type=int),
            max_per_page=10,
            count=True,
        )

    return render_template(
        "contabilidad/serie_lista.html",
        consulta=consulta,
        documentos=lista_tipos_documentos(),
        titulo=TITULO,
    )


@contabilidad.route("/accounts/serie/new", methods=["GET", "POST"])
@login_required
@modulo_activo("accounting")
@verifica_acceso("accounting")
def nueva_serie():
    """Nueva Serie."""

    from cacao_accounting.contabilidad.forms import FormularioSerie
    from cacao_accounting.contabilidad.registros.serie import RegistroSerie
    from cacao_accounting.database import Entidad, database
    from cacao_accounting.transaccion import Transaccion

    form = FormularioSerie()

    CONSULTA_ENTIDADES = database.session.execute(database.select(Entidad)).all()
    LISTA_DE_ENTIDADES = []
    SERIE = RegistroSerie()

    for e in CONSULTA_ENTIDADES:
        LISTA_DE_ENTIDADES.append((e[0].entidad, e[0].nombre_comercial))

    form.entidad.choices = LISTA_DE_ENTIDADES

    if form.validate_on_submit() or request.method == "POST":
        DATA = {
            "entidad": form.entidad.data,
            "documento": form.documento.data,
            "serie": form.serie.data,
            "habilitada": True,
            "predeterminada": False,
        }

        NUEVA_SERIE_TRANSACCION = Transaccion(
            tipo="principal",
            accion="crear",
            datos=DATA,
            registro="Serie",
            estatus_actual=None,
            nuevo_estatus=None,
            uuid=None,
            relaciones=None,
            relacion_id=None,
            datos_detalle=None,
        )

        SERIE.ejecutar_transaccion(NUEVA_SERIE_TRANSACCION)

        return redirect(url_for("contabilidad.series"))

    return render_template(
        "contabilidad/serie_crear.html",
        form=form,
    )
