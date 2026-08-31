"""Modulo de Contabilidad."""

from typing import Any, cast

from decimal import Decimal

from cacao_accounting.exceptions import flash_error

from flask import Blueprint, abort, flash, jsonify, redirect, render_template, request

from flask.helpers import url_for

from flask_login import current_user, login_required

from sqlalchemy import false, or_

from cacao_accounting.contabilidad.services import (
    _company_label,
    _validate_active_entity_submission,
    _accounting_period_status_label,
    _validate_entity_can_be_deactivated,
    _resolve_account_parent,
    _validate_account_parent,
    _build_cost_center_edit_form,
    _build_account_edit_form,
    _resolve_cost_center_parent,
    _validate_cost_center_parent,
    _validate_project_creation_form,
    _populate_project_edit_form,
    _validate_project_edit_form,
    _setup_project_edit_form,
    _render_project_edit_form,
    _resolve_project_budget_currency,
    _update_project_from_form,
    _get_templates_and_applied_ids,
    _get_period_close_checks,
    _monthly_ledger_source_entries,
    _discover_applicable_templates,
    _apply_recurring_templates,
    _record_check_result,
    PeriodCloseError,
    COMPLETED_MONTHLY_CLOSE_STATUSES,
    finalize_monthly_close,
    reopen_accounting_period,
    _handle_exchange_revaluation_post,
    _build_journal_selected_books,
    _build_journal_lineas,
    _get_journal_currency_label,
    _update_series_sequence,
    _update_counter_from_form,
    _sync_counter_naming_series_map,
)

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


from cacao_accounting.contabilidad.presupuesto import presupuestos

from cacao_accounting.contabilidad.auxiliares import (
    build_tree_data,
    obtener_arbol_cuentas,
    obtener_arbol_ccostos,
    obtener_arbol_proyectos,
    obtener_arbol_unidades,
    obtener_catalogo,
    obtener_catalogo_base,
    obtener_catalogo_centros_costo_base,
    obtener_centros_costos,
    obtener_entidad,
    obtener_entidades,
    obtener_lista_entidades_por_id_razonsocial,
    obtener_lista_monedas,
    obtener_lista_monedas_activas,
)

from cacao_accounting.contabilidad.currency_guard import CurrencyGuard, CurrencyGuardError

from cacao_accounting.setup.service import (
    available_catalog_files,
    create_company,
)


from cacao_accounting.contabilidad.gl import gl

from cacao_accounting.audit_trail_service import format_document_timeline

from cacao_accounting.database import (
    STATUS,
    Accounts,
    ComprobanteContable,
    ExchangeRevaluation,
    Project,
    RecurringJournalTemplate,
    database,
)

from cacao_accounting.database.helpers import (
    check_hierarchy_cycle,
    get_descendant_ids,
    obtener_id_modulo_por_nombre,
    update_hierarchy_attributes,
)

from cacao_accounting.decorators import exige_acceso_compania, modulo_activo, verifica_acceso, verifica_permiso

from cacao_accounting.list_filters import apply_list_filters

from cacao_accounting.version import APPNAME


def _accounting_company_scope(query, company_column, action: str = "consultar"):
    """Limit an accounting master-data query to assigned active companies."""
    from cacao_accounting.auth.permisos import Permisos

    permissions = Permisos(modulo=obtener_id_modulo_por_nombre("accounting"), usuario=current_user.id)
    if permissions.administrador:
        return query
    permission_name = {"consultar": "consultar", "crear": "crear", "editar": "editar"}.get(action, "consultar")
    companies = permissions.obtener_companias_autorizadas() if getattr(permissions, permission_name, False) else []
    if not companies:
        return query.where(false())
    return query.where(company_column.in_(companies))


def _accounting_entity_choices(action: str = "consultar") -> list[tuple[str, str]]:
    """Build company choices using the accounting book ACL."""
    from cacao_accounting.database import Entity

    entities = database.session.execute(_accounting_company_scope(database.select(Entity), Entity.code, action)).scalars()
    return [("", "")] + [(entity.code, entity.name) for entity in entities]


def _journal_list_scope(
    query: Any,
    period_from: str | None,
    period_to: str | None,
    selected_company: str | None,
    companies: list[str],
) -> tuple[Any, str | None, Any]:
    """Aplica el filtro de compañía y período al listado de comprobantes."""
    from cacao_accounting.reportes.periods import resolve_period_range

    period_range = None
    if period_from or period_to:
        company = selected_company or (companies[0] if len(companies) == 1 else None)
        if company is None:
            abort(400, description=_("Seleccione una compañía para aplicar el filtro por período."))
        period_range = resolve_period_range(company, period_from, period_to)
        if period_range is not None:
            query = query.where(ComprobanteContable.entity == company)
            query = query.where(ComprobanteContable.date >= period_range.period_start)
            query = query.where(ComprobanteContable.date <= period_range.period_end)
    else:
        company = selected_company or (companies[0] if len(companies) else None)
    return query, company, period_range


def _journal_list_period_values(
    company: str | None,
    period_from: str | None,
    period_to: str | None,
    period_range: Any,
) -> tuple[list[dict[str, Any]], str | None, str | None]:
    """Prepara períodos y valores activos para los filtros del listado."""
    from cacao_accounting.reportes.periods import list_periods_for_company, resolve_period_range

    periods = [
        {"id": str(item.id), "name": item.name, "is_closed": bool(item.is_closed)}
        for item in list_periods_for_company(cast(str, company))
    ]
    active_from, active_to = period_from, period_to
    if period_range is not None:
        active_from, active_to = period_range.from_id, period_range.to_id
    elif not (active_from or active_to):
        current = resolve_period_range(cast(str, company), None, None)
        active_from = active_to = current.from_id if current is not None else ""
    return periods, active_from, active_to


contabilidad = Blueprint("contabilidad", __name__, template_folder="templates")

contabilidad.register_blueprint(gl, url_prefix="/gl")

contabilidad.register_blueprint(presupuestos, url_prefix="/presupuestos")

LISTA_ENTIDADES = redirect("/accounting/entity/list")

CONTABILIDAD_LIBROS = "contabilidad.libros"

SIN_PADRE = "Sin padre"

CONTABILIDAD_CCOSTOS = "contabilidad.ccostos"

CONTABILIDAD_PROYECTOS = "contabilidad.proyectos"

CONTABILIDAD_FISCAL_YEAR_LIST = "contabilidad.fiscal_year_list"

CONTABILIDAD_PERIODO_CONTABLE = "contabilidad.periodo_contable"

CONTABILIDAD_VER_PLANTILLA_RECURRENTE = "contabilidad.ver_plantilla_recurrente"

CONTABILIDAD_ASISTENTE_CIERRE_MENSUAL = "contabilidad.asistente_cierre_mensual"

CONTABILIDAD_VER_CIERRE_MENSUAL = "contabilidad.ver_cierre_mensual"

CONTABILIDAD_VER_COMPROBANTE = "contabilidad.ver_comprobante"

CONTABILIDAD_EDITAR_COMPROBANTE = "contabilidad.editar_comprobante"

CONTABILIDAD_NAMING_SERIES_LIST = "contabilidad.naming_series_list"

CONTABILIDAD_EXTERNAL_COUNTER_LIST = "contabilidad.external_counter_list"

CONTABILIDAD_FISCAL_YEAR_CLOSING_LIST = "contabilidad.fiscal_year_closing_list"

CONTABILIDAD_REVALORIZACION_LIST = "contabilidad.revalorizaciones_cambiarias"

CONTABILIDAD_REVALORIZACION_VER = "contabilidad.ver_revalorizacion_cambiaria"

CONTABILIDAD_MONEDAS = "contabilidad.monedas"

CONTABILIDAD_MONEDA_CREAR_TEMPLATE = "contabilidad/moneda_crear.html"

CONTABILIDAD_MONEDA_NO_EXISTE_MESSAGE = "La moneda indicada no existe."

CONTABILIDAD_UNIDADES = "contabilidad.unidades"

CONTABILIDAD_FISCAL_YEAR_CREAR_TEMPLATE = "contabilidad/fiscal_year_crear.html"

CONTABILIDAD_TASA_CAMBIO = "contabilidad.tasa_cambio"

CONTABILIDAD_PERIODO_NO_EXISTE_MESSAGE = "Periodo no encontrado."

CONTABILIDAD_CIERRE_MENSUAL_NO_EXISTE_MESSAGE = "Cierre mensual no encontrado."

ENTIDAD_NO_EXISTE_MSG = "La entidad indicada no existe."

CONTABILIDAD_CUENTAS_ENDPOINT = "contabilidad.cuentas"
CONTABILIDAD_ENTIDAD_ENDPOINT = "contabilidad.entidad"
ENTRADAS_GL_LABEL = "entradas GL"
MOVIMIENTOS_INVENTARIO_LABEL = "movimientos de inventario"

_TPL_UNIDAD_CREAR = "contabilidad/unidad_crear.html"

_TPL_BOOK_CREAR = "contabilidad/book_crear.html"

_TPL_CUENTA_CREAR = "contabilidad/cuenta_crear.html"

_TPL_CENTRO_COSTO_CREAR = "contabilidad/centro-costo_crear.html"

_TPL_PROYECTO_CREAR = "contabilidad/proyecto_crear.html"

_TPL_PERIODO_CREAR = "contabilidad/periodo_crear.html"

_TPL_TC_CREAR = "contabilidad/tc_crear.html"


def _reject_delete_with_dependencies(label: str, checks: list[tuple[str, Any]]) -> bool:
    """Bloquea eliminaciones cuando existe cualquier registro dependiente."""
    dependencies = [name for name, query in checks if database.session.execute(query.limit(1)).first()]
    if not dependencies:
        return False
    flash(
        f"No se puede eliminar {label}: existen dependencias ({', '.join(dependencies)}). "
        "Desactive el registro para conservar la trazabilidad.",
        "danger",
    )
    return True


@contabilidad.route("/currency/list")
@login_required
@modulo_activo("accounting")
@verifica_acceso("accounting")
def monedas():
    """Listado de monedas registradas en el sistema."""
    from cacao_accounting.database import Currency

    query = database.select(Currency)
    search = request.args.get("search")
    if search:
        query = query.filter(or_(Currency.code.ilike(f"%{search}%"), Currency.name.ilike(f"%{search}%")))

    CONSULTA = database.paginate(
        query,
        page=request.args.get("page", default=1, type=int),
        max_per_page=10,
        count=True,
    )

    TITULO = "Contabilidad | Monedas - " + APPNAME
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
    TITULO = "Contabilidad | Nueva Moneda - " + APPNAME

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
        return redirect(url_for(CONTABILIDAD_MONEDAS))

    return render_template(
        CONTABILIDAD_MONEDA_CREAR_TEMPLATE,
        titulo=TITULO,
        form=formulario,
    )


@contabilidad.route("/currency/<code>")
@login_required
@modulo_activo("accounting")
@verifica_acceso("accounting")
def moneda(code):
    """Vista de una moneda."""
    from cacao_accounting.database import Currency

    registro = database.session.execute(database.select(Currency).filter_by(code=code)).scalar_one_or_none()
    if registro is None:
        flash(_(CONTABILIDAD_MONEDA_NO_EXISTE_MESSAGE), "warning")
        return redirect(url_for(CONTABILIDAD_MONEDAS))

    return render_template(
        "contabilidad/moneda.html",
        registro=registro,
        titulo=f"Contabilidad | Moneda {registro.code} - {APPNAME}",
    )


@contabilidad.route("/currency/<code>/edit", methods=["GET", "POST"])
@login_required
@modulo_activo("accounting")
@verifica_acceso("accounting")
def editar_moneda(code):
    """Edita una moneda."""
    from cacao_accounting.contabilidad.forms import FormularioMoneda
    from cacao_accounting.database import Currency

    registro = database.session.execute(database.select(Currency).filter_by(code=code)).scalar_one_or_none()
    if registro is None:
        flash(_(CONTABILIDAD_MONEDA_NO_EXISTE_MESSAGE), "warning")
        return redirect(url_for(CONTABILIDAD_MONEDAS))

    formulario = FormularioMoneda(obj=registro)
    formulario.code.data = registro.code
    if request.method != "POST":
        formulario.name.data = registro.name
        formulario.decimals.data = registro.decimals
        formulario.active.data = bool(registro.active)
        formulario.default.data = bool(registro.default)
    if formulario.validate_on_submit():
        registro.name = formulario.name.data
        registro.decimals = formulario.decimals.data
        try:
            CurrencyGuard().apply_currency_edit(
                registro,
                active=bool(formulario.active.data),
                default=bool(formulario.default.data),
            )
        except CurrencyGuardError as error:
            flash_error(error)
            return render_template(
                CONTABILIDAD_MONEDA_CREAR_TEMPLATE,
                titulo=f"Contabilidad | Editar Moneda {registro.code} - {APPNAME}",
                form=formulario,
                edit=True,
            )
        database.session.commit()
        return redirect(url_for("contabilidad.moneda", code=registro.code))

    return render_template(
        CONTABILIDAD_MONEDA_CREAR_TEMPLATE,
        titulo=f"Contabilidad | Editar Moneda {registro.code} - {APPNAME}",
        form=formulario,
        edit=True,
    )


@contabilidad.route("/currency/<code>/toggle-active", methods=["POST"])
@login_required
@modulo_activo("accounting")
@verifica_acceso("accounting")
def currency_toggle_active(code):
    """Habilita o deshabilita una moneda."""
    from cacao_accounting.database import Currency

    registro = database.session.execute(database.select(Currency).filter_by(code=code)).scalar_one_or_none()
    if registro is None:
        flash(_(CONTABILIDAD_MONEDA_NO_EXISTE_MESSAGE), "warning")
        return redirect(url_for(CONTABILIDAD_MONEDAS))

    if registro.active:
        try:
            CurrencyGuard().assert_can_deactivate(registro)
        except CurrencyGuardError as error:
            flash_error(error, "warning")
            return redirect(url_for("contabilidad.moneda", code=code))
        registro.active = False
    else:
        registro.active = True

    database.session.commit()
    return redirect(url_for(CONTABILIDAD_MONEDAS))


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


@contabilidad.route("/entity/list")
@login_required
@modulo_activo("accounting")
@verifica_acceso("accounting")
def entidades():
    """Listado de entidades."""
    from cacao_accounting.database import Entity

    query = database.select(Entity)
    search = request.args.get("search")
    if search:
        query = query.filter(
            or_(
                Entity.code.ilike(f"%{search}%"),
                Entity.name.ilike(f"%{search}%"),
                Entity.company_name.ilike(f"%{search}%"),
            )
        )

    CONSULTA = database.paginate(
        query,
        page=request.args.get("page", default=1, type=int),
        max_per_page=10,
        count=True,
    )
    TITULO = "Contabilidad | Entidades - " + APPNAME
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

    registro = database.session.execute(database.select(Entity).filter_by(code=entidad_id)).scalar_one_or_none()
    if registro is None:
        flash(_(ENTIDAD_NO_EXISTE_MSG), "warning")
        return redirect(url_for("contabilidad.entidades"))

    return render_template(
        "contabilidad/entidad.html",
        registro=registro,
        titulo=f"Contabilidad | Entidad {registro.code} - {APPNAME}",
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

    TITULO = "Contabilidad | Nueva Entidad - " + APPNAME
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
            flash_error(exc)
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
    formulario = FormularioEntidad()
    formulario.moneda.choices = obtener_lista_monedas()

    if request.method == "POST":
        ENTIDAD.tax_id = request.form.get("id_fiscal", None)
        ENTIDAD.name = request.form.get("nombre_comercial", None)
        ENTIDAD.company_name = request.form.get("razon_social", None)
        ENTIDAD.phone1 = request.form.get("telefono1", None)
        ENTIDAD.phone2 = request.form.get("telefono2", None)
        ENTIDAD.e_mail = request.form.get("correo_electronico", None)
        ENTIDAD.fax = request.form.get("fax", None)
        ENTIDAD.web = request.form.get("web", None)
        ENTIDAD.enabled = bool(request.form.get("habilitado"))
        database.session.add(ENTIDAD)
        database.session.commit()
        return redirect(url_for(CONTABILIDAD_ENTIDAD_ENDPOINT, entidad_id=ENTIDAD.code))
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
            "habilitado": bool(ENTIDAD.enabled),
        }

        formulario = FormularioEntidad(data=DATA)
        formulario.moneda.choices = obtener_lista_monedas()
        return render_template(
            "contabilidad/entidad_editar.html",
            entidad=ENTIDAD,
            form=formulario,
            titulo=f"Contabilidad | Editar Entidad {ENTIDAD.code} - {APPNAME}",
        )


@contabilidad.route("/entity/delete/<id_entidad>", methods=["POST"])
@login_required
@modulo_activo("accounting")
@verifica_permiso("accounting", "eliminar")
@verifica_acceso("accounting")
def eliminar_entidad(id_entidad):
    """Elimina una entidad de sistema."""
    from cacao_accounting.database import (
        Accounts,
        AccountingPeriod,
        BankAccount,
        Book,
        Budget,
        ComprobanteContable,
        CostCenter,
        Entity,
        FiscalYear,
        GLEntry,
        Project,
        Unit,
    )

    ENTIDAD = database.session.execute(database.select(Entity).filter_by(id=id_entidad)).first()
    if ENTIDAD is None:
        return LISTA_ENTIDADES
    company = ENTIDAD[0].code
    if _reject_delete_with_dependencies(
        f"la entidad {company}",
        [
            ("años fiscales", database.select(FiscalYear.id).filter_by(entity=company)),
            ("períodos contables", database.select(AccountingPeriod.id).filter_by(entity=company)),
            ("libros", database.select(Book.id).filter_by(entity=company)),
            ("cuentas", database.select(Accounts.id).filter_by(entity=company)),
            ("centros de costo", database.select(CostCenter.id).filter_by(entity=company)),
            ("unidades", database.select(Unit.id).filter_by(entity=company)),
            ("proyectos", database.select(Project.id).filter_by(entity=company)),
            ("presupuestos", database.select(Budget.id).filter_by(company=company)),
            ("comprobantes", database.select(ComprobanteContable.id).filter_by(entity=company)),
            (_(ENTRADAS_GL_LABEL), database.select(GLEntry.id).filter_by(company=company)),
            ("cuentas bancarias", database.select(BankAccount.id).filter_by(company=company)),
        ],
    ):
        return redirect(url_for(CONTABILIDAD_ENTIDAD_ENDPOINT, entidad_id=company))
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
    if ENTIDAD is None:
        return LISTA_ENTIDADES
    try:
        _validate_entity_can_be_deactivated(ENTIDAD[0].code)
    except ValueError as error:
        flash_error(error, "warning")
        return redirect(url_for(CONTABILIDAD_ENTIDAD_ENDPOINT, entidad_id=ENTIDAD[0].code))
    ENTIDAD[0].enabled = False
    ENTIDAD[0].status = "inactivo"
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
    if ENTIDAD is None:
        return LISTA_ENTIDADES
    ENTIDAD[0].enabled = True
    if ENTIDAD[0].status != "predeterminado":
        ENTIDAD[0].status = "activo"
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


@contabilidad.route("/unit/list")
@login_required
@modulo_activo("accounting")
@verifica_acceso("accounting")
def unidades():
    """Listado de unidades de negocios."""
    entidad_arg = request.args.get("entidad", None)
    arbol = obtener_arbol_unidades(entidad_=entidad_arg)
    tree_roots, tree_all = build_tree_data(
        arbol,
        parent_field="parent_id",
        id_field="id",
        get_url_func=lambda n: url_for("contabilidad.unidad", id_unidad=n.code),
    )

    TITULO = "Contabilidad | Unidades de Negocio - " + APPNAME
    return render_template(
        "contabilidad/unidad_lista.html",
        titulo=TITULO,
        tree_roots=tree_roots,
        tree_all=tree_all,
        entidades=obtener_entidades(),
        entidad=obtener_entidad(ent=entidad_arg),
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
    return render_template(
        "contabilidad/unidad.html",
        registro=REGISTRO[0],
        titulo=f"Contabilidad | Unidad {REGISTRO[0].code} - {APPNAME}",
    )


@contabilidad.route("/unit/delete/<id_unidad>", methods=["POST"])
@modulo_activo("accounting")
@login_required
@verifica_permiso("accounting", "eliminar")
def eliminar_unidad(id_unidad):
    """Elimina una unidad de negocios de la base de datos."""
    from cacao_accounting.database import Unit

    unidad = database.session.execute(database.select(Unit).filter_by(code=id_unidad)).scalar_one_or_none()
    if unidad:
        if len(unidad.children) > 0:
            flash("No se puede eliminar la unidad porque tiene unidades hijas asignadas (RN-006).", "danger")
            return redirect(url_for(CONTABILIDAD_UNIDADES))
        from cacao_accounting.database import BudgetLine, ComprobanteContableDetalle, GLEntry, StockEntry

        if _reject_delete_with_dependencies(
            f"la unidad {id_unidad}",
            [
                ("presupuestos", database.select(BudgetLine.id).filter_by(business_unit_id=unidad.id)),
                (_(ENTRADAS_GL_LABEL), database.select(GLEntry.id).filter_by(unit_code=unidad.code)),
                ("comprobantes", database.select(ComprobanteContableDetalle.id).filter_by(unit=unidad.code)),
                (_(MOVIMIENTOS_INVENTARIO_LABEL), database.select(StockEntry.id).filter_by(unit_code=unidad.code)),
            ],
        ):
            return redirect(url_for(CONTABILIDAD_UNIDADES))
        database.session.delete(unidad)
        database.session.commit()
    return redirect(url_for(CONTABILIDAD_UNIDADES))


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
    formulario.parent_id.choices = [("", "— Ninguna —")] + [
        (u.id, f"{u.code} - {u.name}")
        for u in database.session.execute(database.select(Unit).order_by(Unit.code)).scalars().all()
    ]
    TITULO = "Contabilidad | Nueva Unidad de Negocio - " + APPNAME
    if formulario.validate_on_submit() or request.method == "POST":
        try:
            _validate_active_entity_submission(request.form.get("entidad", ""))
            parent_id = request.form.get("parent_id") or None
            if parent_id:
                check_hierarchy_cycle(Unit, None, parent_id)
        except ValueError as error:
            flash_error(error)
            return render_template(
                _TPL_UNIDAD_CREAR,
                titulo=TITULO,
                form=formulario,
            )
        DATA = Unit(
            code=request.form.get("id", None),
            name=request.form.get("nombre", None),
            entity=request.form.get("entidad", None),
            status="activo",
            enabled=bool(formulario.habilitado.data),
            parent_id=parent_id,
        )
        database.session.add(DATA)
        database.session.flush()
        update_hierarchy_attributes(DATA)
        database.session.commit()

        return redirect(url_for(CONTABILIDAD_UNIDADES))
    return render_template(
        _TPL_UNIDAD_CREAR,
        titulo=TITULO,
        form=formulario,
    )


@contabilidad.route("/unit/<id_unidad>/edit", methods=["GET", "POST"])
@login_required
@modulo_activo("accounting")
@verifica_acceso("accounting")
def editar_unidad(id_unidad):
    """Editar una unidad de negocios."""
    from cacao_accounting.contabilidad.forms import FormularioUnidad
    from cacao_accounting.database import Unit

    registro = database.session.execute(database.select(Unit).filter_by(code=id_unidad)).scalar_one_or_none()
    if registro is None:
        return redirect(url_for(CONTABILIDAD_UNIDADES))

    exclude_ids = {registro.id, *get_descendant_ids(Unit, registro.id)}
    formulario = FormularioUnidad(obj=registro)
    formulario.entidad.choices = obtener_lista_entidades_por_id_razonsocial()
    formulario.parent_id.choices = [("", "— Ninguna —")] + [
        (u.id, f"{u.code} - {u.name}")
        for u in database.session.execute(database.select(Unit).where(Unit.id.notin_(exclude_ids)).order_by(Unit.code))
        .scalars()
        .all()
    ]
    formulario.id.data = registro.code
    if request.method != "POST":
        formulario.nombre.data = registro.name
        formulario.entidad.data = registro.entity
        formulario.habilitado.data = bool(registro.enabled)
        formulario.parent_id.data = registro.parent_id or ""
    entity_initial_label = _company_label(registro.entity) if registro.entity else ""

    if formulario.validate_on_submit():
        try:
            _validate_active_entity_submission(formulario.entidad.data)
            parent_id = request.form.get("parent_id") or None
            if parent_id:
                check_hierarchy_cycle(Unit, registro.id, parent_id)
        except ValueError as error:
            flash_error(error)
            return render_template(
                _TPL_UNIDAD_CREAR,
                titulo="Editar Unidad de Negocio - " + APPNAME,
                form=formulario,
                edit=True,
                entity_initial_label=entity_initial_label,
            )
        registro.name = formulario.nombre.data
        registro.entity = formulario.entidad.data
        registro.enabled = bool(formulario.habilitado.data)
        registro.parent_id = parent_id
        update_hierarchy_attributes(registro)
        database.session.commit()
        return redirect(url_for("contabilidad.unidad", id_unidad=registro.code))

    return render_template(
        _TPL_UNIDAD_CREAR,
        titulo="Editar Unidad de Negocio - " + APPNAME,
        form=formulario,
        edit=True,
        entity_initial_label=entity_initial_label,
    )


@contabilidad.route("/book/list")
@login_required
@modulo_activo("accounting")
@verifica_acceso("accounting")
def libros():
    """Listado de libros de contabilidad."""
    from cacao_accounting.database import Book, database

    query = database.select(Book)
    search = request.args.get("search")
    if search:
        query = query.filter(or_(Book.code.ilike(f"%{search}%"), Book.name.ilike(f"%{search}%")))

    CONSULTA = database.paginate(
        query,
        page=request.args.get("page", default=1, type=int),
        max_per_page=10,
        count=True,
    )

    TITULO = "Contabilidad | Libros de Contabilidad - " + APPNAME
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
    return render_template(
        "contabilidad/book.html",
        registro=REGISTRO[0],
        titulo=f"Contabilidad | Libro {REGISTRO[0].code} - {APPNAME}",
    )


@contabilidad.route("/book/delete/<id_unidad>", methods=["POST"])
@modulo_activo("accounting")
@login_required
@verifica_permiso("accounting", "eliminar")
def eliminar_libro(id_unidad):
    """Elimina un libro de contabilidad de la base de datos."""
    from cacao_accounting.database import Book

    libro = database.session.execute(database.select(Book).filter_by(code=id_unidad)).scalar_one_or_none()
    if libro:
        from cacao_accounting.database import (
            Budget,
            ComprobanteContable,
            GLEntry,
            RecurringJournalApplication,
            RecurringJournalTemplate,
        )

        if _reject_delete_with_dependencies(
            f"el libro {id_unidad}",
            [
                ("presupuestos", database.select(Budget.id).filter_by(ledger_id=libro.id)),
                ("comprobantes", database.select(ComprobanteContable.id).filter_by(book=libro.code)),
                (_(ENTRADAS_GL_LABEL), database.select(GLEntry.id).filter_by(ledger_id=libro.id)),
                ("plantillas recurrentes", database.select(RecurringJournalTemplate.id).filter_by(ledger_id=libro.id)),
                (
                    "aplicaciones recurrentes",
                    database.select(RecurringJournalApplication.id).filter_by(ledger_id=libro.id),
                ),
            ],
        ):
            return redirect(url_for(CONTABILIDAD_LIBROS))
        database.session.delete(libro)
        database.session.commit()
    return redirect(url_for(CONTABILIDAD_LIBROS))


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
        return redirect(url_for(CONTABILIDAD_LIBROS))

    formulario = FormularioLibro(obj=libro)
    formulario.entidad.choices = obtener_lista_entidades_por_id_razonsocial()
    formulario.moneda.choices = obtener_lista_monedas_activas()
    formulario.id.data = libro.code
    if request.method != "POST":
        formulario.nombre.data = libro.name
        formulario.entidad.data = libro.entity
        formulario.moneda.data = libro.currency
        formulario.estado.data = libro.status or "activo"
    entity_initial_label = _company_label(libro.entity) if libro.entity else ""
    TITULO = "Contabilidad | Editar Libro de Contabilidad - " + APPNAME

    if formulario.validate_on_submit():
        try:
            _validate_active_entity_submission(formulario.entidad.data)
        except ValueError as error:
            flash_error(error)
            return render_template(
                _TPL_BOOK_CREAR,
                titulo=TITULO,
                form=formulario,
                edit=True,
                entity_initial_label=entity_initial_label,
            )
        try:
            if formulario.estado.data == "activo":
                CurrencyGuard().validate_active_currency(
                    formulario.moneda.data,
                    _("No se puede activar un libro con una moneda inactiva."),
                )
            else:
                CurrencyGuard().get_currency(formulario.moneda.data)
        except CurrencyGuardError as error:
            flash_error(error)
            return render_template(
                _TPL_BOOK_CREAR,
                titulo=TITULO,
                form=formulario,
                edit=True,
                entity_initial_label=entity_initial_label,
            )
        from cacao_accounting.database import (
            Budget,
            ComprobanteContable,
            ExchangeRevaluationItem,
            GLEntry,
            PeriodCloseRun,
            RecurringJournalApplication,
            RecurringJournalTemplate,
        )

        history_queries = (
            database.select(GLEntry.id).filter_by(ledger_id=libro.id),
            database.select(ExchangeRevaluationItem.id).filter_by(ledger_id=libro.id),
            database.select(Budget.id).filter_by(ledger_id=libro.id),
            database.select(RecurringJournalTemplate.id).filter_by(ledger_id=libro.id),
            database.select(RecurringJournalApplication.id).filter_by(ledger_id=libro.id),
            database.select(ComprobanteContable.id).filter_by(book=libro.code),
            database.select(PeriodCloseRun.id).filter_by(company=libro.entity),
        )
        if any(database.session.execute(query.limit(1)).scalar_one_or_none() for query in history_queries):
            flash(
                _(
                    "No se puede cambiar compañía o moneda de un libro con historial contable; "
                    "cree un libro nuevo para ese contexto."
                ),
                "danger",
            )
            return render_template(
                _TPL_BOOK_CREAR,
                titulo=TITULO,
                form=formulario,
                edit=True,
                entity_initial_label=entity_initial_label,
            )
        libro.name = formulario.nombre.data
        libro.entity = formulario.entidad.data
        libro.currency = formulario.moneda.data
        libro.status = formulario.estado.data
        database.session.commit()
        return redirect(url_for(CONTABILIDAD_LIBROS))

    return render_template(
        _TPL_BOOK_CREAR,
        titulo=TITULO,
        form=formulario,
        edit=True,
        entity_initial_label=entity_initial_label,
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
    formulario.moneda.choices = obtener_lista_monedas_activas()
    TITULO = "Crear Nuevo Libro de Contabilidad - " + APPNAME
    if formulario.validate_on_submit():
        try:
            _validate_active_entity_submission(formulario.entidad.data)
        except ValueError as error:
            flash_error(error)
            return render_template(
                _TPL_BOOK_CREAR,
                titulo=TITULO,
                form=formulario,
            )
        try:
            if formulario.estado.data == "activo":
                CurrencyGuard().validate_active_currency(
                    formulario.moneda.data,
                    _("No se puede crear un libro activo con una moneda inactiva."),
                )
            else:
                CurrencyGuard().get_currency(formulario.moneda.data)
        except CurrencyGuardError as error:
            flash_error(error)
            return render_template(
                _TPL_BOOK_CREAR,
                titulo=TITULO,
                form=formulario,
            )
        DATA = Book(
            code=formulario.id.data,
            name=formulario.nombre.data,
            entity=formulario.entidad.data,
            currency=formulario.moneda.data,
            status=formulario.estado.data,
        )
        database.session.add(DATA)
        database.session.commit()

        return redirect(url_for(CONTABILIDAD_LIBROS))
    return render_template(
        _TPL_BOOK_CREAR,
        titulo=TITULO,
        form=formulario,
    )


@contabilidad.route("/journal/books")
@login_required
@modulo_activo("accounting")
@verifica_acceso("accounting")
def journal_books():
    """Lista libros activos disponibles para un comprobante contable."""
    from cacao_accounting.auth.permisos import Permisos
    from cacao_accounting.database import Book
    from cacao_accounting.database.helpers import obtener_id_modulo_por_nombre

    company = request.args.get("company", type=str)
    if not company:
        return jsonify({"results": []})

    permisos = Permisos(modulo=obtener_id_modulo_por_nombre("accounting"), usuario=current_user.id)
    if not permisos.tiene_acceso_compania(company):
        return jsonify({"results": []})

    books = (
        database.session.execute(
            database.select(Book)
            .where(Book.entity == company, Book.status == "activo")
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


@contabilidad.route("/accounts", methods=["GET", "POST"])
@login_required
@modulo_activo("accounting")
@verifica_acceso("accounting")
def cuentas():
    """Catalogo de cuentas contables."""
    TITULO = "Catalogo de Cuentas Contables - " + APPNAME

    entidad_arg = request.args.get("entidad", None)
    arbol = obtener_arbol_cuentas(entidad_=entidad_arg)
    tree_roots, tree_all = build_tree_data(
        arbol,
        parent_field="parent",
        id_field="code",
        get_url_func=lambda n: url_for("contabilidad.cuenta", entity=n.entity, id_cta=n.code),
    )
    return render_template(
        "contabilidad/cuenta_lista.html",
        base_cuentas=obtener_catalogo_base(entidad_=entidad_arg),
        cuentas=obtener_catalogo(entidad_=entidad_arg),
        tree_roots=tree_roots,
        tree_all=tree_all,
        entidades=obtener_entidades(),
        entidad=obtener_entidad(ent=entidad_arg),
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
    ).scalar_one_or_none()
    if registro is None:
        flash(_("La cuenta contable no existe"), "warning")
        return redirect(url_for(CONTABILIDAD_CUENTAS_ENDPOINT))

    return render_template(
        "contabilidad/cuenta.html",
        registro=registro,
        statusweb=STATUS,
        titulo=f"Contabilidad | Cuenta {registro.code} - {APPNAME}",
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
    formulario.padre.choices = [("", SIN_PADRE)]
    entity_initial_label = _company_label(formulario.entidad.data) if formulario.entidad.data else ""
    parent_initial_label = ""
    if request.method == "POST" and request.form.get("padre"):
        formulario.padre.choices.append((request.form["padre"], request.form["padre"]))
        entity_initial_label = _company_label(formulario.entidad.data) if formulario.entidad.data else ""
        try:
            _parent_code, parent_initial_label = _resolve_account_parent(formulario.entidad.data, request.form["padre"])
        except ValueError:
            parent_initial_label = request.form["padre"]
    TITULO = "Contabilidad | Nueva Cuenta Contable - " + APPNAME

    if formulario.validate_on_submit():
        try:
            _validate_active_entity_submission(formulario.entidad.data)
        except ValueError as error:
            flash_error(error)
            return render_template(
                _TPL_CUENTA_CREAR,
                titulo=TITULO,
                form=formulario,
                entity_initial_label=entity_initial_label,
                parent_initial_label=parent_initial_label,
            )
        try:
            parent_code = _validate_account_parent(formulario.entidad.data, formulario.padre.data or None)
        except ValueError as error:
            flash_error(error)
            return render_template(
                _TPL_CUENTA_CREAR,
                titulo=TITULO,
                form=formulario,
                entity_initial_label=entity_initial_label,
                parent_initial_label=parent_initial_label,
            )
        DATA = Accounts(
            entity=formulario.entidad.data,
            code=formulario.code.data,
            name=formulario.name.data,
            group=bool(formulario.grupo.data),
            parent=parent_code,
            currency=None,
            classification=formulario.clasificacion.data or None,
            type_=None,
            account_type=formulario.account_type.data or None,
            active=bool(formulario.activo.data),
            enabled=bool(formulario.activo.data),
        )
        database.session.add(DATA)
        database.session.commit()
        return redirect(url_for(CONTABILIDAD_CUENTAS_ENDPOINT))

    return render_template(
        _TPL_CUENTA_CREAR,
        titulo=TITULO,
        form=formulario,
        entity_initial_label=entity_initial_label,
        parent_initial_label=parent_initial_label,
    )


@contabilidad.route("/account/<entity>/<id_cta>/edit", methods=["GET", "POST"])
@login_required
@modulo_activo("accounting")
@verifica_acceso("accounting")
def editar_cuenta(entity, id_cta):
    """Formulario para editar una cuenta contable existente."""
    from cacao_accounting.database import Accounts

    registro = database.session.execute(
        database.select(Accounts).filter(Accounts.code == id_cta, Accounts.entity == entity)
    ).scalar_one_or_none()

    if registro is None:
        flash("La cuenta contable indicada no existe.", "warning")
        return redirect(url_for(CONTABILIDAD_CUENTAS_ENDPOINT))

    formulario, entity_initial_label, parent_initial_label = _build_account_edit_form(registro, entity)
    TITULO = "Contabilidad | Editar Cuenta Contable - " + APPNAME

    if not formulario.validate_on_submit():
        return render_template(
            _TPL_CUENTA_CREAR,
            titulo=TITULO,
            form=formulario,
            edit=True,
            entity_initial_label=entity_initial_label,
            parent_initial_label=parent_initial_label,
        )

    try:
        _validate_active_entity_submission(formulario.entidad.data)
    except ValueError as error:
        flash_error(error)
        return render_template(
            _TPL_CUENTA_CREAR,
            titulo=TITULO,
            form=formulario,
            edit=True,
            entity_initial_label=entity_initial_label,
            parent_initial_label=parent_initial_label,
        )
    try:
        parent_code = _validate_account_parent(
            formulario.entidad.data,
            formulario.padre.data or None,
            current_code=registro.code,
        )
    except ValueError as error:
        flash_error(error)
        return render_template(
            _TPL_CUENTA_CREAR,
            titulo=TITULO,
            form=formulario,
            edit=True,
            entity_initial_label=entity_initial_label,
            parent_initial_label=parent_initial_label,
        )
    registro.name = formulario.name.data
    registro.group = bool(formulario.grupo.data)
    registro.parent = parent_code
    registro.classification = formulario.clasificacion.data or None
    registro.account_type = formulario.account_type.data or None
    registro.active = bool(formulario.activo.data)
    registro.enabled = bool(formulario.activo.data)
    database.session.commit()
    return redirect(url_for("contabilidad.cuenta", entity=entity, id_cta=registro.code))


@contabilidad.route("/costs_center", methods=["GET", "POST"])
@login_required
@modulo_activo("accounting")
@verifica_acceso("accounting")
def ccostos():
    """Catalogo de centros de costos."""
    TITULO = "Catalogo de Centros de Costos - " + APPNAME

    entidad_arg = request.args.get("entidad", None)
    arbol = obtener_arbol_ccostos(entidad_=entidad_arg)
    tree_roots, tree_all = build_tree_data(
        arbol,
        parent_field="parent",
        id_field="code",
        get_url_func=lambda n: url_for("contabilidad.centro_costo", id_cc=n.code),
    )
    return render_template(
        "contabilidad/centro-costo_lista.html",
        base_centro_costos=obtener_catalogo_centros_costo_base(entidad_=entidad_arg),
        ccostos=obtener_centros_costos(entidad_=entidad_arg),
        tree_roots=tree_roots,
        tree_all=tree_all,
        entidades=obtener_entidades(),
        entidad=obtener_entidad(ent=entidad_arg),
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
    formulario.padre.choices = [("", SIN_PADRE)]
    entity_initial_label = _company_label(formulario.entidad.data) if formulario.entidad.data else ""
    parent_initial_label = ""
    if request.method == "POST" and request.form.get("padre"):
        formulario.padre.choices.append((request.form["padre"], request.form["padre"]))
        entity_initial_label = _company_label(formulario.entidad.data) if formulario.entidad.data else ""
        try:
            _parent_code, parent_initial_label = _resolve_cost_center_parent(formulario.entidad.data, request.form["padre"])
        except ValueError:
            parent_initial_label = request.form["padre"]
    TITULO = "Contabilidad | Nuevo Centro de Costos - " + APPNAME

    if formulario.validate_on_submit():
        entity = request.form.get("entidad", formulario.entidad.data)
        try:
            _validate_active_entity_submission(entity)
        except ValueError as error:
            flash_error(error)
            return render_template(
                _TPL_CENTRO_COSTO_CREAR,
                titulo=TITULO,
                form=formulario,
                entity_initial_label=entity_initial_label,
                parent_initial_label=parent_initial_label,
            )
        try:
            parent_code = _validate_cost_center_parent(entity, request.form.get("padre") or None)
        except ValueError as error:
            flash_error(error)
            return render_template(
                _TPL_CENTRO_COSTO_CREAR,
                titulo=TITULO,
                form=formulario,
                entity_initial_label=entity_initial_label,
                parent_initial_label=parent_initial_label,
            )
        DATA = CostCenter(
            entity=entity,
            code=request.form.get("id", None),
            name=request.form.get("nombre", None),
            active=bool(formulario.activo.data),
            enabled=bool(formulario.activo.data),
            default=bool(formulario.predeterminado.data),
            group=bool(formulario.grupo.data),
            parent=parent_code,
            status="activo",
        )
        database.session.add(DATA)
        database.session.commit()
        return redirect(url_for(CONTABILIDAD_CCOSTOS))

    return render_template(
        _TPL_CENTRO_COSTO_CREAR,
        titulo=TITULO,
        form=formulario,
        entity_initial_label=entity_initial_label,
        parent_initial_label=parent_initial_label,
    )


@contabilidad.route("/costs_center/<id_cc>/edit", methods=["GET", "POST"])
@login_required
@modulo_activo("accounting")
@verifica_acceso("accounting")
def editar_centro_costo(id_cc):
    """Editar un centro de costos existente."""
    from cacao_accounting.database import CostCenter

    registro = database.session.execute(database.select(CostCenter).filter_by(code=id_cc)).scalar_one_or_none()
    if registro is None:
        return redirect(url_for(CONTABILIDAD_CCOSTOS))

    formulario, entity_initial_label, parent_initial_label = _build_cost_center_edit_form(registro)
    TITULO = "Contabilidad | Editar Centro de Costos - " + APPNAME

    if not formulario.validate_on_submit():
        return render_template(
            _TPL_CENTRO_COSTO_CREAR,
            titulo=TITULO,
            form=formulario,
            edit=True,
            entity_initial_label=entity_initial_label,
            parent_initial_label=parent_initial_label,
        )

    entity = request.form.get("entidad", registro.entity)
    try:
        _validate_active_entity_submission(entity)
    except ValueError as error:
        flash_error(error)
        return render_template(
            _TPL_CENTRO_COSTO_CREAR,
            titulo=TITULO,
            form=formulario,
            edit=True,
            entity_initial_label=entity_initial_label,
            parent_initial_label=parent_initial_label,
        )
    try:
        parent_code = _validate_cost_center_parent(
            entity,
            request.form.get("padre") or None,
            current_code=registro.code,
        )
    except ValueError as error:
        flash_error(error)
        return render_template(
            _TPL_CENTRO_COSTO_CREAR,
            titulo=TITULO,
            form=formulario,
            edit=True,
            entity_initial_label=entity_initial_label,
            parent_initial_label=parent_initial_label,
        )
    registro.name = request.form.get("nombre", registro.name)
    registro.entity = entity
    registro.active = bool(formulario.activo.data)
    registro.enabled = bool(formulario.activo.data)
    registro.default = bool(formulario.predeterminado.data)
    registro.group = bool(formulario.grupo.data)
    registro.parent = parent_code
    database.session.commit()
    return redirect(url_for("contabilidad.centro_costo", id_cc=registro.code))


@contabilidad.route("/costs_center/<id_cc>")
@login_required
@modulo_activo("accounting")
@verifica_acceso("accounting")
def centro_costo(id_cc: str):
    """Detalle de un centro de costos."""
    from cacao_accounting.database import CostCenter

    registro = database.session.execute(database.select(CostCenter).filter_by(code=id_cc)).scalars().first()
    if registro is None:
        return redirect(url_for(CONTABILIDAD_CCOSTOS))

    return render_template(
        "contabilidad/centro-costo.html",
        registro=registro,
        statusweb=STATUS,
        titulo=f"Contabilidad | Centro de Costos {registro.code} - {APPNAME}",
    )


@contabilidad.route("/costs_center/<id_cc>/delete", methods=["POST"])
@login_required
@modulo_activo("accounting")
@verifica_permiso("accounting", "eliminar")
@verifica_acceso("accounting")
def eliminar_centro_costo(id_cc):
    """Elimina un centro de costos."""
    from cacao_accounting.database import CostCenter

    registro = database.session.execute(database.select(CostCenter).filter_by(code=id_cc)).scalar_one_or_none()
    if registro:
        from cacao_accounting.database import BudgetLine, ComprobanteContableDetalle, GLEntry, StockEntry

        if _reject_delete_with_dependencies(
            f"el centro de costo {id_cc}",
            [
                ("presupuestos", database.select(BudgetLine.id).filter_by(cost_center_id=registro.id)),
                (_(ENTRADAS_GL_LABEL), database.select(GLEntry.id).filter_by(cost_center_code=registro.code)),
                ("comprobantes", database.select(ComprobanteContableDetalle.id).filter_by(cost_center=registro.code)),
                (_(MOVIMIENTOS_INVENTARIO_LABEL), database.select(StockEntry.id).filter_by(cost_center_code=registro.code)),
            ],
        ):
            return redirect(url_for(CONTABILIDAD_CCOSTOS))
        database.session.delete(registro)
        database.session.commit()
    return redirect(url_for(CONTABILIDAD_CCOSTOS))


@contabilidad.route("/project/list")
@login_required
@modulo_activo("accounting")
@verifica_acceso("accounting")
def proyectos():
    """Listado de proyectos."""
    entidad_arg = request.args.get("entidad", None)
    arbol = obtener_arbol_proyectos(entidad_=entidad_arg)
    tree_roots, tree_all = build_tree_data(
        arbol,
        parent_field="parent_id",
        id_field="id",
        get_url_func=lambda n: url_for("contabilidad.proyecto", project_id=n.code),
        get_badges_func=lambda n: [{"class": "bg-success", "label": _("Capitalizable")}] if n.capitalizable else [],
    )

    return render_template(
        "contabilidad/proyecto_lista.html",
        tree_roots=tree_roots,
        tree_all=tree_all,
        entidades=obtener_entidades(),
        entidad=obtener_entidad(ent=entidad_arg),
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

    formulario = FormularioProyecto()
    formulario.entidad.choices = obtener_lista_entidades_por_id_razonsocial()
    formulario.parent_id.choices = [("", "— Ninguno —")] + [
        (p.id, f"{p.code} - {p.name}")
        for p in database.session.execute(database.select(Project).order_by(Project.code)).scalars().all()
    ]
    formulario.capitalization_account_id.choices = [("", "— Seleccionar Cuenta —")] + [
        (a.id, f"{a.code} - {a.name}")
        for a in database.session.execute(database.select(Accounts).order_by(Accounts.code)).scalars().all()
    ]
    TITULO = "Contabilidad | Nuevo Proyecto - " + APPNAME

    if formulario.validate_on_submit() or request.method == "POST":
        try:
            parent_id, capitalization_account_id, capitalizable = _validate_project_creation_form(formulario)
        except ValueError as error:
            flash_error(error)
            return render_template(
                _TPL_PROYECTO_CREAR,
                titulo=TITULO,
                form=formulario,
                budget_currency_code="",
            )
        budget_amount = formulario.presupuesto.data
        budget_currency = None
        if budget_amount is not None:
            try:
                budget_currency = CurrencyGuard().validate_company_functional_currency(request.form.get("entidad")).code
            except CurrencyGuardError as error:
                flash_error(error)
                return render_template(
                    _TPL_PROYECTO_CREAR,
                    titulo=TITULO,
                    form=formulario,
                    budget_currency_code="",
                )
        DATA = Project(
            code=request.form.get("id", None),
            name=request.form.get("nombre", None),
            entity=request.form.get("entidad", None),
            start=formulario.inicio.data,
            end=formulario.fin.data,
            budget=Decimal(str(budget_amount or 0)),
            budget_currency_code=budget_currency,
            enabled=bool(formulario.habilitado.data),
            status=formulario.status.data or "open",
            parent_id=parent_id,
            capitalizable=capitalizable,
            capitalization_account_id=capitalization_account_id,
        )
        database.session.add(DATA)
        database.session.flush()
        update_hierarchy_attributes(DATA)
        database.session.commit()
        return redirect(url_for(CONTABILIDAD_PROYECTOS))

    return render_template(
        _TPL_PROYECTO_CREAR,
        titulo=TITULO,
        form=formulario,
        budget_currency_code="",
    )


@contabilidad.route("/project/<project_id>")
@login_required
@modulo_activo("accounting")
@verifica_acceso("accounting")
def proyecto(project_id):
    """Vista de un proyecto."""
    registro = database.session.execute(database.select(Project).filter_by(code=project_id)).scalar_one_or_none()
    if registro is None:
        flash(_("El proyecto indicado no existe."), "warning")
        return redirect(url_for(CONTABILIDAD_PROYECTOS))

    return render_template(
        "contabilidad/proyecto.html",
        registro=registro,
        statusweb=STATUS,
        titulo=f"Contabilidad | Proyecto {registro.code} - {APPNAME}",
    )


@contabilidad.route("/project/<project_id>/edit", methods=["GET", "POST"])
@login_required
@modulo_activo("accounting")
@verifica_acceso("accounting")
def editar_proyecto(project_id):
    """Editar un proyecto existente."""
    from cacao_accounting.contabilidad.forms import FormularioProyecto

    proyecto = database.session.execute(database.select(Project).filter_by(code=project_id)).scalar_one_or_none()
    if proyecto is None:
        return redirect(url_for(CONTABILIDAD_PROYECTOS))

    formulario = FormularioProyecto(obj=proyecto)
    _setup_project_edit_form(formulario, proyecto)

    if request.method != "POST":
        _populate_project_edit_form(formulario, proyecto)

    entity_initial_label = _company_label(proyecto.entity) if proyecto.entity else ""
    TITULO = "Contabilidad | Editar Proyecto - " + APPNAME

    if formulario.validate_on_submit():
        try:
            _validate_project_edit_form(formulario, proyecto)
        except ValueError as error:
            flash_error(error)
            return _render_project_edit_form(formulario, TITULO, proyecto, entity_initial_label)
        budget_amount = formulario.presupuesto.data
        try:
            budget_currency = _resolve_project_budget_currency(request.form.get("entidad", proyecto.entity), budget_amount)
        except CurrencyGuardError as error:
            flash_error(error)
            return _render_project_edit_form(formulario, TITULO, proyecto, entity_initial_label)
        _update_project_from_form(proyecto, formulario, budget_amount, budget_currency)
        database.session.commit()
        return redirect(url_for(CONTABILIDAD_PROYECTOS))

    return _render_project_edit_form(formulario, TITULO, proyecto, entity_initial_label)


@contabilidad.route("/project/<project_id>/delete", methods=["POST"])
@login_required
@modulo_activo("accounting")
@verifica_permiso("accounting", "eliminar")
@verifica_acceso("accounting")
def eliminar_proyecto(project_id):
    """Elimina un proyecto."""
    proyecto = database.session.execute(database.select(Project).filter_by(code=project_id)).scalar_one_or_none()
    if proyecto:
        if len(proyecto.children) > 0:
            flash("No se puede eliminar el proyecto porque tiene proyectos hijos asignados (RN-006).", "danger")
            return redirect(url_for(CONTABILIDAD_PROYECTOS))
        from cacao_accounting.database import BudgetLine, ComprobanteContableDetalle, GLEntry, StockEntry

        if _reject_delete_with_dependencies(
            f"el proyecto {project_id}",
            [
                ("presupuestos", database.select(BudgetLine.id).filter_by(project_id=proyecto.id)),
                (_(ENTRADAS_GL_LABEL), database.select(GLEntry.id).filter_by(project_code=proyecto.code)),
                ("comprobantes", database.select(ComprobanteContableDetalle.id).filter_by(project=proyecto.code)),
                (_(MOVIMIENTOS_INVENTARIO_LABEL), database.select(StockEntry.id).filter_by(project_code=proyecto.code)),
            ],
        ):
            return redirect(url_for(CONTABILIDAD_PROYECTOS))
        database.session.delete(proyecto)
        database.session.commit()
    return redirect(url_for(CONTABILIDAD_PROYECTOS))


@contabilidad.route("/fiscal_year/list")
@login_required
@modulo_activo("accounting")
@verifica_acceso("accounting")
def fiscal_year_list():
    """Listado de años fiscales."""
    from cacao_accounting.database import FiscalYear

    query = _accounting_company_scope(database.select(FiscalYear), FiscalYear.entity)
    search = request.args.get("search")
    if search:
        query = query.filter(or_(FiscalYear.name.ilike(f"%{search}%"), FiscalYear.entity.ilike(f"%{search}%")))

    CONSULTA = database.paginate(
        query,
        page=request.args.get("page", default=1, type=int),
        max_per_page=10,
        count=True,
    )

    return render_template(
        "contabilidad/fiscal_year_lista.html",
        titulo="Contabilidad | Años Fiscales - " + APPNAME,
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
    formulario.entidad.choices = _accounting_entity_choices("crear")
    TITULO = "Contabilidad | Nuevo Año Fiscal - " + APPNAME

    if formulario.validate_on_submit():
        DATA = FiscalYear(
            entity=request.form.get("entidad", None),
            name=request.form.get("id", None),
            year_start_date=formulario.inicio.data,
            year_end_date=formulario.fin.data,
            is_closed=bool(formulario.cerrado.data),
        )
        exige_acceso_compania("accounting", DATA.entity, "crear")
        database.session.add(DATA)
        database.session.commit()
        return redirect(url_for(CONTABILIDAD_FISCAL_YEAR_LIST))

    return render_template(
        CONTABILIDAD_FISCAL_YEAR_CREAR_TEMPLATE,
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
        return redirect(url_for(CONTABILIDAD_FISCAL_YEAR_LIST))
    exige_acceso_compania("accounting", fiscal_year.entity, "consultar")

    formulario = FormularioFiscalYear(obj=fiscal_year)
    formulario.id.data = fiscal_year.name
    formulario.entidad.choices = _accounting_entity_choices("editar")
    if request.method != "POST":
        formulario.entidad.data = fiscal_year.entity
        formulario.inicio.data = fiscal_year.year_start_date
        formulario.fin.data = fiscal_year.year_end_date
        formulario.cerrado.data = bool(fiscal_year.is_closed)
    entity_initial_label = _company_label(fiscal_year.entity) if fiscal_year.entity else ""
    TITULO = "Contabilidad | Editar Año Fiscal - " + APPNAME

    if formulario.validate_on_submit():
        try:
            requested_entity = request.form.get("entidad", fiscal_year.entity)
            _validate_active_entity_submission(requested_entity)
            if requested_entity != fiscal_year.entity:
                raise ValueError("La compañía del año fiscal no puede cambiarse.")
            exige_acceso_compania("accounting", fiscal_year.entity, "editar")
        except ValueError as error:
            flash_error(error)
            return render_template(
                CONTABILIDAD_FISCAL_YEAR_CREAR_TEMPLATE,
                titulo=TITULO,
                form=formulario,
                edit=True,
                entity_initial_label=entity_initial_label,
            )
        if fiscal_year.financial_closed and not bool(formulario.cerrado.data):
            flash("No se puede abrir un año con cierre contable realizado.", "danger")
            return redirect(url_for("contabilidad.fiscal_year_edit", fy_id=fy_id))

        fiscal_year.name = request.form.get("id", fiscal_year.name)
        fiscal_year.year_start_date = formulario.inicio.data
        fiscal_year.year_end_date = formulario.fin.data
        fiscal_year.is_closed = bool(formulario.cerrado.data)
        database.session.commit()
        return redirect(url_for(CONTABILIDAD_FISCAL_YEAR_LIST))

    return render_template(
        CONTABILIDAD_FISCAL_YEAR_CREAR_TEMPLATE,
        titulo=TITULO,
        form=formulario,
        edit=True,
        entity_initial_label=entity_initial_label,
    )


@contabilidad.route("/fiscal_year/<fy_id>")
@login_required
@modulo_activo("accounting")
@verifica_acceso("accounting")
def fiscal_year_detail(fy_id):
    """Vista de un año fiscal."""
    from cacao_accounting.database import FiscalYear

    registro = database.session.execute(database.select(FiscalYear).filter_by(id=fy_id)).scalar_one_or_none()
    if registro is None:
        flash(_("El año fiscal indicado no existe."), "warning")
        return redirect(url_for(CONTABILIDAD_FISCAL_YEAR_LIST))
    exige_acceso_compania("accounting", registro.entity, "consultar")

    return render_template(
        "contabilidad/fiscal_year.html",
        registro=registro,
        titulo=f"Contabilidad | Año Fiscal {registro.name} - {APPNAME}",
    )


@contabilidad.route("/fiscal_year/<fy_id>/delete", methods=["POST"])
@login_required
@modulo_activo("accounting")
@verifica_permiso("accounting", "eliminar")
@verifica_acceso("accounting")
def fiscal_year_delete(fy_id):
    """Elimina un año fiscal."""
    from cacao_accounting.database import AccountingPeriod, Budget, CashForecast, ComprobanteContable, FiscalYear, GLEntry

    fiscal_year = database.session.execute(database.select(FiscalYear).filter_by(id=fy_id)).scalar_one_or_none()
    if fiscal_year:
        exige_acceso_compania("accounting", fiscal_year.entity, "eliminar")
        if fiscal_year.financial_closed or _reject_delete_with_dependencies(
            f"el año fiscal {fiscal_year.name}",
            [
                ("períodos contables", database.select(AccountingPeriod.id).filter_by(fiscal_year_id=fiscal_year.id)),
                ("presupuestos", database.select(Budget.id).filter_by(fiscal_year_id=fiscal_year.id)),
                ("pronósticos de caja", database.select(CashForecast.id).filter_by(fiscal_year_id=fiscal_year.id)),
                ("comprobantes", database.select(ComprobanteContable.id).filter_by(fiscal_year_id=fiscal_year.id)),
                (_(ENTRADAS_GL_LABEL), database.select(GLEntry.id).filter_by(fiscal_year_id=fiscal_year.id)),
            ],
        ):
            (
                flash("No se puede eliminar un año fiscal cerrado financieramente.", "danger")
                if fiscal_year.financial_closed
                else None
            )
            return redirect(url_for(CONTABILIDAD_FISCAL_YEAR_LIST))
        database.session.delete(fiscal_year)
        database.session.commit()
    return redirect(url_for(CONTABILIDAD_FISCAL_YEAR_LIST))


@contabilidad.route("/accounting_period/new", methods=["GET", "POST"])
@login_required
@modulo_activo("accounting")
@verifica_acceso("accounting")
def accounting_period_new():
    """Crear un nuevo período contable."""
    from cacao_accounting.contabilidad.forms import FormularioAccountingPeriod
    from cacao_accounting.database import AccountingPeriod, FiscalYear

    formulario = FormularioAccountingPeriod()
    formulario.entidad.choices = _accounting_entity_choices("crear")
    formulario.fiscal_year.choices = [("", "Seleccione un año fiscal")]
    fiscal_years = (
        database.session.execute(_accounting_company_scope(database.select(FiscalYear), FiscalYear.entity, "crear"))
        .scalars()
        .all()
    )
    formulario.fiscal_year.choices += [(fy.id, fy.name) for fy in fiscal_years]
    no_fiscal_years = len(fiscal_years) == 0
    TITULO = "Contabilidad | Nuevo Período Contable - " + APPNAME

    if formulario.validate_on_submit():
        try:
            requested_entity = request.form.get("entidad", "")
            _validate_active_entity_submission(requested_entity)
            selected_fiscal_year = database.session.get(FiscalYear, request.form.get("fiscal_year"))
            if not selected_fiscal_year or selected_fiscal_year.entity != requested_entity:
                raise ValueError("El año fiscal debe pertenecer a la compañía del período.")
            exige_acceso_compania("accounting", requested_entity, "crear")
        except ValueError as error:
            flash_error(error)
            return render_template(
                _TPL_PERIODO_CREAR,
                titulo=TITULO,
                form=formulario,
                no_fiscal_years=no_fiscal_years,
            )
        DATA = AccountingPeriod(
            entity=request.form.get("entidad", None),
            fiscal_year_id=request.form.get("fiscal_year", None),
            name=request.form.get("nombre", None),
            status=_accounting_period_status_label(bool(formulario.habilitado.data), False),
            enabled=bool(formulario.habilitado.data),
            is_closed=False,
            start=formulario.inicio.data,
            end=formulario.fin.data,
        )
        database.session.add(DATA)
        database.session.commit()
        return redirect(url_for(CONTABILIDAD_PERIODO_CONTABLE))

    return render_template(
        _TPL_PERIODO_CREAR,
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
        return redirect(url_for(CONTABILIDAD_PERIODO_CONTABLE))
    exige_acceso_compania("accounting", period.entity, "consultar")

    formulario = FormularioAccountingPeriod(obj=period)
    formulario.id.data = period.name
    fiscal_years = (
        database.session.execute(_accounting_company_scope(database.select(FiscalYear), FiscalYear.entity, "editar"))
        .scalars()
        .all()
    )
    formulario.fiscal_year.choices = [(fy.id, fy.name) for fy in fiscal_years]
    formulario.entidad.choices = _accounting_entity_choices("editar")
    if request.method != "POST":
        formulario.entidad.data = period.entity
        formulario.fiscal_year.data = str(period.fiscal_year_id) if period.fiscal_year_id is not None else ""
        formulario.nombre.data = period.name
        formulario.habilitado.data = bool(period.enabled)
        formulario.inicio.data = period.start
        formulario.fin.data = period.end
    entity_initial_label = _company_label(period.entity) if period.entity else ""
    TITULO = "Contabilidad | Editar Período Contable - " + APPNAME

    if formulario.validate_on_submit():
        try:
            requested_entity = request.form.get("entidad", period.entity)
            _validate_active_entity_submission(requested_entity)
            if requested_entity != period.entity:
                raise ValueError("La compañía del período no puede cambiarse.")
            exige_acceso_compania("accounting", period.entity, "editar")
            fiscal_year_id = request.form.get("fiscal_year", period.fiscal_year_id)
            selected_fiscal_year = database.session.get(FiscalYear, fiscal_year_id)
            if not selected_fiscal_year or selected_fiscal_year.entity != period.entity:
                raise ValueError("El año fiscal debe pertenecer a la compañía del período.")
        except ValueError as error:
            flash_error(error)
            return render_template(
                _TPL_PERIODO_CREAR,
                titulo=TITULO,
                form=formulario,
                edit=True,
                entity_initial_label=entity_initial_label,
                period_id=period.id,
                period_is_closed=bool(period.is_closed),
            )
        period.fiscal_year_id = fiscal_year_id
        period.name = request.form.get("nombre", period.name)
        period.status = _accounting_period_status_label(bool(formulario.habilitado.data), bool(period.is_closed))
        period.enabled = bool(formulario.habilitado.data)
        period.start = formulario.inicio.data
        period.end = formulario.fin.data
        database.session.commit()
        return redirect(url_for(CONTABILIDAD_PERIODO_CONTABLE))

    return render_template(
        _TPL_PERIODO_CREAR,
        titulo=TITULO,
        form=formulario,
        edit=True,
        entity_initial_label=entity_initial_label,
        period_id=period.id,
        period_is_closed=bool(period.is_closed),
    )


@contabilidad.route("/accounting_period/<period_id>/reopen", methods=["POST"])
@login_required
@modulo_activo("accounting")
@verifica_acceso("accounting")
def accounting_period_reopen(period_id: str):
    """Reabre un periodo mediante el servicio controlado de cierre mensual."""
    from cacao_accounting.database import AccountingPeriod

    period = database.session.get(AccountingPeriod, period_id)
    if period is None:
        flash(_(CONTABILIDAD_PERIODO_NO_EXISTE_MESSAGE), "danger")
        return redirect(url_for(CONTABILIDAD_PERIODO_CONTABLE))
    exige_acceso_compania("accounting", period.entity, "editar")

    try:
        reopen_accounting_period(
            period_id=period.id,
            user_id=str(current_user.id),
            reason=request.form.get("reason", ""),
        )
    except PeriodCloseError as exc:
        database.session.rollback()
        flash_error(exc)
    else:
        flash(_("El período fue reabierto y la operación quedó registrada en auditoría."), "success")
    return redirect(url_for("contabilidad.accounting_period_edit", period_id=period.id))


@contabilidad.route("/accounting_period/<period_id>/delete", methods=["POST"])
@login_required
@modulo_activo("accounting")
@verifica_permiso("accounting", "eliminar")
@verifica_acceso("accounting")
def accounting_period_delete(period_id):
    """Elimina un período contable."""
    from cacao_accounting.database import AccountingPeriod, BudgetLine, ComprobanteContable, GLEntry, PeriodCloseRun

    period = database.session.execute(database.select(AccountingPeriod).filter_by(id=period_id)).scalar_one_or_none()
    if period:
        exige_acceso_compania("accounting", period.entity, "eliminar")
        if _reject_delete_with_dependencies(
            f"el período {period.name}",
            [
                ("presupuesto", database.select(BudgetLine.id).filter_by(period_id=period.id)),
                ("cierre mensual", database.select(PeriodCloseRun.id).filter_by(period_id=period.id)),
                (_(ENTRADAS_GL_LABEL), database.select(GLEntry.id).filter_by(accounting_period_id=period.id)),
                (
                    "entradas GL por fecha",
                    database.select(GLEntry.id).filter(
                        GLEntry.company == period.entity,
                        GLEntry.posting_date >= period.start,
                        GLEntry.posting_date <= period.end,
                    ),
                ),
                (
                    "comprobantes",
                    database.select(ComprobanteContable.id).filter(
                        ComprobanteContable.entity == period.entity,
                        ComprobanteContable.date >= period.start,
                        ComprobanteContable.date <= period.end,
                    ),
                ),
            ],
        ):
            return redirect(url_for(CONTABILIDAD_PERIODO_CONTABLE))
        database.session.delete(period)
        database.session.commit()
    return redirect(url_for(CONTABILIDAD_PERIODO_CONTABLE))


@contabilidad.route("/accounting_period/<period_id>")
@login_required
@modulo_activo("accounting")
@verifica_acceso("accounting")
def accounting_period_detail(period_id):
    """Vista de un período contable."""
    from cacao_accounting.database import AccountingPeriod

    registro = database.session.execute(database.select(AccountingPeriod).filter_by(id=period_id)).scalar_one_or_none()
    if registro is None:
        flash(_("El período contable indicado no existe."), "warning")
        return redirect(url_for(CONTABILIDAD_PERIODO_CONTABLE))
    exige_acceso_compania("accounting", registro.entity, "consultar")

    return render_template(
        "contabilidad/periodo.html",
        registro=registro,
        titulo=f"Contabilidad | Período {registro.name} - {APPNAME}",
    )


@contabilidad.route("/exchange")
@login_required
@modulo_activo("accounting")
@verifica_acceso("accounting")
def tasa_cambio():
    """Listado de tasas de cambio."""
    from cacao_accounting.database import ExchangeRate

    query = database.select(ExchangeRate)
    search = request.args.get("search")
    if search:
        query = query.filter(or_(ExchangeRate.origin.ilike(f"%{search}%"), ExchangeRate.destination.ilike(f"%{search}%")))

    CONSULTA = database.paginate(
        query,
        page=request.args.get("page", default=1, type=int),
        max_per_page=10,
        count=True,
    )
    TITULO = "Contabilidad | Tasas de Cambio - " + APPNAME

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
    monedas_choices = obtener_lista_monedas_activas()
    formulario.origin.choices = monedas_choices
    formulario.destination.choices = monedas_choices
    TITULO = "Contabilidad | Nueva Tasa de Cambio - " + APPNAME

    if formulario.validate_on_submit():
        try:
            CurrencyGuard().validate_active_currency(
                formulario.origin.data,
                _("La moneda origen debe existir y estar activa."),
            )
            CurrencyGuard().validate_active_currency(
                formulario.destination.data,
                _("La moneda destino debe existir y estar activa."),
            )
        except CurrencyGuardError as error:
            flash_error(error)
            return render_template(
                _TPL_TC_CREAR,
                titulo=TITULO,
                form=formulario,
            )
        if formulario.origin.data == formulario.destination.data:
            flash(_("La moneda origen y destino deben ser diferentes."), "danger")
            return render_template(
                _TPL_TC_CREAR,
                titulo=TITULO,
                form=formulario,
            )
        if formulario.rate.data is None or formulario.rate.data <= 0:
            flash(_("La tasa debe ser mayor a cero."), "danger")
            return render_template(
                _TPL_TC_CREAR,
                titulo=TITULO,
                form=formulario,
            )
        DATA = ExchangeRate(
            origin=formulario.origin.data,
            destination=formulario.destination.data,
            rate=formulario.rate.data,
            date=formulario.date.data,
        )
        database.session.add(DATA)
        database.session.commit()
        return redirect(url_for(CONTABILIDAD_TASA_CAMBIO))

    return render_template(
        _TPL_TC_CREAR,
        titulo=TITULO,
        form=formulario,
    )


@contabilidad.route("/exchange/<rate_id>")
@login_required
@modulo_activo("accounting")
@verifica_acceso("accounting")
def tipo_cambio(rate_id):
    """Vista de una tasa de cambio."""
    from cacao_accounting.database import ExchangeRate

    registro = database.session.execute(database.select(ExchangeRate).filter_by(id=rate_id)).scalar_one_or_none()
    if registro is None:
        flash(_("La tasa de cambio indicada no existe."), "warning")
        return redirect(url_for(CONTABILIDAD_TASA_CAMBIO))

    return render_template(
        "contabilidad/tc.html",
        registro=registro,
        titulo=f"Contabilidad | Tasa {registro.origin}-{registro.destination} - {APPNAME}",
    )


@contabilidad.route("/exchange/<rate_id>/edit", methods=["GET", "POST"])
@login_required
@modulo_activo("accounting")
@verifica_acceso("accounting")
def editar_tasa_cambio(rate_id):
    """Editar una tasa de cambio."""
    from cacao_accounting.contabilidad.forms import FormularioTasaCambio
    from cacao_accounting.database import ExchangeRate

    registro = database.session.execute(database.select(ExchangeRate).filter_by(id=rate_id)).scalar_one_or_none()
    if registro is None:
        flash(_("La tasa de cambio indicada no existe."), "warning")
        return redirect(url_for(CONTABILIDAD_TASA_CAMBIO))

    formulario = FormularioTasaCambio(obj=registro)
    monedas_choices = obtener_lista_monedas_activas()
    formulario.origin.choices = monedas_choices
    formulario.destination.choices = monedas_choices
    if formulario.validate_on_submit():
        if formulario.origin.data == formulario.destination.data:
            flash(_("La moneda origen y destino deben ser diferentes."), "danger")
        elif formulario.rate.data is None or formulario.rate.data <= 0:
            flash(_("La tasa debe ser mayor a cero."), "danger")
        else:
            from cacao_accounting.database import ExchangeRevaluation, ExchangeRevaluationItem, GLEntry

            used_by_gl = database.session.execute(
                database.select(GLEntry.id)
                .where(
                    GLEntry.posting_date == registro.date,
                    GLEntry.account_currency == registro.origin,
                    GLEntry.company_currency == registro.destination,
                    GLEntry.exchange_rate.is_not(None),
                )
                .limit(1)
            ).scalar_one_or_none()
            used_by_revaluation = database.session.execute(
                database.select(ExchangeRevaluationItem.id)
                .join(ExchangeRevaluation, ExchangeRevaluation.id == ExchangeRevaluationItem.revaluation_id)
                .where(
                    ExchangeRevaluation.run_date == registro.date,
                    ExchangeRevaluationItem.original_currency_id == registro.origin,
                    ExchangeRevaluationItem.ledger_currency_id == registro.destination,
                )
                .limit(1)
            ).scalar_one_or_none()
            if used_by_gl or used_by_revaluation:
                flash(
                    _(
                        "No se puede editar una tasa que ya fue utilizada en contabilidad; "
                        "registre una nueva tasa correctiva."
                    ),
                    "danger",
                )
            else:
                registro.origin = formulario.origin.data
                registro.destination = formulario.destination.data
                registro.rate = formulario.rate.data
                registro.date = formulario.date.data
                database.session.commit()
                return redirect(url_for("contabilidad.tipo_cambio", rate_id=registro.id))

    return render_template(
        _TPL_TC_CREAR,
        titulo="Editar Tasa de Cambio - " + APPNAME,
        form=formulario,
        edit=True,
    )


@contabilidad.route("/accounting_period")
@login_required
@modulo_activo("accounting")
@verifica_acceso("accounting")
def periodo_contable():
    """Lista de periodos contables."""
    from cacao_accounting.database import AccountingPeriod

    query = _accounting_company_scope(database.select(AccountingPeriod), AccountingPeriod.entity)
    search = request.args.get("search")
    if search:
        query = query.filter(or_(AccountingPeriod.name.ilike(f"%{search}%"), AccountingPeriod.entity.ilike(f"%{search}%")))

    CONSULTA = database.paginate(
        query,
        page=request.args.get("page", default=1, type=int),
        max_per_page=10,
        count=True,
    )

    TITULO = "Contabilidad | Períodos Contables - " + APPNAME

    return render_template(
        "contabilidad/periodo_lista.html",
        titulo=TITULO,
        consulta=CONSULTA,
        statusweb=STATUS,
    )


@contabilidad.route("/journal/list")
@login_required
@modulo_activo("accounting")
@verifica_acceso("accounting")
def listar_comprobantes():
    """Lista comprobantes contables manuales."""
    from cacao_accounting.contabilidad.journal_service import journal_display_document_name
    from cacao_accounting.database import Entity

    query = (
        database.select(ComprobanteContable)
        .where(ComprobanteContable.is_fiscal_year_closing.is_(False))
        .order_by(ComprobanteContable.date.desc(), ComprobanteContable.created.desc())
    )

    period_from = request.args.get("accounting_period_from") or request.args.get("period_from")
    period_to = request.args.get("accounting_period_to") or request.args.get("period_to")
    selected_company = request.args.get("company")
    companies = list(
        database.session.execute(_accounting_company_scope(database.select(Entity.code), Entity.code, "consultar")).scalars()
    )
    query, company, period_range = _journal_list_scope(query, period_from, period_to, selected_company, companies)

    query = apply_list_filters(
        query,
        ComprobanteContable,
        (
            ComprobanteContable.document_no,
            ComprobanteContable.entity,
            ComprobanteContable.reference,
            ComprobanteContable.memo,
        ),
    )

    consulta = database.paginate(
        query,
        page=request.args.get("page", default=1, type=int),
        max_per_page=10,
        count=True,
    )
    for registro in consulta.items:
        setattr(registro, "display_document_name", journal_display_document_name(registro))

    periods, active_from, active_to = _journal_list_period_values(company, period_from, period_to, period_range)
    return render_template(
        "contabilidad/journal_lista.html",
        consulta=consulta,
        titulo="Comprobantes Contables - " + APPNAME,
        periods=periods,
        period_from=active_from,
        period_to=active_to or active_from,
        company_choices=_accounting_entity_choices(),
        selected_company=company or "",
    )


@contabilidad.route("/journal/recurring")
@login_required
@modulo_activo("accounting")
@verifica_acceso("accounting")
def comprobantes_recurrentes():
    """Lista de plantillas de comprobantes recurrentes."""
    from cacao_accounting.contabilidad.recurring_journal_service import accessible_recurring_template_ids

    accessible_ids = accessible_recurring_template_ids(str(current_user.id))
    query = apply_list_filters(
        database.select(RecurringJournalTemplate)
        .where(RecurringJournalTemplate.id.in_(accessible_ids) if accessible_ids else false())
        .order_by(RecurringJournalTemplate.code),
        RecurringJournalTemplate,
        (
            RecurringJournalTemplate.code,
            RecurringJournalTemplate.name,
            RecurringJournalTemplate.company,
            RecurringJournalTemplate.description,
        ),
        include_status=False,
    )
    consulta = database.paginate(
        query,
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
            selected_books = request.form.getlist("books")
            ledger_id = selected_books[0] if selected_books else formulario.ledger_id.data
            create_recurring_template(
                data={
                    "code": formulario.code.data,
                    "name": formulario.name.data,
                    "company": formulario.company.data,
                    "ledger_id": ledger_id or None,
                    "books": selected_books,
                    "naming_series_id": request.form.get("naming_series_id") or None,
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
            flash_error(exc)

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
    from cacao_accounting.contabilidad.recurring_journal_service import (
        RecurringJournalError,
        validate_recurring_template_access,
    )
    from cacao_accounting.database import RecurringJournalTemplate, RecurringJournalItem, RecurringJournalApplication

    plantilla = database.session.get(RecurringJournalTemplate, identifier)
    if not plantilla:
        flash("Plantilla no encontrada.", "warning")
        return redirect(url_for("contabilidad.comprobantes_recurrentes"))
    try:
        validate_recurring_template_access(plantilla, str(current_user.id), "consultar")
    except RecurringJournalError:
        abort(403)

    lineas = database.session.query(RecurringJournalItem).filter_by(template_id=plantilla.id).all()
    aplicaciones = (
        database.session.query(RecurringJournalApplication)
        .filter_by(template_id=plantilla.id)
        .order_by(RecurringJournalApplication.application_date.desc())
        .all()
    )

    audit_timeline = format_document_timeline("recurring_journal_template", plantilla.id)
    return render_template(
        "contabilidad/recurring_journal_ver.html",
        plantilla=plantilla,
        lineas=lineas,
        aplicaciones=aplicaciones,
        titulo="Detalle de Plantilla Recurrente - " + APPNAME,
        audit_timeline=audit_timeline,
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
        flash_error(exc)

    return redirect(url_for(CONTABILIDAD_VER_PLANTILLA_RECURRENTE, identifier=identifier))


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
        return redirect(url_for(CONTABILIDAD_VER_PLANTILLA_RECURRENTE, identifier=identifier))

    try:
        cancel_recurring_template(identifier, reason=motivo, user_id=str(current_user.id))
        flash("Plantilla recurrente cancelada.", "warning")
    except RecurringJournalError as exc:
        flash_error(exc)

    return redirect(url_for(CONTABILIDAD_VER_PLANTILLA_RECURRENTE, identifier=identifier))


@contabilidad.route("/period-close/monthly")
@login_required
@modulo_activo("accounting")
@verifica_acceso("accounting")
def asistente_cierre_mensual():
    """Lista de ejecuciones de cierre mensual."""
    from cacao_accounting.auth.permisos import Permisos
    from cacao_accounting.database import AccountingPeriod, PeriodCloseRun

    permisos = Permisos(modulo=obtener_id_modulo_por_nombre("accounting"), usuario=current_user.id)
    companies = permisos.obtener_companias_autorizadas() if permisos.consultar else []

    runs = (
        database.session.execute(
            database.select(PeriodCloseRun)
            .where(PeriodCloseRun.company.in_(companies) if companies else false())
            .order_by(PeriodCloseRun.created.desc(), PeriodCloseRun.id.desc())
        )
        .scalars()
        .all()
    )
    periods = (
        database.session.execute(
            database.select(AccountingPeriod)
            .where(AccountingPeriod.is_closed.is_(False))
            .where(AccountingPeriod.entity.in_(companies) if companies else false())
        )
        .scalars()
        .all()
    )
    period_by_id = {period.id: period for period in periods}

    return render_template(
        "contabilidad/monthly_close_assistant.html",
        titulo="Asistente de Cierre Mensual - " + APPNAME,
        runs=runs,
        periods=periods,
        period_by_id=period_by_id,
    )


@contabilidad.route("/period-close/monthly/new", methods=["POST"])
@login_required
@modulo_activo("accounting")
@verifica_acceso("accounting")
def nuevo_cierre_mensual():
    """Crea un registro de cierre mensual para un periodo."""
    from cacao_accounting.database import AccountingPeriod, PeriodCloseRun

    period_id = request.form.get("period_id")
    period = database.session.get(AccountingPeriod, period_id)
    if not period:
        flash(CONTABILIDAD_PERIODO_NO_EXISTE_MESSAGE, "danger")
        return redirect(url_for(CONTABILIDAD_ASISTENTE_CIERRE_MENSUAL))
    exige_acceso_compania("accounting", period.entity, "autorizar")

    existing = database.session.execute(
        database.select(PeriodCloseRun).filter_by(company=period.entity, period_id=period.id)
    ).scalar_one_or_none()
    if existing:
        flash("Ya existe un cierre mensual para ese periodo.", "warning")
        return redirect(url_for(CONTABILIDAD_VER_CIERRE_MENSUAL, identifier=existing.id))

    close_run = PeriodCloseRun(company=period.entity, period_id=period.id, run_status="open")
    database.session.add(close_run)
    database.session.commit()
    flash("Cierre mensual creado.", "success")
    return redirect(url_for(CONTABILIDAD_VER_CIERRE_MENSUAL, identifier=close_run.id))


@contabilidad.route("/period-close/monthly/<identifier>/project-capitalization", methods=["POST"])
@login_required
@modulo_activo("accounting")
@verifica_acceso("accounting")
def ejecutar_capitalizacion_cierre(identifier: str):
    """Ejecuta la capitalización automática de proyectos desde el asistente de cierre mensual."""
    from cacao_accounting.contabilidad.project_capitalization_service import ProjectCapitalizationService
    from cacao_accounting.database import AccountingPeriod, PeriodCloseRun, PeriodCloseCheck

    close_run = database.session.get(PeriodCloseRun, identifier)
    if not close_run:
        flash(CONTABILIDAD_CIERRE_MENSUAL_NO_EXISTE_MESSAGE, "danger")
        return redirect(url_for(CONTABILIDAD_ASISTENTE_CIERRE_MENSUAL))

    period = database.session.get(AccountingPeriod, close_run.period_id)
    if not period:
        flash(CONTABILIDAD_PERIODO_NO_EXISTE_MESSAGE, "danger")
        return redirect(url_for(CONTABILIDAD_VER_CIERRE_MENSUAL, identifier=close_run.id))

    try:
        success_count, errors = ProjectCapitalizationService().run_capitalization(
            company=close_run.company, period_id=str(period.id), user_id=str(current_user.id)
        )
    except Exception as exc:
        database.session.rollback()
        database.session.add(
            PeriodCloseCheck(
                close_run_id=close_run.id, check_type="project_capitalization", check_status="failed", message=str(exc)
            )
        )
        database.session.commit()
        flash_error(exc)
        return redirect(url_for(CONTABILIDAD_VER_CIERRE_MENSUAL, identifier=close_run.id))

    close_run.run_status = "in_progress"
    check_status = "passed" if not errors else "failed"
    message = f"Proyectos capitalizados: {success_count}."
    if errors:
        message += f" Errores: {' | '.join(errors)}"

    database.session.add(
        PeriodCloseCheck(
            close_run_id=close_run.id, check_type="project_capitalization", check_status=check_status, message=message
        )
    )
    database.session.commit()
    flash(f"La capitalización automática de proyectos finalizó con {success_count} registros procesados.", "success")
    if errors:
        for err in errors:
            flash(err, "danger")

    return redirect(url_for(CONTABILIDAD_VER_CIERRE_MENSUAL, identifier=close_run.id))


@contabilidad.route("/period-close/monthly/<identifier>")
@login_required
@modulo_activo("accounting")
@verifica_acceso("accounting")
def ver_cierre_mensual(identifier: str):
    """Vista paso a paso de una ejecución de cierre mensual."""
    from cacao_accounting.database import AccountingPeriod, PeriodCloseRun

    close_run = database.session.get(PeriodCloseRun, identifier)
    if not close_run:
        flash(CONTABILIDAD_CIERRE_MENSUAL_NO_EXISTE_MESSAGE, "warning")
        return redirect(url_for(CONTABILIDAD_ASISTENTE_CIERRE_MENSUAL))

    period = database.session.get(AccountingPeriod, close_run.period_id)
    templates, applied_ids = _get_templates_and_applied_ids(close_run, period)
    checks = _get_period_close_checks(close_run)
    for check in checks:
        check.source_links = []
        if check.check_status in COMPLETED_MONTHLY_CLOSE_STATUSES:
            continue
        if check.check_type == "ledger_integrity" and period:
            for source in _monthly_ledger_source_entries(close_run.company, period.start, period.end):
                endpoint = {
                    "salesinvoice": ("ventas.ventas_factura_venta", "invoice_id"),
                    "purchaseinvoice": ("compras.compras_factura_compra", "invoice_id"),
                    "paymententry": ("bancos.bancos_pago", "payment_id"),
                    "comprobantecontable": ("contabilidad.ver_comprobante", "identifier"),
                }.get(source["voucher_type"].lower().replace("_", "").replace(" ", ""))
                if endpoint:
                    ep_name: str = endpoint[0]
                    ep_param: str = endpoint[1]
                    check.source_links.append(
                        {
                            "label": source["label"],
                            "url": url_for(ep_name, **{ep_param: source["voucher_id"]}),  # type: ignore[arg-type]
                        }
                    )
                else:
                    check.source_links.append({"label": source["label"], "url": None})
        elif check.check_type == "subledger_integrity" and period:
            check.source_links.append(
                {
                    "label": "Matriz de conciliación detallada",
                    "url": url_for(
                        "reportes.reconciliation_matrix",
                        company=close_run.company,
                        accounting_period=period.name,
                        as_of_date=period.end.isoformat(),
                    ),
                }
            )

    return render_template(
        "contabilidad/monthly_close_assistant.html",
        titulo="Asistente de Cierre Mensual - " + APPNAME,
        close_run=close_run,
        selected_period=period,
        templates=templates,
        applied_ids=applied_ids,
        checks=checks,
    )


@contabilidad.route("/period-close/monthly/<identifier>/apply-recurring", methods=["POST"])
@login_required
@modulo_activo("accounting")
@verifica_acceso("accounting")
def aplicar_recurrentes_cierre(identifier: str):
    """Aplica plantillas recurrentes desde un registro de cierre mensual."""
    from cacao_accounting.database import AccountingPeriod, PeriodCloseRun

    close_run = database.session.get(PeriodCloseRun, identifier)
    if not close_run:
        flash(CONTABILIDAD_CIERRE_MENSUAL_NO_EXISTE_MESSAGE, "danger")
        return redirect(url_for(CONTABILIDAD_ASISTENTE_CIERRE_MENSUAL))

    period = database.session.get(AccountingPeriod, close_run.period_id)
    if not period:
        flash(CONTABILIDAD_PERIODO_NO_EXISTE_MESSAGE, "danger")
        return redirect(url_for(CONTABILIDAD_VER_CIERRE_MENSUAL, identifier=close_run.id))

    template_ids = request.form.getlist("template_ids")
    if not template_ids:
        template_ids = _discover_applicable_templates(close_run.company, period.end)

    close_run.run_status = "in_progress"
    success_count, errors = _apply_recurring_templates(
        template_ids,
        fiscal_year=str(period.fiscal_year_id),
        period_name=period.name,
        application_date=period.end,
        user_id=str(current_user.id),
        company=close_run.company,
    )

    _record_check_result(close_run.id, success_count, errors)
    close_run.run_status = "in_progress" if success_count else "open"
    database.session.commit()

    if success_count > 0:
        flash(f"Se aplicaron {success_count} plantillas correctamente.", "success")
    if errors:
        for err in errors:
            flash(err, "danger")

    return redirect(url_for(CONTABILIDAD_VER_CIERRE_MENSUAL, identifier=close_run.id))


@contabilidad.route("/period-close/monthly/<identifier>/exchange-revaluation", methods=["POST"])
@login_required
@modulo_activo("accounting")
@verifica_acceso("accounting")
def ejecutar_revalorizacion_cierre(identifier: str) -> "Any":
    """Ejecuta revalorizacion cambiaria desde el asistente de cierre mensual."""
    from cacao_accounting.contabilidad.exchange_revaluation_service import (
        ExchangeRevaluationError,
        ExchangeRevaluationService,
    )
    from cacao_accounting.database import AccountingPeriod, PeriodCloseCheck, PeriodCloseRun

    close_run = database.session.get(PeriodCloseRun, identifier)
    if not close_run:
        flash(CONTABILIDAD_CIERRE_MENSUAL_NO_EXISTE_MESSAGE, "danger")
        return redirect(url_for(CONTABILIDAD_ASISTENTE_CIERRE_MENSUAL))

    period = database.session.get(AccountingPeriod, close_run.period_id)
    if not period:
        flash(CONTABILIDAD_PERIODO_NO_EXISTE_MESSAGE, "danger")
        return redirect(url_for(CONTABILIDAD_VER_CIERRE_MENSUAL, identifier=close_run.id))

    try:
        run = ExchangeRevaluationService().run(
            company=close_run.company,
            year=period.end.year,
            month=period.end.month,
            user_id=str(current_user.id),
        )
    except ExchangeRevaluationError as exc:
        database.session.rollback()
        database.session.add(
            PeriodCloseCheck(
                close_run_id=close_run.id,
                check_type="exchange_revaluation",
                check_status="failed",
                message=str(exc),
            )
        )
        database.session.commit()
        flash_error(exc)
    else:
        close_run.run_status = "in_progress"
        database.session.add(
            PeriodCloseCheck(
                close_run_id=close_run.id,
                check_type="exchange_revaluation",
                check_status="passed",
                message=f"Revalorizacion {run.document_no or run.id}: {run.status}.",
            )
        )
        database.session.commit()
        flash("La revalorizacion fue ejecutada correctamente.", "success")
        if run.status == "completed_no_changes":
            flash("No se generaron diferencias cambiarias.", "info")

    return redirect(url_for(CONTABILIDAD_VER_CIERRE_MENSUAL, identifier=close_run.id))


@contabilidad.route("/period-close/monthly/<identifier>/close", methods=["POST"])
@login_required
@modulo_activo("accounting")
@verifica_acceso("accounting")
def finalizar_cierre_mensual(identifier: str) -> "Any":
    """Finaliza el cierre mensual después de ejecutar todos sus controles."""
    from cacao_accounting.database import PeriodCloseRun

    close_run = database.session.get(PeriodCloseRun, identifier)
    if not close_run:
        flash(CONTABILIDAD_CIERRE_MENSUAL_NO_EXISTE_MESSAGE, "danger")
        return redirect(url_for(CONTABILIDAD_ASISTENTE_CIERRE_MENSUAL))

    try:
        finalize_monthly_close(close_run_id=close_run.id, user_id=str(current_user.id))
    except PeriodCloseError as exc:
        flash_error(exc)
        return redirect(url_for(CONTABILIDAD_VER_CIERRE_MENSUAL, identifier=close_run.id))

    flash(_("El cierre mensual ha finalizado y el periodo ha sido cerrado."), "success")
    return redirect(url_for(CONTABILIDAD_VER_CIERRE_MENSUAL, identifier=close_run.id))


@contabilidad.route("/exchange-revaluation")
@login_required
@modulo_activo("accounting")
@verifica_acceso("accounting")
def revalorizaciones_cambiarias():
    """Listado de revalorizaciones cambiarias."""
    from cacao_accounting.database import Entity

    companies = database.session.execute(database.select(Entity).order_by(Entity.code)).scalars().all()
    query = database.select(ExchangeRevaluation).order_by(
        ExchangeRevaluation.run_date.desc(), ExchangeRevaluation.created.desc(), ExchangeRevaluation.id.desc()
    )
    query = apply_list_filters(
        query,
        ExchangeRevaluation,
        (
            ExchangeRevaluation.document_no,
            ExchangeRevaluation.company,
            ExchangeRevaluation.currency,
            ExchangeRevaluation.voucher_type,
            ExchangeRevaluation.voucher_id,
        ),
    )
    return render_template(
        "contabilidad/exchange_revaluation_lista.html",
        titulo="Revalorizacion cambiaria - " + APPNAME,
        consulta=database.paginate(
            query,
            page=request.args.get("page", default=1, type=int),
            max_per_page=10,
            count=True,
        ),
        companies=companies,
    )


@contabilidad.route("/exchange-revaluation/new", methods=["GET", "POST"])
@login_required
@modulo_activo("accounting")
@verifica_acceso("accounting")
def nueva_revalorizacion_cambiaria():
    """Formulario minimo para ejecutar una revalorizacion cambiaria."""
    from cacao_accounting.database import Entity

    if request.method == "POST":
        result = _handle_exchange_revaluation_post()
        if result:
            return result

    companies = database.session.execute(database.select(Entity).order_by(Entity.code)).scalars().all()
    return render_template(
        "contabilidad/exchange_revaluation_nueva.html",
        titulo="Nueva revalorizacion cambiaria - " + APPNAME,
        companies=companies,
    )


@contabilidad.route("/exchange-revaluation/<identifier>")
@login_required
@modulo_activo("accounting")
@verifica_acceso("accounting")
def ver_revalorizacion_cambiaria(identifier: str):
    """Detalle solo lectura de una revalorizacion cambiaria."""
    from cacao_accounting.contabilidad.exchange_revaluation_service import ExchangeRevaluationService
    from cacao_accounting.database import AccountingPeriod, Accounts, Book, ExchangeRevaluation

    run = database.session.get(ExchangeRevaluation, identifier)
    if not run:
        flash("Revalorizacion no encontrada.", "warning")
        return redirect(url_for(CONTABILIDAD_REVALORIZACION_LIST))

    period = None
    if run.run_date:
        period = (
            database.session.execute(
                database.select(AccountingPeriod)
                .filter_by(entity=run.company)
                .where(AccountingPeriod.start <= run.run_date)
                .where(AccountingPeriod.end >= run.run_date)
            )
            .scalars()
            .first()
        )

    service = ExchangeRevaluationService()
    lines = service.list_lines(run.id)
    account_ids = {line.account_id for line in lines if line.account_id}
    ledger_ids = {line.ledger_id for line in lines if line.ledger_id}
    accounts = (
        {
            account.id: account
            for account in database.session.execute(database.select(Accounts).where(Accounts.id.in_(account_ids)))
            .scalars()
            .all()
        }
        if account_ids
        else {}
    )
    ledgers = (
        {
            ledger.id: ledger
            for ledger in database.session.execute(database.select(Book).where(Book.id.in_(ledger_ids))).scalars().all()
        }
        if ledger_ids
        else {}
    )
    audit_timeline = format_document_timeline("exchange_revaluation", run.id)
    return render_template(
        "contabilidad/exchange_revaluation.html",
        titulo="Revalorizacion cambiaria - " + APPNAME,
        run=run,
        lines=lines,
        accounts=accounts,
        ledgers=ledgers,
        selected_period=period,
        audit_timeline=audit_timeline,
    )


@contabilidad.route("/exchange-revaluation/<identifier>/void", methods=["POST"])
@login_required
@modulo_activo("accounting")
@verifica_acceso("accounting")
def anular_revalorizacion_cambiaria(identifier: str):
    """Anula una revalorizacion cambiaria contabilizada."""
    from cacao_accounting.contabilidad.exchange_revaluation_service import (
        ExchangeRevaluationError,
        ExchangeRevaluationService,
    )

    try:
        run = ExchangeRevaluationService().void(
            run_id=identifier,
            user_id=str(current_user.id),
            reason=request.form.get("reason") or None,
        )
    except ExchangeRevaluationError as exc:
        database.session.rollback()
        flash_error(exc)
        return redirect(url_for(CONTABILIDAD_REVALORIZACION_VER, identifier=identifier))

    flash("Revalorizacion anulada correctamente.", "success")
    return redirect(url_for(CONTABILIDAD_REVALORIZACION_VER, identifier=run.id))


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

    if request.method == "POST":
        try:
            journal = create_journal_draft(
                parse_journal_form(request.form),
                user_id=str(current_user.id),
                allow_closing=current_user.classification == "admin",
            )
        except JournalValidationError as exc:
            flash_error(exc)
        else:
            flash("Comprobante contable guardado como borrador.", "success")
            return redirect(url_for(CONTABILIDAD_VER_COMPROBANTE, identifier=journal.id))

    TITULO = "Nuevo Comprobante Contable - " + APPNAME
    is_closing = request.args.get("isclosing", "").lower() in {"1", "true", "yes", "on"}
    initial_journal = {"is_closing": True} if is_closing else None
    return render_template(
        "contabilidad/journal_nuevo.html",
        titulo=TITULO,
        initial_journal=initial_journal,
        submit_url=url_for("contabilidad.nuevo_comprobante"),
        cancel_url=url_for("contabilidad.conta"),
        currencies=obtener_lista_monedas_activas(),
    )


@contabilidad.route("/journal/<identifier>/submit", methods=["POST"])
@login_required
@modulo_activo("accounting")
@verifica_acceso("accounting")
def contabilizar_comprobante(identifier: str):
    """Contabiliza un comprobante contable manual."""
    from cacao_accounting.auth.permisos import Permisos
    from cacao_accounting.contabilidad.journal_service import JournalValidationError, submit_journal
    from cacao_accounting.database.helpers import obtener_id_modulo_por_nombre
    from cacao_accounting.approval_engine import ApprovalEngine

    permisos = Permisos(modulo=obtener_id_modulo_por_nombre("accounting"), usuario=current_user.id)
    if not permisos.autorizar:
        abort(403)

    journal = database.session.get(ComprobanteContable, identifier)
    if not journal:
        abort(404)
    exige_acceso_compania("accounting", journal.entity, "autorizar")

    try:
        if ApprovalEngine.is_enabled(journal.entity):
            if ApprovalEngine.can_approve(journal, current_user):
                ApprovalEngine.request_approval(journal)
                ApprovalEngine.approve(journal, current_user, "Aprobado por el remitente")
                database.session.commit()
                flash("Comprobante contable aprobado.", "success")
            else:
                ApprovalEngine.request_approval(journal)
                journal.status = "Pending Approval"
                database.session.commit()
                flash("Comprobante contable enviado para aprobación (Pendiente de Aprobación).", "info")
            return redirect(url_for(CONTABILIDAD_VER_COMPROBANTE, identifier=identifier))

        submit_journal(identifier, user_id=str(current_user.id))
    except JournalValidationError as exc:
        flash_error(exc)
    else:
        flash("Comprobante contable contabilizado.", "success")
    return redirect(url_for(CONTABILIDAD_VER_COMPROBANTE, identifier=identifier))


@contabilidad.route("/journal/<identifier>/reject", methods=["POST"])
@login_required
@modulo_activo("accounting")
@verifica_acceso("accounting")
def rechazar_comprobante(identifier: str):
    """Rechaza un comprobante contable manual en borrador sin afectar ledger."""
    from cacao_accounting.auth.permisos import Permisos
    from cacao_accounting.contabilidad.journal_service import JournalValidationError, reject_journal_draft
    from cacao_accounting.database.helpers import obtener_id_modulo_por_nombre

    permisos = Permisos(modulo=obtener_id_modulo_por_nombre("accounting"), usuario=current_user.id)
    if not permisos.validar:
        abort(403)

    journal = database.session.get(ComprobanteContable, identifier)
    if not journal:
        abort(404)
    exige_acceso_compania("accounting", journal.entity, "autorizar")

    try:
        reject_journal_draft(identifier, user_id=str(current_user.id))
    except JournalValidationError as exc:
        flash_error(exc)
    else:
        flash("Comprobante contable rechazado.", "warning")
    return redirect(url_for(CONTABILIDAD_VER_COMPROBANTE, identifier=identifier))


@contabilidad.route("/journal/<identifier>/cancel", methods=["POST"])
@login_required
@modulo_activo("accounting")
@verifica_acceso("accounting")
def anular_comprobante(identifier: str):
    """Anula un comprobante contabilizado aplicando reversa en el ledger."""
    from cacao_accounting.auth.permisos import Permisos
    from cacao_accounting.contabilidad.journal_service import JournalValidationError, cancel_submitted_journal
    from cacao_accounting.database.helpers import obtener_id_modulo_por_nombre
    from cacao_accounting.approval_engine import ApprovalEngine

    permisos = Permisos(modulo=obtener_id_modulo_por_nombre("accounting"), usuario=current_user.id)
    if not permisos.anular:
        abort(403)

    journal = database.session.get(ComprobanteContable, identifier)
    if not journal:
        abort(404)
    exige_acceso_compania("accounting", journal.entity, "anular")
    reason = (request.form.get("reason") or "").strip()
    if not reason:
        flash(_("Debe indicar el motivo de la anulación."), "danger")
        return redirect(url_for(CONTABILIDAD_VER_COMPROBANTE, identifier=identifier))

    try:
        if ApprovalEngine.is_enabled(journal.entity):
            ApprovalEngine.request_cancellation(
                journal,
                reason=reason,
                cancellation_date=request.form.get("cancellation_date") or journal.date,
            )
            database.session.commit()
            flash("Solicitud de cancelación enviada para aprobación (Pendiente de Cancelación).", "info")
            return redirect(url_for(CONTABILIDAD_VER_COMPROBANTE, identifier=identifier))

        cancel_submitted_journal(
            identifier,
            user_id=str(current_user.id),
            reason=reason,
            cancellation_date=request.form.get("cancellation_date") or journal.date,
        )
    except JournalValidationError as exc:
        flash_error(exc)
    else:
        flash("Comprobante contable anulado con reversa contable.", "warning")
    return redirect(url_for(CONTABILIDAD_VER_COMPROBANTE, identifier=identifier))


@contabilidad.route("/journal/<identifier>")
@login_required
@modulo_activo("accounting")
@verifica_acceso("accounting")
def ver_comprobante(identifier: str):
    """Ver comprobante contable."""
    from cacao_accounting.contabilidad.journal_repository import get_journal, list_journal_lines
    from cacao_accounting.database import Accounts, CostCenter, User

    journal = get_journal(identifier)
    if journal is None:
        flash("El comprobante contable indicado no existe.", "warning")
        return redirect(url_for("contabilidad.conta"))
    exige_acceso_compania("accounting", journal.entity, "consultar")
    creator = database.session.get(User, journal.user_id) if journal.user_id else None
    creator_nickname = creator.user if creator is not None else (journal.user_id or "")
    lineas_raw = list_journal_lines(identifier)

    selected_books = _build_journal_selected_books(journal, journal.entity)
    currency_label = _get_journal_currency_label(journal, journal.entity)

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

    from cacao_accounting.contabilidad.journal_service import journal_display_document_name

    lineas = _build_journal_lineas(lineas_raw, account_labels, cost_center_labels)
    audit_timeline = format_document_timeline("journal_entry", journal.id)
    display_name = journal_display_document_name(journal)

    return render_template(
        "contabilidad/journal.html",
        registro=journal,
        lineas=lineas,
        selected_books=selected_books,
        currency_label=currency_label,
        creator_nickname=creator_nickname,
        audit_timeline=audit_timeline,
        display_name=display_name,
        titulo="Comprobante Contable - " + APPNAME,
    )


@contabilidad.route("/journal/<identifier>/duplicate", methods=["POST"])
@login_required
@modulo_activo("accounting")
@verifica_acceso("accounting")
def duplicar_comprobante(identifier: str):
    """Duplica un comprobante y crea un nuevo borrador editable."""
    from cacao_accounting.contabilidad.journal_service import JournalValidationError, duplicate_journal_as_draft

    journal = database.session.get(ComprobanteContable, identifier)
    if not journal:
        abort(404)
    exige_acceso_compania("accounting", journal.entity, "crear")

    try:
        duplicated = duplicate_journal_as_draft(identifier, user_id=str(current_user.id))
    except JournalValidationError as exc:
        flash_error(exc)
        return redirect(url_for(CONTABILIDAD_VER_COMPROBANTE, identifier=identifier))

    flash("Comprobante duplicado como nuevo borrador.", "success")
    return redirect(url_for(CONTABILIDAD_EDITAR_COMPROBANTE, identifier=duplicated.id))


@contabilidad.route("/journal/<identifier>/revert", methods=["POST"])
@login_required
@modulo_activo("accounting")
@verifica_acceso("accounting")
def revertir_comprobante(identifier: str):
    """Crea borrador de reversión invirtiendo débitos y créditos del comprobante origen."""
    from cacao_accounting.contabilidad.journal_service import JournalValidationError, duplicate_journal_as_reversal_draft

    journal = database.session.get(ComprobanteContable, identifier)
    if not journal:
        abort(404)
    exige_acceso_compania("accounting", journal.entity, "crear")

    reversal_date = request.form.get("reversal_date")
    reason = (request.form.get("reason") or "").strip()
    if not reversal_date:
        flash(_("Debe seleccionar la fecha de reversión."), "danger")
        return redirect(url_for(CONTABILIDAD_VER_COMPROBANTE, identifier=identifier))
    if not reason:
        flash(_("Debe indicar el motivo de la reversión."), "danger")
        return redirect(url_for(CONTABILIDAD_VER_COMPROBANTE, identifier=identifier))

    try:
        reversed_draft = duplicate_journal_as_reversal_draft(
            identifier,
            user_id=str(current_user.id),
            reversal_date_raw=reversal_date,
            reason=reason,
        )
    except JournalValidationError as exc:
        flash_error(exc)
        return redirect(url_for(CONTABILIDAD_VER_COMPROBANTE, identifier=identifier))

    flash("Reversión creada como nuevo borrador editable.", "success")
    return redirect(url_for(CONTABILIDAD_EDITAR_COMPROBANTE, identifier=reversed_draft.id))


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

    journal = get_journal(identifier)
    if journal is None:
        flash("El comprobante contable indicado no existe.", "warning")
        return redirect(url_for("contabilidad.listar_comprobantes"))
    exige_acceso_compania("accounting", journal.entity, "editar")
    if journal.voucher_type == "Capitalización Automática de Proyecto":
        flash("No se puede editar un comprobante de capitalización automática.", "warning")
        return redirect(url_for(CONTABILIDAD_VER_COMPROBANTE, identifier=identifier))
    if journal.status != "draft":
        flash("Solo se puede editar un comprobante en borrador.", "warning")
        return redirect(url_for(CONTABILIDAD_VER_COMPROBANTE, identifier=identifier))

    if request.method == "POST":
        try:
            journal = update_journal_draft(identifier, parse_journal_form(request.form), user_id=str(current_user.id))
        except JournalValidationError as exc:
            flash_error(exc)
        else:
            flash("Comprobante contable actualizado.", "success")
            return redirect(url_for(CONTABILIDAD_VER_COMPROBANTE, identifier=journal.id))

    TITULO = "Editar Comprobante Contable - " + APPNAME
    return render_template(
        "contabilidad/journal_nuevo.html",
        titulo=TITULO,
        initial_journal=serialize_journal_for_form(journal),
        submit_url=url_for(CONTABILIDAD_EDITAR_COMPROBANTE, identifier=identifier),
        cancel_url=url_for(CONTABILIDAD_VER_COMPROBANTE, identifier=identifier),
        currencies=obtener_lista_monedas(),
    )


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
        return redirect(url_for(CONTABILIDAD_NAMING_SERIES_LIST))

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
        return redirect(url_for(CONTABILIDAD_NAMING_SERIES_LIST))

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
    return redirect(url_for(CONTABILIDAD_NAMING_SERIES_LIST))


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
        return redirect(url_for(CONTABILIDAD_NAMING_SERIES_LIST))

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

    if not form.validate_on_submit():
        return render_template(
            "contabilidad/naming_series_nueva.html",
            form=form,
            titulo="Editar Serie de Numeracion - " + APPNAME,
            edit=True,
        )

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

    _update_series_sequence(serie, form)

    database.session.commit()
    return redirect(url_for(CONTABILIDAD_NAMING_SERIES_LIST))


@contabilidad.route("/naming-series/<series_id>/delete", methods=["POST"])
@login_required
@modulo_activo("accounting")
@verifica_permiso("accounting", "eliminar")
@verifica_acceso("accounting")
def naming_series_delete(series_id: str):
    """Eliminar una serie de numeracion si no ha sido utilizada."""
    from cacao_accounting.database import GeneratedIdentifierLog, NamingSeries, SeriesSequenceMap

    serie = database.session.get(NamingSeries, series_id)
    if serie is None:
        return redirect(url_for(CONTABILIDAD_NAMING_SERIES_LIST))

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

    return redirect(url_for(CONTABILIDAD_NAMING_SERIES_LIST))


@contabilidad.route("/naming-series/<series_id>/toggle-active", methods=["POST"])
@login_required
@modulo_activo("accounting")
@verifica_acceso("accounting")
def naming_series_toggle_active(series_id: str):
    """Activa o desactiva una serie de numeracion."""
    from cacao_accounting.database import GeneratedIdentifierLog, NamingSeries, SeriesSequenceMap

    serie = database.session.get(NamingSeries, series_id)
    if not serie:
        return redirect(url_for(CONTABILIDAD_NAMING_SERIES_LIST))

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
    return redirect(url_for(CONTABILIDAD_NAMING_SERIES_LIST))


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
        return redirect(url_for(CONTABILIDAD_EXTERNAL_COUNTER_LIST))

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
        return redirect(url_for(CONTABILIDAD_EXTERNAL_COUNTER_LIST))

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
            flash_error(exc)
        return redirect(url_for(CONTABILIDAD_EXTERNAL_COUNTER_LIST))

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
        return redirect(url_for(CONTABILIDAD_EXTERNAL_COUNTER_LIST))

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


@contabilidad.route("/external-counter/<counter_id>/toggle-active", methods=["POST"])
@login_required
@modulo_activo("accounting")
@verifica_acceso("accounting")
def external_counter_toggle_active(counter_id: str):
    """Activa o desactiva un contador externo."""
    from cacao_accounting.database import ExternalCounter

    counter = database.session.get(ExternalCounter, counter_id)
    if counter:
        counter.is_active = not counter.is_active
        database.session.commit()
    return redirect(url_for(CONTABILIDAD_EXTERNAL_COUNTER_LIST))


@contabilidad.route("/external-counter/<counter_id>/edit", methods=["GET", "POST"])
@login_required
@modulo_activo("accounting")
@verifica_acceso("accounting")
def external_counter_edit(counter_id: str):
    """Edita los datos de un contador externo."""
    from cacao_accounting.contabilidad.forms import FormularioExternalCounter
    from cacao_accounting.database import Entity, ExternalCounter, NamingSeries

    counter = database.session.get(ExternalCounter, counter_id)
    if not counter:
        return redirect(url_for(CONTABILIDAD_EXTERNAL_COUNTER_LIST))

    form = FormularioExternalCounter(obj=counter)
    entidades = database.session.execute(database.select(Entity)).scalars().all()
    form.company.choices = [(e.code, e.name) for e in entidades]

    series_list = (
        database.session.execute(database.select(NamingSeries).filter_by(is_active=True).order_by(NamingSeries.name))
        .scalars()
        .all()
    )
    form.naming_series_id.choices = [("", "— Sin asociar —")] + [(s.id, f"{s.name} ({s.entity_type})") for s in series_list]

    if form.validate_on_submit():
        _update_counter_from_form(counter, form)
        _sync_counter_naming_series_map(counter, form.naming_series_id.data or None)
        database.session.commit()
        return redirect(url_for(CONTABILIDAD_EXTERNAL_COUNTER_LIST))

    return render_template(
        "contabilidad/external_counter_nuevo.html",
        form=form,
        counter=counter,
        titulo="Editar Contador Externo - " + APPNAME,
        modo_edicion=True,
    )


@contabilidad.route("/fiscal_year_closing/list")
@login_required
@modulo_activo("accounting")
@verifica_acceso("accounting")
def fiscal_year_closing_list():
    """Listado de cierres de año fiscal."""
    from cacao_accounting.database import FiscalYear

    company_filter = request.args.get("company", type=str)
    query = database.select(FiscalYear)
    if company_filter:
        query = query.filter_by(entity=company_filter)

    consulta = database.paginate(
        query.order_by(FiscalYear.year_end_date.desc()),
        page=request.args.get("page", default=1, type=int),
        max_per_page=10,
        count=True,
    )

    from cacao_accounting.database import Entity

    entidades = database.session.execute(database.select(Entity)).scalars().all()

    return render_template(
        "contabilidad/fiscal_year_closing_lista.html",
        titulo="Cierres de Año Fiscal - " + APPNAME,
        consulta=consulta,
        entidades=entidades,
        company_filter=company_filter,
        statusweb=STATUS,
    )


@contabilidad.route("/fiscal_year_closing/new", methods=["GET", "POST"])
@login_required
@modulo_activo("accounting")
@verifica_acceso("accounting")
def fiscal_year_closing_new():
    """Formulario para ejecutar un nuevo cierre de año fiscal."""
    if current_user.classification != "admin":
        flash("Solo el administrador del sistema puede ejecutar el cierre de año fiscal.", "danger")
        return redirect(url_for(CONTABILIDAD_FISCAL_YEAR_CLOSING_LIST))

    from cacao_accounting.database import Entity, FiscalYear
    from cacao_accounting.contabilidad.fiscal_year_closing import (
        FiscalYearClosingError,
        create_fiscal_year_closing_voucher,
    )

    entidades = database.session.execute(database.select(Entity)).scalars().all()

    if request.method == "POST":
        company = request.form.get("company")
        fiscal_year_id = request.form.get("fiscal_year_id")
        exige_acceso_compania("accounting", company, "autorizar")
        try:
            create_fiscal_year_closing_voucher(company, fiscal_year_id, user_id=str(current_user.id))
            flash("Cierre de año fiscal ejecutado correctamente.", "success")
            return redirect(url_for(CONTABILIDAD_FISCAL_YEAR_CLOSING_LIST))
        except FiscalYearClosingError as exc:
            flash_error(exc)

    # Obtener años fiscales cerrados administrativamente pero no financieramente
    fiscal_years = (
        database.session.execute(database.select(FiscalYear).filter_by(is_closed=True, financial_closed=False)).scalars().all()
    )

    return render_template(
        "contabilidad/fiscal_year_closing_nuevo.html",
        titulo="Nuevo Cierre de Año Fiscal - " + APPNAME,
        entidades=entidades,
        fiscal_years=fiscal_years,
    )


@contabilidad.route("/fiscal_year_closing/reverse/<fy_id>", methods=["POST"])
@login_required
@modulo_activo("accounting")
@verifica_acceso("accounting")
def fiscal_year_closing_reverse(fy_id):
    """Revierte un cierre de año fiscal."""
    if current_user.classification != "admin":
        flash("Solo el administrador del sistema puede revertir el cierre de año fiscal.", "danger")
        return redirect(url_for(CONTABILIDAD_FISCAL_YEAR_CLOSING_LIST))

    from cacao_accounting.contabilidad.fiscal_year_closing import (
        FiscalYearClosingError,
        reverse_fiscal_year_closing,
    )
    from cacao_accounting.database import FiscalYear

    try:
        fiscal_year = database.session.get(FiscalYear, fy_id)
        if not fiscal_year:
            raise FiscalYearClosingError("Año fiscal no encontrado.")
        exige_acceso_compania("accounting", fiscal_year.entity, "autorizar")
        reverse_fiscal_year_closing(fy_id, user_id=str(current_user.id))
        flash("Cierre de año fiscal revertido correctamente.", "success")
    except FiscalYearClosingError as exc:
        flash_error(exc)

    return redirect(url_for(CONTABILIDAD_FISCAL_YEAR_CLOSING_LIST))


@contabilidad.route("/cash-flow-config", methods=["GET", "POST"], defaults={"company": None})
@contabilidad.route("/cash-flow-config/<company>", methods=["GET", "POST"])
@login_required
@modulo_activo("accounting")
@verifica_acceso("accounting")
def cash_flow_config(company):
    """Vista dedicada de clasificación NIC 7 de cuentas para el EFE.

    Cada cuenta activa no agrupadora puede mapearse explícitamente a
    Operación, Inversión, Financiamiento o Efectivo. La sugerencia mostrada
    es solo visual: el mapeo únicamente se crea al guardar el formulario.
    """
    from cacao_accounting.reportes.cash_flow import (
        SECTION_LABELS,
        VALID_SECTIONS,
        get_cash_flow_config_overview,
        save_cash_flow_mappings,
    )
    from cacao_accounting.database import Entity

    companies = database.session.execute(database.select(Entity).order_by(Entity.code)).scalars().all()
    selected_company = company or request.form.get("company") or (companies[0].code if companies else None)
    if not selected_company:
        return render_template(
            "contabilidad_cash_flow_config.html",
            titulo=f"Contabilidad | Clasificación EFE - {APPNAME}",
            companies=[],
            selected_company=None,
            overview=None,
            section_labels=SECTION_LABELS,
            valid_sections=list(VALID_SECTIONS),
        )

    exige_acceso_compania("accounting", selected_company, "consultar")

    if request.method == "POST":
        overrides = {
            account_id: request.form.get(f"section_{account_id}") for account_id in request.form.getlist("account_ids")
        }
        try:
            save_cash_flow_mappings(selected_company, overrides)
            database.session.commit()
            flash(_("Clasificación del flujo de efectivo guardada correctamente."), "success")
        except ValueError as exc:
            database.session.rollback()
            flash(str(exc), "danger")
        return redirect(url_for("contabilidad.cash_flow_config", company=selected_company))

    return render_template(
        "contabilidad_cash_flow_config.html",
        titulo=f"Contabilidad | Clasificación EFE - {APPNAME}",
        companies=companies,
        selected_company=selected_company,
        overview=get_cash_flow_config_overview(selected_company),
        section_labels=SECTION_LABELS,
        valid_sections=list(VALID_SECTIONS),
    )
