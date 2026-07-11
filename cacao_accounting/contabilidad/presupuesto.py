# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Rutas para el submódulo de Presupuesto."""

from cacao_accounting.exceptions import flash_error
from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from cacao_accounting.auth.permisos import Permisos
from cacao_accounting.contabilidad.budget_service import BudgetService, BudgetError
from cacao_accounting.contabilidad.budget_import_service import BudgetImportService
from cacao_accounting.contabilidad.budget_report_service import BudgetReportService
from cacao_accounting.contabilidad.forms import FormularioBudget, FormularioBudgetLine
from cacao_accounting.database import (
    AccountingPeriod,
    Accounts,
    Book,
    Budget,
    BudgetLine,
    CostCenter,
    FiscalYear,
    Project,
    Unit,
    database,
)
from cacao_accounting.database.helpers import obtener_id_modulo_por_nombre
from cacao_accounting.decorators import modulo_activo, verifica_acceso
from cacao_accounting.version import APPNAME
from cacao_accounting.contabilidad.auxiliares import (
    obtener_lista_entidades_por_id_razonsocial,
    obtener_lista_monedas,
)

_ENDPOINT_LISTAR = "contabilidad.presupuestos.listar"
_ENDPOINT_DETALLE = "contabilidad.presupuestos.detalle"
_TEMPLATE_PRESUPUESTO_IMPORTAR = "contabilidad/presupuestos/import.html"

presupuestos = Blueprint("presupuestos", __name__)


@presupuestos.route("/list")
@login_required
@modulo_activo("accounting")
@verifica_acceso("accounting")
def listar():
    """Listado de presupuestos."""
    query = database.select(Budget)
    search = request.args.get("search")
    if search:
        query = query.filter(Budget.name.ilike(f"%{search}%") | Budget.budget_code.ilike(f"%{search}%"))

    consulta = database.paginate(
        query.order_by(Budget.created.desc()),
        page=request.args.get("page", default=1, type=int),
        max_per_page=10,
        count=True,
    )
    return render_template(
        "contabilidad/presupuestos/list.html",
        consulta=consulta,
        titulo="Administrar Presupuestos - " + APPNAME,
    )


@presupuestos.route("/new", methods=["GET", "POST"])
@login_required
@modulo_activo("accounting")
@verifica_acceso("accounting")
def nuevo():
    """Nuevo presupuesto."""
    permisos = Permisos(modulo=obtener_id_modulo_por_nombre("accounting"), usuario=current_user.id)
    if not permisos.crear:
        flash("No tiene permisos para crear presupuestos.", "danger")
        return redirect(url_for(_ENDPOINT_LISTAR))

    form = FormularioBudget()
    form.company.choices = obtener_lista_entidades_por_id_razonsocial()
    form.currency_id.choices = obtener_lista_monedas()

    if form.validate_on_submit():
        try:
            budget = BudgetService().create_budget(form.data, str(current_user.id))
            flash("Presupuesto creado exitosamente.", "success")
            return redirect(url_for(_ENDPOINT_DETALLE, budget_id=budget.id))
        except BudgetError as e:
            flash_error(e)

    return render_template(
        "contabilidad/presupuestos/form.html",
        form=form,
        titulo="Nuevo Presupuesto - " + APPNAME,
    )


@presupuestos.route("/<budget_id>")
@login_required
@modulo_activo("accounting")
@verifica_acceso("accounting")
def detalle(budget_id):
    """Detalle de presupuesto y sus líneas."""
    budget = database.session.get(Budget, budget_id)
    if not budget:
        flash("Presupuesto no encontrado.", "warning")
        return redirect(url_for(_ENDPOINT_LISTAR))

    lines = (
        database.session.query(BudgetLine, Accounts, CostCenter, AccountingPeriod, Unit, Project)
        .join(Accounts, BudgetLine.account_id == Accounts.id)
        .join(CostCenter, BudgetLine.cost_center_id == CostCenter.id)
        .join(AccountingPeriod, BudgetLine.period_id == AccountingPeriod.id)
        .outerjoin(Unit, BudgetLine.business_unit_id == Unit.id)
        .outerjoin(Project, BudgetLine.project_id == Project.id)
        .filter(BudgetLine.budget_id == budget_id)
        .order_by(AccountingPeriod.start, Accounts.code)
        .all()
    )

    permisos = Permisos(modulo=obtener_id_modulo_por_nombre("accounting"), usuario=current_user.id)

    totals = BudgetService().get_budget_totals(budget_id)
    periods = (
        database.session.query(AccountingPeriod)
        .filter_by(fiscal_year_id=budget.fiscal_year_id)
        .order_by(AccountingPeriod.start)
        .all()
    )

    return render_template(
        "contabilidad/presupuestos/detail.html",
        budget=budget,
        lines=lines,
        totals=totals,
        periods=periods,
        permisos=permisos,
        titulo=f"Presupuesto: {budget.name} - " + APPNAME,
    )


@presupuestos.route("/<budget_id>/edit", methods=["GET", "POST"])
@login_required
@modulo_activo("accounting")
@verifica_acceso("accounting")
def editar(budget_id):
    """Editar encabezado de presupuesto."""
    permisos = Permisos(modulo=obtener_id_modulo_por_nombre("accounting"), usuario=current_user.id)
    if not permisos.editar:
        flash("No tiene permisos para editar presupuestos.", "danger")
        return redirect(url_for(_ENDPOINT_DETALLE, budget_id=budget_id))

    budget = database.session.get(Budget, budget_id)
    if not budget:
        flash("Presupuesto no encontrado.", "warning")
        return redirect(url_for(_ENDPOINT_LISTAR))

    form = FormularioBudget(obj=budget)
    form.company.choices = obtener_lista_entidades_por_id_razonsocial()
    form.currency_id.choices = obtener_lista_monedas()

    if form.validate_on_submit():
        try:
            BudgetService().update_budget(budget_id, form.data, str(current_user.id))
            flash("Presupuesto actualizado.", "success")
            return redirect(url_for(_ENDPOINT_DETALLE, budget_id=budget_id))
        except BudgetError as e:
            flash_error(e)

    return render_template(
        "contabilidad/presupuestos/form.html",
        form=form,
        budget=budget,
        titulo="Editar Presupuesto - " + APPNAME,
    )


@presupuestos.route("/<budget_id>/line/new", methods=["GET", "POST"])
@login_required
@modulo_activo("accounting")
@verifica_acceso("accounting")
def nueva_linea(budget_id):
    """Agregar línea manual."""
    permisos = Permisos(modulo=obtener_id_modulo_por_nombre("accounting"), usuario=current_user.id)
    if not permisos.crear:
        flash("No tiene permisos para agregar líneas.", "danger")
        return redirect(url_for(_ENDPOINT_DETALLE, budget_id=budget_id))

    budget = database.session.get(Budget, budget_id)
    if not budget or budget.status != "draft":
        flash("No se pueden agregar líneas a este presupuesto.", "warning")
        return redirect(url_for(_ENDPOINT_DETALLE, budget_id=budget_id))

    form = FormularioBudgetLine()
    # Cargar choices dinámicamente según la compañía del presupuesto
    form.account_id.choices = [
        (a.id, f"{a.code} - {a.name}")
        for a in database.session.query(Accounts).filter_by(entity=budget.company, group=False).all()
    ]
    form.cost_center_id.choices = [
        (c.id, f"{c.code} - {c.name}") for c in database.session.query(CostCenter).filter_by(entity=budget.company).all()
    ]
    form.period_id.choices = [
        (p.id, p.name) for p in database.session.query(AccountingPeriod).filter_by(fiscal_year_id=budget.fiscal_year_id).all()
    ]
    form.business_unit_id.choices = [("", "— Ninguna —")] + [
        (u.id, u.name) for u in database.session.query(Unit).filter_by(entity=budget.company).all()
    ]
    form.project_id.choices = [("", "— Ninguno —")] + [
        (p.id, p.name) for p in database.session.query(Project).filter_by(entity=budget.company).all()
    ]

    if form.validate_on_submit():
        try:
            data = form.data
            if not data.get("business_unit_id"):
                data["business_unit_id"] = None
            if not data.get("project_id"):
                data["project_id"] = None
            BudgetService().add_budget_line(budget_id, data, str(current_user.id))
            flash("Línea agregada.", "success")
            return redirect(url_for(_ENDPOINT_DETALLE, budget_id=budget_id))
        except BudgetError as e:
            flash_error(e)

    return render_template(
        "contabilidad/presupuestos/line_form.html",
        form=form,
        budget=budget,
        titulo="Agregar Línea de Presupuesto - " + APPNAME,
    )


@presupuestos.route("/line/<line_id>/edit", methods=["GET", "POST"])
@login_required
@modulo_activo("accounting")
@verifica_acceso("accounting")
def editar_linea(line_id):
    """Editar línea manual."""
    permisos = Permisos(modulo=obtener_id_modulo_por_nombre("accounting"), usuario=current_user.id)
    if not permisos.editar:
        flash("No tiene permisos para editar líneas.", "danger")
        return redirect(url_for(_ENDPOINT_LISTAR))

    line = database.session.get(BudgetLine, line_id)
    if not line:
        flash("Línea no encontrada.", "warning")
        return redirect(url_for(_ENDPOINT_LISTAR))

    budget = database.session.get(Budget, line.budget_id)
    if budget.status != "draft":
        flash("Solo se pueden editar líneas en presupuestos en borrador.", "warning")
        return redirect(url_for(_ENDPOINT_DETALLE, budget_id=budget.id))

    form = FormularioBudgetLine(obj=line)
    form.account_id.choices = [
        (a.id, f"{a.code} - {a.name}")
        for a in database.session.query(Accounts).filter_by(entity=budget.company, group=False).all()
    ]
    form.cost_center_id.choices = [
        (c.id, f"{c.code} - {c.name}") for c in database.session.query(CostCenter).filter_by(entity=budget.company).all()
    ]
    form.period_id.choices = [
        (p.id, p.name) for p in database.session.query(AccountingPeriod).filter_by(fiscal_year_id=budget.fiscal_year_id).all()
    ]
    form.business_unit_id.choices = [("", "— Ninguna —")] + [
        (u.id, u.name) for u in database.session.query(Unit).filter_by(entity=budget.company).all()
    ]
    form.project_id.choices = [("", "— Ninguno —")] + [
        (p.id, p.name) for p in database.session.query(Project).filter_by(entity=budget.company).all()
    ]

    if form.validate_on_submit():
        try:
            data = form.data
            if not data.get("business_unit_id"):
                data["business_unit_id"] = None
            if not data.get("project_id"):
                data["project_id"] = None
            BudgetService().update_budget_line(line_id, data, str(current_user.id))
            flash("Línea actualizada.", "success")
            return redirect(url_for(_ENDPOINT_DETALLE, budget_id=budget.id))
        except BudgetError as e:
            flash_error(e)

    return render_template(
        "contabilidad/presupuestos/line_form.html",
        form=form,
        budget=budget,
        line=line,
        titulo="Editar Línea de Presupuesto - " + APPNAME,
    )


@presupuestos.route("/line/<line_id>/delete", methods=["POST"])
@login_required
@modulo_activo("accounting")
@verifica_acceso("accounting")
def eliminar_linea(line_id):
    """Eliminar línea."""
    permisos = Permisos(modulo=obtener_id_modulo_por_nombre("accounting"), usuario=current_user.id)
    if not permisos.eliminar:
        flash("No tiene permisos para eliminar líneas.", "danger")
        return redirect(url_for(_ENDPOINT_LISTAR))

    line = database.session.get(BudgetLine, line_id)
    if not line:
        return redirect(url_for(_ENDPOINT_LISTAR))

    budget_id = line.budget_id
    try:
        BudgetService().delete_budget_line(line_id, str(current_user.id))
        flash("Línea eliminada.", "info")
    except BudgetError as e:
        flash_error(e)

    return redirect(url_for(_ENDPOINT_DETALLE, budget_id=budget_id))


@presupuestos.route("/<budget_id>/approve", methods=["POST"])
@login_required
@modulo_activo("accounting")
@verifica_acceso("accounting")
def aprobar(budget_id):
    """Aprobar presupuesto."""
    permisos = Permisos(modulo=obtener_id_modulo_por_nombre("accounting"), usuario=current_user.id)
    if not permisos.autorizar:
        flash("No tiene permisos para aprobar presupuestos.", "danger")
        return redirect(url_for(_ENDPOINT_DETALLE, budget_id=budget_id))

    try:
        BudgetService().approve_budget(budget_id, str(current_user.id))
        flash("Presupuesto aprobado.", "success")
    except BudgetError as e:
        flash_error(e)
    return redirect(url_for(_ENDPOINT_DETALLE, budget_id=budget_id))


@presupuestos.route("/<budget_id>/close", methods=["POST"])
@login_required
@modulo_activo("accounting")
@verifica_acceso("accounting")
def cerrar(budget_id):
    """Cerrar presupuesto."""
    permisos = Permisos(modulo=obtener_id_modulo_por_nombre("accounting"), usuario=current_user.id)
    if not permisos.cerrar:
        flash("No tiene permisos para cerrar presupuestos.", "danger")
        return redirect(url_for(_ENDPOINT_DETALLE, budget_id=budget_id))

    try:
        BudgetService().close_budget(budget_id, str(current_user.id))
        flash("Presupuesto cerrado.", "info")
    except BudgetError as e:
        flash_error(e)
    return redirect(url_for(_ENDPOINT_DETALLE, budget_id=budget_id))


@presupuestos.route("/<budget_id>/import", methods=["GET", "POST"])
@login_required
@modulo_activo("accounting")
@verifica_acceso("accounting")
def importar(budget_id):
    """Importar líneas desde hoja de cálculo."""
    budget = database.session.get(Budget, budget_id)
    if not budget or budget.status != "draft":
        flash("No se puede importar a este presupuesto.", "warning")
        return redirect(url_for(_ENDPOINT_DETALLE, budget_id=budget_id))

    permisos = Permisos(modulo=obtener_id_modulo_por_nombre("accounting"), usuario=current_user.id)
    if not permisos.importar:
        flash("No tiene permisos para realizar importaciones.", "danger")
        return redirect(url_for(_ENDPOINT_DETALLE, budget_id=budget_id))

    if request.method == "POST":
        return _handle_budget_import_post(budget, budget_id)

    return render_template(
        _TEMPLATE_PRESUPUESTO_IMPORTAR,
        budget=budget,
        columns=BudgetImportService().get_template_columns(budget_id),
        titulo="Importar Presupuesto - " + APPNAME,
    )


def _handle_budget_import_post(budget: Budget, budget_id: str):
    """Maneja el POST de importacion de presupuesto (paso 1 o 2)."""
    import_id = request.form.get("import_id")
    if import_id:
        try:
            BudgetImportService().insert_lines(import_id, str(current_user.id))
            flash("Importación completada exitosamente.", "success")
            return redirect(url_for(_ENDPOINT_DETALLE, budget_id=budget_id))
        except Exception as e:
            flash(f"Error al procesar la importación: {str(e)}", "danger")
    else:
        file = request.files.get("file")
        if not file:
            flash("Por favor suba un archivo válido.", "danger")
        else:
            filename = file.filename
            if not filename:
                flash("El archivo no tiene nombre válido.", "danger")
            else:
                try:
                    import_service = BudgetImportService()
                    import_obj = import_service.validate_import(budget_id, filename, file.read(), str(current_user.id))
                    staged_lines = import_service.get_staged_lines(import_obj.id, limit=100)

                    return render_template(
                        _TEMPLATE_PRESUPUESTO_IMPORTAR,
                        budget=budget,
                        staged_lines=staged_lines,
                        import_id=import_obj.id,
                        titulo="Previsualizar Importación - " + APPNAME,
                    )
                except Exception as e:
                    flash(f"Error al procesar el archivo: {str(e)}", "danger")
    return render_template(
        _TEMPLATE_PRESUPUESTO_IMPORTAR,
        budget=budget,
        columns=BudgetImportService().get_template_columns(budget_id),
        titulo="Importar Presupuesto - " + APPNAME,
    )


@presupuestos.route("/report/real-vs-budget", methods=["GET", "POST"])
@login_required
@modulo_activo("accounting")
@verifica_acceso("accounting")
def reporte():
    """Generate Real versus Presupuesto report."""
    permisos = Permisos(modulo=obtener_id_modulo_por_nombre("accounting"), usuario=current_user.id)
    if not permisos.reportes:
        flash("No tiene permisos para ver reportes.", "danger")
        return redirect(url_for(_ENDPOINT_LISTAR))

    companies = obtener_lista_entidades_por_id_razonsocial()
    report_data = None
    filters = {}

    # Opciones para filtros
    company_id = request.form.get("company") or request.args.get("company")
    books = []
    fiscal_years = []
    budgets = []
    cost_centers = []
    units = []
    projects = []

    if company_id:
        books = database.session.query(Book).filter_by(entity=company_id).all()
        fiscal_years = database.session.query(FiscalYear).filter_by(entity=company_id).all()
        budgets = database.session.query(Budget).filter_by(company=company_id).all()
        cost_centers = database.session.query(CostCenter).filter_by(entity=company_id).all()
        units = database.session.query(Unit).filter_by(entity=company_id).all()
        projects = database.session.query(Project).filter_by(entity=company_id).all()

    if request.method == "POST" or request.args.get("budget_id"):
        filters = {
            "company": company_id,
            "ledger_id": request.form.get("ledger_id") or request.args.get("ledger_id"),
            "fiscal_year_id": request.form.get("fiscal_year_id") or request.args.get("fiscal_year_id"),
            "budget_id": request.form.get("budget_id") or request.args.get("budget_id"),
            "granularity": request.form.get("granularity", "month"),
            "cost_center_id": request.form.get("cost_center_id"),
            "business_unit_id": request.form.get("business_unit_id"),
            "project_id": request.form.get("project_id"),
        }

        if all([filters["company"], filters["budget_id"], filters["ledger_id"], filters["fiscal_year_id"]]):
            try:
                report_data = BudgetReportService().get_real_vs_budget_report(filters)
            except Exception as e:
                flash(f"Error al generar reporte: {str(e)}", "danger")

    return render_template(
        "contabilidad/presupuestos/real_vs_budget.html",
        companies=companies,
        books=books,
        fiscal_years=fiscal_years,
        budgets=budgets,
        cost_centers=cost_centers,
        units=units,
        projects=projects,
        report_data=report_data,
        filters=filters,
        titulo="Real versus Presupuesto - " + APPNAME,
    )
