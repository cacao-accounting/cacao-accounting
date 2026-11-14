# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""La ficha de unidad de negocio responde 404 controlado cuando no existe (#2164).

La ruta ``unidad`` (contabilidad/routes.py) debe abortar con 404 cuando el código
de unidad no está registrado en la base de datos, en lugar de fallar con un 500
al renderizar un registro inexistente.
"""

from __future__ import annotations

from uuid import uuid4

import pytest

from cacao_accounting.database import Unit, database

CODIGO_INEXISTENTE = "NO-EXISTE-QA3"


@pytest.fixture
def unidad_qa(app):
    """Crea una unidad vigente en cacao con código único y la elimina al terminar."""
    codigo = f"U{uuid4().hex[:6].upper()}"
    with app.app_context():
        database.session.add(Unit(code=codigo, name="Unidad de detalle QA", entity="cacao", enabled=True))
        database.session.commit()

    yield codigo

    with app.app_context():
        unidad = database.session.execute(database.select(Unit).filter_by(code=codigo)).scalar_one_or_none()
        if unidad is not None:
            database.session.delete(unidad)
            database.session.commit()


def test_unidad_inexistente_responde_404_y_nunca_500(authenticated_client):
    """GET de una unidad inexistente responde 404 controlado, no un error interno."""
    response = authenticated_client().get(f"/accounting/unit/{CODIGO_INEXISTENTE}")

    assert response.status_code == 404
    assert b"Internal Server Error" not in response.data
    assert CODIGO_INEXISTENTE not in response.get_data(as_text=True)


def test_unidad_existente_renderiza_su_detalle(authenticated_client, unidad_qa):
    """GET de una unidad vigente responde 200 y muestra su código y nombre."""
    response = authenticated_client().get(f"/accounting/unit/{unidad_qa}")

    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert unidad_qa in html
    assert "Unidad de detalle QA" in html
