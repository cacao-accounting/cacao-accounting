# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 William José Moreno Reyes

"""Localization of inventory valuation method labels (#1557)."""

from flask_babel import force_locale

from cacao_accounting.database import Modules, User, database
from cacao_accounting.i18n import _
from cacao_accounting.inventario.valuation_settings import valuation_method_choices, valuation_method_label


def test_average_cost_method_label_is_translated_in_english(app):
    """The value passed through the template gettext call uses the English label."""
    with app.app_context(), force_locale("en"):
        assert _(valuation_method_label("moving_average")) == "Average cost"
        assert _(valuation_method_choices()[0][1]) == "Average cost"


def test_la_configuracion_http_muestra_etiquetas_traducidas(app, authenticated_client, entorno_contable, reference_users):
    """La página admin en inglés no imprime la etiqueta literal en español."""
    del entorno_contable
    user_id = str(reference_users["admin"].id)
    with app.app_context():
        modulo = database.session.execute(database.select(Modules).filter_by(module="admin")).scalar_one_or_none()
        if modulo is None:
            modulo = Modules(module="admin", default=False, enabled=True)
            database.session.add(modulo)
            creado = True
        else:
            creado = False
            anterior_modulo = modulo.enabled
            modulo.enabled = True
        usuario = database.session.get(User, user_id)
        anterior_lang = usuario.language
        usuario.language = "en"
        database.session.commit()
    try:
        response = authenticated_client("admin").get("/settings/inventory-valuation?company=cacao")
    finally:
        with app.app_context():
            usuario = database.session.get(User, user_id)
            usuario.language = anterior_lang
            modulo = database.session.execute(database.select(Modules).filter_by(module="admin")).scalar_one_or_none()
            if modulo is not None:
                if creado:
                    database.session.delete(modulo)
                else:
                    modulo.enabled = anterior_modulo
            database.session.commit()

    assert response.status_code == 200
    cuerpo = response.get_data(as_text=True)
    assert "Average cost" in cuerpo
    assert "Costo promedio" not in cuerpo
    assert "FIFO" in cuerpo
