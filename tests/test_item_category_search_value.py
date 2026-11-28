# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1850: el Smart Select de categoría devuelve el ID que espera el formulario."""

from __future__ import annotations

from uuid import uuid4

from cacao_accounting.database import ItemCategory, database


def test_search_select_de_categoria_devuelve_id(app, authenticated_client, entorno_contable):
    """El value del API coincide con el ID de ItemCategory y con la opción del form."""
    del entorno_contable
    sufijo = uuid4().hex[:6]
    nombre = f"Categoria {sufijo}"
    with app.app_context():
        categoria = ItemCategory(name=nombre, is_active=True)
        database.session.add(categoria)
        database.session.commit()
        categoria_id = categoria.id

    try:
        client = authenticated_client("admin")
        response = client.get(
            "/api/search-select",
            query_string={"doctype": "item_category", "q": nombre},
        )

        assert response.status_code == 200, response.get_json()
        resultados = response.get_json()["results"]
        assert resultados
        assert resultados[0]["value"] == categoria_id
        assert resultados[0]["id"] == categoria_id
    finally:
        with app.app_context():
            database.session.execute(database.delete(ItemCategory).where(ItemCategory.id == categoria_id))
            database.session.commit()
