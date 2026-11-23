# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1723: desmarcar «Activo» al crear un proveedor lo deja inactivo."""

from __future__ import annotations

from uuid import uuid4

from sqlalchemy import select

from cacao_accounting.database import Party, database


def _persisted(name: str) -> Party:
    """Devuelve el proveedor recién creado por nombre."""
    party = database.session.execute(select(Party).filter_by(name=name)).scalar_one_or_none()
    assert party is not None, f"No se creó el proveedor {name!r}"
    return party


def test_alta_de_proveedor_sin_checkbox_lo_deja_inactivo(app, authenticated_client):
    """El navegador omite el checkbox desmarcado; el proveedor debe quedar inactivo."""
    name = f"Proveedor inactivo {uuid4().hex[:8]}"
    client = authenticated_client("admin")

    response = client.post("/buying/supplier/new", data={"name": name, "company": "cacao"})

    assert response.status_code == 302
    with app.app_context():
        assert _persisted(name).is_active is False


def test_alta_de_proveedor_con_checkbox_lo_deja_activo(app, authenticated_client):
    """Marcar «Activo» sigue creando un proveedor activo."""
    name = f"Proveedor activo {uuid4().hex[:8]}"
    client = authenticated_client("admin")

    response = client.post("/buying/supplier/new", data={"name": name, "company": "cacao", "is_active": "on"})

    assert response.status_code == 302
    with app.app_context():
        assert _persisted(name).is_active is True
