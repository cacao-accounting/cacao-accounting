# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1720: el tipo de dimensión respeta el checkbox «Activo» del alta."""

from __future__ import annotations

from uuid import uuid4

from sqlalchemy import select

from cacao_accounting.database import DimensionType, Modules, database


def _enable_admin_module(app) -> None:
    """Habilita el módulo administrativo que el fixture base no siembra."""
    with app.app_context():
        module = database.session.execute(database.select(Modules).filter_by(module="admin")).scalar_one_or_none()
        if module is None:
            database.session.add(Modules(module="admin", default=False, enabled=True))
        else:
            module.enabled = True
        database.session.commit()


def _persisted(name: str) -> DimensionType:
    """Devuelve el tipo de dimensión recién creado."""
    dimension_type = database.session.execute(select(DimensionType).filter_by(name=name)).scalar_one_or_none()
    assert dimension_type is not None, f"No se creó el tipo {name!r}"
    return dimension_type


def test_crear_tipo_sin_checkbox_lo_deja_inactivo(app, authenticated_client):
    """El navegador omite el checkbox desmarcado; el tipo debe quedar inactivo."""
    name = f"Dimensión inactiva {uuid4().hex[:8]}"
    _enable_admin_module(app)
    client = authenticated_client("admin")

    response = client.post("/settings/dimensions", data={"action": "create_type", "name": name})

    assert response.status_code == 302
    with app.app_context():
        assert _persisted(name).is_active is False


def test_crear_tipo_con_checkbox_lo_deja_activo(app, authenticated_client):
    """Marcar «Activo» crea el tipo activo."""
    name = f"Dimensión activa {uuid4().hex[:8]}"
    _enable_admin_module(app)
    client = authenticated_client("admin")

    response = client.post("/settings/dimensions", data={"action": "create_type", "name": name, "is_active": "on"})

    assert response.status_code == 302
    with app.app_context():
        assert _persisted(name).is_active is True
