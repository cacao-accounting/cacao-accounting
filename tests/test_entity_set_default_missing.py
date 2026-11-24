# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1787: predeterminar una entidad inexistente responde 404 sin mutar nada."""

from __future__ import annotations


def test_set_default_inexistente_responde_404(app, entorno_contable, authenticated_client):
    """Un ID desconocido no produce 500 ni cambia la entidad predeterminada."""
    from cacao_accounting.database import Entity, database

    with app.app_context():
        antes = (
            database.session.execute(database.select(Entity.code).filter_by(default=True).order_by(Entity.code))
            .scalars()
            .all()
        )

    response = authenticated_client("admin").get("/accounting/entity/set_default/ENTIDAD-QUE-NO-EXISTE")

    assert response.status_code == 404
    with app.app_context():
        despues = (
            database.session.execute(database.select(Entity.code).filter_by(default=True).order_by(Entity.code))
            .scalars()
            .all()
        )
        assert despues == antes


def test_editar_entidad_inexistente_responde_404(app, entorno_contable, authenticated_client):
    """La ruta de edición incluida en el alcance no responde 500."""
    response = authenticated_client("admin").get("/accounting/entity/edit/ENTIDAD-QUE-NO-EXISTE")

    assert response.status_code == 404
