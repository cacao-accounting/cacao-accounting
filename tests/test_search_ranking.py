# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Pruebas de búsqueda con varios términos y relevancia (issue #771).

Cubre que el selector global:
1. Refina la búsqueda cuando se envían varios términos (AND lógico) en lugar de
   devolver la unión de patrones sueltos.
2. Ordene los resultados por relevancia: coincidencia por prefijo antes que por
   substring, conservando un determinismo para empates.
"""

from __future__ import annotations

import pytest

from cacao_accounting import create_app
from cacao_accounting.config import configuracion
from cacao_accounting.database import Accounts, Entity, database
from cacao_accounting.search_select import search_select

COMPANY = "srch8"


@pytest.fixture()
def app_ctx():
    """Aplicación aislada con catálogo de cuentas para búsqueda."""
    app = create_app(
        {
            **configuracion,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
            "WTF_CSRF_ENABLED": False,
            "TESTING": True,
        }
    )
    with app.app_context():
        database.create_all()
        database.session.add(Entity(code=COMPANY, name="Search8", company_name="Search8", tax_id="SR-8", currency="NIO"))
        database.session.add_all(
            [
                Accounts(entity=COMPANY, code="1001", name="Banco Central", active=True, enabled=True, group=False),
                Accounts(entity=COMPANY, code="4102", name="Gastos Bancarios", active=True, enabled=True, group=False),
                Accounts(entity=COMPANY, code="4101", name="Gastos Financieros", active=True, enabled=True, group=False),
            ]
        )
        database.session.commit()
        yield app
        database.session.remove()
        database.drop_all()


def test_multiterm_search_refines_results(app_ctx):
    """Dos términos deben reducir el resultado a los registros que los contienen todos."""
    payload = search_select("account", "gastos financieros", {"company": [COMPANY]})
    names = [item.get("display_name") for item in payload["results"]]
    assert any("Gastos Financieros" in name for name in names)
    assert not any("Gastos Bancarios" in name for name in names)
    assert not any("Banco Central" in name for name in names)


def test_partial_contains_search_still_matches(app_ctx):
    """Una búsqueda parcial por substring conserva el comportamiento previo."""
    payload = search_select("account", "fin", {"company": [COMPANY]})
    names = [item.get("display_name") for item in payload["results"]]
    assert any("Gastos Financieros" in name for name in names)


def test_prefix_results_ranked_before_contains(app_ctx):
    """Los registros que coinciden por prefijo aparecen antes que por substring."""
    payload = search_select("account", "ban", {"company": [COMPANY]})
    names = [item.get("display_name") for item in payload["results"]]
    prefix_rows = [name for name in names if "Banco Central" in name]
    contains_rows = [name for name in names if "Gastos Bancarios" in name]
    assert prefix_rows and contains_rows
    assert names.index(prefix_rows[0]) < names.index(contains_rows[0])
