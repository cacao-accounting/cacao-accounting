# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Modulo de Contabilidad."""

# ---------------------------------------------------------------------------------------
# Libreria estandar
# --------------------------------------------------------------------------------------

# ---------------------------------------------------------------------------------------
# Librerias de terceros
# ---------------------------------------------------------------------------------------
from flask import Blueprint, flash, jsonify, redirect, render_template, request
from flask.helpers import url_for
from flask_login import current_user, login_required
from sqlalchemy import or_

try:  # pragma: no cover - fallback defensivo para contextos sin Flask-Babel inicializado.
    from flask_babel import gettext as _babel_gettext
except ImportError:  # pragma: no cover

    def _(value: str) -> str:
        return value

else:

    def _(value: str) -> str:
        try:
            return _babel_gettext(value)
        except (KeyError, RuntimeError):
            return value


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
from cacao_accounting.setup.service import (
    available_catalog_files,
    create_company,
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


@contabilidad.route("/currency/new", methods=["GET", "POST"])
@login_required
@modulo_activo("accounting")
@verifica_acceso("accounting")
def nueva_moneda():
    """Formulario para crear una nueva moneda."""
    from cacao_accounting.contabilidad.forms import FormularioMoneda
    from cacao_accounting.database import Currency

    formulario = FormularioMoneda()
    TITULO = "Nueva Moneda - " + APPNAME

    if formulario.validate_on_submit():
        DATA = Currency(
            code=formulario.code.data,
            name=formulario.name.data,
            decimals=formulario.decimals.data,
            active=bool(formulario.active.data),
            default=bool(formulario.default.data),
        )
        database.session.add(DATA)
        database.session.commit()
        return redirect(url_for("contabilidad.monedas"))

    return render_template(
        "contabilidad/moneda_crear.html",
        titulo=TITULO,
        form=formulario,
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

    formulario = FormularioEntidad()
    formulario.moneda.choices = obtener_lista_monedas()
    formulario.catalogo_origen.choices = [("", "Seleccione un catálogo existente")] + available_catalog_files()

    TITULO = "Crear Nueva Entidad - " + APPNAME
    if formulario.validate_on_submit():
        try:
            ENTIDAD = create_company(
                {
                    "id": formulario.id.data,
                    "razon_social": formulario.razon_social.data,
                    "nombre_comercial": formulario.nombre_comercial.data,
                    "id_fiscal": formulario.id_fiscal.data,
                    "moneda": formulario.moneda.data,
                    "pais": formulario.pais.data,
                    "tipo_entidad": formulario.tipo_entidad.data,
                    "inicio_anio_fiscal": formulario.inicio_anio_fiscal.data,
                    "fin_anio_fiscal": formulario.fin_anio_fiscal.data,
                },
                catalogo_tipo=formulario.catalogo.data,
                country=formulario.pais.data,
                idioma=formulario.idioma.data,
                catalogo_archivo=formulario.catalogo_origen.data if formulario.catalogo.data == "preexistente" else None,
                status="activo",
                default=False,
            )
        except ValueError as exc:
            database.session.rollback()
            flash(str(exc), "danger")
            return render_template(
                "contabilidad/entidad_crear.html",
                form=formulario,
                titulo=TITULO,
            )

        from cacao_accounting.compras.purchase_reconciliation_service import seed_matching_config_for_company

        seed_matching_config_for_company(ENTIDAD.code)
        database.session.commit()

        return LISTA_ENTIDADES
    elif request.method == "POST":
        flash("Complete los campos correctamente.", "danger")

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
    ENTIDAD[0].enabled = True
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
    ENTIDAD_PREDETERMINADA = database.session.execute(database.select(Entity).filter_by(default=True)).all()

    if ENTIDAD_PREDETERMINADA:
        for e in ENTIDAD_PREDETERMINADA:
            e[0].default = False

    ENTIDAD = database.session.execute(database.select(Entity).filter_by(id=id_entidad)).first()
    ENTIDAD[0].default = True
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
    """Elimina una unidad de negocios de la base de datos."""
    from cacao_accounting.database import Unit

    unidad = database.session.execute(database.select(Unit).filter_by(code=id_unidad)).scalar_one_or_none()
    if unidad:
        database.session.delete(unidad)
        database.session.commit()
    return redirect(url_for("contabilidad.unidades"))


@contabilidad.route("/unit/new", methods=["GET", "POST"])
@login_required
@modulo_activo("accounting")
@verifica_acceso("accounting")
def nueva_unidad():
    """Formulario para crear una nueva unidad de negocios."""
    from cacao_accounting.contabilidad.forms import FormularioUnidad
    from cacao_accounting.database import Unit

    formulario = FormularioUnidad()
    formulario.entidad.choices = obtener_lista_entidades_por_id_razonsocial()
    TITULO = "Crear Nueva Unidad de Negocio - " + APPNAME
    if formulario.validate_on_submit() or request.method == "POST":
        DATA = Unit(
            code=request.form.get("id", None),
            name=request.form.get("nombre", None),
            entity=request.form.get("entidad", None),
            status="activo",
            enabled=bool(formulario.habilitado.data),
        )
        database.session.add(DATA)
        database.session.commit()

        return redirect(url_for("contabilidad.unidades"))
    return render_template(
        "contabilidad/unidad_crear.html",
        titulo=TITULO,
        form=formulario,
    )


# <------------------------------------------------------------------------------------------------------------------------> #
# Libro de Contabilidad
@contabilidad.route("/book/list")
@login_required
@modulo_activo("accounting")
@verifica_acceso("accounting")
def libros():
    """Listado de libros de contabilidad."""
    from cacao_accounting.database import Book, database

    CONSULTA = database.paginate(
        database.select(Book),  # noqa: E712
        page=request.args.get("page", default=1, type=int),
        max_per_page=10,
        count=True,
    )

    TITULO = "Listado de Libros de Contabilidad - " + APPNAME
    return render_template(
        "contabilidad/book_lista.html",
        titulo=TITULO,
        consulta=CONSULTA,
        statusweb=STATUS,
    )


@contabilidad.route("/book/<id_unidad>")
@login_required
@modulo_activo("accounting")
@verifica_acceso("accounting")
def libro(id_unidad):
    """Libro de Contabilidad."""
    from cacao_accounting.database import Book

    REGISTRO = database.session.execute(database.select(Book).filter_by(code=id_unidad)).first()
    return render_template("contabilidad/book.html", registro=REGISTRO[0])


@contabilidad.route("/book/delete/<id_unidad>")
@modulo_activo("accounting")
@login_required
def eliminar_libro(id_unidad):
    """Elimina un libro de contabilidad de la base de datos."""
    from cacao_accounting.database import Book

    libro = database.session.execute(database.select(Book).filter_by(code=id_unidad)).scalar_one_or_none()
    if libro:
        database.session.delete(libro)
        database.session.commit()
    return redirect(url_for("contabilidad.libros"))


@contabilidad.route("/book/edit/<id_libro>", methods=["GET", "POST"])
@login_required
@modulo_activo("accounting")
@verifica_acceso("accounting")
def editar_libro(id_libro):
    """Editar un libro de contabilidad."""
    from cacao_accounting.contabilidad.forms import FormularioLibro
    from cacao_accounting.database import Book

    libro = database.session.execute(database.select(Book).filter_by(code=id_libro)).scalar_one_or_none()
    if libro is None:
        return redirect(url_for("contabilidad.libros"))

    formulario = FormularioLibro(obj=libro)
    formulario.entidad.choices = obtener_lista_entidades_por_id_razonsocial()
    formulario.moneda.choices = obtener_lista_monedas()
    formulario.id.data = libro.code
    formulario.moneda.data = libro.currency
    formulario.estado.data = libro.status or "activo"
    TITULO = "Editar Libro de Contabilidad - " + APPNAME

    if formulario.validate_on_submit():
        libro.name = formulario.nombre.data
        libro.entity = formulario.entidad.data
        libro.currency = formulario.moneda.data
        libro.status = formulario.estado.data
        database.session.commit()
        return redirect(url_for("contabilidad.libros"))

    return render_template(
        "contabilidad/book_crear.html",
        titulo=TITULO,
        form=formulario,
        edit=True,
    )


@contabilidad.route("/book/new", methods=["GET", "POST"])
@login_required
@modulo_activo("accounting")
@verifica_acceso("accounting")
def nuevo_libro():
    """Formulario para crear un nuevo libro de contabilidad."""
    from cacao_accounting.contabilidad.forms import FormularioLibro
    from cacao_accounting.database import Book

    formulario = FormularioLibro()
    formulario.entidad.choices = obtener_lista_entidades_por_id_razonsocial()
    formulario.moneda.choices = obtener_lista_monedas()
    TITULO = "Crear Nuevo Libro de Contabilidad - " + APPNAME
    if formulario.validate_on_submit():
        DATA = Book(
            code=formulario.id.data,
            name=formulario.nombre.data,
            entity=formulario.entidad.data,
            currency=formulario.moneda.data,
            status=formulario.estado.data,
        )
        database.session.add(DATA)
        database.session.commit()

        return redirect(url_for("contabilidad.libros"))
    return render_template(
        "contabilidad/book_crear.html",
        titulo=TITULO,
        form=formulario,
    )


@contabilidad.route("/journal/books")
@login_required
@modulo_activo("accounting")
@verifica_acceso("accounting")
def journal_books():
    """Lista libros activos disponibles para un comprobante contable."""
    from cacao_accounting.database import Book

    company = request.args.get("company", type=str)
    if not company:
        return jsonify({"results": []})

    books = (
        database.session.execute(
            database.select(Book)
            .where(Book.entity == company, or_(Book.status == "activo", Book.status.is_(None)))
            .order_by(Book.is_primary.desc(), Book.code)
        )
        .scalars()
        .all()
    )
    return jsonify(
        {
            "results": [
                {
                    "value": book.code,
                    "display_name": f"{book.code} - {book.name}",
                    "currency": book.currency,
                    "is_primary": bool(book.is_primary),
                }
                for book in books
            ]
        }
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


@contabilidad.route("/account/new", methods=["GET", "POST"])
@login_required
@modulo_activo("accounting")
@verifica_acceso("accounting")
def nueva_cuenta():
    """Formulario para crear una nueva cuenta contable."""
    from cacao_accounting.contabilidad.forms import FormularioCuenta
    from cacao_accounting.database import Accounts

    formulario = FormularioCuenta()
    formulario.entidad.choices = obtener_lista_entidades_por_id_razonsocial()
    formulario.moneda.choices = [("", "Sin moneda específica")] + obtener_lista_monedas()
    formulario.padre.choices = [("", "Sin padre")]
    TITULO = "Nueva Cuenta Contable - " + APPNAME

    if formulario.validate_on_submit():
        DATA = Accounts(
            entity=formulario.entidad.data,
            code=formulario.code.data,
            name=formulario.name.data,
            group=bool(formulario.grupo.data),
            parent=formulario.padre.data or None,
            currency=formulario.moneda.data or None,
            classification=formulario.clasificacion.data or None,
            type_=formulario.tipo.data or None,
            account_type=formulario.account_type.data or None,
            active=bool(formulario.activo.data),
            enabled=bool(formulario.habilitado.data),
        )
        database.session.add(DATA)
        database.session.commit()
        return redirect(url_for("contabilidad.cuentas"))

    return render_template(
        "contabilidad/cuenta_crear.html",
        titulo=TITULO,
        form=formulario,
    )


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


@contabilidad.route("/costs_center/new", methods=["GET", "POST"])
@login_required
@modulo_activo("accounting")
@verifica_acceso("accounting")
def nuevo_centro_costo():
    """Formulario para crear un nuevo centro de costos."""
    from cacao_accounting.contabilidad.forms import FormularioCentroCosto
    from cacao_accounting.database import CostCenter

    formulario = FormularioCentroCosto()
    formulario.entidad.choices = obtener_lista_entidades_por_id_razonsocial()
    formulario.padre.choices = [("", "Sin padre")]
    TITULO = "Nuevo Centro de Costos - " + APPNAME

    if formulario.validate_on_submit():
        DATA = CostCenter(
            entity=formulario.entidad.data,
            code=request.form.get("id", None),
            name=request.form.get("nombre", None),
            active=bool(formulario.activo.data),
            enabled=bool(formulario.habilitado.data),
            default=bool(formulario.predeterminado.data),
            group=bool(formulario.grupo.data),
            parent=request.form.get("padre") or None,
            status="activo",
        )
        database.session.add(DATA)
        database.session.commit()
        return redirect(url_for("contabilidad.ccostos"))

    return render_template(
        "contabilidad/centro-costo_crear.html",
        titulo=TITULO,
        form=formulario,
    )


@contabilidad.route("/costs_center/<id_cc>/edit", methods=["GET", "POST"])
@login_required
@modulo_activo("accounting")
@verifica_acceso("accounting")
def editar_centro_costo(id_cc):
    """Editar un centro de costos existente."""
    from cacao_accounting.contabilidad.forms import FormularioCentroCosto
    from cacao_accounting.database import CostCenter

    registro = database.session.execute(database.select(CostCenter).filter_by(code=id_cc)).scalar_one_or_none()
    if registro is None:
        return redirect(url_for("contabilidad.ccostos"))

    formulario = FormularioCentroCosto(obj=registro)
    formulario.id.data = registro.code
    formulario.entidad.choices = obtener_lista_entidades_por_id_razonsocial()
    formulario.padre.choices = [("", "Sin padre")]
    TITULO = "Editar Centro de Costos - " + APPNAME

    if formulario.validate_on_submit():
        registro.name = request.form.get("nombre", registro.name)
        registro.entity = request.form.get("entidad", registro.entity)
        registro.active = bool(formulario.activo.data)
        registro.enabled = bool(formulario.habilitado.data)
        registro.default = bool(formulario.predeterminado.data)
        registro.group = bool(formulario.grupo.data)
        registro.parent = request.form.get("padre") or None
        database.session.commit()
        return redirect(url_for("contabilidad.centro_costo", id_cc=registro.code))

    return render_template(
        "contabilidad/centro-costo_crear.html",
        titulo=TITULO,
        form=formulario,
        edit=True,
    )


@contabilidad.route("/costs_center/<id_cc>")
@login_required
@modulo_activo("accounting")
@verifica_acceso("accounting")
def centro_costo(id_cc: str):
    """Detalle de un centro de costos."""
    from cacao_accounting.database import CostCenter

    registro = database.session.execute(database.select(CostCenter).filter_by(code=id_cc)).scalars().first()
    if registro is None:
        return redirect(url_for("contabilidad.ccostos"))

    return render_template(
        "contabilidad/centro-costo.html",
        registro=registro,
        statusweb=STATUS,
    )


@contabilidad.route("/costs_center/<id_cc>/delete")
@login_required
@modulo_activo("accounting")
@verifica_acceso("accounting")
def eliminar_centro_costo(id_cc):
    """Elimina un centro de costos."""
    from cacao_accounting.database import CostCenter

    registro = database.session.execute(database.select(CostCenter).filter_by(code=id_cc)).scalar_one_or_none()
    if registro:
        database.session.delete(registro)
        database.session.commit()
    return redirect(url_for("contabilidad.ccostos"))


# <------------------------------------------------------------------------------------------------------------------------> #
# Proyectos
@contabilidad.route("/project/list")
@login_required
@modulo_activo("accounting")
@verifica_acceso("accounting")
def proyectos():
    """Listado de proyectos."""
    from cacao_accounting.database import Project

    consulta = database.paginate(
        database.select(Project),
        page=request.args.get("page", default=1, type=int),
        max_per_page=10,
        count=True,
    )

    return render_template(
        "contabilidad/proyecto_lista.html",
        consulta=consulta,
        titulo="Listado de Proyectos - " + APPNAME,
        statusweb=STATUS,
    )


@contabilidad.route("/project/new", methods=["GET", "POST"])
@login_required
@modulo_activo("accounting")
@verifica_acceso("accounting")
def nuevo_proyecto():
    """Formulario para crear un nuevo proyecto."""
    from cacao_accounting.contabilidad.forms import FormularioProyecto
    from cacao_accounting.database import Project

    formulario = FormularioProyecto()
    formulario.entidad.choices = obtener_lista_entidades_por_id_razonsocial()
    TITULO = "Nuevo Proyecto - " + APPNAME

    if formulario.validate_on_submit():
        DATA = Project(
            code=request.form.get("id", None),
            name=request.form.get("nombre", None),
            entity=request.form.get("entidad", None),
            start=formulario.inicio.data,
            end=formulario.fin.data,
            budget=float(formulario.presupuesto.data or 0),
            enabled=bool(formulario.habilitado.data),
            status=formulario.status.data or "open",
        )
        database.session.add(DATA)
        database.session.commit()
        return redirect(url_for("contabilidad.proyectos"))

    return render_template(
        "contabilidad/proyecto_crear.html",
        titulo=TITULO,
        form=formulario,
    )


@contabilidad.route("/project/<project_id>/edit", methods=["GET", "POST"])
@login_required
@modulo_activo("accounting")
@verifica_acceso("accounting")
def editar_proyecto(project_id):
    """Editar un proyecto existente."""
    from cacao_accounting.contabilidad.forms import FormularioProyecto
    from cacao_accounting.database import Project

    proyecto = database.session.execute(database.select(Project).filter_by(code=project_id)).scalar_one_or_none()
    if proyecto is None:
        return redirect(url_for("contabilidad.proyectos"))

    formulario = FormularioProyecto(obj=proyecto)
    formulario.id.data = proyecto.code
    formulario.entidad.choices = obtener_lista_entidades_por_id_razonsocial()
    TITULO = "Editar Proyecto - " + APPNAME

    if formulario.validate_on_submit():
        proyecto.name = request.form.get("nombre", proyecto.name)
        proyecto.entity = request.form.get("entidad", proyecto.entity)
        proyecto.start = formulario.inicio.data
        proyecto.end = formulario.fin.data
        proyecto.budget = float(formulario.presupuesto.data or 0)
        proyecto.enabled = bool(formulario.habilitado.data)
        proyecto.status = formulario.status.data or "open"
        database.session.commit()
        return redirect(url_for("contabilidad.proyectos"))

    return render_template(
        "contabilidad/proyecto_crear.html",
        titulo=TITULO,
        form=formulario,
        edit=True,
    )


@contabilidad.route("/project/<project_id>/delete")
@login_required
@modulo_activo("accounting")
@verifica_acceso("accounting")
def eliminar_proyecto(project_id):
    """Elimina un proyecto."""
    from cacao_accounting.database import Project

    proyecto = database.session.execute(database.select(Project).filter_by(code=project_id)).scalar_one_or_none()
    if proyecto:
        database.session.delete(proyecto)
        database.session.commit()
    return redirect(url_for("contabilidad.proyectos"))


# <------------------------------------------------------------------------------------------------------------------------> #
# Proyectos
@contabilidad.route("/fiscal_year/list")
@login_required
@modulo_activo("accounting")
@verifica_acceso("accounting")
def fiscal_year_list():
    """Listado de años fiscales."""
    from cacao_accounting.database import FiscalYear

    CONSULTA = database.paginate(
        database.select(FiscalYear),
        page=request.args.get("page", default=1, type=int),
        max_per_page=10,
        count=True,
    )

    return render_template(
        "contabilidad/fiscal_year_lista.html",
        titulo="Años Fiscales - " + APPNAME,
        consulta=CONSULTA,
        statusweb=STATUS,
    )


@contabilidad.route("/fiscal_year/new", methods=["GET", "POST"])
@login_required
@modulo_activo("accounting")
@verifica_acceso("accounting")
def fiscal_year_new():
    """Crear un nuevo año fiscal."""
    from cacao_accounting.contabilidad.forms import FormularioFiscalYear
    from cacao_accounting.database import FiscalYear

    formulario = FormularioFiscalYear()
    formulario.entidad.choices = obtener_lista_entidades_por_id_razonsocial()
    TITULO = "Nuevo Año Fiscal - " + APPNAME

    if formulario.validate_on_submit():
        DATA = FiscalYear(
            entity=request.form.get("entidad", None),
            name=request.form.get("id", None),
            year_start_date=formulario.inicio.data,
            year_end_date=formulario.fin.data,
            is_closed=bool(formulario.cerrado.data),
        )
        database.session.add(DATA)
        database.session.commit()
        return redirect(url_for("contabilidad.fiscal_year_list"))

    return render_template(
        "contabilidad/fiscal_year_crear.html",
        titulo=TITULO,
        form=formulario,
    )


@contabilidad.route("/fiscal_year/<fy_id>/edit", methods=["GET", "POST"])
@login_required
@modulo_activo("accounting")
@verifica_acceso("accounting")
def fiscal_year_edit(fy_id):
    """Editar un año fiscal."""
    from cacao_accounting.contabilidad.forms import FormularioFiscalYear
    from cacao_accounting.database import FiscalYear

    fiscal_year = database.session.execute(database.select(FiscalYear).filter_by(id=fy_id)).scalar_one_or_none()
    if fiscal_year is None:
        return redirect(url_for("contabilidad.fiscal_year_list"))

    formulario = FormularioFiscalYear(obj=fiscal_year)
    formulario.id.data = fiscal_year.name
    formulario.entidad.choices = obtener_lista_entidades_por_id_razonsocial()
    TITULO = "Editar Año Fiscal - " + APPNAME

    if formulario.validate_on_submit():
        fiscal_year.entity = request.form.get("entidad", fiscal_year.entity)
        fiscal_year.name = request.form.get("id", fiscal_year.name)
        fiscal_year.year_start_date = formulario.inicio.data
        fiscal_year.year_end_date = formulario.fin.data
        fiscal_year.is_closed = bool(formulario.cerrado.data)
        database.session.commit()
        return redirect(url_for("contabilidad.fiscal_year_list"))

    return render_template(
        "contabilidad/fiscal_year_crear.html",
        titulo=TITULO,
        form=formulario,
        edit=True,
    )


@contabilidad.route("/fiscal_year/<fy_id>/delete")
@login_required
@modulo_activo("accounting")
@verifica_acceso("accounting")
def fiscal_year_delete(fy_id):
    """Elimina un año fiscal."""
    from cacao_accounting.database import FiscalYear

    fiscal_year = database.session.execute(database.select(FiscalYear).filter_by(id=fy_id)).scalar_one_or_none()
    if fiscal_year:
        database.session.delete(fiscal_year)
        database.session.commit()
    return redirect(url_for("contabilidad.fiscal_year_list"))


# <------------------------------------------------------------------------------------------------------------------------> #
# Años Fiscales
@contabilidad.route("/accounting_period/new", methods=["GET", "POST"])
@login_required
@modulo_activo("accounting")
@verifica_acceso("accounting")
def accounting_period_new():
    """Crear un nuevo período contable."""
    from cacao_accounting.contabilidad.forms import FormularioAccountingPeriod
    from cacao_accounting.database import AccountingPeriod, FiscalYear

    formulario = FormularioAccountingPeriod()
    formulario.entidad.choices = obtener_lista_entidades_por_id_razonsocial()
    formulario.fiscal_year.choices = [("", "Seleccione un año fiscal")]
    fiscal_years = database.session.execute(database.select(FiscalYear)).scalars().all()
    formulario.fiscal_year.choices += [(fy.id, fy.name) for fy in fiscal_years]
    no_fiscal_years = len(fiscal_years) == 0
    TITULO = "Nuevo Período Contable - " + APPNAME

    if formulario.validate_on_submit():
        DATA = AccountingPeriod(
            entity=request.form.get("entidad", None),
            fiscal_year_id=request.form.get("fiscal_year", None),
            name=request.form.get("nombre", None),
            status=request.form.get("status", None),
            enabled=bool(formulario.habilitado.data),
            is_closed=bool(formulario.cerrado.data),
            start=formulario.inicio.data,
            end=formulario.fin.data,
        )
        database.session.add(DATA)
        database.session.commit()
        return redirect(url_for("contabilidad.periodo_contable"))

    return render_template(
        "contabilidad/periodo_crear.html",
        titulo=TITULO,
        form=formulario,
        no_fiscal_years=no_fiscal_years,
    )


@contabilidad.route("/accounting_period/<period_id>/edit", methods=["GET", "POST"])
@login_required
@modulo_activo("accounting")
@verifica_acceso("accounting")
def accounting_period_edit(period_id):
    """Editar un período contable."""
    from cacao_accounting.contabilidad.forms import FormularioAccountingPeriod
    from cacao_accounting.database import AccountingPeriod, FiscalYear

    period = database.session.execute(database.select(AccountingPeriod).filter_by(id=period_id)).scalar_one_or_none()
    if period is None:
        return redirect(url_for("contabilidad.periodo_contable"))

    formulario = FormularioAccountingPeriod(obj=period)
    formulario.id.data = period.name
    fiscal_years = database.session.execute(database.select(FiscalYear)).scalars().all()
    formulario.fiscal_year.choices = [(fy.id, fy.name) for fy in fiscal_years]
    formulario.entidad.choices = obtener_lista_entidades_por_id_razonsocial()
    TITULO = "Editar Período Contable - " + APPNAME

    if formulario.validate_on_submit():
        period.entity = request.form.get("entidad", period.entity)
        period.fiscal_year_id = request.form.get("fiscal_year", period.fiscal_year_id)
        period.name = request.form.get("nombre", period.name)
        period.status = request.form.get("status", period.status)
        period.enabled = bool(formulario.habilitado.data)
        period.is_closed = bool(formulario.cerrado.data)
        period.start = formulario.inicio.data
        period.end = formulario.fin.data
        database.session.commit()
        return redirect(url_for("contabilidad.periodo_contable"))

    return render_template(
        "contabilidad/periodo_crear.html",
        titulo=TITULO,
        form=formulario,
        edit=True,
    )


@contabilidad.route("/accounting_period/<period_id>/delete")
@login_required
@modulo_activo("accounting")
@verifica_acceso("accounting")
def accounting_period_delete(period_id):
    """Elimina un período contable."""
    from cacao_accounting.database import AccountingPeriod

    period = database.session.execute(database.select(AccountingPeriod).filter_by(id=period_id)).scalar_one_or_none()
    if period:
        database.session.delete(period)
        database.session.commit()
    return redirect(url_for("contabilidad.periodo_contable"))


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


@contabilidad.route("/exchange/new", methods=["GET", "POST"])
@login_required
@modulo_activo("accounting")
@verifica_acceso("accounting")
def nueva_tasa_cambio():
    """Formulario para crear una nueva tasa de cambio."""
    from cacao_accounting.contabilidad.forms import FormularioTasaCambio
    from cacao_accounting.database import ExchangeRate

    formulario = FormularioTasaCambio()
    monedas_choices = obtener_lista_monedas()
    formulario.origin.choices = monedas_choices
    formulario.destination.choices = monedas_choices
    TITULO = "Nueva Tasa de Cambio - " + APPNAME

    if formulario.validate_on_submit():
        DATA = ExchangeRate(
            origin=formulario.origin.data,
            destination=formulario.destination.data,
            rate=formulario.rate.data,
            date=formulario.date.data,
        )
        database.session.add(DATA)
        database.session.commit()
        return redirect(url_for("contabilidad.tasa_cambio"))

    return render_template(
        "contabilidad/tc_crear.html",
        titulo=TITULO,
        form=formulario,
    )


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
@contabilidad.route("/journal/list")
@login_required
@modulo_activo("accounting")
@verifica_acceso("accounting")
def listar_comprobantes():
    """Lista comprobantes contables manuales."""
    from cacao_accounting.contabilidad.journal_repository import list_journals

    return render_template(
        "contabilidad/journal_lista.html",
        consulta=list_journals(),
        titulo="Comprobantes Contables - " + APPNAME,
    )


@contabilidad.route("/journal/recurring")
@login_required
@modulo_activo("accounting")
@verifica_acceso("accounting")
def comprobantes_recurrentes():
    """Lista de plantillas de comprobantes recurrentes."""
    from cacao_accounting.database import RecurringJournalTemplate

    consulta = database.paginate(
        database.select(RecurringJournalTemplate).order_by(RecurringJournalTemplate.code),
        page=request.args.get("page", default=1, type=int),
        max_per_page=10,
        count=True,
    )

    return render_template(
        "contabilidad/recurring_journal_lista.html",
        consulta=consulta,
        titulo="Comprobantes Recurrentes - " + APPNAME,
    )


@contabilidad.route("/journal/recurring/new", methods=["GET", "POST"])
@login_required
@modulo_activo("accounting")
@verifica_acceso("accounting")
def nuevo_comprobante_recurrente():
    """Nueva plantilla de comprobante recurrente."""
    from cacao_accounting.contabilidad.forms import FormularioRecurringJournalTemplate
    from cacao_accounting.contabilidad.recurring_journal_service import (
        RecurringJournalError,
        create_recurring_template,
    )
    import json

    formulario = FormularioRecurringJournalTemplate()
    formulario.company.choices = obtener_lista_entidades_por_id_razonsocial()
    formulario.currency.choices = [("", "— Moneda local —")] + obtener_lista_monedas()
    formulario.ledger_id.choices = [("", "— Seleccione libro —")]

    if formulario.validate_on_submit():
        try:
            items_json = request.form.get("items_json")
            if not items_json:
                raise RecurringJournalError("Debe incluir al menos dos líneas contables.")

            items = json.loads(items_json)
            create_recurring_template(
                data={
                    "code": formulario.code.data,
                    "name": formulario.name.data,
                    "company": formulario.company.data,
                    "ledger_id": formulario.ledger_id.data or None,
                    "description": formulario.description.data,
                    "start_date": formulario.start_date.data,
                    "end_date": formulario.end_date.data,
                    "frequency": formulario.frequency.data,
                    "currency": formulario.currency.data or None,
                },
                items=items,
                user_id=str(current_user.id),
            )
            flash("Plantilla de comprobante recurrente creada.", "success")
            return redirect(url_for("contabilidad.comprobantes_recurrentes"))
        except (RecurringJournalError, json.JSONDecodeError) as exc:
            flash(str(exc), "danger")

    return render_template(
        "contabilidad/recurring_journal_nuevo.html",
        form=formulario,
        titulo="Nueva Plantilla Recurrente - " + APPNAME,
    )


@contabilidad.route("/journal/recurring/<identifier>")
@login_required
@modulo_activo("accounting")
@verifica_acceso("accounting")
def ver_plantilla_recurrente(identifier: str):
    """Ver detalle de plantilla recurrente."""
    from cacao_accounting.database import RecurringJournalTemplate, RecurringJournalItem, RecurringJournalApplication

    plantilla = database.session.get(RecurringJournalTemplate, identifier)
    if not plantilla:
        flash("Plantilla no encontrada.", "warning")
        return redirect(url_for("contabilidad.comprobantes_recurrentes"))

    lineas = database.session.query(RecurringJournalItem).filter_by(template_id=plantilla.id).all()
    aplicaciones = (
        database.session.query(RecurringJournalApplication)
        .filter_by(template_id=plantilla.id)
        .order_by(RecurringJournalApplication.application_date.desc())
        .all()
    )

    return render_template(
        "contabilidad/recurring_journal_ver.html",
        plantilla=plantilla,
        lineas=lineas,
        aplicaciones=aplicaciones,
        titulo="Detalle de Plantilla Recurrente - " + APPNAME,
    )


@contabilidad.route("/journal/recurring/<identifier>/approve", methods=["POST"])
@login_required
@modulo_activo("accounting")
@verifica_acceso("accounting")
def aprobar_plantilla_recurrente(identifier: str):
    """Aprueba una plantilla recurrente."""
    from cacao_accounting.contabilidad.recurring_journal_service import RecurringJournalError, approve_recurring_template

    try:
        approve_recurring_template(identifier, user_id=str(current_user.id))
        flash("Plantilla recurrente aprobada.", "success")
    except RecurringJournalError as exc:
        flash(str(exc), "danger")

    return redirect(url_for("contabilidad.ver_plantilla_recurrente", identifier=identifier))


@contabilidad.route("/journal/recurring/<identifier>/cancel", methods=["POST"])
@login_required
@modulo_activo("accounting")
@verifica_acceso("accounting")
def cancelar_plantilla_recurrente(identifier: str):
    """Cancela una plantilla recurrente."""
    from cacao_accounting.contabilidad.recurring_journal_service import RecurringJournalError, cancel_recurring_template

    motivo = request.form.get("reason")
    if not motivo:
        flash("Debe indicar un motivo de cancelación.", "danger")
        return redirect(url_for("contabilidad.ver_plantilla_recurrente", identifier=identifier))

    try:
        cancel_recurring_template(identifier, reason=motivo, user_id=str(current_user.id))
        flash("Plantilla recurrente cancelada.", "warning")
    except RecurringJournalError as exc:
        flash(str(exc), "danger")

    return redirect(url_for("contabilidad.ver_plantilla_recurrente", identifier=identifier))


@contabilidad.route("/period-close/monthly")
@login_required
@modulo_activo("accounting")
@verifica_acceso("accounting")
def asistente_cierre_mensual():
    """Asistente de cierre mensual."""
    from cacao_accounting.database import Entity, Book, AccountingPeriod
    from cacao_accounting.contabilidad.recurring_journal_service import get_applicable_templates

    company_code = request.args.get("company")
    ledger_id = request.args.get("ledger")
    period_id = request.args.get("period")

    entidades = database.session.execute(database.select(Entity)).scalars().all()
    books = []
    if company_code:
        books = database.session.execute(database.select(Book).filter_by(entity=company_code, status="activo")).scalars().all()

    periods = []
    if company_code:
        periods = (
            database.session.execute(database.select(AccountingPeriod).filter_by(entity=company_code, is_closed=False))
            .scalars()
            .all()
        )

    templates = []
    selected_period = None
    if company_code and ledger_id and period_id:
        selected_period = database.session.get(AccountingPeriod, period_id)
        if selected_period:
            templates = get_applicable_templates(company_code, ledger_id, selected_period.end)

    from cacao_accounting.database import RecurringJournalApplication

    applied_ids = []
    if selected_period:
        applied_apps = (
            database.session.query(RecurringJournalApplication)
            .filter_by(
                company=company_code,
                ledger_id=ledger_id,
                fiscal_year=str(selected_period.fiscal_year_id),
                accounting_period=selected_period.name,
                status="applied",
            )
            .all()
        )
        applied_ids = [app.template_id for app in applied_apps]

    return render_template(
        "contabilidad/monthly_close_assistant.html",
        titulo="Asistente de Cierre Mensual - " + APPNAME,
        entidades=entidades,
        books=books,
        periods=periods,
        company_code=company_code,
        ledger_id=ledger_id,
        period_id=period_id,
        templates=templates,
        applied_ids=applied_ids,
        selected_period=selected_period,
    )


@contabilidad.route("/period-close/monthly/apply-recurring", methods=["POST"])
@login_required
@modulo_activo("accounting")
@verifica_acceso("accounting")
def aplicar_recurrentes_cierre():
    """Aplica plantillas recurrentes desde el asistente de cierre."""
    from cacao_accounting.contabilidad.recurring_journal_service import (
        RecurringJournalError,
        apply_recurring_template,
    )
    from cacao_accounting.database import AccountingPeriod

    template_ids = request.form.getlist("template_ids")
    period_id = request.form.get("period_id")
    ledger_id = request.form.get("ledger_id")

    if not template_ids or not period_id:
        flash("Debe seleccionar al menos una plantilla y un periodo.", "warning")
        return redirect(url_for("contabilidad.asistente_cierre_mensual"))

    period = database.session.get(AccountingPeriod, period_id)
    if not period:
        flash("Periodo no encontrado.", "danger")
        return redirect(url_for("contabilidad.asistente_cierre_mensual"))

    success_count = 0
    errors = []

    for tid in template_ids:
        try:
            apply_recurring_template(
                template_id=tid,
                fiscal_year=str(period.fiscal_year_id),
                period_name=period.name,
                application_date=period.end,
                user_id=str(current_user.id),
            )
            success_count += 1
        except RecurringJournalError as exc:
            errors.append(str(exc))

    if success_count > 0:
        flash(f"Se aplicaron {success_count} plantillas correctamente.", "success")
    if errors:
        for err in errors:
            flash(err, "danger")

    return redirect(
        url_for(
            "contabilidad.asistente_cierre_mensual",
            company=period.entity,
            ledger=ledger_id,
            period=period_id,
        )
    )


@contabilidad.route("/journal/new", methods=["GET", "POST"])
@login_required
@modulo_activo("accounting")
@verifica_acceso("accounting")
def nuevo_comprobante():
    """Nuevo comprobante contable."""
    from cacao_accounting.contabilidad.journal_service import (
        JournalValidationError,
        create_journal_draft,
        parse_journal_form,
    )
    from cacao_accounting.form_preferences import DEFAULT_VIEW_KEY, JOURNAL_FORM_KEY, get_form_preference

    if request.method == "POST":
        try:
            journal = create_journal_draft(parse_journal_form(request.form), user_id=str(current_user.id))
        except JournalValidationError as exc:
            flash(str(exc), "danger")
        else:
            flash("Comprobante contable guardado como borrador.", "success")
            return redirect(url_for("contabilidad.ver_comprobante", identifier=journal.id))

    TITULO = "Nuevo Comprobante Contable - " + APPNAME
    column_preferences = get_form_preference(str(current_user.id), JOURNAL_FORM_KEY, DEFAULT_VIEW_KEY)
    initial_journal = {"is_closing": True} if request.args.get("isclosing", "").lower() in {"1", "true", "yes", "on"} else None
    return render_template(
        "contabilidad/journal_nuevo.html",
        titulo=TITULO,
        column_preferences=column_preferences,
        form_key=JOURNAL_FORM_KEY,
        view_key=DEFAULT_VIEW_KEY,
        initial_journal=initial_journal,
        submit_url=url_for("contabilidad.nuevo_comprobante"),
        cancel_url=url_for("contabilidad.conta"),
        currencies=obtener_lista_monedas(),
    )


@contabilidad.route("/journal/<identifier>/submit", methods=["POST"])
@login_required
@modulo_activo("accounting")
@verifica_acceso("accounting")
def contabilizar_comprobante(identifier: str):
    """Contabiliza un comprobante contable manual."""
    from cacao_accounting.contabilidad.journal_service import JournalValidationError, submit_journal

    try:
        submit_journal(identifier)
    except JournalValidationError as exc:
        flash(str(exc), "danger")
    else:
        flash("Comprobante contable contabilizado.", "success")
    return redirect(url_for("contabilidad.ver_comprobante", identifier=identifier))


@contabilidad.route("/journal/<identifier>/reject", methods=["POST"])
@login_required
@modulo_activo("accounting")
@verifica_acceso("accounting")
def rechazar_comprobante(identifier: str):
    """Rechaza un comprobante contable manual en borrador sin afectar ledger."""
    from cacao_accounting.contabilidad.journal_service import JournalValidationError, reject_journal_draft

    try:
        reject_journal_draft(identifier, user_id=str(current_user.id))
    except JournalValidationError as exc:
        flash(str(exc), "danger")
    else:
        flash("Comprobante contable rechazado.", "warning")
    return redirect(url_for("contabilidad.ver_comprobante", identifier=identifier))


@contabilidad.route("/journal/<identifier>/cancel", methods=["POST"])
@login_required
@modulo_activo("accounting")
@verifica_acceso("accounting")
def anular_comprobante(identifier: str):
    """Anula un comprobante contabilizado aplicando reversa en el ledger."""
    from cacao_accounting.contabilidad.journal_service import JournalValidationError, cancel_submitted_journal

    try:
        cancel_submitted_journal(identifier, user_id=str(current_user.id))
    except JournalValidationError as exc:
        flash(str(exc), "danger")
    else:
        flash("Comprobante contable anulado con reversa contable.", "warning")
    return redirect(url_for("contabilidad.ver_comprobante", identifier=identifier))


@contabilidad.route("/journal/<identifier>")
@login_required
@modulo_activo("accounting")
@verifica_acceso("accounting")
def ver_comprobante(identifier: str):
    """Ver comprobante contable."""
    from cacao_accounting.contabilidad.journal_repository import get_journal, list_journal_lines
    from cacao_accounting.contabilidad.journal_service import serialize_journal_for_form
    from cacao_accounting.database import Accounts, Book, CostCenter, Currency, Entity, User

    journal = get_journal(identifier)
    if journal is None:
        flash("El comprobante contable indicado no existe.", "warning")
        return redirect(url_for("contabilidad.conta"))
    creator = database.session.get(User, journal.user_id) if journal.user_id else None
    creator_nickname = creator.user if creator is not None else (journal.user_id or "")
    lineas_raw = list_journal_lines(identifier)

    selected_book_codes = serialize_journal_for_form(journal).get("books") or []
    selected_book_rows = (
        database.session.execute(
            database.select(Book).filter(Book.entity == journal.entity).where(Book.code.in_(selected_book_codes))
        )
        .scalars()
        .all()
        if selected_book_codes
        else []
    )
    selected_books = [
        f"{book.code} - {book.name}" + (f" ({book.currency})" if getattr(book, "currency", None) else "")
        for book in selected_book_rows
    ]
    if not selected_books:
        fallback_book_rows = (
            database.session.execute(
                database.select(Book)
                .filter(Book.entity == journal.entity)
                .where(Book.status.is_(None) | (Book.status == "activo"))
            )
            .scalars()
            .all()
        )
        selected_books = [
            f"{book.code} - {book.name}" + (f" ({book.currency})" if getattr(book, "currency", None) else "")
            for book in fallback_book_rows
        ]
    if not selected_books and journal.book:
        selected_books = [str(journal.book)]

    entity = database.session.get(Entity, journal.entity) if journal.entity else None
    company_currency_code = getattr(entity, "currency", None)
    currency_label = ""
    if journal.transaction_currency:
        currency_row = database.session.get(Currency, journal.transaction_currency)
        if currency_row is not None:
            currency_label = f"{currency_row.code} - {currency_row.name}"
        else:
            currency_label = str(journal.transaction_currency)
    elif company_currency_code:
        company_currency_row = database.session.get(Currency, company_currency_code)
        if company_currency_row is not None:
            currency_label = f"{company_currency_row.code} - {company_currency_row.name}"
        else:
            currency_label = f"{company_currency_code} - {_('Moneda local')}"
    else:
        currency_label = _("Moneda local")

    account_codes = {line.account for line in lineas_raw if line.account}
    cost_center_codes = {line.cost_center for line in lineas_raw if line.cost_center}
    account_rows = (
        database.session.execute(
            database.select(Accounts).filter(Accounts.entity == journal.entity).where(Accounts.code.in_(account_codes))
        )
        .scalars()
        .all()
        if account_codes
        else []
    )
    cost_center_rows = (
        database.session.execute(
            database.select(CostCenter)
            .filter(CostCenter.entity == journal.entity)
            .where(CostCenter.code.in_(cost_center_codes))
        )
        .scalars()
        .all()
        if cost_center_codes
        else []
    )
    account_labels = {row.code: f"{row.code} - {row.name}" if row.name else row.code for row in account_rows}
    cost_center_labels = {row.code: f"{row.code} - {row.name}" if row.name else row.code for row in cost_center_rows}

    lineas = []
    for line in lineas_raw:
        account_code = line.account or ""
        cost_center_code = line.cost_center or ""
        lineas.append(
            {
                "order": line.order,
                "account": account_code,
                "account_label": account_labels.get(account_code, account_code),
                "cost_center": cost_center_code,
                "cost_center_label": cost_center_labels.get(cost_center_code, cost_center_code),
                "third_type": line.third_type,
                "third_code": line.third_code,
                "value": line.value,
                "unit": line.unit,
                "project": line.project,
                "internal_reference": line.internal_reference,
                "internal_reference_id": line.internal_reference_id,
                "reference": line.reference,
                "reference1": line.reference1,
                "reference2": line.reference2,
                "is_advance": line.is_advance,
                "memo": line.memo,
                "line_memo": line.line_memo,
            }
        )

    return render_template(
        "contabilidad/journal.html",
        registro=journal,
        lineas=lineas,
        selected_books=selected_books,
        currency_label=currency_label,
        creator_nickname=creator_nickname,
        titulo="Comprobante Contable - " + APPNAME,
    )


@contabilidad.route("/journal/<identifier>/duplicate", methods=["POST"])
@login_required
@modulo_activo("accounting")
@verifica_acceso("accounting")
def duplicar_comprobante(identifier: str):
    """Duplica un comprobante y crea un nuevo borrador editable."""
    from cacao_accounting.contabilidad.journal_service import JournalValidationError, duplicate_journal_as_draft

    try:
        duplicated = duplicate_journal_as_draft(identifier, user_id=str(current_user.id))
    except JournalValidationError as exc:
        flash(str(exc), "danger")
        return redirect(url_for("contabilidad.ver_comprobante", identifier=identifier))

    flash("Comprobante duplicado como nuevo borrador.", "success")
    return redirect(url_for("contabilidad.editar_comprobante", identifier=duplicated.id))


@contabilidad.route("/journal/<identifier>/revert", methods=["POST"])
@login_required
@modulo_activo("accounting")
@verifica_acceso("accounting")
def revertir_comprobante(identifier: str):
    """Crea borrador de reversión invirtiendo débitos y créditos del comprobante origen."""
    from cacao_accounting.contabilidad.journal_service import JournalValidationError, duplicate_journal_as_reversal_draft

    try:
        reversed_draft = duplicate_journal_as_reversal_draft(identifier, user_id=str(current_user.id))
    except JournalValidationError as exc:
        flash(str(exc), "danger")
        return redirect(url_for("contabilidad.ver_comprobante", identifier=identifier))

    flash("Reversión creada como nuevo borrador editable.", "success")
    return redirect(url_for("contabilidad.editar_comprobante", identifier=reversed_draft.id))


@contabilidad.route("/journal/edit/<identifier>", methods=["GET", "POST"])
@login_required
@modulo_activo("accounting")
@verifica_acceso("accounting")
def editar_comprobante(identifier: str):
    """Editar comprobante contable."""
    from cacao_accounting.contabilidad.journal_repository import get_journal
    from cacao_accounting.contabilidad.journal_service import (
        JournalValidationError,
        parse_journal_form,
        serialize_journal_for_form,
        update_journal_draft,
    )
    from cacao_accounting.form_preferences import DEFAULT_VIEW_KEY, JOURNAL_FORM_KEY, get_form_preference

    journal = get_journal(identifier)
    if journal is None:
        flash("El comprobante contable indicado no existe.", "warning")
        return redirect(url_for("contabilidad.listar_comprobantes"))
    if journal.status != "draft":
        flash("Solo se puede editar un comprobante en borrador.", "warning")
        return redirect(url_for("contabilidad.ver_comprobante", identifier=identifier))

    if request.method == "POST":
        try:
            journal = update_journal_draft(identifier, parse_journal_form(request.form), user_id=str(current_user.id))
        except JournalValidationError as exc:
            flash(str(exc), "danger")
        else:
            flash("Comprobante contable actualizado.", "success")
            return redirect(url_for("contabilidad.ver_comprobante", identifier=journal.id))

    TITULO = "Editar Comprobante Contable - " + APPNAME
    column_preferences = get_form_preference(str(current_user.id), JOURNAL_FORM_KEY, DEFAULT_VIEW_KEY)
    return render_template(
        "contabilidad/journal_nuevo.html",
        titulo=TITULO,
        column_preferences=column_preferences,
        form_key=JOURNAL_FORM_KEY,
        view_key=DEFAULT_VIEW_KEY,
        initial_journal=serialize_journal_for_form(journal),
        submit_url=url_for("contabilidad.editar_comprobante", identifier=identifier),
        cancel_url=url_for("contabilidad.ver_comprobante", identifier=identifier),
        currencies=obtener_lista_monedas(),
    )


# <------------------------------------------------------------------------------------------------------------------------> #
# NamingSeries — CRUD robusto de series de numeracion

# NamingSeries — CRUD robusto de series de numeracion


@contabilidad.route("/naming-series/list")
@login_required
@modulo_activo("accounting")
@verifica_acceso("accounting")
def naming_series_list():
    """Lista de series de numeracion (NamingSeries)."""
    from cacao_accounting.database import NamingSeries, Sequence, SeriesExternalCounterMap, SeriesSequenceMap

    company_filter = request.args.get("company", type=str)

    if company_filter:
        query = database.select(NamingSeries).filter_by(company=company_filter)
    else:
        query = database.select(NamingSeries)

    consulta = database.paginate(
        query.order_by(NamingSeries.entity_type, NamingSeries.name),
        page=request.args.get("page", default=1, type=int),
        max_per_page=20,
        count=True,
    )

    from cacao_accounting.database import Entity

    entidades = database.session.execute(database.select(Entity)).scalars().all()
    sequence_rows = database.session.execute(
        database.select(SeriesSequenceMap.naming_series_id, Sequence)
        .join(Sequence, SeriesSequenceMap.sequence_id == Sequence.id)
        .order_by(SeriesSequenceMap.priority.asc())
    ).all()
    series_sequences = {series_id: sequence for series_id, sequence in sequence_rows}
    external_counter_counts = {
        series_id: count
        for series_id, count in database.session.execute(
            database.select(
                SeriesExternalCounterMap.naming_series_id, database.func.count(SeriesExternalCounterMap.id)
            ).group_by(SeriesExternalCounterMap.naming_series_id)
        ).all()
    }

    return render_template(
        "contabilidad/naming_series_lista.html",
        consulta=consulta,
        entidades=entidades,
        external_counter_counts=external_counter_counts,
        series_sequences=series_sequences,
        company_filter=company_filter,
        titulo="Series de Numeracion - " + APPNAME,
    )


@contabilidad.route("/naming-series/new", methods=["GET", "POST"])
@login_required
@modulo_activo("accounting")
@verifica_acceso("accounting")
def naming_series_new():
    """Nueva serie de numeracion."""
    from cacao_accounting.contabilidad.forms import FormularioNamingSeries
    from cacao_accounting.database import Entity, NamingSeries, Sequence, SeriesSequenceMap
    from cacao_accounting.document_identifiers import enforce_single_default_series

    form = FormularioNamingSeries()
    entidades = database.session.execute(database.select(Entity)).scalars().all()
    company_choices = [("", "— Global (sin compania) —")] + [(e.code, e.name) for e in entidades]
    form.company.choices = company_choices

    if form.validate_on_submit():
        company = form.company.data or None
        is_default = bool(form.is_default.data)

        if is_default:
            enforce_single_default_series(
                entity_type=form.entity_type.data,
                company=company,
                exclude_id=None,
            )

        secuencia = Sequence(
            name=f"{form.nombre.data} sequence",
            current_value=form.current_value.data or 0,
            increment=form.increment.data or 1,
            padding=form.padding.data or 5,
            reset_policy=form.reset_policy.data or "never",
        )
        database.session.add(secuencia)
        database.session.flush()

        nueva = NamingSeries(
            name=form.nombre.data,
            entity_type=form.entity_type.data,
            company=company,
            prefix_template=form.prefix_template.data,
            is_active=bool(form.is_active.data),
            is_default=is_default,
        )
        database.session.add(nueva)
        database.session.flush()
        database.session.add(
            SeriesSequenceMap(
                naming_series_id=nueva.id,
                sequence_id=secuencia.id,
                priority=0,
                condition=None,
            )
        )
        database.session.commit()
        return redirect(url_for("contabilidad.naming_series_list"))

    return render_template(
        "contabilidad/naming_series_nueva.html",
        form=form,
        titulo="Nueva Serie de Numeracion - " + APPNAME,
    )


@contabilidad.route("/naming-series/<series_id>/toggle-default", methods=["POST"])
@login_required
@modulo_activo("accounting")
@verifica_acceso("accounting")
def naming_series_toggle_default(series_id: str):
    """Alterna el estado predeterminado de una serie de numeracion."""
    from cacao_accounting.database import NamingSeries
    from cacao_accounting.document_identifiers import enforce_single_default_series

    serie = database.session.get(NamingSeries, series_id)
    if not serie:
        return redirect(url_for("contabilidad.naming_series_list"))

    if not serie.is_default:
        enforce_single_default_series(
            entity_type=serie.entity_type,
            company=serie.company,
            exclude_id=serie.id,
        )
        serie.is_default = True
    else:
        serie.is_default = False

    database.session.commit()
    return redirect(url_for("contabilidad.naming_series_list"))


@contabilidad.route("/naming-series/<series_id>/edit", methods=["GET", "POST"])
@login_required
@modulo_activo("accounting")
@verifica_acceso("accounting")
def naming_series_edit(series_id: str):
    """Editar una serie de numeracion."""
    from cacao_accounting.contabilidad.forms import FormularioNamingSeries
    from cacao_accounting.database import Entity, NamingSeries, Sequence, SeriesSequenceMap
    from cacao_accounting.document_identifiers import enforce_single_default_series

    serie = database.session.get(NamingSeries, series_id)
    if serie is None:
        return redirect(url_for("contabilidad.naming_series_list"))

    form = FormularioNamingSeries(obj=serie)
    entidades = database.session.execute(database.select(Entity)).scalars().all()
    form.company.choices = [("", "— Global (sin compania) —")] + [(e.code, e.name) for e in entidades]
    form.company.data = serie.company or ""
    form.current_value.data = (
        database.session.execute(
            database.select(Sequence.current_value)
            .join(SeriesSequenceMap, SeriesSequenceMap.sequence_id == Sequence.id)
            .filter(SeriesSequenceMap.naming_series_id == series_id)
        ).scalar_one_or_none()
        or 0
    )

    if form.validate_on_submit():
        company = form.company.data or None
        if form.is_default.data:
            enforce_single_default_series(
                entity_type=form.entity_type.data,
                company=company,
                exclude_id=serie.id,
            )
        serie.name = form.nombre.data
        serie.entity_type = form.entity_type.data
        serie.company = company
        serie.prefix_template = form.prefix_template.data
        serie.is_active = bool(form.is_active.data)
        serie.is_default = bool(form.is_default.data)

        sequence_id = database.session.execute(
            database.select(SeriesSequenceMap.sequence_id).filter_by(naming_series_id=serie.id)
        ).scalar_one_or_none()
        if sequence_id:
            sequence = database.session.get(Sequence, sequence_id)
            if sequence is not None:
                sequence.current_value = form.current_value.data or 0
                sequence.increment = form.increment.data or 1
                sequence.padding = form.padding.data or 5
                sequence.reset_policy = form.reset_policy.data or "never"
            else:
                from cacao_accounting.logs import log

                log.warning(f"Sequence record not found for sequence_id={sequence_id} on series={serie.id}")

        database.session.commit()
        return redirect(url_for("contabilidad.naming_series_list"))

    return render_template(
        "contabilidad/naming_series_nueva.html",
        form=form,
        titulo="Editar Serie de Numeracion - " + APPNAME,
        edit=True,
    )


@contabilidad.route("/naming-series/<series_id>/delete", methods=["GET", "POST"])
@login_required
@modulo_activo("accounting")
@verifica_acceso("accounting")
def naming_series_delete(series_id: str):
    """Eliminar una serie de numeracion si no ha sido utilizada."""
    from cacao_accounting.database import GeneratedIdentifierLog, NamingSeries, SeriesSequenceMap

    serie = database.session.get(NamingSeries, series_id)
    if serie is None:
        return redirect(url_for("contabilidad.naming_series_list"))

    has_history = (
        database.session.execute(
            database.select(GeneratedIdentifierLog)
            .join(SeriesSequenceMap, GeneratedIdentifierLog.sequence_id == SeriesSequenceMap.sequence_id)
            .filter(SeriesSequenceMap.naming_series_id == series_id)
            .limit(1)
        ).scalar_one_or_none()
        is not None
    )
    if not has_history:
        database.session.delete(serie)
        database.session.commit()

    return redirect(url_for("contabilidad.naming_series_list"))


@contabilidad.route("/naming-series/<series_id>/toggle-active", methods=["POST"])
@login_required
@modulo_activo("accounting")
@verifica_acceso("accounting")
def naming_series_toggle_active(series_id: str):
    """Activa o desactiva una serie de numeracion."""
    from cacao_accounting.database import GeneratedIdentifierLog, NamingSeries, SeriesSequenceMap

    serie = database.session.get(NamingSeries, series_id)
    if not serie:
        return redirect(url_for("contabilidad.naming_series_list"))

    if serie.is_active:
        # Comprobar si la serie ya genero identificadores (no se puede eliminar, solo desactivar)
        series_has_generated_identifiers = (
            database.session.execute(
                database.select(GeneratedIdentifierLog)
                .join(SeriesSequenceMap, GeneratedIdentifierLog.sequence_id == SeriesSequenceMap.sequence_id)
                .filter(SeriesSequenceMap.naming_series_id == series_id)
                .limit(1)
            ).scalar_one_or_none()
            is not None
        )
        # Serie utilizada — solo marcarla inactiva, nunca eliminar aunque no haya generado documentos
        _ = series_has_generated_identifiers
        serie.is_active = False
        if serie.is_default:
            serie.is_default = False
    else:
        serie.is_active = True

    database.session.commit()
    return redirect(url_for("contabilidad.naming_series_list"))


# <------------------------------------------------------------------------------------------------------------------------> #
# ExternalCounter — CRUD de contadores externos con auditoria


@contabilidad.route("/external-counter/list")
@login_required
@modulo_activo("accounting")
@verifica_acceso("accounting")
def external_counter_list():
    """Lista de contadores externos."""
    from cacao_accounting.database import ExternalCounter

    company_filter = request.args.get("company", type=str)

    if company_filter:
        query = database.select(ExternalCounter).filter_by(company=company_filter)
    else:
        query = database.select(ExternalCounter)

    consulta = database.paginate(
        query.order_by(ExternalCounter.company, ExternalCounter.name),
        page=request.args.get("page", default=1, type=int),
        max_per_page=20,
        count=True,
    )

    from cacao_accounting.database import Entity

    entidades = database.session.execute(database.select(Entity)).scalars().all()

    return render_template(
        "contabilidad/external_counter_lista.html",
        consulta=consulta,
        entidades=entidades,
        company_filter=company_filter,
        titulo="Contadores Externos - " + APPNAME,
    )


@contabilidad.route("/external-counter/new", methods=["GET", "POST"])
@login_required
@modulo_activo("accounting")
@verifica_acceso("accounting")
def external_counter_new():
    """Nuevo contador externo."""
    from cacao_accounting.contabilidad.forms import FormularioExternalCounter
    from cacao_accounting.database import Entity, ExternalCounter, NamingSeries, SeriesExternalCounterMap

    form = FormularioExternalCounter()
    entidades = database.session.execute(database.select(Entity)).scalars().all()
    form.company.choices = [(e.code, e.name) for e in entidades]

    series_list = (
        database.session.execute(database.select(NamingSeries).filter_by(is_active=True).order_by(NamingSeries.name))
        .scalars()
        .all()
    )
    form.naming_series_id.choices = [("", "— Sin asociar —")] + [(s.id, f"{s.name} ({s.entity_type})") for s in series_list]

    if form.validate_on_submit():
        naming_series_id = form.naming_series_id.data or None
        nuevo = ExternalCounter(
            company=form.company.data,
            name=form.nombre.data,
            counter_type=form.counter_type.data,
            prefix=form.prefix.data or None,
            last_used=form.last_used.data or 0,
            padding=form.padding.data or 5,
            is_active=bool(form.is_active.data),
            description=form.description.data or None,
            naming_series_id=naming_series_id,
        )
        database.session.add(nuevo)
        database.session.flush()
        if naming_series_id:
            database.session.add(
                SeriesExternalCounterMap(
                    naming_series_id=naming_series_id,
                    external_counter_id=nuevo.id,
                    priority=0,
                    condition_json=None,
                )
            )
        database.session.commit()
        return redirect(url_for("contabilidad.external_counter_list"))

    return render_template(
        "contabilidad/external_counter_nuevo.html",
        form=form,
        titulo="Nuevo Contador Externo - " + APPNAME,
    )


@contabilidad.route("/external-counter/<counter_id>/adjust", methods=["GET", "POST"])
@login_required
@modulo_activo("accounting")
@verifica_acceso("accounting")
def external_counter_adjust(counter_id: str):
    """Ajusta el ultimo numero usado de un contador externo con auditoria obligatoria."""
    from flask_login import current_user

    from cacao_accounting.contabilidad.forms import FormularioAjusteContadorExterno
    from cacao_accounting.database import ExternalCounter
    from cacao_accounting.document_identifiers import IdentifierConfigurationError, adjust_external_counter

    counter = database.session.get(ExternalCounter, counter_id)
    if not counter:
        return redirect(url_for("contabilidad.external_counter_list"))

    form = FormularioAjusteContadorExterno()

    if form.validate_on_submit():
        try:
            adjust_external_counter(
                external_counter_id=counter_id,
                new_last_used=form.new_last_used.data,
                reason=form.reason.data,
                changed_by=current_user.id if current_user.is_authenticated else None,
            )
            database.session.commit()
            flash("Contador externo ajustado correctamente.", "success")
        except IdentifierConfigurationError as exc:
            from cacao_accounting.logs import log

            log.warning(f"Error al ajustar contador externo {counter_id}: {exc}")
            flash(str(exc), "danger")
        return redirect(url_for("contabilidad.external_counter_list"))

    return render_template(
        "contabilidad/external_counter_ajuste.html",
        form=form,
        counter=counter,
        titulo="Ajustar Contador Externo - " + APPNAME,
    )


@contabilidad.route("/external-counter/<counter_id>/audit-log")
@login_required
@modulo_activo("accounting")
@verifica_acceso("accounting")
def external_counter_audit_log(counter_id: str):
    """Bitacora de auditoria de un contador externo."""
    from cacao_accounting.database import ExternalCounter, ExternalCounterAuditLog

    counter = database.session.get(ExternalCounter, counter_id)
    if not counter:
        return redirect(url_for("contabilidad.external_counter_list"))

    registros = (
        database.session.execute(
            database.select(ExternalCounterAuditLog)
            .filter_by(external_counter_id=counter_id)
            .order_by(ExternalCounterAuditLog.changed_at.desc())
        )
        .scalars()
        .all()
    )

    return render_template(
        "contabilidad/external_counter_auditoria.html",
        counter=counter,
        registros=registros,
        titulo="Auditoria de Contador Externo - " + APPNAME,
    )
