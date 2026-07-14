# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Controlador de rutas para el Pronóstico de Flujo de Caja."""

from datetime import date
from decimal import Decimal
from flask import abort, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from cacao_accounting.bancos import bancos
from cacao_accounting.database import (
    database,
    CashForecast,
    CashForecastEntry,
    FiscalYear,
)
from cacao_accounting.decorators import modulo_activo
from cacao_accounting.runtime_mode import is_desktop_mode
from cacao_accounting.contabilidad.auxiliares import (
    obtener_lista_entidades_por_id_razonsocial,
    obtener_lista_monedas,
)
from cacao_accounting.bancos.cash_forecast_service import (
    get_cash_forecast_matrix,
    get_forecast_comparison,
)
from cacao_accounting.document_flow.status import _


def _check_desktop_mode():
    """Check if desktop mode is active and redirect with a warning if so."""
    if is_desktop_mode():
        flash("Proyección de flujo de caja no disponible en modo DESKTOP", "danger")
        return True
    return False


@bancos.route("/cash-forecast/list")
@modulo_activo("cash")
@login_required
def cash_forecast_list():
    """Listado de pronósticos de flujo de caja."""
    if _check_desktop_mode():
        return redirect(url_for("bancos.bancos_"))

    company = request.args.get("company")
    companies = obtener_lista_entidades_por_id_razonsocial()
    if company in (None, "") and companies:
        for code, name in companies:
            if code:
                company = code
                break

    forecasts = database.session.query(CashForecast).filter_by(company=company).order_by(CashForecast.created.desc()).all()

    return render_template(
        "bancos/cash_forecast_lista.html",
        forecasts=forecasts,
        companies=companies,
        selected_company=company,
        titulo="Pronósticos de Flujo de Caja",
    )


@bancos.route("/cash-forecast/new", methods=["GET", "POST"])
@modulo_activo("cash")
@login_required
def cash_forecast_new():
    """Crea un nuevo pronóstico de flujo de caja (Draft)."""
    if _check_desktop_mode():
        return redirect(url_for("bancos.bancos_"))

    companies = obtener_lista_entidades_por_id_razonsocial()
    company = request.args.get("company") or request.form.get("company")
    if company in (None, "") and companies:
        for code, name in companies:
            if code:
                company = code
                break

    fiscal_years = database.session.query(FiscalYear).filter_by(entity=company).all()

    if request.method == "POST":
        version = request.form.get("version", "").strip()
        description = request.form.get("description", "").strip()
        fiscal_year_id = request.form.get("fiscal_year_id")
        periodicity = request.form.get("periodicity")

        if not version or not fiscal_year_id or not periodicity:
            flash("Todos los campos obligatorios deben ser completados.", "danger")
        else:
            # Check unique version for this company and fiscal year
            existing = (
                database.session.query(CashForecast)
                .filter_by(company=company, fiscal_year_id=fiscal_year_id, version=version)
                .first()
            )
            if existing:
                flash(f"La versión '{version}' ya existe para este año fiscal.", "danger")
            else:
                forecast = CashForecast(
                    version=version,
                    description=description,
                    fiscal_year_id=fiscal_year_id,
                    company=company,
                    periodicity=periodicity,
                    status="Draft",
                    created_by=getattr(current_user, "id", None),
                )
                database.session.add(forecast)
                database.session.commit()
                flash("Pronóstico de flujo de caja creado correctamente.", "success")
                return redirect(url_for("bancos.cash_forecast_detail", forecast_id=forecast.id))

    return render_template(
        "bancos/cash_forecast_nuevo.html",
        companies=companies,
        selected_company=company,
        fiscal_years=fiscal_years,
        titulo="Nuevo Pronóstico de Flujo de Caja",
    )


@bancos.route("/cash-forecast/<forecast_id>", methods=["GET"])
@modulo_activo("cash")
@login_required
def cash_forecast_detail(forecast_id):
    """Muestra la matriz YTD y permite gestionar las proyecciones manuales."""
    if _check_desktop_mode():
        return redirect(url_for("bancos.bancos_"))

    forecast = database.session.get(CashForecast, forecast_id)
    if not forecast:
        abort(404)

    fiscal_year = database.session.get(FiscalYear, forecast.fiscal_year_id)
    currencies = obtener_lista_monedas()

    # Obtener matriz de flujo
    matrix = get_cash_forecast_matrix(forecast.company, forecast.id)

    # Obtener entradas manuales de este forecast
    entries = (
        database.session.query(CashForecastEntry)
        .filter_by(forecast_id=forecast.id)
        .order_by(CashForecastEntry.estimated_date.asc())
        .all()
    )

    return render_template(
        "bancos/cash_forecast_detalle.html",
        forecast=forecast,
        fiscal_year=fiscal_year,
        currencies=currencies,
        matrix=matrix,
        entries=entries,
        titulo=f"Pronóstico de Flujo de Caja: {forecast.version}",
    )


@bancos.route("/cash-forecast/<forecast_id>/approve", methods=["POST"])
@modulo_activo("cash")
@login_required
def cash_forecast_approve(forecast_id):
    """Aprueba el pronóstico y lo hace inmutable."""
    if _check_desktop_mode():
        return redirect(url_for("bancos.bancos_"))

    forecast = database.session.get(CashForecast, forecast_id)
    if not forecast:
        abort(404)
    if forecast.status != "Draft":
        flash("Sólo los pronósticos en estado Borrador pueden ser aprobados.", "danger")
        return redirect(url_for("bancos.cash_forecast_detail", forecast_id=forecast.id))

    forecast.status = "Approved"
    forecast.approved_by = getattr(current_user, "id", None)
    forecast.approved_at = database.func.now()
    database.session.commit()
    flash("Pronóstico de flujo de caja aprobado con éxito.", "success")
    return redirect(url_for("bancos.cash_forecast_detail", forecast_id=forecast.id))


@bancos.route("/cash-forecast/<forecast_id>/close", methods=["POST"])
@modulo_activo("cash")
@login_required
def cash_forecast_close(forecast_id):
    """Cierra el pronóstico."""
    if _check_desktop_mode():
        return redirect(url_for("bancos.bancos_"))

    forecast = database.session.get(CashForecast, forecast_id)
    if not forecast:
        abort(404)
    if forecast.status != "Approved":
        flash("Sólo los pronósticos en estado Aprobado pueden ser cerrados.", "danger")
        return redirect(url_for("bancos.cash_forecast_detail", forecast_id=forecast.id))

    forecast.status = "Closed"
    database.session.commit()
    flash("Pronóstico de flujo de caja cerrado con éxito.", "success")
    return redirect(url_for("bancos.cash_forecast_detail", forecast_id=forecast.id))


@bancos.route("/cash-forecast/<forecast_id>/archive", methods=["POST"])
@modulo_activo("cash")
@login_required
def cash_forecast_archive(forecast_id):
    """Archiva el pronóstico."""
    if _check_desktop_mode():
        return redirect(url_for("bancos.bancos_"))

    forecast = database.session.get(CashForecast, forecast_id)
    if not forecast:
        abort(404)
    if forecast.status not in ("Approved", "Closed"):
        flash("Sólo los pronósticos Aprobados o Cerrados pueden ser archivados.", "danger")
        return redirect(url_for("bancos.cash_forecast_detail", forecast_id=forecast.id))

    forecast.status = "Archived"
    database.session.commit()
    flash("Pronóstico de flujo de caja archivado con éxito.", "success")
    return redirect(url_for("bancos.cash_forecast_detail", forecast_id=forecast.id))


@bancos.route("/cash-forecast/<forecast_id>/delete", methods=["POST"])
@modulo_activo("cash")
@login_required
def cash_forecast_delete(forecast_id):
    """Elimina el pronóstico de flujo de caja si está en Borrador."""
    if _check_desktop_mode():
        return redirect(url_for("bancos.bancos_"))

    forecast = database.session.get(CashForecast, forecast_id)
    if not forecast:
        abort(404)
    if forecast.status != "Draft":
        flash("Sólo los pronósticos en estado Borrador pueden ser eliminados.", "danger")
        return redirect(url_for("bancos.cash_forecast_detail", forecast_id=forecast.id))

    company = forecast.company
    database.session.delete(forecast)
    database.session.commit()
    flash("Pronóstico de flujo de caja eliminado con éxito.", "success")
    return redirect(url_for("bancos.cash_forecast_list", company=company))


@bancos.route("/cash-forecast/<forecast_id>/entry/add", methods=["POST"])
@modulo_activo("cash")
@login_required
def cash_forecast_entry_add(forecast_id):
    """Añade un movimiento proyectado manual al pronóstico."""
    if _check_desktop_mode():
        return redirect(url_for("bancos.bancos_"))

    forecast = database.session.get(CashForecast, forecast_id)
    if not forecast:
        abort(404)
    if forecast.status != "Draft":
        flash("No se pueden modificar pronósticos aprobados o cerrados.", "danger")
        return redirect(url_for("bancos.cash_forecast_detail", forecast_id=forecast.id))

    try:
        type_ = request.form.get("type")
        concept = request.form.get("concept", "").strip()
        currency = request.form.get("currency")
        amount = Decimal(request.form.get("amount", "0"))
        estimated_date = date.fromisoformat(request.form.get("estimated_date", ""))
        notes = request.form.get("notes", "").strip()

        if not type_ or not concept or not currency or amount <= 0 or not estimated_date:
            flash("Todos los campos obligatorios deben tener valores válidos.", "danger")
        else:
            entry = CashForecastEntry(
                forecast_id=forecast.id,
                type=type_,
                concept=concept,
                currency=currency,
                amount=amount,
                estimated_date=estimated_date,
                notes=notes,
                created_by=getattr(current_user, "id", None),
            )
            database.session.add(entry)
            database.session.commit()
            flash("Proyección manual agregada correctamente.", "success")
    except Exception as exc:
        database.session.rollback()
        flash(f"Error al agregar proyección: {str(exc)}", "danger")

    next_url = request.args.get("next")
    if next_url and next_url.startswith("/") and not next_url.startswith("//"):
        return redirect(next_url)
    return redirect(url_for("bancos.cash_forecast_detail", forecast_id=forecast.id))


@bancos.route("/cash-forecast/<forecast_id>/entry/<entry_id>/delete", methods=["POST"])
@modulo_activo("cash")
@login_required
def cash_forecast_entry_delete(forecast_id, entry_id):
    """Elimina un movimiento proyectado manual del pronóstico."""
    if _check_desktop_mode():
        return redirect(url_for("bancos.bancos_"))

    forecast = database.session.get(CashForecast, forecast_id)
    if not forecast:
        abort(404)
    if forecast.status != "Draft":
        flash("No se pueden modificar pronósticos aprobados o cerrados.", "danger")
        return redirect(url_for("bancos.cash_forecast_detail", forecast_id=forecast.id))

    entry = database.session.get(CashForecastEntry, entry_id)
    if entry and entry.forecast_id == forecast.id:
        database.session.delete(entry)
        database.session.commit()
        flash("Proyección manual eliminada correctamente.", "success")

    next_url = request.args.get("next")
    if next_url and next_url.startswith("/") and not next_url.startswith("//"):
        return redirect(next_url)
    return redirect(url_for("bancos.cash_forecast_detail", forecast_id=forecast.id))


@bancos.route("/cash-forecast/<forecast_id>/entry/import", methods=["POST"])
@modulo_activo("cash")
@login_required
def cash_forecast_entry_import(forecast_id):
    """Redirige al asistente de importación compartido."""
    flash(
        _("La importación de proyecciones manuales ahora se realiza a través del asistente de importación compartido."),
        "info",
    )
    return redirect(url_for("imports.new"))


@bancos.route("/cash-forecast/compare", methods=["GET"])
@modulo_activo("cash")
@login_required
def cash_forecast_compare():
    """Formulario y resultado de comparación de pronósticos."""
    if _check_desktop_mode():
        return redirect(url_for("bancos.bancos_"))

    company = request.args.get("company")
    companies = obtener_lista_entidades_por_id_razonsocial()
    if company in (None, "") and companies:
        for code, name in companies:
            if code:
                company = code
                break

    # Obtener todos los forecast de esta compañía
    forecasts = database.session.query(CashForecast).filter_by(company=company).order_by(CashForecast.version.asc()).all()

    base_id = request.args.get("base_id")
    compare_id = request.args.get("compare_id")

    comparison = []
    base_forecast = None
    compare_forecast = None

    if base_id and compare_id:
        base_forecast = database.session.get(CashForecast, base_id)
        compare_forecast = database.session.get(CashForecast, compare_id)
        if base_forecast and compare_forecast:
            comparison = get_forecast_comparison(company, base_id, compare_id)

    return render_template(
        "bancos/cash_forecast_comparar.html",
        companies=companies,
        selected_company=company,
        forecasts=forecasts,
        base_id=base_id,
        compare_id=compare_id,
        base_forecast=base_forecast,
        compare_forecast=compare_forecast,
        comparison=comparison,
        titulo="Comparación de Escenarios de Flujo de Caja",
    )


@bancos.route("/cash-forecast/manual-entries", methods=["GET"])
@modulo_activo("cash")
@login_required
def cash_forecast_manual_entries():
    """Vista dedicada para gestionar el Forecast de Entradas manuales."""
    if _check_desktop_mode():
        return redirect(url_for("bancos.bancos_"))

    company = request.args.get("company")
    companies = obtener_lista_entidades_por_id_razonsocial()
    if company in (None, "") and companies:
        for code, name in companies:
            if code:
                company = code
                break

    # Obtener todos los forecast de esta compañía
    forecasts = database.session.query(CashForecast).filter_by(company=company).order_by(CashForecast.version.asc()).all()

    selected_forecast_id = request.args.get("forecast_id")
    # Default to first forecast if not specified
    if not selected_forecast_id and forecasts:
        selected_forecast_id = forecasts[0].id

    selected_forecast = None
    entries = []
    if selected_forecast_id:
        selected_forecast = database.session.get(CashForecast, selected_forecast_id)
        if selected_forecast:
            entries = (
                database.session.query(CashForecastEntry)
                .filter_by(forecast_id=selected_forecast.id)
                .order_by(CashForecastEntry.estimated_date.asc())
                .all()
            )

    currencies = obtener_lista_monedas()

    return render_template(
        "bancos/cash_forecast_entradas.html",
        companies=companies,
        selected_company=company,
        forecasts=forecasts,
        selected_forecast=selected_forecast,
        entries=entries,
        currencies=currencies,
        titulo="Forecast de Entradas manuales",
    )


@bancos.route("/cash-forecast/<forecast_id>/entry/<entry_id>/edit", methods=["POST"])
@modulo_activo("cash")
@login_required
def cash_forecast_entry_edit(forecast_id, entry_id):
    """Edita un movimiento proyectado manual del pronóstico."""
    if _check_desktop_mode():
        return redirect(url_for("bancos.bancos_"))

    forecast = database.session.get(CashForecast, forecast_id)
    if not forecast:
        abort(404)
    if forecast.status != "Draft":
        flash("No se pueden modificar pronósticos aprobados o cerrados.", "danger")
        return redirect(url_for("bancos.cash_forecast_detail", forecast_id=forecast.id))

    entry = database.session.get(CashForecastEntry, entry_id)
    if not entry or entry.forecast_id != forecast.id:
        abort(404)

    try:
        type_ = request.form.get("type")
        concept = request.form.get("concept", "").strip()
        currency = request.form.get("currency")
        amount = Decimal(request.form.get("amount", "0"))
        estimated_date = date.fromisoformat(request.form.get("estimated_date", ""))
        notes = request.form.get("notes", "").strip()

        if not type_ or not concept or not currency or amount <= 0 or not estimated_date:
            flash("Todos los campos obligatorios deben tener valores válidos.", "danger")
        else:
            entry.type = type_
            entry.concept = concept
            entry.currency = currency
            entry.amount = amount
            entry.estimated_date = estimated_date
            entry.notes = notes
            database.session.commit()
            flash("Proyección manual actualizada correctamente.", "success")
    except Exception as exc:
        database.session.rollback()
        flash(f"Error al actualizar la proyección: {str(exc)}", "danger")

    next_url = request.args.get("next")
    if next_url and next_url.startswith("/") and not next_url.startswith("//"):
        return redirect(next_url)
    return redirect(url_for("bancos.cash_forecast_detail", forecast_id=forecast.id))
