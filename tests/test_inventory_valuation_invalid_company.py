# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1866: la valuación de inventario rechaza una compañía inexistente."""

from __future__ import annotations

from cacao_accounting.database import Entity, Modules, database

URL = "/settings/inventory-valuation"


def _enable_admin_module(app) -> None:
    """Habilita el módulo administrativo que el fixture base no siembra."""
    with app.app_context():
        module = database.session.execute(database.select(Modules).filter_by(module="admin")).scalar_one_or_none()
        if module is None:
            database.session.add(Modules(module="admin", default=False, enabled=True))
        else:
            module.enabled = True
        database.session.commit()


def _selected_company(body: str) -> str:
    """Extrae la compañía marcada como seleccionada en el formulario."""
    marker = '<option value="'
    for fragment in body.split(marker)[1:]:
        value, _, rest = fragment.partition('"')
        if rest.startswith(" selected"):
            return value
    return ""


def test_get_con_compania_inexistente_redirige_a_una_valida(app, authenticated_client):
    """Un código desconocido no produce 500 y la pantalla sigue accesible."""
    _enable_admin_module(app)
    client = authenticated_client("admin")
    with app.app_context():
        primera = database.session.execute(database.select(Entity.code).order_by(Entity.code)).scalars().first()

    response = client.get(f"{URL}?company=NO_EXISTE")

    assert response.status_code == 302
    assert URL in response.headers["Location"]
    seguimiento = client.get(response.headers["Location"])
    assert seguimiento.status_code == 200
    assert _selected_company(seguimiento.get_data(as_text=True)) == primera


def test_get_con_compania_valida_la_preselecciona(app, authenticated_client):
    """Una compañía existente se conserva en la selección."""
    _enable_admin_module(app)
    client = authenticated_client("admin")

    response = client.get(f"{URL}?company=cacao")

    assert response.status_code == 200
    assert _selected_company(response.get_data(as_text=True)) == "cacao"


def test_post_con_compania_inexistente_no_actualiza_ni_falla(app, authenticated_client):
    """El POST con compañía desconocida también se rechaza con control visible."""
    _enable_admin_module(app)
    client = authenticated_client("admin")

    response = client.post(f"{URL}?company=NO_EXISTE", data={"company": "NO_EXISTE", "valuation_method": "fifo"})

    assert response.status_code == 302
    assert client.get(response.headers["Location"]).status_code == 200
