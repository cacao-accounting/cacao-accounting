# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1859: las traducciones inline de JS usan ``|tojson``.

Una traducción con apóstrofe no debe romper atributos ``onsubmit``,
``onclick``, ``:title``, ``:placeholder`` ni ``x-text``.
"""

from __future__ import annotations

import re
from pathlib import Path

from cacao_accounting import create_app
from cacao_accounting.config import configuracion

PLANTILLAS = (
    "macros.html",
    "transaction_form_macros.html",
    "admin/balance_confirmation_detail.html",
)
PATRON_INSEGURO = re.compile(r"'{{ _\(.*?\) }}'")


def test_traducciones_inline_no_quedan_entre_comillas_js():
    """Las plantillas compilan y no conservan interpolaciones sin tojson."""
    app = create_app({**configuracion, "TESTING": True})
    base = Path(__file__).parents[1] / "cacao_accounting/templates"
    with app.app_context():
        for nombre in PLANTILLAS:
            ruta = base / nombre
            contenido = ruta.read_text(encoding="utf-8")
            assert not PATRON_INSEGURO.search(contenido), nombre
            app.jinja_env.get_template(nombre)
    assert "|tojson" in (base / "macros.html").read_text(encoding="utf-8")
