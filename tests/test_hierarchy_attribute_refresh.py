# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 William José Moreno Reyes

"""#2188: la actualización jerárquica relee los hijos bajo lock."""

from __future__ import annotations

from uuid import uuid4

from cacao_accounting.database import Unit, database
from cacao_accounting.database.helpers import update_hierarchy_attributes


def test_actualizacion_jerarquica_relee_hijos_con_lock(app, entorno_contable, monkeypatch):
    """El recorrido posterior no reutiliza una lectura ordinaria de hijos."""
    del entorno_contable
    sufijo = uuid4().hex[:6]
    with app.app_context():
        raiz = Unit(entity="cacao", code=f"RA{sufijo}", name="Raíz", enabled=True)
        database.session.add(raiz)
        database.session.flush()
        update_hierarchy_attributes(raiz)
        hijo = Unit(entity="cacao", code=f"HI{sufijo}", name="Hijo", enabled=True, parent_id=raiz.id)
        database.session.add(hijo)
        database.session.flush()

        capturados: list[object] = []
        original = database.session.execute

        def tracking(statement, *args, **kwargs):
            capturados.append(statement)
            return original(statement, *args, **kwargs)

        monkeypatch.setattr(database.session, "execute", tracking)
        update_hierarchy_attributes(raiz)

        database.session.refresh(hijo)
        assert hijo.level == 1
        assert hijo.path == f"{raiz.path} / Hijo"
        assert any(getattr(statement, "_for_update_arg", None) is not None for statement in capturados)
