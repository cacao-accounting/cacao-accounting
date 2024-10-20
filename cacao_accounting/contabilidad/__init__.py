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
from cacao_accounting.contabilidad.gl import gl
from cacao_accounting.database import STATUS, database
from cacao_accounting.decorators import modulo_activo, verifica_acceso
from cacao_accounting.version import APPNAME


# <------------------------------------------------------------------------------------------------------------------------> #
contabilidad = Blueprint("contabilidad", __name__, template_folder="templates")
contabilidad.register_blueprint(gl, url_prefix="/gl")
LISTA_ENTIDADES = redirect("/accounting/entity/list")


# <------------------------------------------------------------------------------------------------------------------------> #
# Monedas
@contabilidad.route("/currency/list")
@login_required
@modulo_activo("accounting")
@verifica_acceso("accounting")
def monedas():
    """Listado de monedas registradas en el sistema."""
    from cacao_accounting.database import Currency

    CONSULTA = database.paginate(
        database.select(Currency),
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
@contabilidad.route("/")
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
@contabilidad.route("/entity/list")
@login_required
@modulo_activo("accounting")
@verifica_acceso("accounting")
def entidades():
    """Listado de entidades."""
    from cacao_accounting.database import Entity

    CONSULTA = database.paginate(
        database.select(Entity),  # noqa: E712
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


@contabilidad.route("/entity/<entidad_id>")
@login_required
@modulo_activo("accounting")
@verifica_acceso("accounting")
def entidad(entidad_id):
    """Entidad individual."""
    from cacao_accounting.database import Entity

    registro = database.session.execute(database.select(Entity).filter_by(code=entidad_id)).first()

    return render_template(
        "contabilidad/entidad.html",
        registro=registro[0],
    )


@contabilidad.route("/entity/new", methods=["GET", "POST"])
@login_required
@modulo_activo("accounting")
@verifica_acceso("accounting")
def nueva_entidad():
    """Formulario para crear una nueva entidad."""
    from cacao_accounting.contabilidad.forms import FormularioEntidad
    from cacao_accounting.database import Entity

    formulario = FormularioEntidad()
    formulario.moneda.choices = obtener_lista_monedas()

    TITULO = "Crear Nueva Entidad - " + APPNAME
    if formulario.validate_on_submit() or request.method == "POST":
        ENTIDAD = Entity(
            code=request.form.get("id", None),
            company_name=request.form.get("razon_social", None),
            name=request.form.get("nombre_comercial", None),
            tax_id=request.form.get("id_fiscal", None),
            currency=request.form.get("moneda", None),
            entity_type=request.form.get("tipo_entidad", None),
            e_mail=request.form.get("correo_electronico", None),
            web=request.form.get("web", None),
            phone1=request.form.get("telefono1", None),
            phone2=request.form.get("telefono2", None),
            fax=request.form.get("fax", None),
            status="activo",
            enabled=True,
            default=False,
        )

        database.session.add(ENTIDAD)
        database.session.commit()

        return LISTA_ENTIDADES

    return render_template(
        "contabilidad/entidad_crear.html",
        form=formulario,
        titulo=TITULO,
    )


@contabilidad.route("/entity/edit/<id_entidad>", methods=["GET", "POST"])
@login_required
@modulo_activo("accounting")
@verifica_acceso("accounting")
def editar_entidad(id_entidad):
    """Formulario para editar una entidad."""
    from cacao_accounting.contabilidad.forms import FormularioEntidad
    from cacao_accounting.database import Entity

    ENTIDAD = database.session.execute(database.select(Entity).filter_by(code=id_entidad)).first()
    ENTIDAD = ENTIDAD[0]

    if request.method == "POST":
        ENTIDAD.tax_id = request.form.get("id_fiscal", None)
        ENTIDAD.name = request.form.get("nombre_comercial", None)
        ENTIDAD.company_name = request.form.get("razon_social", None)
        ENTIDAD.phone1 = request.form.get("telefono1", None)
        ENTIDAD.phone2 = request.form.get("telefono2", None)
        ENTIDAD.e_mail = request.form.get("correo_electronico", None)
        ENTIDAD.fax = request.form.get("fax", None)
        ENTIDAD.web = request.form.get("web", None)
        database.session.add(ENTIDAD)
        database.session.commit()
        return redirect(url_for("contabilidad.entidad", entidad_id=ENTIDAD.entidad))
    else:
        DATA = {
            "nombre_comercial": ENTIDAD.name,
            "razon_social": ENTIDAD.company_name,
            "id_fiscal": ENTIDAD.tax_id,
            "correo_electronico": ENTIDAD.e_mail,
            "telefono1": ENTIDAD.phone1,
            "telefono2": ENTIDAD.phone2,
            "fax": ENTIDAD.fax,
            "web": ENTIDAD.web,
        }

        formulario = FormularioEntidad(data=DATA)
        formulario.moneda.choices = obtener_lista_monedas()
        return render_template("contabilidad/entidad_editar.html", entidad=ENTIDAD, form=formulario)


@contabilidad.route("/entity/delete/<id_entidad>")
@login_required
@modulo_activo("accounting")
@verifica_acceso("accounting")
def eliminar_entidad(id_entidad):
    """Elimina una entidad de sistema."""
    from cacao_accounting.database import Entity

    ENTIDAD = database.session.execute(database.select(Entity).filter_by(id=id_entidad)).first()
    database.session.delete(ENTIDAD[0])
    database.session.commit()

    return LISTA_ENTIDADES


@contabilidad.route("/entity/set_inactive/<id_entidad>")
@login_required
@modulo_activo("accounting")
@verifica_acceso("accounting")
def inactivar_entidad(id_entidad):
    """Estable una entidad como inactiva."""
    from cacao_accounting.database import Entity

    ENTIDAD = database.session.execute(database.select(Entity).filter_by(id=id_entidad)).first()
    ENTIDAD[0].habilitada = False
    database.session.commit()

    return LISTA_ENTIDADES


@contabilidad.route("/entity/set_active/<id_entidad>")
@login_required
@modulo_activo("accounting")
@verifica_acceso("accounting")
def activar_entidad(id_entidad):
    """Estable una entidad como inactiva."""
    from cacao_accounting.database import Entity

    ENTIDAD = database.session.execute(database.select(Entity).filter_by(id=id_entidad)).first()
    ENTIDAD[0].habilitada = True
    database.session.commit()

    return LISTA_ENTIDADES


@contabilidad.route("/entity/set_default/<id_entidad>")
@login_required
@modulo_activo("accounting")
@verifica_acceso("accounting")
def predeterminar_entidad(id_entidad):
    """Establece una entidad como predeterminada."""
    from cacao_accounting.database import Entity

    # Establece cualquier entidad establecida como predeterminada a falso
    ENTIDAD_PREDETERMINADA = database.session.execute(database.select(Entity).filter_by(predeterminada=True)).all()

    if ENTIDAD_PREDETERMINADA:
        for e in ENTIDAD_PREDETERMINADA:
            e[0].predeterminada = False

    ENTIDAD = database.session.execute(database.select(Entity).filter_by(id=id_entidad)).first()
    ENTIDAD[0].predeterminada = True
    database.session.commit()

    return LISTA_ENTIDADES


# <------------------------------------------------------------------------------------------------------------------------> #
# Unidades de Negocio
@contabilidad.route("/unit/list")
@login_required
@modulo_activo("accounting")
@verifica_acceso("accounting")
def unidades():
    """Listado de unidades de negocios."""
    from cacao_accounting.database import Unit, database

    CONSULTA = database.paginate(
        database.select(Unit),  # noqa: E712
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


@contabilidad.route("/unit/<id_unidad>")
@login_required
@modulo_activo("accounting")
@verifica_acceso("accounting")
def unidad(id_unidad):
    """Unidad de negocios."""
    from cacao_accounting.database import Unit

    REGISTRO = database.session.execute(database.select(Unit).filter_by(code=id_unidad)).first()
    return render_template("contabilidad/unidad.html", registro=REGISTRO[0])


@contabilidad.route("/unit/delete/<id_unidad>")
@modulo_activo("accounting")
@login_required
def eliminar_unidad(id_unidad):
    """Elimina una entidad de la base de datos."""
    return redirect("/app")


@contabilidad.route("/unit/new", methods=["GET", "POST"])
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
        from cacao_accounting.database import Unidad

        DATA = Unidad(
            code=request.form.get("id", None),
            name=request.form.get("nombre", None),
            entity=request.form.get("entidad", None),
            status="activo",
        )
        database.session.add(DATA)
        database.session.commit()

        return redirect("/unit/list")
    return render_template(
        "contabilidad/unidad_crear.html",
        titulo=TITULO,
        form=formulario,
    )


# <------------------------------------------------------------------------------------------------------------------------> #
# Cuentas Contables


@contabilidad.route("/accounts", methods=["GET", "POST"])
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


@contabilidad.route("/account/<entity>/<id_cta>")
@login_required
@modulo_activo("accounting")
@verifica_acceso("accounting")
def cuenta(entity, id_cta):
    """Cuenta Contable."""
    from cacao_accounting.database import Accounts

    registro = database.session.execute(
        database.select(Accounts).filter(Accounts.code == id_cta, Accounts.entity == entity)
    ).first()

    return render_template(
        "contabilidad/cuenta.html",
        registro=registro[0],
        statusweb=STATUS,
    )


# <------------------------------------------------------------------------------------------------------------------------> #
# Centros de Costos
@contabilidad.route("/costs_center", methods=["GET", "POST"])
@login_required
@modulo_activo("accounting")
@verifica_acceso("accounting")
def ccostos():
    """Catalogo de centros de costos."""
    TITULO = "Catalogo de Centros de Costos - " + APPNAME

    return render_template(
        "contabilidad/centro-costo_lista.html",
        base_centro_costos=obtener_catalogo_centros_costo_base(entidad_=request.args.get("entidad", None)),
        ccostos=obtener_centros_costos(entidad_=request.args.get("entidad", None)),
        entidades=obtener_entidades(),
        entidad=obtener_entidad(ent=request.args.get("entidad", None)),
        titulo=TITULO,
    )


@contabilidad.route("/costs_center/<id_cc>")
@login_required
@modulo_activo("accounting")
@verifica_acceso("accounting")
def centro_costo(id_cc):
    """Centro de Costos."""
    from cacao_accounting.database import CostCenter

    registro = database.session.execute(database.select(CostCenter).filter_by(code=id_cc)).first()

    return render_template(
        "contabilidad/centro-costo.html",
        registro=registro[0],
        statusweb=STATUS,
    )


# <------------------------------------------------------------------------------------------------------------------------> #
# Proyectos
@contabilidad.route("/project/list")
@login_required
@modulo_activo("accounting")
@verifica_acceso("accounting")
def proyectos():
    """Listado de proyectos."""
    from cacao_accounting.database import Project

    CONSULTA = database.paginate(
        database.select(Project),
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
@contabilidad.route("/exchange")
@login_required
@modulo_activo("accounting")
@verifica_acceso("accounting")
def tasa_cambio():
    """Listado de tasas de cambio."""
    from cacao_accounting.database import ExchangeRate

    CONSULTA = database.paginate(
        database.select(ExchangeRate),  # noqa: E712
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
@contabilidad.route("/accounting_period")
@login_required
@modulo_activo("accounting")
@verifica_acceso("accounting")
def periodo_contable():
    """Lista de periodos contables."""
    from cacao_accounting.database import AccountingPeriod

    CONSULTA = database.paginate(
        database.select(AccountingPeriod),  # noqa: E712
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
@contabilidad.route("/journal/new", methods=["GET", "POST"])
@login_required
@modulo_activo("accounting")
@verifica_acceso("accounting")
def nuevo_comprobante():
    """Nuevo comprobante contable."""


@contabilidad.route("/journal/<identifier>")
@login_required
@modulo_activo("accounting")
@verifica_acceso("accounting")
def ver_comprobante():
    """Nuevo comprobante contable."""


@contabilidad.route("/journal/edit/<identifier>", methods=["GET", "POST"])
@login_required
@modulo_activo("accounting")
@verifica_acceso("accounting")
def editar_comprobante():
    """Editar comprobante contable."""


# <------------------------------------------------------------------------------------------------------------------------> #
# Series e Identificadores


@contabilidad.route("/series", methods=["GET", "POST"])
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
            database.select(Serie).filter_by(doc=request.args.get("doc", type=str)),
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


@contabilidad.route("/serie/new", methods=["GET", "POST"])
@login_required
@modulo_activo("accounting")
@verifica_acceso("accounting")
def nueva_serie():
    """Nueva Serie."""

    from cacao_accounting.contabilidad.forms import FormularioSerie
    from cacao_accounting.database import Entity, Serie, database

    form = FormularioSerie()

    CONSULTA_ENTIDADES = database.session.execute(database.select(Entity)).all()
    LISTA_DE_ENTIDADES = []

    for e in CONSULTA_ENTIDADES:
        LISTA_DE_ENTIDADES.append((e[0].code, e[0].name))

    form.entidad.choices = LISTA_DE_ENTIDADES

    if form.validate_on_submit() or request.method == "POST":
        SERIE = Serie(
            entity=form.entidad.data,
            doc=form.documento.data,
            serie=form.serie.data,
            enabled=True,
            default=False,
        )

        database.session.add(SERIE)
        database.session.commit()

        return redirect(url_for("contabilidad.series"))

    return render_template(
        "contabilidad/serie_crear.html",
        form=form,
    )
