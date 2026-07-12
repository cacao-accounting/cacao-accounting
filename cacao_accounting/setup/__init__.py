# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes
"""Configuración Inicial."""

# ---------------------------------------------------------------------------------------
# Libreria estandar
# --------------------------------------------------------------------------------------

# ---------------------------------------------------------------------------------------
# Librerias de terceros
# ---------------------------------------------------------------------------------------
from flask import Blueprint, flash, redirect, render_template, request, session, url_for
from flask_login import login_required

from cacao_accounting.setup.forms import (
    SetupCompanyForm,
    SetupLanguageForm,
    SetupRegionalForm,
)
from cacao_accounting.setup.catalogs import (
    setup_template_context,
    setup_texts,
)
from cacao_accounting.setup.service import (
    available_currencies,
    finalize_setup,
    get_setup_configuration,
    save_language,
    save_regional_settings,
)

# ---------------------------------------------------------------------------------------
# Recursos locales
# ---------------------------------------------------------------------------------------

# <---------------------------------------------------------------------------------------------> #
# Configuración inicial.
# <---------------------------------------------------------------------------------------------> #
setup_ = Blueprint("setup", __name__, template_folder="templates")
SETUP_ROUTE = "setup.setup"


@setup_.route("/", methods=["GET", "POST"])
@login_required
def setup():
    """Configuración inicial."""
    step = int(session.get("setup_step", 1))
    setup_data = get_setup_configuration()
    language = setup_data.get("idioma", "es")

    if request.method == "POST":
        handled_response = _handle_setup_post(step, setup_data)
        if handled_response is not None:
            return handled_response

    form = _setup_form(step, setup_data)
    template_context = setup_template_context(language)

    return render_template(
        "setup.html",
        form=form,
        step=step,
        setup_data=setup_data,
        currencies=available_currencies(),
        **template_context,
    )


def _handle_setup_post(step: int, setup_data: dict[str, str]) -> object | None:
    """Process the current setup step and return a redirect when completed."""
    action = request.form.get("action")
    texts = setup_texts(setup_data.get("idioma"))

    if action == "back" and step > 1:
        session["setup_step"] = step - 1
        return redirect(url_for(SETUP_ROUTE))

    if step == 1:
        return _handle_setup_language_step()
    if step == 2:
        return _handle_setup_regional_step()
    if step == 3:
        return _handle_setup_company_step(setup_data)

    flash(texts["invalid_step"], "danger")
    return None


def _handle_setup_language_step() -> object | None:
    """Handle the language selection step."""
    form = SetupLanguageForm()
    if form.validate_on_submit():
        save_language(form.idioma.data)
        session["setup_step"] = 1 if request.form.get("action") == "apply_language" else 2
        return redirect(url_for(SETUP_ROUTE))
    flash(setup_texts("es")["invalid_language"], "danger")
    return None


def _handle_setup_regional_step() -> object | None:
    """Handle the regional settings step."""
    setup_data = get_setup_configuration()
    texts = setup_texts(setup_data.get("idioma"))
    form = SetupRegionalForm(language=setup_data.get("idioma"), currencies=available_currencies())
    if form.validate_on_submit():
        try:
            save_regional_settings(form.pais.data, form.moneda.data, form.zona_horaria.data)
        except ValueError as exc:
            flash(texts["invalid_currency"] if str(exc) else texts["invalid_regional"], "danger")
            return None
        else:
            session["setup_step"] = 3
            return redirect(url_for(SETUP_ROUTE))
    flash(texts["invalid_regional"], "danger")
    return None


def _handle_setup_company_step(setup_data: dict[str, str]) -> object | None:
    """Handle the company setup step."""
    texts = setup_texts(setup_data.get("idioma"))
    form = SetupCompanyForm(language=setup_data.get("idioma"))
    if not form.validate_on_submit():
        flash(texts["invalid_company"], "danger")
        return None

    company_data = _build_company_data(form, setup_data)
    catalogo_tipo = form.catalogo.data
    catalogo_archivo = form.catalogo_origen.data if catalogo_tipo == "preexistente" else None
    if catalogo_tipo == "preexistente" and not catalogo_archivo:
        flash(texts["catalog_required"], "danger")
        return None

    finalize_setup(
        company_data,
        catalogo_tipo,
        setup_data.get("pais", "NI"),
        setup_data.get("idioma", "es"),
        catalogo_archivo,
    )
    session.pop("setup_step", None)
    flash(texts["setup_complete"], "success")
    return redirect(url_for("cacao_app.pagina_inicio"))


def _build_company_data(form: SetupCompanyForm, setup_data: dict[str, str]) -> dict[str, object | None]:
    """Build the payload required by the company setup service."""
    return {
        "id": form.id.data,
        "razon_social": form.razon_social.data,
        "nombre_comercial": form.nombre_comercial.data,
        "id_fiscal": form.id_fiscal.data,
        "tipo_entidad": form.tipo_entidad.data,
        "moneda": setup_data.get("moneda"),
        "inicio_anio_fiscal": form.inicio_anio_fiscal.data,
        "fin_anio_fiscal": form.fin_anio_fiscal.data,
    }


def _setup_form(step: int, setup_data: dict[str, str]) -> SetupLanguageForm | SetupRegionalForm | SetupCompanyForm:
    """Return the form instance for the current setup step."""
    if step == 1:
        return SetupLanguageForm(data={"idioma": setup_data.get("idioma")})
    if step == 2:
        return SetupRegionalForm(
            data={
                "pais": setup_data.get("pais"),
                "moneda": setup_data.get("moneda"),
                "zona_horaria": setup_data.get("zona_horaria"),
            },
            language=setup_data.get("idioma"),
            currencies=available_currencies(),
        )
    return SetupCompanyForm(language=setup_data.get("idioma"))
