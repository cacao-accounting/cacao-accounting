# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#2152: el formulario distingue alta y edición de series de numeración."""

from __future__ import annotations

from uuid import uuid4

import pytest

from cacao_accounting.database import NamingSeries, database


@pytest.fixture
def serie_de_prueba(app):
    """Crea una serie no predeterminada y la elimina al terminar."""
    suffix = uuid4().hex[:6].upper()
    with app.app_context():
        series = NamingSeries(
            name=f"SERIE-{suffix}",
            entity_type="sales_invoice",
            company="cacao",
            prefix_template=f"*COMP*-{suffix}-",
            is_active=True,
            is_default=False,
        )
        database.session.add(series)
        database.session.commit()
        series_id = series.id
    yield series_id
    with app.app_context():
        remaining = database.session.get(NamingSeries, series_id)
        if remaining is not None:
            database.session.delete(remaining)
            database.session.commit()


def test_editar_serie_muestra_rotulos_de_edicion(app, authenticated_client, serie_de_prueba):
    """El breadcrumb, encabezado y botón reflejan la edición."""
    response = authenticated_client().get(f"/accounting/naming-series/{serie_de_prueba}/edit")

    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert "Editar Serie de Numeracion" in html
    assert "Editar Serie" in html
    assert "Guardar Cambios" in html
    assert "Nueva Serie de Numeracion" not in html


def test_nueva_serie_conserva_rotulos_de_alta(authenticated_client):
    """El alta sigue mostrando Nueva Serie y Guardar."""
    response = authenticated_client().get("/accounting/naming-series/new")

    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert "Nueva Serie de Numeracion" in html
    assert "Guardar" in html
    assert "Editar Serie de Numeracion" not in html
