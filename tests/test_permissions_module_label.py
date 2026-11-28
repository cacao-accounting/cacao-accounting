# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#2007: la pantalla de permisos etiqueta cada módulo con su nombre.

La plantilla mostraba el módulo a partir de un atributo inexistente y el
encabezado quedaba vacío. La regresión renderiza la pantalla real y exige que
cada módulo habilitado aparezca con el nombre que expone el modelo (`module`),
no con un identificador interno ni con una cadena vacía.
"""

from __future__ import annotations

import re

import pytest

from cacao_accounting.database import Modules, database

MODULOS_ESPERADOS = {
    "accounting": "Accounting",
    "sales": "Sales",
    "purchases": "Purchases",
    "cash": "Cash",
    "inventory": "Inventory",
}


@pytest.fixture
def modulos_habilitados(app):
    """Garantiza que la base de pruebas contiene los módulos visibles."""
    with app.app_context():
        existentes = {row.module for row in database.session.execute(database.select(Modules)).scalars().all()}
        faltantes = [module for module in MODULOS_ESPERADOS if module not in existentes]
        if faltantes:
            database.session.add_all([Modules(module=module, enabled=True) for module in faltantes])
            database.session.commit()
        yield existentes | set(faltantes)


def test_pantalla_de_permisos_muestra_el_nombre_de_cada_modulo(modulos_habilitados, authenticated_client):
    """Cada encabezado de módulo contiene el nombre legible, no un atributo vacío."""
    client = authenticated_client("admin")

    response = client.get("/permisos_usuario")

    assert response.status_code == 200
    html = response.get_data(as_text=True)
    encabezados = set(re.findall(r"(?:Módulo|Module):\s*([A-Za-zÁÉÍÓÚáéíóúÑñ]+)", html))
    esperados = {etiqueta for codigo, etiqueta in MODULOS_ESPERADOS.items() if codigo in modulos_habilitados}
    assert esperados <= encabezados
