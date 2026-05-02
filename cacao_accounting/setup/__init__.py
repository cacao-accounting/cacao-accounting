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


@setup_.route("/", methods=["GET", "POST"])
@login_required
def setup():
    """Configuración inicial."""
    step = int(session.get("setup_step", 1))
    setup_data = get_setup_configuration()

    if request.method == "POST":
        action = request.form.get("action")

        if action == "back" and step > 1:
            step -= 1
            session["setup_step"] = step
            return redirect(url_for("setup.setup"))

        if step == 1:
            form = SetupLanguageForm()
            if form.validate_on_submit():
                save_language(form.idioma.data)
                step = 2
                session["setup_step"] = step
                return redirect(url_for("setup.setup"))
            flash("Seleccione un idioma válido.", "danger")
        elif step == 2:
            form = SetupRegionalForm()
            if form.validate_on_submit():
                save_regional_settings(form.pais.data, form.moneda.data)
                step = 3
                session["setup_step"] = step
                return redirect(url_for("setup.setup"))
            flash("Complete los datos regionales correctamente.", "danger")
        elif step == 3:
            form = SetupCompanyForm()
            if form.validate_on_submit():
                company_data = {
                    "id": form.id.data,
                    "razon_social": form.razon_social.data,
                    "nombre_comercial": form.nombre_comercial.data,
                    "id_fiscal": form.id_fiscal.data,
                    "tipo_entidad": form.tipo_entidad.data,
                    "moneda": setup_data.get("moneda"),
                }
                catalogo_tipo = form.catalogo.data
                catalogo_archivo = form.catalogo_origen.data if catalogo_tipo == "preexistente" else None
                if catalogo_tipo == "preexistente" and not catalogo_archivo:
                    flash("Seleccione un catálogo de cuentas existente.", "danger")
                else:
                    finalize_setup(
                        company_data,
                        catalogo_tipo,
                        setup_data.get("pais", "NI"),
                        setup_data.get("idioma", "es"),
                        catalogo_archivo,
                    )
                    session.pop("setup_step", None)
                    flash("Configuración inicial completada.", "success")
                    return redirect(url_for("cacao_app.pagina_inicio"))
            flash("Complete los datos de la empresa correctamente.", "danger")
        else:
            flash("Paso inválido del asistente.", "danger")

    if step == 1:
        form = SetupLanguageForm()
    elif step == 2:
        form = SetupRegionalForm(data={"moneda": setup_data.get("moneda")})
    else:
        form = SetupCompanyForm()

    return render_template(
        "setup.html",
        form=form,
        step=step,
        setup_data=setup_data,
        currencies=available_currencies(),
    )
