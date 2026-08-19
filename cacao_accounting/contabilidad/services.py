"""Modulo de Contabilidad."""

from collections.abc import Sequence

from typing import Any

from datetime import date


from decimal import Decimal

from cacao_accounting.exceptions import flash_error

from flask import Blueprint, flash, redirect, render_template, request

from flask.helpers import url_for

from flask_login import current_user

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
    obtener_lista_entidades_por_id_razonsocial,
)

from cacao_accounting.contabilidad.currency_guard import CurrencyGuard


from cacao_accounting.runtime_mode import force_single_entity

from cacao_accounting.contabilidad.gl import gl


from cacao_accounting.database import (
    Accounts,
    Project,
    RecurringJournalTemplate,
    database,
)

from cacao_accounting.database.helpers import (
    check_hierarchy_cycle,
    get_descendant_ids,
    update_hierarchy_attributes,
)

from cacao_accounting.decorators import exige_acceso_compania

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

REQUIRED_MONTHLY_CLOSE_CHECKS = frozenset({"apply_recurring_journals", "exchange_revaluation", "project_capitalization"})

COMPLETED_MONTHLY_CLOSE_STATUSES = frozenset({"passed", "skipped"})

_TPL_UNIDAD_CREAR = "contabilidad/unidad_crear.html"

_TPL_BOOK_CREAR = "contabilidad/book_crear.html"

_TPL_CUENTA_CREAR = "contabilidad/cuenta_crear.html"

_TPL_CENTRO_COSTO_CREAR = "contabilidad/centro-costo_crear.html"

_TPL_PROYECTO_CREAR = "contabilidad/proyecto_crear.html"

_TPL_PERIODO_CREAR = "contabilidad/periodo_crear.html"

_TPL_TC_CREAR = "contabilidad/tc_crear.html"


@contabilidad.before_request
def enforce_close_and_recurring_company_access():
    """Enforce company isolation for close runs and recurring templates."""
    if not request.view_args:
        return None
    identifier = request.view_args.get("identifier")
    if not identifier:
        return None
    if request.path.startswith("/accounting/period-close/"):
        from cacao_accounting.database import PeriodCloseRun

        close_run = database.session.get(PeriodCloseRun, identifier)
        if close_run:
            exige_acceso_compania("accounting", close_run.company, "autorizar" if request.method == "POST" else "consultar")
    elif request.path.startswith("/accounting/journal/recurring/"):
        template = database.session.get(RecurringJournalTemplate, identifier)
        if template:
            exige_acceso_compania("accounting", template.company, "autorizar" if request.method == "POST" else "consultar")
    return None


def _company_label(company_code: str) -> str:
    """Devuelve etiqueta de entidad para Smart Select."""
    from cacao_accounting.database import Entity

    company = database.session.execute(database.select(Entity).filter_by(code=company_code)).scalar_one_or_none()
    if company is None:
        return company_code
    return f"{company.code} - {company.company_name}"


def _validate_active_entity_submission(company_code: str) -> None:
    """Valida que la entidad exista y esté activa para formularios operativos."""
    from cacao_accounting.database import Entity

    company = database.session.execute(database.select(Entity).filter_by(code=company_code)).scalar_one_or_none()
    if company is None:
        raise ValueError(_(ENTIDAD_NO_EXISTE_MSG))
    if not bool(company.enabled):
        raise ValueError(_("La entidad indicada está inactiva."))


def _accounting_period_status_label(enabled: bool, is_closed: bool) -> str:
    """Genera etiqueta de estado derivada de habilitado/cerrado."""
    if enabled and not is_closed:
        return "habilitado_abierto"
    if enabled and is_closed:
        return "habilitado_cerrado"
    if not enabled and not is_closed:
        return "deshabilitado_abierto"
    return "deshabilitado_cerrado"


def _validate_entity_can_be_deactivated(company_code: str) -> None:
    """Valida reglas administrativas antes de desactivar una entidad."""
    from cacao_accounting.database import Entity

    company = database.session.execute(database.select(Entity).filter_by(code=company_code)).scalar_one_or_none()
    if company is None:
        raise ValueError(_(ENTIDAD_NO_EXISTE_MSG))
    active_count = (
        database.session.execute(database.select(database.func.count(Entity.id)).filter(Entity.enabled.is_(True))).scalar()
        or 0
    )
    if force_single_entity() and active_count <= 1:
        raise ValueError(_("No se puede desactivar la única entidad activa en modo escritorio."))


def _account_descendant_codes(entity: str, account_code: str) -> set[str]:
    from cacao_accounting.database import Accounts

    descendants: set[str] = set()
    pending = [account_code]
    while pending:
        current = pending.pop()
        children = database.session.execute(
            database.select(Accounts.code).filter(Accounts.entity == entity, Accounts.parent == current)
        ).scalars()
        for child_code in children:
            if child_code not in descendants:
                descendants.add(child_code)
                pending.append(child_code)
    return descendants


def _resolve_account_parent(entity: str, parent_ref: str) -> tuple[str, str]:
    from cacao_accounting.database import Accounts

    normalized_ref = str(parent_ref).strip()
    id_value: str | int | None = normalized_ref
    try:
        id_python_type = getattr(Accounts.__table__.c.id.type, "python_type", str)
    except NotImplementedError:
        id_python_type = str
    if id_python_type is int:
        id_value = int(normalized_ref) if normalized_ref.isdigit() else None
    parent = None
    if id_value is not None:
        parent = database.session.execute(
            database.select(Accounts).filter(Accounts.entity == entity, Accounts.id == id_value)
        ).scalar_one_or_none()
    if parent is None:
        parent = database.session.execute(
            database.select(Accounts).filter(Accounts.entity == entity, Accounts.code == normalized_ref)
        ).scalar_one_or_none()
    if parent is None:
        raise ValueError(_("La cuenta padre indicada no existe para la entidad seleccionada."))
    return parent.code, f"{parent.code} - {parent.name}"


def _validate_account_parent(entity: str, parent_ref: str | None, *, current_code: str | None = None) -> str | None:
    from cacao_accounting.database import Accounts

    if not parent_ref:
        return None
    parent_code, _parent_label = _resolve_account_parent(entity, parent_ref)
    if current_code and parent_code == current_code:
        raise ValueError(_("Una cuenta no puede ser padre de si misma."))
    parent = database.session.execute(
        database.select(Accounts).filter(Accounts.entity == entity, Accounts.code == parent_code)
    ).scalar_one_or_none()
    if parent is None:
        raise ValueError(_("La cuenta padre indicada no existe para la entidad seleccionada."))
    if not bool(parent.active) or not bool(parent.enabled):
        raise ValueError(_("La cuenta padre debe estar activa."))
    if not bool(parent.group):
        raise ValueError(_("La cuenta padre debe ser una cuenta de grupo."))
    if current_code and parent_code in _account_descendant_codes(entity, current_code):
        raise ValueError(_("La cuenta padre seleccionada genera un ciclo jerarquico."))
    return parent_code


def _build_cost_center_edit_form(registro):
    from cacao_accounting.contabilidad.forms import FormularioCentroCosto
    from cacao_accounting.database import CostCenter

    formulario = FormularioCentroCosto(obj=registro)
    formulario.id.data = registro.code
    formulario.entidad.choices = obtener_lista_entidades_por_id_razonsocial()
    formulario.padre.choices = [("", SIN_PADRE)]
    formulario.entidad.data = registro.entity

    padre_row = None
    if request.method == "POST" and request.form.get("padre"):
        formulario.padre.choices.append((request.form["padre"], request.form["padre"]))
    if registro.parent:
        padre_row = database.session.execute(
            database.select(CostCenter).filter(CostCenter.entity == registro.entity, CostCenter.code == registro.parent)
        ).scalar_one_or_none()
        if padre_row:
            formulario.padre.choices.append((str(padre_row.id), f"{padre_row.code} - {padre_row.name}"))

    if request.method != "POST":
        formulario.nombre.data = registro.name
        formulario.activo.data = bool(registro.active)
        formulario.predeterminado.data = bool(registro.default)
        formulario.grupo.data = bool(registro.group)
        formulario.padre.data = str(padre_row.id) if padre_row else registro.parent

    entity_initial_label = _company_label(registro.entity) if registro.entity else ""
    parent_initial_label = f"{padre_row.code} - {padre_row.name}" if padre_row else ""
    return formulario, entity_initial_label, parent_initial_label


def _build_account_edit_form(registro, entity):
    from cacao_accounting.contabilidad.forms import FormularioCuenta
    from cacao_accounting.database import Accounts

    formulario = FormularioCuenta(obj=registro)
    formulario.entidad.choices = obtener_lista_entidades_por_id_razonsocial()
    formulario.entidad.data = registro.entity
    formulario.padre.choices = [("", SIN_PADRE)]
    padre_row = None
    if request.method == "POST" and request.form.get("padre"):
        formulario.padre.choices.append((request.form["padre"], request.form["padre"]))
    if registro.parent:
        padre_row = database.session.execute(
            database.select(Accounts).filter(Accounts.code == registro.parent, Accounts.entity == entity)
        ).scalar_one_or_none()
        if padre_row:
            formulario.padre.choices.append((str(padre_row.id), f"{padre_row.code} - {padre_row.name}"))
        if request.method != "POST":
            formulario.padre.data = str(padre_row.id) if padre_row else registro.parent
    entity_initial_label = _company_label(registro.entity) if registro.entity else ""
    parent_initial_label = f"{padre_row.code} - {padre_row.name}" if registro.parent and padre_row else ""
    return formulario, entity_initial_label, parent_initial_label


def _cost_center_descendant_codes(entity: str, center_code: str) -> set[str]:
    from cacao_accounting.database import CostCenter

    descendants: set[str] = set()
    pending = [center_code]
    while pending:
        current = pending.pop()
        children = database.session.execute(
            database.select(CostCenter.code).filter(CostCenter.entity == entity, CostCenter.parent == current)
        ).scalars()
        for child_code in children:
            if child_code not in descendants:
                descendants.add(child_code)
                pending.append(child_code)
    return descendants


def _resolve_cost_center_parent(entity: str, parent_ref: str) -> tuple[str, str]:
    from cacao_accounting.database import CostCenter

    normalized_ref = str(parent_ref).strip()
    id_value: str | int | None = normalized_ref
    try:
        id_python_type = getattr(CostCenter.__table__.c.id.type, "python_type", str)
    except NotImplementedError:
        id_python_type = str
    if id_python_type is int:
        id_value = int(normalized_ref) if normalized_ref.isdigit() else None
    parent = None
    if id_value is not None:
        parent = database.session.execute(
            database.select(CostCenter).filter(CostCenter.entity == entity, CostCenter.id == id_value)
        ).scalar_one_or_none()
    if parent is None:
        parent = database.session.execute(
            database.select(CostCenter).filter(CostCenter.entity == entity, CostCenter.code == normalized_ref)
        ).scalar_one_or_none()
    if parent is None:
        raise ValueError(_("El centro de costos padre indicado no existe para la entidad seleccionada."))
    return parent.code, f"{parent.code} - {parent.name}"


def _validate_cost_center_parent(
    entity: str,
    parent_ref: str | None,
    *,
    current_code: str | None = None,
) -> str | None:
    from cacao_accounting.database import CostCenter

    if not parent_ref:
        return None
    parent_code, _parent_label = _resolve_cost_center_parent(entity, parent_ref)
    if current_code and parent_code == current_code:
        raise ValueError(_("Un centro de costos no puede ser padre de si mismo."))
    parent = database.session.execute(
        database.select(CostCenter).filter(CostCenter.entity == entity, CostCenter.code == parent_code)
    ).scalar_one_or_none()
    if parent is None:
        raise ValueError(_("El centro de costos padre indicado no existe para la entidad seleccionada."))
    if not bool(parent.active) or not bool(parent.enabled):
        raise ValueError(_("El centro de costos padre debe estar activo."))
    if not bool(parent.group):
        raise ValueError(_("El centro de costos padre debe ser un grupo."))
    if current_code and parent_code in _cost_center_descendant_codes(entity, current_code):
        raise ValueError(_("El centro de costos padre seleccionado genera un ciclo jerarquico."))
    return parent_code


def _validate_project_creation_form(formulario: Any) -> tuple[str | None, str | None, bool]:
    """Valida los campos del formulario de creacion de proyecto.

    Retorna (parent_id, capitalization_account_id, error_flag).
    """
    _validate_active_entity_submission(request.form.get("entidad", ""))
    parent_id = request.form.get("parent_id") or None
    if parent_id:
        check_hierarchy_cycle(Project, None, parent_id)

    capitalizable = bool(formulario.capitalizable.data)
    capitalization_account_id = request.form.get("capitalization_account_id") or None
    if capitalizable and not capitalization_account_id:
        raise ValueError("La cuenta de activo es obligatoria si el proyecto es capitalizable.")
    if not capitalizable:
        capitalization_account_id = None

    return parent_id, capitalization_account_id, capitalizable


def _build_project_from_form(formulario: Any, budget_currency: str | None) -> Project:
    """Construye un objeto Project desde los datos del formulario."""
    budget_amount = formulario.presupuesto.data
    return Project(
        code=request.form.get("id", None),
        name=request.form.get("nombre", None),
        entity=request.form.get("entidad", None),
        start=formulario.inicio.data,
        end=formulario.fin.data,
        budget=Decimal(str(budget_amount or 0)),
        budget_currency_code=budget_currency,
        enabled=bool(formulario.habilitado.data),
        status=formulario.status.data or "open",
        parent_id=request.form.get("parent_id") or None,
        capitalizable=bool(formulario.capitalizable.data),
        capitalization_account_id=request.form.get("capitalization_account_id") or None,
    )


def _populate_project_edit_form(formulario: Any, proyecto: Any) -> None:
    """Puebla los campos del formulario con los datos actuales del proyecto."""
    formulario.nombre.data = proyecto.name
    formulario.entidad.data = proyecto.entity
    formulario.inicio.data = proyecto.start
    formulario.fin.data = proyecto.end
    formulario.presupuesto.data = proyecto.budget
    formulario.habilitado.data = bool(proyecto.enabled)
    formulario.status.data = proyecto.status or "open"
    formulario.parent_id.data = proyecto.parent_id or ""
    formulario.capitalizable.data = bool(proyecto.capitalizable)
    formulario.capitalization_account_id.data = proyecto.capitalization_account_id or ""


def _validate_project_edit_form(formulario: Any, proyecto: Any) -> tuple[str | None, str | None]:
    """Valida los campos del formulario de edicion de proyecto.

    Retorna (parent_id, capitalization_account_id).
    """
    _validate_active_entity_submission(request.form.get("entidad", proyecto.entity))
    parent_id = request.form.get("parent_id") or None
    if parent_id:
        check_hierarchy_cycle(Project, proyecto.id, parent_id)

    capitalizable = bool(formulario.capitalizable.data)
    capitalization_account_id = request.form.get("capitalization_account_id") or None
    if capitalizable and not capitalization_account_id:
        raise ValueError("La cuenta de activo es obligatoria si el proyecto es capitalizable.")
    if not capitalizable:
        capitalization_account_id = None

    return parent_id, capitalization_account_id


def _setup_project_edit_form(formulario: Any, proyecto: Any) -> None:
    """Configura las choices del formulario de edicion."""
    exclude_ids = {proyecto.id, *get_descendant_ids(Project, proyecto.id)}
    formulario.id.data = proyecto.code
    formulario.entidad.choices = obtener_lista_entidades_por_id_razonsocial()
    formulario.parent_id.choices = [("", "— Ninguno —")] + [
        (p.id, f"{p.code} - {p.name}")
        for p in database.session.execute(
            database.select(Project).where(Project.id.notin_(exclude_ids)).order_by(Project.code)
        )
        .scalars()
        .all()
    ]
    formulario.capitalization_account_id.choices = [("", "— Seleccionar Cuenta —")] + [
        (a.id, f"{a.code} - {a.name}")
        for a in database.session.execute(database.select(Accounts).order_by(Accounts.code)).scalars().all()
    ]


def _render_project_edit_form(formulario: Any, titulo: str, proyecto: Any, entity_initial_label: str) -> str:
    """Renderiza el formulario de edición de proyecto con el contexto estándar."""
    return render_template(
        _TPL_PROYECTO_CREAR,
        titulo=titulo,
        form=formulario,
        edit=True,
        budget_currency_code=proyecto.budget_currency_code or "",
        entity_initial_label=entity_initial_label,
    )


def _resolve_project_budget_currency(entity: str | None, budget_amount: Any) -> str | None:
    """Resuelve la moneda funcional del presupuesto cuando aplica."""
    if budget_amount is None:
        return None
    return CurrencyGuard().validate_company_functional_currency(entity).code


def _update_project_from_form(
    proyecto: Any,
    formulario: Any,
    budget_amount: Any,
    budget_currency: str | None,
) -> None:
    """Actualiza un proyecto editado con los valores enviados por formulario."""
    proyecto.name = request.form.get("nombre", proyecto.name)
    proyecto.entity = request.form.get("entidad", proyecto.entity)
    proyecto.start = formulario.inicio.data
    proyecto.end = formulario.fin.data
    proyecto.budget = Decimal(str(budget_amount or 0))
    proyecto.budget_currency_code = budget_currency
    proyecto.enabled = bool(formulario.habilitado.data)
    proyecto.status = formulario.status.data or "open"
    proyecto.parent_id = request.form.get("parent_id") or None
    proyecto.capitalizable = bool(formulario.capitalizable.data)
    proyecto.capitalization_account_id = request.form.get("capitalization_account_id") or None
    if not proyecto.capitalizable:
        proyecto.capitalization_account_id = None

    update_hierarchy_attributes(proyecto)


def _get_templates_and_applied_ids(close_run: Any, period: Any) -> tuple[Sequence[Any], list[str]]:
    """Obtiene plantillas aplicables y sus aplicaciones para un periodo de cierre."""
    from cacao_accounting.database import RecurringJournalApplication, RecurringJournalTemplate

    if not period:
        return (), []

    templates = (
        database.session.execute(
            database.select(RecurringJournalTemplate)
            .filter_by(company=close_run.company, status="approved")
            .where(RecurringJournalTemplate.start_date <= period.end)
            .where(RecurringJournalTemplate.end_date >= period.end)
            .where(RecurringJournalTemplate.is_completed.is_(False))
            .order_by(RecurringJournalTemplate.code)
        )
        .scalars()
        .all()
    )
    applied_apps = (
        database.session.query(RecurringJournalApplication)
        .filter_by(
            company=close_run.company,
            fiscal_year=str(period.fiscal_year_id),
            accounting_period=period.name,
            status="applied",
        )
        .all()
    )
    applied_ids = [app.template_id for app in applied_apps]
    return templates, applied_ids


def _get_period_close_checks(close_run: Any) -> Sequence[Any]:
    """Obtiene los checks de cierre mensual."""
    from cacao_accounting.database import PeriodCloseCheck

    return (
        database.session.execute(
            database.select(PeriodCloseCheck)
            .filter_by(close_run_id=close_run.id)
            .order_by(PeriodCloseCheck.created.desc(), PeriodCloseCheck.id.desc())
        )
        .scalars()
        .all()
    )


def _monthly_close_check_errors(checks: Sequence[Any]) -> tuple[set[str], set[str]]:
    """Return missing and unsuccessful mandatory close steps using latest results."""
    latest: dict[str, Any] = {}
    for check in checks:
        latest.setdefault(str(check.check_type), check)
    missing = set(REQUIRED_MONTHLY_CLOSE_CHECKS) - set(latest)
    unsuccessful = {
        check_type
        for check_type, check in latest.items()
        if check_type in REQUIRED_MONTHLY_CLOSE_CHECKS and check.check_status not in COMPLETED_MONTHLY_CLOSE_STATUSES
    }
    return missing, unsuccessful


def _discover_applicable_templates(company: str, period_end: date) -> list[str]:
    templates = (
        database.session.execute(
            database.select(RecurringJournalTemplate)
            .filter_by(company=company, status="approved")
            .where(RecurringJournalTemplate.start_date <= period_end)
            .where(RecurringJournalTemplate.end_date >= period_end)
            .where(RecurringJournalTemplate.is_completed.is_(False))
        )
        .scalars()
        .all()
    )
    return [template.id for template in templates]


def _apply_recurring_templates(
    template_ids: list[str],
    fiscal_year: str,
    period_name: str,
    application_date: date,
    user_id: str,
) -> tuple[int, list[str]]:
    from cacao_accounting.contabilidad.recurring_journal_service import (
        RecurringJournalError,
        apply_recurring_template,
    )

    success_count = 0
    errors = []
    for tid in template_ids:
        try:
            apply_recurring_template(
                template_id=tid,
                fiscal_year=fiscal_year,
                period_name=period_name,
                application_date=application_date,
                user_id=user_id,
            )
            success_count += 1
        except RecurringJournalError as exc:
            errors.append(str(exc))
    return success_count, errors


def _record_check_result(
    close_run_id: str,
    success_count: int,
    errors: list[str],
) -> None:
    from cacao_accounting.database import PeriodCloseCheck

    if success_count and not errors:
        check_status = "passed"
    elif errors:
        check_status = "failed"
    else:
        check_status = "skipped"
    message = f"Plantillas aplicadas: {success_count}."
    if errors:
        message = f"{message} Errores: {' | '.join(errors)}"
    database.session.add(
        PeriodCloseCheck(
            close_run_id=close_run_id,
            check_type="apply_recurring_journals",
            check_status=check_status,
            message=message,
        )
    )


def _resolve_period_from_date(company: str, year: str, month: str) -> tuple[str, str]:
    """Resuelve periodo contable a partir de año y mes."""
    from cacao_accounting.database import AccountingPeriod

    try:
        period_date = date(int(year), int(month), 1)
    except ValueError:
        return "", ""
    period = (
        database.session.execute(
            database.select(AccountingPeriod)
            .filter_by(entity=company, enabled=True)
            .where(AccountingPeriod.start <= period_date)
            .where(AccountingPeriod.end >= period_date)
        )
        .scalars()
        .first()
    )
    if period:
        return period.fiscal_year_id or "", period.id
    return "", ""


def _validate_exchange_revaluation_period(company: str, fiscal_year_id: str, period_id: str):
    from cacao_accounting.database import AccountingPeriod

    period = database.session.get(AccountingPeriod, period_id)
    if not period or period.entity != company:
        flash("Periodo contable inválido para la compañía y período seleccionados.", "danger")
        return None
    if fiscal_year_id and period.fiscal_year_id != fiscal_year_id:
        flash("Periodo contable inválido para la compañía y año fiscal seleccionados.", "danger")
        return None
    return period


def _handle_exchange_revaluation_post() -> "Any":
    """Procesa el formulario POST de revalorizacion cambiaria. Retorna redirect o None."""
    from cacao_accounting.contabilidad.exchange_revaluation_service import (
        ExchangeRevaluationError,
        ExchangeRevaluationService,
    )

    company = request.form.get("company") or ""
    fiscal_year_id = request.form.get("fiscal_year_id") or ""
    period_id = request.form.get("period_id") or ""
    year = request.form.get("year")
    month = request.form.get("month")

    if not company:
        flash("La compañía es requerida.", "danger")
        return None

    if not fiscal_year_id and year and month:
        resolved_fiscal_year_id, resolved_period_id = _resolve_period_from_date(company, year, month)
        if resolved_period_id:
            period_id = resolved_period_id
            fiscal_year_id = resolved_fiscal_year_id or fiscal_year_id

    if not period_id:
        flash("El periodo contable es requerido.", "danger")
        return None

    period = _validate_exchange_revaluation_period(company, fiscal_year_id, period_id)
    if not period:
        return None

    try:
        run = ExchangeRevaluationService().run(company=company, period_id=period_id, user_id=str(current_user.id))
    except ExchangeRevaluationError as exc:
        database.session.rollback()
        flash_error(exc)
        return None

    flash("La revalorizacion fue ejecutada correctamente.", "success")
    if run.status == "completed_no_changes":
        flash("No se generaron diferencias cambiarias.", "info")
    return redirect(url_for(CONTABILIDAD_REVALORIZACION_VER, identifier=run.id))


def _build_journal_selected_books(journal, entity: str) -> list[str]:
    from cacao_accounting.contabilidad.journal_service import serialize_journal_for_form
    from cacao_accounting.database import Book

    selected_book_codes = serialize_journal_for_form(journal).get("books") or []
    if not selected_book_codes:
        return []
    selected_book_rows = (
        database.session.execute(database.select(Book).filter(Book.entity == entity).where(Book.code.in_(selected_book_codes)))
        .scalars()
        .all()
    )
    selected_books = [
        f"{book.code} - {book.name}" + (f" ({book.currency})" if getattr(book, "currency", None) else "")
        for book in selected_book_rows
    ]
    if not selected_books:
        fallback_book_rows = (
            database.session.execute(
                database.select(Book).filter(Book.entity == entity).where(Book.status.is_(None) | (Book.status == "activo"))
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
    return selected_books


def _build_journal_lineas(lineas_raw, account_labels: dict, cost_center_labels: dict) -> list[dict]:
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
    return lineas


def _get_journal_currency_label(journal, entity) -> str:
    from cacao_accounting.database import Entity

    entity_obj = database.session.execute(database.select(Entity).filter_by(code=entity)).scalars().first() if entity else None
    company_currency_code = getattr(entity_obj, "currency", None)
    if journal.transaction_currency:
        return str(journal.transaction_currency)
    if company_currency_code:
        return str(company_currency_code)
    return _("Moneda local")


def _update_series_sequence(serie, form):
    from cacao_accounting.database import Sequence, SeriesSequenceMap
    from cacao_accounting.logs import log

    sequence_id = database.session.execute(
        database.select(SeriesSequenceMap.sequence_id).filter_by(naming_series_id=serie.id)
    ).scalar_one_or_none()
    if not sequence_id:
        return
    sequence = database.session.get(Sequence, sequence_id)
    if sequence is not None:
        sequence.current_value = form.current_value.data or 0
        sequence.increment = form.increment.data or 1
        sequence.padding = form.padding.data or 5
        sequence.reset_policy = form.reset_policy.data or "never"
    else:
        log.warning(f"Sequence record not found for sequence_id={sequence_id} on series={serie.id}")


def _update_counter_from_form(counter: Any, form: Any) -> None:
    """Apply form field values to an ExternalCounter instance."""
    counter.company = form.company.data
    counter.name = form.nombre.data
    counter.counter_type = form.counter_type.data or None
    counter.prefix = form.prefix.data or None
    counter.last_used = form.last_used.data or 0
    counter.padding = form.padding.data or 5
    counter.is_active = bool(form.is_active.data)
    counter.description = form.description.data or None


def _sync_counter_naming_series_map(counter: Any, new_naming_series_id: str | None) -> None:
    """Synchronize the SeriesExternalCounterMap for a counter."""
    from cacao_accounting.database import SeriesExternalCounterMap

    if counter.naming_series_id == new_naming_series_id:
        return

    counter.naming_series_id = new_naming_series_id
    existing_map = database.session.execute(
        database.select(SeriesExternalCounterMap).filter_by(external_counter_id=counter.id)
    ).scalar_one_or_none()

    if new_naming_series_id:
        if existing_map:
            existing_map.naming_series_id = new_naming_series_id
        else:
            database.session.add(
                SeriesExternalCounterMap(
                    naming_series_id=new_naming_series_id,
                    external_counter_id=counter.id,
                    priority=0,
                    condition_json=None,
                )
            )
    elif existing_map:
        database.session.delete(existing_map)
