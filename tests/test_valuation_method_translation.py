# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 William José Moreno Reyes

"""Localization of inventory valuation method labels (#1557)."""

from flask_babel import force_locale

from cacao_accounting.i18n import _
from cacao_accounting.inventario.valuation_settings import valuation_method_choices, valuation_method_label


def test_average_cost_method_label_is_translated_in_english(app):
    """The value passed through the template gettext call uses the English label."""
    with app.app_context(), force_locale("en"):
        assert _(valuation_method_label("moving_average")) == "Average cost"
        assert _(valuation_method_choices()[0][1]) == "Average cost"
